"""Auto-chain tu webhook Airtable (Buoc 1 + Buoc 2 D1).

Buoc 1: form submit -> phan tich (analyze_one).
Buoc 2: du thong tin -> propose (AI #2). VONG DIEU CHINH/LAM RO HOP NHAT (_request_adjust,
1 bo dem chung CLARIFY_ROUND_FIELD, qua MAX_CLARIFY_ROUNDS -> Can PIC):
  a) Yeu cau dac biet unmet -> "Cho lam ro yeu cau": requester tra loi text o "Tra loi lam ro".
  b) Vuot budget / Deadline khong du (ke ca hang co san) -> "Cho dieu chinh": requester SUA
     field Budget/Deadline (hoac bo yeu cau) roi tick "Gui phan hoi" -> tinh lai (khong can text).
  c) Du dieu kien -> proposal + render HTML + upload -> Status "Cho duyet items"
     -> requester set "Duyet proposal?" tren Airtable:
        Duyet   -> chot items (Status "Da duyet items")
        Can sua -> doc Feedback -> chay lai AI #2 -> upload lai -> +1 round (>3 -> Can PIC xu ly)

Loi AI/LLM khong hop le (JSON hong/rong/thieu key) -> _mark_ai_error: tick Can PIC xu ly,
clear "Gui phan hoi" (chong retry loop), ghi log — khong de record kep im lang.
"""
import json
import threading
import time
import urllib.request
from datetime import date, timedelta

from airtable_client import (airtable, append_note, fetch_items_of,
                             fetch_projects, update_items, update_project)
from analysis import analyze_one
from config import (MAX_CLARIFY_ROUNDS, MAX_PROPOSAL_ROUNDS, MAX_SUPPLEMENT_ROUNDS,
                    PROJECTS_TABLE, PROPOSAL_APPROVAL_DAYS)
from llm_client import estimate_cost_vnd, get_cost_summary, reset_cost
from plan import build_plan, render_plan_xlsx
from brief import build_brief_content, gather_brief_images, render_brief_pptx
from proposal import game_insight, propose_items_for
from proposal_render import build_proposal_html, upload_brief, upload_plan, upload_proposal

_analyze_lock = threading.Lock()
_analyze_again = threading.Event()
_decide_lock = threading.Lock()
_decide_again = threading.Event()

HISTORY_FIELD = "Lịch sử chỉnh sửa"  # log tung round feedback / duyet / escalate
CLARIFY_STATUS = "Chờ làm rõ yêu cầu"  # YEU CAU DAC BIET unmet -> can text answer o "Tra loi lam ro"
ADJUST_STATUS = "Chờ điều chỉnh"        # BUDGET/DEADLINE -> requester SUA field (Budget/Deadline) roi tick, KHONG can text
PIC_STATUS = "Chờ Merch PIC"            # escalate -> PIC xu ly (kem checkbox "Cần PIC xử lý"); Status ngoai 4 trang thai can phan hoi -> Fillout tu an form
CLARIFY_FIELD = "Trao đổi yêu cầu"     # cau hoi/huong dan AI gui requester (dung chung clarify + adjust)
CLARIFY_ROUND_FIELD = "Số vòng làm rõ"  # BO DEM KHA THI CHUNG (yeu cau + budget + deadline); KHAC "Số round proposal"
CLARIFY_MAIL_FLAG = "Gửi mail làm rõ"   # co bat moi vong -> Automation gui mail requester roi tu untick
CLARIFY_ANSWER_FIELD = "Trả lời làm rõ"  # requester tra loi cau hoi lam ro (chi yeu cau dac biet)


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
        update_project(record_id, {"Status": PIC_STATUS, "Cần PIC xử lý": True, "Gửi phản hồi": False,
                                   "Lý do cần PIC": f"Lỗi AI ({stage}): {err}"})
        append_note(record_id, f"[AI] Lỗi xử lý ({stage}): {err} — cần PIC kiểm tra.",
                    field=HISTORY_FIELD)
    except Exception as e:  # noqa: BLE001
        print(f"[pipeline] không ghi được trạng thái lỗi cho {record_id}: {e}")


