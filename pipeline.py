"""Auto-chain tu webhook Airtable (Buoc 1 + Buoc 2 D1).

Buoc 1: form submit -> phan tich (analyze_one).
Buoc 2: du thong tin -> proposal + render HTML + upload -> Status "Cho duyet items"
        -> requester set "Duyet proposal?" tren Airtable:
           Duyet   -> chot items (Status "Da duyet items")
           Can sua -> doc Feedback -> chay lai AI #2 -> upload lai -> +1 round (>3 -> Can PIC xu ly)
"""
import threading
from datetime import date, timedelta

from airtable_client import (airtable, append_note, fetch_items_of,
                             fetch_projects, update_items, update_project)
from analysis import analyze_one
from config import MAX_PROPOSAL_ROUNDS, PROJECTS_TABLE, PROPOSAL_APPROVAL_DAYS
from proposal import propose_items_for
from proposal_render import build_proposal_html, upload_proposal

_analyze_lock = threading.Lock()
_analyze_again = threading.Event()
_decide_lock = threading.Lock()
_decide_again = threading.Event()


def _run_guarded(lock: threading.Lock, again: threading.Event, work) -> None:
    """Chay `work` tuan tu (1 luong/luc). Co ping moi luc dang chay -> danh dau `again`
    de chay lai sau khi xong (khong bo sot). Tranh race khi webhook ping don dap
    (nhieu _revise/_approve song song -> nhan ban items)."""
    again.set()
    if not lock.acquire(blocking=False):
        return  # da co luong chay; no se thay `again` va chay lai
    try:
        while again.is_set():
            again.clear()
            work()
    finally:
        lock.release()


def _make_proposal(record_id: str, feedback: str | None = None) -> tuple[dict, str]:
    """Sinh proposal (ghi Items + Phan tich) + render HTML. CHUA upload. Tra (result, html)."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    result = propose_items_for(rec, feedback=feedback)
    html = build_proposal_html(rec["fields"], result["proposal"], result["total"])
    return result, html


def first_send(record_id: str) -> None:
    """Lan dau: propose -> set Status/han/round -> upload file CUOI CUNG (de trigger mail).

    Upload de cuoi de khi Automation bat theo field 'File proposal', moi field khac da san sang.
    """
    result, html = _make_proposal(record_id)
    deadline = (date.today() + timedelta(days=PROPOSAL_APPROVAL_DAYS)).isoformat()
    update_project(record_id, {
        "Status": "Chờ duyệt items",
        "Deadline phê duyệt": deadline,
        "Số round proposal": 0,
        "File proposal": [],  # clear truoc khi upload -> luon chi 1 file (ban moi nhat)
    })
    upload_proposal(record_id, html, result["project_code"])  # upload CUOI -> trigger Automation gui mail
    print(f"[proposal] {result['project_code']} sent: "
          f"{result['n_catalogue']} catalogue + {result['n_creative']} creative, "
          f"{result['total']:,}đ / {result['budget']:,}đ -> Chờ duyệt items")


def _scan_new() -> None:
    records = fetch_projects("OR({Status} = 'Mới tiếp nhận', {Status} = BLANK())")
    for r in records:
        try:
            result = analyze_one(r)
            print(f"[webhook] analyzed {result['project_code']} -> {result['new_status']}")
            if result["new_status"] == "Chờ duyệt items":
                first_send(r["id"])
        except Exception as e:  # noqa: BLE001
            print(f"[webhook] pipeline error: {e}")


def analyze_new_async() -> None:
    """Buoc 1->2: quet record moi -> phan tich -> (du thong tin) gui proposal. Tuan tu."""
    _run_guarded(_analyze_lock, _analyze_again, _scan_new)


def _approve_proposal(record_id: str, code: str) -> None:
    """Requester duyet: chot items + Status 'Da duyet items'."""
    updates = [{"id": it["id"], "fields": {"Status": "Đã duyệt"}}
               for it in fetch_items_of(record_id)
               if it["fields"].get("Status") == "Đề xuất"]
    if updates:
        update_items(updates)
    update_project(record_id, {"Status": "Đã duyệt items", "Duyệt proposal?": None, "Gửi phản hồi": False})
    print(f"[proposal] {code} DUYỆT -> chốt {len(updates)} items -> Đã duyệt items")


def _revise_or_escalate(record_id: str, code: str, fields: dict) -> None:
    """Requester yeu cau sua: chay lai AI #2 theo feedback, dem round, >3 -> escalate PIC."""
    feedback = fields.get("Feedback proposal", "") or ""
    rounds = int(fields.get("Số round proposal") or 0) + 1
    if rounds > MAX_PROPOSAL_ROUNDS:
        update_project(record_id, {"Cần PIC xử lý": True, "Duyệt proposal?": None, "Gửi phản hồi": False})
        append_note(record_id, f"[AI] Proposal đã sửa {MAX_PROPOSAL_ROUNDS} round vẫn chưa duyệt "
                               f"— chuyển Merch PIC xử lý. Feedback gần nhất: {feedback}")
        print(f"[proposal] {code} vượt {MAX_PROPOSAL_ROUNDS} round -> Cần PIC xử lý")
        return
    append_note(record_id, f"[AI] Round {rounds} — sửa proposal theo feedback: {feedback}")
    result, html = _make_proposal(record_id, feedback=feedback)
    update_project(record_id, {
        "Số round proposal": rounds,
        "Duyệt proposal?": None,
        "Feedback proposal": None,
        "Gửi phản hồi": False,
        "File proposal": [],  # clear ban cu -> chi giu ban moi nhat
    })
    upload_proposal(record_id, html, result["project_code"])  # upload CUOI -> trigger mail
    print(f"[proposal] {code} CẦN SỬA -> round {rounds} đã gửi lại")


