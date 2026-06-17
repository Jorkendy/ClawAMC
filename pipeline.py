"""Auto-chain tu webhook Airtable (Buoc 1 + Buoc 2 D1).

Buoc 1: form submit -> phan tich (analyze_one).
Buoc 2: du thong tin -> propose (AI #2). Ba nhanh:
  a) Con yeu cau dac biet chua dap ung -> Status "Cho lam ro yeu cau", hoi requester
     (mail qua Automation). Requester tra loi o "Tra loi lam ro" -> cham lai;
     qua MAX_CLARIFY_ROUNDS -> Can PIC xu ly.
  b) Sau cac vong tu sua van vuot budget -> KHONG chot, Can PIC xu ly (_escalate_over_budget).
  c) Du dieu kien -> proposal + render HTML + upload -> Status "Cho duyet items"
     -> requester set "Duyet proposal?" tren Airtable:
        Duyet   -> chot items (Status "Da duyet items")
        Can sua -> doc Feedback -> chay lai AI #2 -> upload lai -> +1 round (>3 -> Can PIC xu ly)

Loi AI/LLM khong hop le (JSON hong/rong/thieu key) -> _mark_ai_error: tick Can PIC xu ly,
clear "Gui phan hoi" (chong retry loop), ghi log — khong de record kep im lang.
"""
import threading
from datetime import date, timedelta

from airtable_client import (airtable, append_note, fetch_items_of,
                             fetch_projects, update_items, update_project)
from analysis import analyze_one
from config import (MAX_CLARIFY_ROUNDS, MAX_PROPOSAL_ROUNDS, PROJECTS_TABLE,
                    PROPOSAL_APPROVAL_DAYS)
from proposal import propose_items_for
from proposal_render import build_proposal_html, upload_proposal

_analyze_lock = threading.Lock()
_analyze_again = threading.Event()
_decide_lock = threading.Lock()
_decide_again = threading.Event()

HISTORY_FIELD = "Lịch sử chỉnh sửa"  # log tung round feedback / duyet / escalate
CLARIFY_STATUS = "Chờ làm rõ yêu cầu"  # con yeu cau dac biet chua dap ung
CLARIFY_FIELD = "Trao đổi yêu cầu"     # cau hoi AI hoi requester (requester doc o record view)
CLARIFY_ROUND_FIELD = "Số vòng làm rõ"  # dem rieng, KHONG dung chung Số round proposal
CLARIFY_MAIL_FLAG = "Gửi mail làm rõ"   # co bat moi vong -> Automation gui mail requester roi tu untick
CLARIFY_ANSWER_FIELD = "Trả lời làm rõ"  # requester tra loi cau hoi lam ro (KHAC 'Feedback proposal' — luc nay chua co proposal)


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


def _mark_ai_error(record_id: str, stage: str, err: Exception) -> None:
    """AI/LLM trả về không hợp lệ -> đừng để record kẹt im lặng: tick Cần PIC xử lý,
    clear 'Gửi phản hồi' (chống retry loop mỗi webhook ping), ghi log cho PIC."""
    try:
        update_project(record_id, {"Cần PIC xử lý": True, "Gửi phản hồi": False})
        append_note(record_id, f"[AI] Lỗi xử lý ({stage}): {err} — cần PIC kiểm tra.",
                    field=HISTORY_FIELD)
    except Exception as e:  # noqa: BLE001
        print(f"[pipeline] không ghi được trạng thái lỗi cho {record_id}: {e}")