def _log_cost(record_id: str, code: str, elapsed: float) -> None:
    """Ghi chi phi AI + thoi gian xu ly 1 proposal -> Lich su chinh sua + stdout (Coolify log).
    De co so lieu THAT chung minh chi phi van hanh (thay vi uoc tinh). Cache anh -> lan revise re hon."""
    s = get_cost_summary()
    cost = estimate_cost_vnd(s)
    tok = s["chat_tok_in"] + s["chat_tok_out"]
    msg = (f"[Chi phí] ~{cost:,}đ · {elapsed:.0f}s · {s['images']} ảnh · "
           f"{s['grounded_calls']} grounded · {s['chat_calls']} chat ({tok:,} tok)")
    print(f"[proposal] {code} {msg}")
    try:
        append_note(record_id, msg, field=HISTORY_FIELD)
    except Exception as e:  # noqa: BLE001
        print(f"[pipeline] không ghi được chi phí {code}: {e}")


def _make_proposal(record_id: str, feedback: str | None = None,
                   clarify: str | None = None) -> tuple[dict, str | None]:
    """Sinh proposal + render HTML. CHUA upload. Tra (result, html).
    Neu con yeu cau dac biet chua dap ung -> result['blocked']=True, html=None (chua co proposal)."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    reset_cost()  # do chi phi AI rieng cho proposal nay (token + anh + grounding)
    t0 = time.monotonic()
    result = propose_items_for(rec, feedback=feedback, clarify=clarify)
    _log_cost(record_id, result.get("project_code", record_id), time.monotonic() - t0)
    if result.get("blocked") or result.get("over_budget") or result.get("infeasible_deadline"):
        return result, None
    html = build_proposal_html(rec["fields"], result["proposal"], result["total"],
                               images=result.get("images"),
                               decision={"tier": result.get("tier"), "per_unit": result.get("per_unit"),
                                         "insight": result.get("insight"),
                                         "rationale": result["proposal"].get("co_so_quyet_dinh")})
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
        CLARIFY_ROUND_FIELD: 0,  # publish thanh cong = da kha thi -> reset bo dem dieu chinh chung
    }
    if reset_round:
        fields["Số round proposal"] = 0
    update_project(record_id, fields)
    upload_proposal(record_id, html, result["project_code"])  # upload CUOI -> trigger Automation gui mail
    print(f"[proposal] {result['project_code']} sent: "
          f"{result['n_catalogue']} catalogue + {result['n_creative']} creative, "
          f"{result['total']:,}đ / {result['budget']:,}đ -> Chờ duyệt items")


def _request_adjust(record_id: str, status: str, message: str, pic_reason: str, log: str) -> None:
    """VONG DIEU CHINH/LAM RO HOP NHAT (yeu cau dac biet / budget / deadline) — 1 BO DEM CHUNG
    (CLARIFY_ROUND_FIELD). Tang bo dem; qua MAX -> escalate PIC; else set status + cau hoi + co mail,
    cho requester chinh (text answer / sua Budget|Deadline) roi tick 'Gui phan hoi' -> tinh lai."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    f = rec["fields"]
    code = f.get("Mã project", record_id)
    rounds = int(f.get(CLARIFY_ROUND_FIELD) or 0) + 1
    if rounds > MAX_CLARIFY_ROUNDS:
        update_project(record_id, {
            "Status": PIC_STATUS, CLARIFY_ROUND_FIELD: rounds, "Cần PIC xử lý": True,
            "Gửi phản hồi": False, "Feedback proposal": None, "Duyệt proposal?": None,
            "Lý do cần PIC": pic_reason,
        })
        append_note(record_id, f"[AI] {pic_reason} (sau {MAX_CLARIFY_ROUNDS} vòng điều chỉnh) — chuyển Merch PIC.",
                    field=HISTORY_FIELD)
        print(f"[proposal] {code} quá {MAX_CLARIFY_ROUNDS} vòng điều chỉnh -> Cần PIC xử lý")
        return
    update_project(record_id, {
        "Status": status,
        CLARIFY_FIELD: message,
        CLARIFY_ROUND_FIELD: rounds,
        CLARIFY_MAIL_FLAG: True,  # bat co -> Automation gui mail requester (tu untick sau khi gui)
        "Gửi phản hồi": False, "Feedback proposal": None, "Duyệt proposal?": None,
        CLARIFY_ANSWER_FIELD: None,
    })
    append_note(record_id, f"[AI] Vòng điều chỉnh {rounds} — {log}; đã hỏi requester.", field=HISTORY_FIELD)
    print(f"[proposal] {code} -> {status} (vòng điều chỉnh {rounds})")


