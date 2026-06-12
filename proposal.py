"""Diem AI #2 — proposal items + bao gia du kien tu Price History (code kiem tra tong, LLM sang tao)."""
import json
from datetime import date

from airtable_client import airtable, fetch_all, update_project
from analysis import build_brief
from llm_client import ask_llm_json


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