def _make_proposal(record_id: str, feedback: str | None = None,
                   clarify: str | None = None) -> tuple[dict, str | None]:
    """Sinh proposal + render HTML. CHUA upload. Tra (result, html).
    Neu con yeu cau dac biet chua dap ung -> result['blocked']=True, html=None (chua co proposal)."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    result = propose_items_for(rec, feedback=feedback, clarify=clarify)
    if result.get("blocked") or result.get("over_budget"):
        return result, None
    html = build_proposal_html(rec["fields"], result["proposal"], result["total"])
    return result, html


def _publish_proposal(record_id: str, result: dict, html: str, *, reset_round: bool) -> None:
    """Chot 1 ban proposal: set Status 'Cho duyet items' + don sach co phan hoi/clarify -> upload CUOI (trigger mail)."""
    deadline = (date.today() + timedelta(days=PROPOSAL_APPROVAL_DAYS)).isoformat()
    fields = {
        "Status": "Chờ duyệt items",
        "Deadline phê duyệt": deadline,
        "File proposal": [],  # clear truoc khi upload -> luon chi 1 file (ban moi nhat)
        "Duyệt proposal?": None,
        "Gửi phản hồi": False,
        "Feedback proposal": None,
        CLARIFY_FIELD: None,  # da giai quyet yeu cau dac biet -> xoa cau hoi
        CLARIFY_ANSWER_FIELD: None,  # don cau tra loi lam ro
        CLARIFY_MAIL_FLAG: False,  # don co (truong hop con sot)
    }
    if reset_round:
        fields["Số round proposal"] = 0
    update_project(record_id, fields)
    upload_proposal(record_id, html, result["project_code"])  # upload CUOI -> trigger Automation gui mail
    print(f"[proposal] {result['project_code']} sent: "
          f"{result['n_catalogue']} catalogue + {result['n_creative']} creative, "
          f"{result['total']:,}đ / {result['budget']:,}đ -> Chờ duyệt items")


def _enter_clarify(record_id: str, result: dict) -> None:
    """Con yeu cau dac biet chua dap ung -> dem vong lam ro, hoi requester; qua MAX -> escalate PIC."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    f = rec["fields"]
    code = f.get("Mã project", record_id)
    rounds = int(f.get(CLARIFY_ROUND_FIELD) or 0) + 1
    if rounds > MAX_CLARIFY_ROUNDS:
        update_project(record_id, {
            CLARIFY_ROUND_FIELD: rounds, "Cần PIC xử lý": True,
            "Gửi phản hồi": False, "Feedback proposal": None,
        })
        append_note(record_id, f"[AI] Yêu cầu đặc biệt làm rõ {MAX_CLARIFY_ROUNDS} vòng vẫn chưa thỏa "
                               f"— chuyển Merch PIC xử lý.", field=HISTORY_FIELD)
        print(f"[proposal] {code} vượt {MAX_CLARIFY_ROUNDS} vòng làm rõ -> Cần PIC xử lý")
        return
    update_project(record_id, {
        "Status": CLARIFY_STATUS,
        CLARIFY_FIELD: result["clarify_message"],
        CLARIFY_ROUND_FIELD: rounds,
        CLARIFY_MAIL_FLAG: True,  # bat co -> Automation gui mail requester (tu untick sau khi gui)
        "Gửi phản hồi": False,
        CLARIFY_ANSWER_FIELD: None,  # xoa cau tra loi cu -> vong sau nhap moi
    })
    append_note(record_id, f"[AI] Vòng làm rõ {rounds} — yêu cầu đặc biệt chưa thỏa, đã hỏi requester.",
                field=HISTORY_FIELD)
    print(f"[proposal] {code} có yêu cầu đặc biệt chưa thỏa -> Chờ làm rõ yêu cầu (vòng {rounds})")


def _escalate_over_budget(record_id: str, result: dict) -> None:
    """Proposal sau cac vong tu sua van vuot budget -> KHONG chot cho requester, chuyen PIC."""
    code = result.get("project_code", record_id)
    update_project(record_id, {
        "Cần PIC xử lý": True, "Gửi phản hồi": False, "Duyệt proposal?": None,
    })
    append_note(record_id,
                f"[AI] Proposal vẫn vượt budget sau khi tự điều chỉnh "
                f"({result['total']:,}đ / {result['budget']:,}đ) — chuyển Merch PIC xử lý.",
                field=HISTORY_FIELD)
    print(f"[proposal] {code} vượt budget -> Cần PIC xử lý")


def first_send(record_id: str) -> None:
    """Lan dau: propose -> (neu con yeu cau dac biet chua thoa: hoi requester) -> publish + upload."""
    result, html = _make_proposal(record_id)
    if result.get("blocked"):
        _enter_clarify(record_id, result)
        return
    if result.get("over_budget"):
        _escalate_over_budget(record_id, result)
        return
    _publish_proposal(record_id, result, html, reset_round=True)