def _enter_clarify(record_id: str, result: dict) -> None:
    """Yeu cau dac biet unmet -> hoi requester (can text answer)."""
    _request_adjust(record_id, CLARIFY_STATUS, result["clarify_message"],
                    f"Yêu cầu đặc biệt làm rõ {MAX_CLARIFY_ROUNDS} vòng vẫn chưa thỏa.",
                    "yêu cầu đặc biệt chưa thỏa")


def _enter_adjust_budget(record_id: str, result: dict) -> None:
    """Vuot budget sau 2 vong tu sua -> hoi requester tang budget / bo bot yeu cau (thay vi PIC ngay)."""
    total, budget = result.get("total") or 0, result.get("budget") or 0
    msg = (f"Phương án tốt nhất vẫn VƯỢT ngân sách ({total:,}đ > {budget:,}đ) sau khi tối ưu. "
           "Vui lòng (a) tăng Budget, hoặc (b) bỏ/nới yêu cầu khiến chi phí cao, "
           "rồi tick \"Gửi phản hồi\" để tính lại.")
    _request_adjust(record_id, ADJUST_STATUS, msg,
                    f"Vẫn vượt budget ({total:,}đ/{budget:,}đ) sau các vòng điều chỉnh.",
                    f"vượt budget {total:,}đ/{budget:,}đ")


def _enter_adjust_deadline(record_id: str, result: dict) -> None:
    """Deadline khong du ke ca hang co san nhanh nhat -> hoi requester doi deadline (thay vi PIC ngay)."""
    need, left = result.get("needed_days", "?"), result.get("days_left", "?")
    msg = (f"Deadline hiện KHÔNG đủ thời gian sản xuất: cần ~{need} ngày kể cả hàng có sẵn nhanh nhất, "
           f"còn {left} ngày. Vui lòng DỜI 'Deadline cần hàng' (hoặc xác nhận chấp nhận rủi ro) "
           "rồi tick \"Gửi phản hồi\" để tính lại.")
    _request_adjust(record_id, ADJUST_STATUS, msg,
                    f"Deadline không khả thi kể cả hàng có sẵn (cần ~{need}d/còn {left}d).",
                    f"deadline không đủ (cần ~{need}d/còn {left}d)")


def _route_result(record_id: str, result: dict, html: str | None, *, reset_round: bool) -> None:
    """Dispatch ket qua _make_proposal: 3 nhanh khong kha thi -> vong dieu chinh hop nhat; else publish."""
    if result.get("blocked"):
        _enter_clarify(record_id, result)
    elif result.get("over_budget"):
        _enter_adjust_budget(record_id, result)
    elif result.get("infeasible_deadline"):
        _enter_adjust_deadline(record_id, result)
    else:
        _publish_proposal(record_id, result, html, reset_round=reset_round)


