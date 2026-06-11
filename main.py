"""Merch Agent — phan tich de bai merchandise VNGGames.

Agent chay tren GreenNode AgentBase (Custom framework):
- HTTP server: GreenNodeAgentBaseApp (POST /invocations, GET /health)
- LLM: GreenNode AI Platform (OpenAI-compatible), model qwen/qwen3-5-27b
- Data: Airtable base "Merch Automation MVP"

Actions (payload JSON cua POST /invocations):
  {"action": "analyze_project", "project_code": "MERCH-001"}
  {"action": "analyze_new"}   # quet tat ca record status "Moi tiep nhan"
"""
import json
import os
import threading
import time
from datetime import date, datetime

import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv
from greennode_agentbase import GreenNodeAgentBaseApp, PingStatus, RequestContext
from openai import OpenAI

load_dotenv()

app = GreenNodeAgentBaseApp()

# --- Config ---
AIRTABLE_BASE_ID = "app46fhZ5wAv9LSzC"
PROJECTS_TABLE = "Projects"
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3-5-27b")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

# Lead time toi thieu (ngay) tu kinh nghiem san xuat — dung de danh gia deadline
LEAD_TIME_DAYS = {
    "San xuat moi": 30,      # proposal 2-3d + design 5d + len mau 7-14d + sx 15-30d
    "Mua san": 10,           # dat hang + khac logo + giao
    "Gia tri cao >50tr": 60, # quy trinh PROC rieng + len mau phuc tap
}

REQUIRED_FIELDS = {
    "Mục đích": "Mục đích sản xuất",
    "Chủ đề": "Chủ đề",
    "Định vị": "Định vị",
    "Target audience": "Target audience",
    "Số lượng (bộ/suất)": "Số lượng items",
    "Deadline cần hàng": "Deadline",
    "Budget (VND)": "Budget",
}