def _scan_decisions() -> None:
    records = fetch_projects("{Gửi phản hồi} = TRUE()")
    for r in records:
        f = r["fields"]
        code = f.get("Mã project", r["id"])
        try:
            # da chot / da chuyen PIC -> bo qua phan hoi (tranh mo lai proposal da duyet / re-escalate)
            if f.get("Status") == "Đã duyệt items" or f.get("Cần PIC xử lý"):
                update_project(r["id"], {"Gửi phản hồi": False, "Duyệt proposal?": None})
                print(f"[proposal] {code} đã chốt/đã chuyển PIC -> bỏ qua phản hồi")
                continue
            decision = f.get("Duyệt proposal?")
            feedback = (f.get("Feedback proposal") or "").strip()
            if decision == "Duyệt":
                _approve_proposal(r["id"], code)
            elif decision == "Cần sửa" and feedback:
                _revise_or_escalate(r["id"], code, f)
            else:
                # tick som: chua chon decision, hoac Can sua ma chua nhap feedback
                # -> bo tick, KHONG lam gi, KHONG ton round
                update_project(r["id"], {"Gửi phản hồi": False})
                print(f"[proposal] {code} tick Gửi nhưng thiếu decision/feedback -> bỏ qua (không tốn round)")
        except Exception as e:  # noqa: BLE001
            print(f"[proposal] decision error {code}: {e}")


def handle_proposal_decisions() -> None:
    """Buoc 2 D1: quet project tick 'Gui phan hoi' -> xu ly theo Duyet proposal? roi bo tick.

    Tuan tu (serialize): webhook ping don dap (ke ca do agent tu ghi lai Projects) khong
    gay chay song song -> tranh nhan ban items / dem round sai.
    """
    _run_guarded(_decide_lock, _decide_again, _scan_decisions)


def on_webhook() -> None:
    """1 webhook ping -> chay ca 2 nhanh: record moi (Buoc 1->2) + quyet dinh proposal (Buoc 2 D1)."""
    analyze_new_async()
    handle_proposal_decisions()