def first_send(record_id: str) -> None:
    """Lan dau: propose -> khong kha thi thi vao vong dieu chinh, else publish + upload."""
    result, html = _make_proposal(record_id)
    _route_result(record_id, result, html, reset_round=True)


def _reevaluate_adjust(record_id: str, code: str) -> None:
    """Requester da SUA Budget/Deadline (hoac bo yeu cau) roi tick -> tinh lai (KHONG can text answer)."""
    result, html = _make_proposal(record_id)
    _route_result(record_id, result, html, reset_round=True)
    print(f"[proposal] {code} tính lại sau điều chỉnh")


SUPPLEMENT_FIELD = "Số lần bổ sung"  # dem so lan re-analyze (chong spam mail / escalate khi qua cap)


def _reanalyze(record_id: str) -> None:
    """Record 'Thieu thong tin' -> requester bo sung roi tick Gui phan hoi -> chay lai Buoc 1;
    du thong tin -> tiep Buoc 2. Qua MAX_SUPPLEMENT_ROUNDS van thieu -> escalate PIC (khong spam mail)."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    rounds = int(rec["fields"].get(SUPPLEMENT_FIELD) or 0)
    # Con duoi cap thi cho gui mail bo sung; tu cap tro di -> im lang + escalate PIC
    notify = rounds < MAX_SUPPLEMENT_ROUNDS
    result = analyze_one(rec, notify_missing=notify)
    code = result["project_code"]
    print(f"[webhook] re-analyzed {code} -> {result['new_status']} (lần bổ sung {rounds + 1})")

    if result["new_status"] == "Chờ duyệt items":
        update_project(record_id, {"Gửi phản hồi": False, SUPPLEMENT_FIELD: 0})
        first_send(record_id)
        return

    rounds += 1
    if rounds > MAX_SUPPLEMENT_ROUNDS:
        update_project(record_id, {
            "Status": PIC_STATUS,
            SUPPLEMENT_FIELD: rounds, "Gửi phản hồi": False, "Gửi mail bổ sung": False,
            "Cần PIC xử lý": True,
            "Lý do cần PIC": f"Requester bổ sung {MAX_SUPPLEMENT_ROUNDS} lần vẫn thiếu: "
                             f"{', '.join(result['missing'])}",
        })
        append_note(record_id, f"[AI] Bổ sung quá {MAX_SUPPLEMENT_ROUNDS} lần vẫn thiếu thông tin "
                               f"({', '.join(result['missing'])}) — chuyển Merch PIC.", field=HISTORY_FIELD)
        print(f"[webhook] {code} bổ sung quá {MAX_SUPPLEMENT_ROUNDS} lần -> Cần PIC xử lý")
    else:
        update_project(record_id, {"Gửi phản hồi": False, SUPPLEMENT_FIELD: rounds})


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


def _plan_items_from_fields(fields: dict, record_id: str) -> list:
    """Nguon item cho plan: uu tien 'Proposal JSON' (snapshot publish gan nhat, co nguon + don gia);
    thieu -> fallback bang Items (suy nguon tu co/khong don gia)."""
    raw = fields.get("Proposal JSON")
    if raw:
        try:
            items = json.loads(raw)
            if items:
                return items
        except Exception:
            pass
    out = []
    for it in fetch_items_of(record_id):
        f = it["fields"]
        dg = f.get("Đơn giá dự kiến (VND)")
        out.append({"ten": f.get("Tên item", ""), "loai": f.get("Loại", ""),
                    "so_luong": f.get("Số lượng") or 0, "don_gia": dg,
                    "nguon": "catalogue" if dg else "creative"})
    return out


def _generate_plan(record_id: str, code: str) -> None:
    """Buoc 4: sinh Excel plan san xuat (timeline + ngan sach) -> upload field 'File plan san xuat'.
    Goi sau khi Duyet items; loi KHONG duoc pha viec chot items (caller bao try/except)."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    fields = rec.get("fields", {})
    items = _plan_items_from_fields(fields, record_id)
    plan = build_plan(fields, items, date.today())
    upload_plan(record_id, render_plan_xlsx(plan), code)
    append_note(record_id, f"[AI] Đã sinh plan sản xuất — giao dự kiến {plan['delivery']} "
                           f"({plan['total_cal']} ngày lịch). {plan['feasible']}", field=HISTORY_FIELD)
    print(f"[plan] {code} -> plan sản xuất uploaded (giao {plan['delivery']})")