# --- Airtable REST helpers ---
def airtable(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {AIRTABLE_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_projects(formula: str) -> list[dict]:
    qs = urllib.parse.urlencode({"filterByFormula": formula})
    return airtable("GET", f"{PROJECTS_TABLE}?{qs}").get("records", [])


def update_project(record_id: str, fields: dict) -> dict:
    return airtable("PATCH", f"{PROJECTS_TABLE}/{record_id}", {"fields": fields})


# --- LLM helpers ---
def ask_llm_json(prompt: str, max_tokens: int = 1500) -> dict:
    resp = llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json").strip()
    return json.loads(raw)


# --- LLM analysis ---
ANALYSIS_PROMPT = """Bạn là chuyên gia sản xuất merchandise cho game với 10 năm kinh nghiệm tại VNGGames.
Phân tích đề bài sản xuất merch dưới đây và trả về DUY NHẤT một JSON object (không markdown, không giải thích ngoài JSON).

ĐỀ BÀI:
{brief}

THÔNG TIN BỔ TRỢ (đã tính sẵn, dùng nguyên — không tự tính lại ngày tháng):
- Hôm nay: {today}
- Số ngày từ hôm nay đến deadline cần hàng: {days_to_deadline}
- Lead time tối thiểu theo loại merch (ngày): Sản xuất mới = 30, Mua sẵn = 10, Giá trị cao >50tr = 60
- Các trường thông tin đang THIẾU (đã kiểm tra sẵn): {missing_fields}

YÊU CẦU PHÂN TÍCH:
1. "phan_loai": đề bài này thuộc nhóm nào trong ["Sản xuất mới", "Mua sẵn", "Giá trị cao >50tr"] — có thể nhiều nhóm. Suy luận từ mục đích/chủ đề/budget (vd: quà thiết kế riêng theo game → Sản xuất mới; có item điện tử/hàng có sẵn thị trường → thêm Mua sẵn). QUY TẮC CỨNG cho "Giá trị cao >50tr": chỉ gán khi có ít nhất 1 MÓN đơn giá vượt 50 triệu VND — ước lượng đơn giá trung bình = budget ÷ số lượng; quà "premium/cao cấp" thông thường (vài trăm nghìn đến vài triệu/món) KHÔNG thuộc nhóm này, trừ khi đề bài nêu rõ có giải thưởng/tượng/vật phẩm đặc biệt đắt tiền.
2. "deadline_kha_thi": true/false — so days_to_deadline với lead time của nhóm phan_loai nặng nhất. Nếu thiếu deadline thì null.
3. "ly_do_deadline": 1-2 câu giải thích (tiếng Việt).
4. "tom_tat": 2-3 câu tóm tắt đề bài + nhận định chuyên môn (gợi ý hướng item phù hợp audience).
5. "muc_do_uu_tien": "cao" | "trung bình" | "thấp" — dựa trên deadline gấp và budget lớn.
6. "mail_bo_sung": nếu missing_fields không rỗng HOẶC deadline không khả thi → soạn email tiếng Việt ngắn gọn, chuyên nghiệp gửi requester: chào theo tên, nêu rõ từng thông tin thiếu cần bổ sung (giải thích vì sao cần), nếu deadline không khả thi thì đề xuất 2 hướng (lùi deadline theo lead time / đổi sang nhóm item nhanh hơn). Kết thúc bằng chữ ký "Merch Agent — VNGGames". Nếu đủ thông tin và deadline ổn → null.

JSON schema: {{"phan_loai": [...], "deadline_kha_thi": bool|null, "ly_do_deadline": str, "tom_tat": str, "muc_do_uu_tien": str, "mail_bo_sung": str|null}}"""


def build_brief(fields: dict) -> str:
    lines = []
    label_map = {
        "Tên project": "Tên project", "Mã project": "Mã", "Game": "Game",
        "Mục đích": "Mục đích", "Chủ đề": "Chủ đề", "Định vị": "Định vị",
        "Target audience": "Target audience", "Số lượng (bộ/suất)": "Số lượng",
        "Deadline cần hàng": "Deadline cần hàng", "Budget (VND)": "Budget (VND)",
    }
    for field, label in label_map.items():
        val = fields.get(field)
        lines.append(f"- {label}: {val if val not in (None, '') else '(chưa có)'}")
    return "\n".join(lines)


def next_project_code() -> str:
    """Tu cap ma MERCH-xxx cho record tu form (form an field Ma project)."""
    records = airtable("GET", f"{PROJECTS_TABLE}?fields%5B%5D=M%C3%A3%20project").get("records", [])
    nums = [int(f["fields"]["Mã project"].split("-")[1])
            for f in records
            if f["fields"].get("Mã project", "").startswith("MERCH-")
            and f["fields"]["Mã project"].split("-")[1].isdigit()]
    return f"MERCH-{(max(nums) + 1 if nums else 1):03d}"


def analyze_one(record: dict) -> dict:
    fields = record["fields"]
    code = fields.get("Mã project")
    if not code:
        code = next_project_code()
        update_project(record["id"], {"Mã project": code})
        fields["Mã project"] = code

    missing = [label for f, label in REQUIRED_FIELDS.items() if fields.get(f) in (None, "")]

    days_to_deadline = "(không có deadline)"
    if fields.get("Deadline cần hàng"):
        d = datetime.strptime(fields["Deadline cần hàng"], "%Y-%m-%d").date()
        days_to_deadline = (d - date.today()).days

    prompt = ANALYSIS_PROMPT.format(
        brief=build_brief(fields),
        today=date.today().isoformat(),
        days_to_deadline=days_to_deadline,
        missing_fields=missing or "(không thiếu gì)",
    )
    analysis = ask_llm_json(prompt, max_tokens=1500)

    ok = not missing and analysis.get("deadline_kha_thi") is not False
    new_status = "Chờ duyệt items" if ok else "Thiếu thông tin"

    note_parts = [
        f"[AI {date.today():%d/%m}] {analysis['tom_tat']}",
        f"Phân loại: {', '.join(analysis['phan_loai'])} | Ưu tiên: {analysis['muc_do_uu_tien']}",
        f"Deadline: {'✅ khả thi' if analysis.get('deadline_kha_thi') else '⚠️ ' + ('KHÔNG khả thi' if analysis.get('deadline_kha_thi') is False else 'chưa có')} — {analysis['ly_do_deadline']}",
    ]
    if missing:
        note_parts.append(f"Thiếu thông tin: {', '.join(missing)}")
    if analysis.get("mail_bo_sung"):
        note_parts.append("--- DRAFT MAIL GỬI REQUESTER ---\n" + analysis["mail_bo_sung"])

    update_fields = {
        "Phân tích AI": "\n".join(note_parts),
        "Status": new_status,
        "Phân loại merch": analysis["phan_loai"],
    }
    update_project(record["id"], update_fields)

    return {
        "project_code": code,
        "new_status": new_status,
        "missing": missing,
        "analysis": analysis,
    }


# --- Proposal items + bao gia du kien ---
def fetch_all(table: str, fields: list[str]) -> list[dict]:
    """Lay het record cua 1 bang (toi da ~100, du cho MVP)."""
    qs = urllib.parse.urlencode([("fields[]", f) for f in fields])
    return airtable("GET", f"{urllib.parse.quote(table)}?{qs}").get("records", [])


def price_history_text() -> str:
    rows = fetch_all("Price History", [
        "Item", "Loại", "Chất liệu", "Kích thước", "Số lượng đặt",
        "Đơn giá (VND)", "MOQ", "Năm", "Ghi chú",
    ])
    lines = []
    for r in rows:
        f = r["fields"]
        note = f" | note: {f['Ghi chú']}" if f.get("Ghi chú") else ""
        lines.append(
            f"- {f.get('Loại')} | {f.get('Item')} | {f.get('Chất liệu')} | "
            f"SL {f.get('Số lượng đặt')} | {f.get('Đơn giá (VND)'):,}đ/c | "
            f"MOQ {f.get('MOQ')} | năm {f.get('Năm')}{note}"
        )
    return "\n".join(lines)


def vendors_info() -> tuple[str, dict]:
    rows = fetch_all("Vendors", ["Tên vendor", "Chuyên môn", "Rating (1-5)",
                                 "Lead time lên mẫu", "Lead time sản xuất", "Ghi chú"])
    lines, name_to_id = [], {}
    for r in rows:
        f = r["fields"]
        name = f.get("Tên vendor", "")
        name_to_id[name] = r["id"]
        note = f" | {f['Ghi chú']}" if f.get("Ghi chú") else ""
        lines.append(
            f"- {name} | rating {f.get('Rating (1-5)')} | "
            f"{', '.join(f.get('Chuyên môn', []))} | mẫu {f.get('Lead time lên mẫu')} | "
            f"sx {f.get('Lead time sản xuất')}{note}"
        )
    return "\n".join(lines), name_to_id


ITEM_TYPES = ["Áo thun", "Hoodie", "Áo khoác gió", "Mũ lưỡi trai", "Ly giữ nhiệt",
              "Bình nước", "Móc khóa", "Sticker set", "Túi tote", "Standee",
              "Gấu bông", "Figure PVC", "Tượng resin", "Tai nghe bluetooth", "Đèn ngủ 3D"]

PROPOSAL_PROMPT = """Bạn là chuyên gia merchandise game 10 năm kinh nghiệm tại VNGGames.
Đề xuất bộ items cho đề bài dưới đây và trả về DUY NHẤT một JSON object.

ĐỀ BÀI:
{brief}

LỊCH SỬ GIÁ ĐÃ SẢN XUẤT (nguồn sự thật duy nhất về giá — KHÔNG được bịa giá ngoài đây):
{price_history}

VENDOR POOL:
{vendors}

YÊU CẦU:
1. Đề xuất 4-6 items phù hợp chủ đề/định vị/target audience. Loại item PHẢI chọn từ: {item_types}.
2. Ít nhất 1 item là "item key" — sáng tạo, mang dấu ấn riêng của game, làm điểm nhấn bộ quà.
3. "don_gia" (VND/cái): tra từ LỊCH SỬ GIÁ — chọn dòng cùng loại + chất liệu gần nhất, và "Số lượng đặt" GẦN NHẤT với số lượng đề xuất (vd đề xuất 300 cái thì dùng dòng SL 300, KHÔNG dùng dòng SL 1000 cho rẻ); ưu tiên dòng năm mới nhất; giá năm cũ cộng ~9%/năm đến 2026, làm tròn nghìn. Nếu số lượng đề xuất < MOQ của dòng giá → cảnh báo trong can_cu_gia. Ghi rõ căn cứ vào "can_cu_gia" (trích dòng nào, điều chỉnh gì).
4. QUY TẮC CỨNG: item KHÔNG có dòng lịch sử giá tương đồng (cùng loại item) → "don_gia": null và "can_cu_gia": "Chưa có dữ liệu giá — cần hỏi vendor". TUYỆT ĐỐI không suy đoán giá.
5. "vendor": chọn từ VENDOR POOL theo chuyên môn khớp loại item; ưu tiên rating cao; tránh vendor có lịch sử trễ hạn nếu đơn gấp. Item chưa rõ vendor → null.
6. Tổng chi phí (đơn giá × số lượng, bỏ qua item giá null) phải ≤ budget. Lưu ý MOQ trong lịch sử giá.
7. "nhan_xet": 2-3 câu về chiến lược bộ quà + lưu ý MOQ/phí khuôn/lead time lấy từ note lịch sử giá nếu liên quan.

JSON schema: {{"items": [{{"ten": str, "loai": str, "chat_lieu": str, "kich_thuoc": str, "so_luong": int, "don_gia": int|null, "vendor": str|null, "can_cu_gia": str, "item_key": bool}}], "tong_du_kien": int, "nhan_xet": str}}"""


def proposal_total(proposal: dict) -> int:
    """Tinh tong bang code — khong tin con so model tu cong."""
    return sum((it.get("don_gia") or 0) * (it.get("so_luong") or 0)
               for it in proposal.get("items", []))


def propose_items_for(record: dict) -> dict:
    fields = record["fields"]
    code = fields.get("Mã project", record["id"])
    budget = fields.get("Budget (VND)") or 0
    vendors_text, vendor_ids = vendors_info()

    base_prompt = PROPOSAL_PROMPT.format(
        brief=build_brief(fields),
        price_history=price_history_text(),
        vendors=vendors_text,
        item_types=", ".join(ITEM_TYPES),
    )
    proposal = ask_llm_json(base_prompt, max_tokens=2500)

    # Vong tu sua: vuot budget -> bat LLM dieu chinh, toi da 2 lan
    revisions = 0
    while budget and proposal_total(proposal) > budget and revisions < 2:
        revisions += 1
        fix_prompt = (
            f"{base_prompt}\n\nPROPOSAL TRƯỚC CỦA BẠN (tổng {proposal_total(proposal):,}đ "
            f"VƯỢT budget {budget:,}đ — KHÔNG chấp nhận được):\n{json.dumps(proposal, ensure_ascii=False)}\n\n"
            "Điều chỉnh lại để tổng (đơn giá × số lượng) ≤ budget: giảm số lượng item đắt, "
            "thay item đắt bằng item rẻ hơn, hoặc bỏ bớt item — nhưng vẫn giữ ít nhất 1 item key "
            "và 4 items tối thiểu. Vẫn tuân thủ mọi quy tắc về giá. Trả về JSON cùng schema."
        )
        proposal = ask_llm_json(fix_prompt, max_tokens=2500)

    item_records = []
    for it in proposal["items"]:
        f = {
            "Tên item": ("⭐ " if it.get("item_key") else "") + it["ten"],
            "Project": [record["id"]],
            "Phân loại": "Sản xuất mới" if it["loai"] != "Tai nghe bluetooth" else "Mua sẵn",
            "Chất liệu": it.get("chat_lieu", ""),
            "Kích thước": it.get("kich_thuoc", ""),
            "Số lượng": it.get("so_luong"),
            "Status": "Đề xuất",
            "Ghi chú AI": f"[AI] {it.get('can_cu_gia', '')}",
        }
        if it["loai"] in ITEM_TYPES:
            f["Loại"] = it["loai"]
        if it.get("don_gia"):
            f["Đơn giá dự kiến (VND)"] = it["don_gia"]
        if it.get("vendor") in vendor_ids:
            f["Vendor"] = [vendor_ids[it["vendor"]]]
        item_records.append({"fields": f})

    airtable("POST", "Items", {"records": item_records, "typecast": True})

    total = proposal_total(proposal)
    old_note = fields.get("Phân tích AI", "")
    summary = (f"[AI {date.today():%d/%m}] PROPOSAL: {len(item_records)} items, "
               f"tổng dự kiến {total:,}đ / budget {budget:,}đ"
               + (f" (đã tự điều chỉnh {revisions} lần để vào budget)" if revisions else "")
               + f".\n{proposal.get('nhan_xet', '')}")
    update_project(record["id"], {"Phân tích AI": f"{old_note}\n\n{summary}".strip()})

    return {"project_code": code, "items_created": len(item_records),
            "total": total, "budget": budget, "revisions": revisions, "proposal": proposal}


# --- Zalo approval flow ---
ZALO_TOKEN = os.environ.get("ZALO_BOT_TOKEN", "")
ZALO_BASE = "https://bot-api.zapps.me/bot{token}/{method}"

# Phieu duyet dang cho: {approver_zalo_id: {record_id, code, approver_name}}
# Luu y MVP: in-memory, mat khi restart — production se chuyen sang bang Airtable rieng
PENDING_APPROVALS: dict[str, dict] = {}


def zalo_call(method: str, payload: dict | None = None) -> dict:
    url = ZALO_BASE.format(token=ZALO_TOKEN, method=method)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode())


def zalo_send(chat_id: str, text: str) -> None:
    zalo_call("sendMessage", {"chat_id": chat_id, "text": text})


def users_map() -> dict:
    rows = fetch_all("Users", ["Tên", "Zalo ID", "Vai trò"])
    return {r["id"]: {"name": r["fields"].get("Tên", "?"),
                      "zalo": r["fields"].get("Zalo ID", "")} for r in rows}


def fetch_items_of(record_id: str) -> list[dict]:
    rows = fetch_all("Items", ["Tên item", "Project", "Số lượng",
                               "Đơn giá dự kiến (VND)", "Status"])
    return [r for r in rows if record_id in (r["fields"].get("Project") or [])]


def request_approval_for(record: dict) -> dict:
    fields = record["fields"]
    code = fields.get("Mã project", record["id"])
    approver_ids = fields.get("Approver") or []
    if not approver_ids:
        # Fallback: form khong chon Approver -> lay quan ly truc tiep cua Requester
        users = fetch_all("Users", ["Tên", "Zalo ID", "Quản lý trực tiếp", "Vai trò"])
        by_id = {r["id"]: r["fields"] for r in users}
        by_name = {r["fields"].get("Tên"): r["id"] for r in users}
        req_ids = fields.get("Requester") or []
        mgr_name = by_id.get(req_ids[0], {}).get("Quản lý trực tiếp", "") if req_ids else ""
        if mgr_name and by_name.get(mgr_name):
            approver_ids = [by_name[mgr_name]]
            reason = f"tự gán {mgr_name} (quản lý của requester) theo approval matrix"
        else:
            pic = next((r for r in users if r["fields"].get("Vai trò") == "Merch PIC"), None)
            if not pic:
                append_note(record["id"], f"[AI {date.today():%d/%m}] ⚠️ KHÔNG gửi được phiếu duyệt: "
                                          f"thiếu Approver/Requester và không có Merch PIC trong Users.")
                return {"status": "error", "message": f"{code} chua co Approver"}
            approver_ids = [pic["id"]]
            reason = f"form không có Requester/Approver — phiếu chuyển về Merch PIC ({pic['fields'].get('Tên')}) triage"
        update_project(record["id"], {"Approver": approver_ids})
        append_note(record["id"], f"[AI {date.today():%d/%m}] {reason}.")
    approver = users_map().get(approver_ids[0], {})
    if not approver.get("zalo"):
        return {"status": "error", "message": f"Approver {approver.get('name')} chua co Zalo ID"}

    items = [r for r in fetch_items_of(record["id"])
             if r["fields"].get("Status") == "Đề xuất"]
    total = sum((r["fields"].get("Đơn giá dự kiến (VND)") or 0)
                * (r["fields"].get("Số lượng") or 0) for r in items)
    item_lines = "\n".join(
        f"• {r['fields'].get('Tên item')} — SL {r['fields'].get('Số lượng')}"
        + (f" × {r['fields'].get('Đơn giá dự kiến (VND)'):,}đ"
           if r['fields'].get('Đơn giá dự kiến (VND)') else " (chờ vendor báo giá)")
        for r in items)

    text = (
        f"📋 PHIẾU DUYỆT ITEMS [{code}]\n"
        f"{fields.get('Tên project', '')}\n"
        f"————————————\n{item_lines}\n————————————\n"
        f"Tổng dự kiến: {total:,}đ / Budget: {fields.get('Budget (VND)', 0):,}đ\n\n"
        f"Reply 1 ✅ Duyệt | Reply 2 ❌ Từ chối"
    )
    zalo_send(approver["zalo"], text)
    PENDING_APPROVALS[approver["zalo"]] = {
        "record_id": record["id"], "code": code, "approver_name": approver["name"],
    }
    return {"status": "success", "project_code": code,
            "sent_to": approver["name"], "items": len(items), "total": total}


# RFQ dang cho vendor tra gia: {vendor_chat_id: {record_id, code, items: [...]}}
PENDING_RFQ: dict[str, dict] = {}


def update_items(records: list[dict]) -> None:
    airtable("PATCH", "Items", {"records": records, "typecast": True})


def send_rfq_for(record: dict) -> dict:
    fields = record["fields"]
    code = fields.get("Mã project", record["id"])
    vendors = {r["id"]: r["fields"] for r in fetch_all(
        "Vendors", ["Tên vendor", "Zalo ID"])}

    items = fetch_all("Items", ["Tên item", "Project", "Loại", "Chất liệu",
                                "Kích thước", "Số lượng", "Status", "Vendor"])
    items = [r for r in items if record["id"] in (r["fields"].get("Project") or [])
             and r["fields"].get("Status") in ("Đề xuất", "Chờ báo giá")]

    by_vendor: dict[str, list] = {}
    skipped = []
    for it in items:
        vids = it["fields"].get("Vendor") or []
        if vids and vendors.get(vids[0], {}).get("Zalo ID"):
            by_vendor.setdefault(vids[0], []).append(it)
        else:
            skipped.append(it["fields"].get("Tên item"))

    sent = []
    for vid, its in by_vendor.items():
        v = vendors[vid]
        chat_id = v["Zalo ID"]
        spec_lines = "\n".join(
            f"• {r['fields'].get('Tên item')}\n"
            f"  Chất liệu: {r['fields'].get('Chất liệu', '?')} | "
            f"Kích thước: {r['fields'].get('Kích thước', '?')} | "
            f"SL: {r['fields'].get('Số lượng', '?')}"
            for r in its)
        text = (
            f"📨 YÊU CẦU BÁO GIÁ [{code}]\n"
            f"Kính gửi {v.get('Tên vendor')},\n"
            f"VNGGames cần báo giá các items sau:\n————————————\n{spec_lines}\n————————————\n"
            f"Deadline cần hàng: {fields.get('Deadline cần hàng', '?')}\n"
            f"Vui lòng báo: đơn giá theo SL, MOQ, thời gian lên mẫu, thời gian sản xuất.\n"
            f"(Reply trực tiếp tin nhắn này — hệ thống tự ghi nhận)"
        )
        zalo_send(chat_id, text)
        entry = PENDING_RFQ.setdefault(chat_id, {
            "record_id": record["id"], "code": code, "items": []})
        entry["items"].extend(
            {"id": r["id"], "ten": r["fields"].get("Tên item"),
             "so_luong": r["fields"].get("Số lượng")} for r in its)
        update_items([{"id": r["id"], "fields": {"Status": "Chờ báo giá"}} for r in its])
        sent.append(v.get("Tên vendor"))

    if sent:
        update_project(record["id"], {"Status": "Chờ vendor báo giá"})
        note = f"[AI {date.today():%d/%m}] Đã gửi RFQ qua Zalo cho: {', '.join(sent)}."
        if skipped:
            note += f" Bỏ qua (chưa có vendor/Zalo): {', '.join(skipped)}."
        append_note(record["id"], note)
    return {"status": "success", "project_code": code,
            "rfq_sent_to": sent, "skipped": skipped}


RFQ_PARSE_PROMPT = """Bạn là trợ lý mua hàng. Vendor vừa reply báo giá qua Zalo. Phân tích và trả về DUY NHẤT một JSON object.

ITEMS ĐANG CHỜ BÁO GIÁ (id | tên | số lượng):
{items}

TIN NHẮN CỦA VENDOR:
{message}

YÊU CẦU:
- Khớp từng báo giá trong tin nhắn với item theo tên (khớp gần đúng). Item vendor không nhắc tới → bỏ qua.
- "don_gia" là VND/cái (vendor viết "115k" = 115000, "1tr2" = 1200000).
- "tu_choi": true CHỈ KHI vendor nói rõ không làm được / không kịp deadline. Nếu tin nhắn báo giá toàn items KHÔNG có trong danh sách (vendor có thể nhầm đơn khác) → "tu_choi": false, "items": [] và ghi chú "báo giá không khớp items đang chờ".
- "ghi_chu": tóm tắt các điều kiện khác vendor nêu (phí khuôn, cọc, điều kiện thanh toán...).

JSON schema: {{"tu_choi": bool, "items": [{{"id": str, "don_gia": int|null, "moq": int|null, "lead_time_mau": str|null, "lead_time_sx": str|null}}], "ghi_chu": str}}"""


def handle_vendor_reply(chat_id: str, msg: dict) -> None:
    pend = PENDING_RFQ[chat_id]
    text = (msg.get("text") or "").strip()
    items_desc = "\n".join(f"- {i['id']} | {i['ten']} | SL {i['so_luong']}"
                           for i in pend["items"])
    parsed = ask_llm_json(RFQ_PARSE_PROMPT.format(items=items_desc, message=text),
                          max_tokens=1200)

    now = datetime.now().strftime("%d/%m %H:%M")
    sender = (msg.get("from") or {}).get("display_name", "vendor")
    if parsed.get("tu_choi"):
        append_note(pend["record_id"],
                    f"[VENDOR {now}] ⚠️ Vendor TỪ CHỐI/không kịp ({sender}): {parsed.get('ghi_chu', '')}")
        zalo_send(chat_id, f"Đã ghi nhận phản hồi cho [{pend['code']}]. "
                           f"Merch PIC sẽ liên hệ lại phương án thay thế.")
        del PENDING_RFQ[chat_id]
        return

    # Bao gia khong khop item nao -> hoi lai vendor, GIU phien cho (khong dong)
    if not parsed.get("items"):
        ten_items = ", ".join(i["ten"] for i in pend["items"])
        zalo_send(chat_id,
                  f"⚠️ Báo giá có vẻ chưa khớp items đang chờ của [{pend['code']}]: {ten_items}.\n"
                  f"Anh/chị kiểm tra lại giúp và báo giá theo đúng các items trên nhé.")
        return

    updates, quoted = [], []
    valid_ids = {i["id"] for i in pend["items"]}
    for q in parsed.get("items", []):
        if q.get("id") not in valid_ids or not q.get("don_gia"):
            continue
        note = (f"[Báo giá vendor {now}] {q['don_gia']:,}đ/c"
                + (f" | MOQ {q['moq']}" if q.get("moq") else "")
                + (f" | mẫu {q['lead_time_mau']}" if q.get("lead_time_mau") else "")
                + (f" | sx {q['lead_time_sx']}" if q.get("lead_time_sx") else ""))
        updates.append({"id": q["id"], "fields": {
            "Đơn giá dự kiến (VND)": q["don_gia"],
            "Status": "Đã có báo giá",
            "Ghi chú AI": note,
        }})
        quoted.append(q["id"])
    if updates:
        update_items(updates)

    remaining = [i for i in pend["items"] if i["id"] not in quoted]
    summary = (f"[VENDOR {now}] Nhận báo giá từ {sender}: {len(quoted)}/{len(pend['items'])} items."
               + (f" Ghi chú: {parsed.get('ghi_chu')}" if parsed.get("ghi_chu") else "")
               + (f" Còn chờ: {', '.join(i['ten'] for i in remaining)}" if remaining else ""))
    append_note(pend["record_id"], summary)
    zalo_send(chat_id, f"✅ Đã ghi nhận báo giá [{pend['code']}] — {len(quoted)} items "
                       f"cập nhật vào hệ thống. Cảm ơn {sender}!")
    if remaining:
        pend["items"] = remaining
    else:
        del PENDING_RFQ[chat_id]

    # Du bao gia TOAN PROJECT (moi vendor co the tra loi luc khac nhau) -> chuyen status
    all_items = fetch_items_of(pend["record_id"])
    waiting = [r for r in all_items
               if r["fields"].get("Status") in ("Đề xuất", "Chờ báo giá")]
    if not waiting:
        update_project(pend["record_id"], {"Status": "Chờ duyệt mẫu"})
        append_note(pend["record_id"],
                    f"[AI {now}] ✅ Đủ báo giá toàn bộ items — Status → Chờ duyệt mẫu. "
                    f"Bước tiếp: chốt vendor, yêu cầu lên mẫu.")
        pic_zalo = next((u["fields"].get("Zalo ID") for u in fetch_all("Users", ["Vai trò", "Zalo ID"])
                         if u["fields"].get("Vai trò") == "Merch PIC"), None)
        if pic_zalo:
            zalo_send(pic_zalo, f"📊 [{pend['code']}] đã đủ báo giá toàn bộ items. "
                                f"Status → Chờ duyệt mẫu. Vào Airtable chốt vendor và yêu cầu lên mẫu nhé.")


def append_note(record_id: str, note: str) -> None:
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    old = rec.get("fields", {}).get("Phân tích AI", "")
    update_project(record_id, {"Phân tích AI": f"{old}\n\n{note}".strip()})


def handle_zalo_message(msg: dict) -> None:
    chat_id = (msg.get("chat") or {}).get("id", "")
    sender = msg.get("from") or {}
    text = (msg.get("text") or "").strip()

    # Routing: phieu duyet (reply 1/2) uu tien; con lai la vendor tra gia neu co RFQ cho
    pend = PENDING_APPROVALS.get(chat_id)
    if pend and text in ("1", "2"):
        now = datetime.now().strftime("%d/%m %H:%M")
        who = f"{sender.get('display_name', '?')} ({sender.get('id', '?')})"
        if text == "1":
            update_project(pend["record_id"], {"Status": "Đã duyệt items"})
            append_note(pend["record_id"], f"[APPROVAL {now}] ✅ DUYỆT bởi {who} qua Zalo.")
            zalo_send(chat_id, f"✅ Đã ghi nhận DUYỆT [{pend['code']}] — {who}, {now}.\n"
                               f"Status → Đã duyệt items. Đang gửi RFQ cho vendor...")
            del PENDING_APPROVALS[chat_id]
            # Auto-chain: duyet xong -> gui RFQ vendor ngay
            try:
                rec = airtable("GET", f"{PROJECTS_TABLE}/{pend['record_id']}")
                result = send_rfq_for(rec)
                if result.get("rfq_sent_to"):
                    zalo_send(chat_id, f"📨 Đã gửi RFQ [{pend['code']}] cho vendor: "
                                       f"{', '.join(result['rfq_sent_to'])}.")
            except Exception as e:  # noqa: BLE001
                print(f"[zalo] auto-RFQ error: {e}")
        else:
            append_note(pend["record_id"], f"[APPROVAL {now}] ❌ TỪ CHỐI bởi {who} qua Zalo — cần làm lại proposal.")
            zalo_send(chat_id, f"❌ Đã ghi nhận TỪ CHỐI [{pend['code']}] — {who}, {now}.\n"
                               f"Merch PIC sẽ điều chỉnh proposal và gửi lại.")
            del PENDING_APPROVALS[chat_id]
        return

    if chat_id in PENDING_RFQ:
        handle_vendor_reply(chat_id, msg)
        return

    if pend:
        zalo_send(chat_id, f"Phiếu [{pend['code']}] đang chờ — reply 1 để duyệt, 2 để từ chối.")


def zalo_poller() -> None:
    """Consumer DUY NHAT cua getUpdates (consume-on-read) — khong duoc chay script khac song song."""
    print("[zalo] poller started")
    while True:
        try:
            res = zalo_call("getUpdates", {"timeout": 25})
            result = res.get("result")
            msg = result.get("message") if isinstance(result, dict) else None
            if isinstance(msg, dict):
                handle_zalo_message(msg)
        except Exception as e:  # noqa: BLE001
            print(f"[zalo] poller error: {e}")
            time.sleep(5)


# --- Reminder / escalation ---
def check_reminders() -> dict:
    """Quet project qua han duyet -> nhac approver, qua 3 ngay -> escalate manager."""
    today = date.today()
    users = fetch_all("Users", ["Tên", "Zalo ID", "Quản lý trực tiếp"])
    by_id = {r["id"]: r["fields"] for r in users}
    by_name = {r["fields"].get("Tên"): r["fields"] for r in users}

    projs = fetch_all("Projects", ["Mã project", "Tên project", "Status",
                                   "Deadline phê duyệt", "Approver"])
    reminded, escalated = [], []
    for p in projs:
        f = p["fields"]
        if f.get("Status") not in ("Chờ duyệt items", "Quá hạn duyệt"):
            continue
        if not f.get("Deadline phê duyệt"):
            continue
        overdue = (today - datetime.strptime(f["Deadline phê duyệt"], "%Y-%m-%d").date()).days
        if overdue <= 0:
            continue

        code = f.get("Mã project", "?")
        approver = by_id.get((f.get("Approver") or [None])[0], {})
        if f.get("Status") != "Quá hạn duyệt":
            update_project(p["id"], {"Status": "Quá hạn duyệt"})
        if approver.get("Zalo ID"):
            zalo_send(approver["Zalo ID"],
                      f"⏰ NHẮC DUYỆT [{code}] {f.get('Tên project', '')}\n"
                      f"Phiếu duyệt items đã quá hạn {overdue} ngày "
                      f"(deadline {f['Deadline phê duyệt']}). Vui lòng xử lý sớm.")
            reminded.append(code)
        if overdue >= 3:
            mgr = by_name.get(approver.get("Quản lý trực tiếp", ""), {})
            if mgr.get("Zalo ID"):
                zalo_send(mgr["Zalo ID"],
                          f"🚨 ESCALATION [{code}] {f.get('Tên project', '')}\n"
                          f"Phiếu duyệt quá hạn {overdue} ngày, approver "
                          f"{approver.get('Tên', '?')} chưa phản hồi sau nhiều lần nhắc. "
                          f"Kính chuyển anh/chị xử lý.")
                escalated.append(code)
        append_note(p["id"], f"[REMINDER {today:%d/%m}] Nhắc duyệt lần nữa (quá hạn {overdue} ngày)"
                             + (" + escalate lên quản lý." if overdue >= 3 else "."))
    return {"status": "success", "reminded": reminded, "escalated": escalated}


def reminder_scheduler() -> None:
    while True:
        time.sleep(6 * 3600)
        try:
            check_reminders()
        except Exception as e:  # noqa: BLE001
            print(f"[reminder] error: {e}")


# --- Webhook tu Airtable: form submit -> tu phan tich ---
_ANALYZE_LOCK = threading.Lock()


def analyze_new_async() -> None:
    """Form submit -> phan tich -> (neu du thong tin) propose -> gui phieu duyet Zalo."""
    if not _ANALYZE_LOCK.acquire(blocking=False):
        return  # dang co lan quet khac chay
    try:
        records = fetch_projects("OR({Status} = 'Mới tiếp nhận', {Status} = BLANK())")
        for r in records:
            try:
                result = analyze_one(r)
                print(f"[webhook] analyzed {result['project_code']} -> {result['new_status']}")
                if result["new_status"] == "Chờ duyệt items":
                    rec = airtable("GET", f"{PROJECTS_TABLE}/{r['id']}")
                    prop = propose_items_for(rec)
                    print(f"[webhook] proposed {prop['items_created']} items "
                          f"({prop['total']:,}d / {prop['budget']:,}d, {prop['revisions']} revisions)")
                    rec = airtable("GET", f"{PROJECTS_TABLE}/{r['id']}")
                    appr = request_approval_for(rec)
                    print(f"[webhook] approval sent to {appr.get('sent_to')}")
            except Exception as e:  # noqa: BLE001
                print(f"[webhook] pipeline error: {e}")
    finally:
        _ANALYZE_LOCK.release()


# --- Entrypoint ---
@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    # Airtable webhook ping (khong co "action", co "webhook"/"base") -> xu ly nen, tra 200 ngay
    if "webhook" in payload and "base" in payload:
        threading.Thread(target=analyze_new_async, daemon=True).start()
        return {"status": "accepted", "trigger": "airtable_webhook"}

    action = payload.get("action", "analyze_new")

    if action == "analyze_project":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return {"status": "success", "results": [analyze_one(records[0])]}

    if action == "analyze_new":
        records = fetch_projects("OR({Status} = 'Mới tiếp nhận', {Status} = BLANK())")
        results = [analyze_one(r) for r in records]
        return {"status": "success", "count": len(results), "results": results}

    if action == "propose_items":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return {"status": "success", "results": [propose_items_for(records[0])]}

    if action == "check_reminders":
        return check_reminders()

    if action == "send_rfq":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return send_rfq_for(records[0])

    if action == "request_approval":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return request_approval_for(records[0])

    return {"status": "error", "message": f"Unknown action: {action}"}


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    if ZALO_TOKEN:
        threading.Thread(target=zalo_poller, daemon=True).start()
        threading.Thread(target=reminder_scheduler, daemon=True).start()
    else:
        print("[zalo] ZALO_BOT_TOKEN chua co trong .env — approval flow tat")
    app.run(port=8080, host="0.0.0.0")