def _reanalyze(record_id: str) -> None:
    """Record 'Thieu thong tin' -> requester bo sung roi tick Gui phan hoi -> chay lai Buoc 1;
    neu da du thong tin -> tiep tuc Buoc 2 (propose)."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    result = analyze_one(rec)
    update_project(record_id, {"Gửi phản hồi": False})
    print(f"[webhook] re-analyzed {result['project_code']} -> {result['new_status']}")
    if result["new_status"] == "Chờ duyệt items":
        first_send(record_id)


def _scan_new() -> None:
    records = fetch_projects("OR({Status} = 'Mới tiếp nhận', {Status} = BLANK())")
    for r in records:
        try:
            result = analyze_one(r)
            print(f"[webhook] analyzed {result['project_code']} -> {result['new_status']}")
            if result["new_status"] == "Chờ duyệt items":
                first_send(r["id"])
        except Exception as e:  # noqa: BLE001
            print(f"[webhook] pipeline error {r['id']}: {e}")
            _mark_ai_error(r["id"], "phân tích / proposal", e)


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
    append_note(record_id, "[AI] Requester đã DUYỆT — chốt đề xuất.", field=HISTORY_FIELD)
    print(f"[proposal] {code} DUYỆT -> chốt {len(updates)} items -> Đã duyệt items")


def _revise_or_escalate(record_id: str, code: str, fields: dict) -> None:
    """Requester yeu cau sua: chay lai AI #2 theo feedback, dem round, >3 -> escalate PIC."""
    feedback = fields.get("Feedback proposal", "") or ""
    rounds = int(fields.get("Số round proposal") or 0) + 1
    if rounds > MAX_PROPOSAL_ROUNDS:
        update_project(record_id, {"Cần PIC xử lý": True, "Duyệt proposal?": None, "Gửi phản hồi": False})
        append_note(record_id, f"[AI] Proposal đã sửa {MAX_PROPOSAL_ROUNDS} round vẫn chưa duyệt "
                               f"— chuyển Merch PIC xử lý. Feedback gần nhất: {feedback}", field=HISTORY_FIELD)
        print(f"[proposal] {code} vượt {MAX_PROPOSAL_ROUNDS} round -> Cần PIC xử lý")
        return
    result, html = _make_proposal(record_id, feedback=feedback)
    if result.get("blocked"):  # feedback lam yeu cau dac biet thanh chua thoa -> hoi lai
        _enter_clarify(record_id, result)
        return
    if result.get("over_budget"):  # feedback day vuot budget, khong tu sua duoc -> PIC
        _escalate_over_budget(record_id, result)
        return
    append_note(record_id, f"[AI] Round {rounds} — sửa proposal theo feedback: {feedback}", field=HISTORY_FIELD)
    update_project(record_id, {"Số round proposal": rounds})
    _publish_proposal(record_id, result, html, reset_round=False)
    print(f"[proposal] {code} CẦN SỬA -> round {rounds} đã gửi lại")


def _reevaluate_clarify(record_id: str, code: str, answer: str) -> None:
    """Requester tra loi cau hoi lam ro -> cham lai yeu cau dac biet; thoa thi gui proposal."""
    result, html = _make_proposal(record_id, clarify=answer)
    if result.get("blocked"):
        _enter_clarify(record_id, result)  # van chua thoa -> hoi tiep (hoac escalate neu qua vong)
        return
    if result.get("over_budget"):
        _escalate_over_budget(record_id, result)
        return
    append_note(record_id, f"[AI] Đã làm rõ yêu cầu đặc biệt theo trả lời requester: {answer}",
                field=HISTORY_FIELD)
    _publish_proposal(record_id, result, html, reset_round=True)
    print(f"[proposal] {code} đã thỏa yêu cầu đặc biệt -> gửi proposal")


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
            # dang cho lam ro yeu cau dac biet -> doc 'Tra loi lam ro' (chua co proposal nen KHONG dung Feedback proposal)
            if f.get("Status") == CLARIFY_STATUS:
                answer = (f.get(CLARIFY_ANSWER_FIELD) or "").strip()
                if not answer:
                    update_project(r["id"], {"Gửi phản hồi": False})
                    print(f"[proposal] {code} tick Gửi nhưng chưa trả lời làm rõ -> bỏ qua")
                    continue
                _reevaluate_clarify(r["id"], code, answer)
                continue
            # record thieu thong tin -> requester bo sung roi tick Gui -> chay lai Buoc 1
            if f.get("Status") == "Thiếu thông tin":
                _reanalyze(r["id"])
                continue
            feedback = (f.get("Feedback proposal") or "").strip()
            decision = f.get("Duyệt proposal?")
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
            _mark_ai_error(r["id"], "xử lý phản hồi", e)


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