def _download_bytes(url: str) -> bytes | None:
    """Tai 1 file ve bytes (logo asset). Loi -> None (khong chan brief)."""
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.read()
    except Exception as e:
        print(f"[brief] tải asset lỗi: {e}")
        return None


def _gather_brief_inputs(fields: dict, record_id: str):
    """Gom input cho brief: items (Proposal JSON -> fallback Items), trang thai asset, insight, logo bytes."""
    items = _plan_items_from_fields(fields, record_id)
    asset_status = {
        "logo": bool(fields.get("Logo game")),
        "kv": bool(fields.get("Key Visual (KV)")),
        "source": bool(fields.get("Source material")),
    }
    insight = game_insight(fields.get("Game") or "")
    logo_atts = fields.get("Logo game") or []
    logo_png = _download_bytes(logo_atts[0].get("url")) if logo_atts else None
    return items, asset_status, insight, logo_png


def _generate_brief(record_id: str, code: str) -> None:
    """Buoc 5: sinh deck brief design -> upload -> clear co. Loi KHONG escalate PIC."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    fields = rec.get("fields", {})
    items, asset_status, insight, logo_png = _gather_brief_inputs(fields, record_id)
    brief_data = build_brief_content(fields, items, asset_status, insight)
    images = gather_brief_images(brief_data["items"], fields.get("Game") or "")
    project = {
        "code": fields.get("Mã project") or code, "name": fields.get("Tên project") or "",
        "game": fields.get("Game") or "", "so_luong": fields.get("Số lượng (bộ/suất)") or "?",
        "deadline": (str(fields.get("Deadline cần hàng"))[:10] if fields.get("Deadline cần hàng") else "?"),
        "logo_png": logo_png,
    }
    pptx = render_brief_pptx(brief_data, images, project)
    update_project(record_id, {"File brief design": []})  # clear ban cu -> re-trigger thay vi cong don
    upload_brief(record_id, pptx, code)
    update_project(record_id, {"Bắt đầu design": False})
    append_note(record_id, f"[AI] Đã sinh brief design ({len(brief_data.get('items', []))} item).",
                field=HISTORY_FIELD)
    print(f"[brief] {code} -> brief design uploaded")


def _scan_design_starts() -> None:
    """Quet record bam nut 'Bat dau design' (co=TRUE + Da duyet items) -> sinh brief."""
    for r in fetch_projects("AND({Bắt đầu design} = TRUE(), {Status} = 'Đã duyệt items')"):
        f = r["fields"]
        code = f.get("Mã project", r["id"])
        try:
            _generate_brief(r["id"], code)
        except Exception as e:
            print(f"[brief] {code} sinh brief lỗi: {e}")
            try:  # nuot loi ghi (Airtable hiccup) de 1 record loi khong bo qua record con lai
                update_project(r["id"], {"Bắt đầu design": False})
                append_note(r["id"], f"[AI] Sinh brief design lỗi (đã clear cờ, bấm lại được): {e}",
                            field=HISTORY_FIELD)
            except Exception as e2:  # noqa: BLE001
                print(f"[brief] {code} không ghi được trạng thái lỗi: {e2}")


def _approve_proposal(record_id: str, code: str) -> None:
    """Requester duyet: chot items + Status 'Da duyet items' + sinh plan san xuat (Buoc 4)."""
    updates = [{"id": it["id"], "fields": {"Status": "Đã duyệt"}}
               for it in fetch_items_of(record_id)
               if it["fields"].get("Status") == "Đề xuất"]
    if updates:
        update_items(updates)
    update_project(record_id, {"Status": "Đã duyệt items", "Duyệt proposal?": None, "Gửi phản hồi": False})
    append_note(record_id, "[AI] Requester đã DUYỆT — chốt đề xuất.", field=HISTORY_FIELD)
    print(f"[proposal] {code} DUYỆT -> chốt {len(updates)} items -> Đã duyệt items")
    try:
        _generate_plan(record_id, code)
    except Exception as e:
        append_note(record_id, f"[AI] Sinh plan sản xuất lỗi (không ảnh hưởng chốt items): {e}",
                    field=HISTORY_FIELD)
        print(f"[plan] {code} sinh plan lỗi: {e}")


def _revise_or_escalate(record_id: str, code: str, fields: dict) -> None:
    """Requester yeu cau sua: chay lai AI #2 theo feedback, dem round, >3 -> escalate PIC."""
    feedback = fields.get("Feedback proposal", "") or ""
    rounds = int(fields.get("Số round proposal") or 0) + 1
    if rounds > MAX_PROPOSAL_ROUNDS:
        update_project(record_id, {"Status": PIC_STATUS, "Cần PIC xử lý": True, "Duyệt proposal?": None,
                                   "Gửi phản hồi": False,
                                   "Lý do cần PIC": f"Sửa proposal {MAX_PROPOSAL_ROUNDS} round vẫn chưa "
                                                    f"duyệt. Feedback gần nhất: {feedback}"})
        append_note(record_id, f"[AI] Proposal đã sửa {MAX_PROPOSAL_ROUNDS} round vẫn chưa duyệt "
                               f"— chuyển Merch PIC xử lý. Feedback gần nhất: {feedback}", field=HISTORY_FIELD)
        print(f"[proposal] {code} vượt {MAX_PROPOSAL_ROUNDS} round -> Cần PIC xử lý")
        return
    result, html = _make_proposal(record_id, feedback=feedback)
    if result.get("blocked") or result.get("over_budget") or result.get("infeasible_deadline"):
        _route_result(record_id, result, html, reset_round=False)  # feedback gây không khả thi -> vòng điều chỉnh
        return
    append_note(record_id, f"[AI] Round {rounds} — sửa proposal theo feedback: {feedback}", field=HISTORY_FIELD)
    update_project(record_id, {"Số round proposal": rounds})
    _publish_proposal(record_id, result, html, reset_round=False)
    print(f"[proposal] {code} CẦN SỬA -> round {rounds} đã gửi lại")


def _reevaluate_clarify(record_id: str, code: str, answer: str) -> None:
    """Requester tra loi cau hoi lam ro -> cham lai; thoa thi gui proposal, chua thi vao vong dieu chinh tiep."""
    result, html = _make_proposal(record_id, clarify=answer)
    if not (result.get("blocked") or result.get("over_budget") or result.get("infeasible_deadline")):
        append_note(record_id, f"[AI] Đã làm rõ yêu cầu đặc biệt theo trả lời requester: {answer}",
                    field=HISTORY_FIELD)
    _route_result(record_id, result, html, reset_round=True)


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
            # dang cho dieu chinh budget/deadline -> requester da sua field (Budget/Deadline) roi tick (KHONG can text)
            if f.get("Status") == ADJUST_STATUS:
                _reevaluate_adjust(r["id"], code)
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
    def _work():
        _scan_decisions()
        _scan_design_starts()
    _run_guarded(_decide_lock, _decide_again, _work)


def on_webhook() -> None:
    """1 webhook ping -> chay ca 2 nhanh: record moi (Buoc 1->2) + quyet dinh proposal (Buoc 2 D1)."""
    analyze_new_async()
    handle_proposal_decisions()
