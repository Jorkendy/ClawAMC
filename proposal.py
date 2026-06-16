"""Diem AI #2 — proposal items tu Catalogue (gia co dinh) + item creative (gia null -> hoi vendor).

Tỉ lệ định hướng ~80% catalogue + ~20% creative (gợi ý mềm). Giá item catalogue lấy ĐÚNG
từ bảng Catalogue (code ép, chống bịa giá); item creative don_gia=null. Code tính tổng (không
tin số model tự cộng) + vòng tự sửa budget. Phân loại merch (project) suy ra từ items đã chọn.
"""
import json
from datetime import date

from airtable_client import airtable, fetch_all, fetch_items_of, update_project
from analysis import build_brief
from llm_client import ask_llm_json

# Loai item — dung de map sang field "Loai" (singleSelect) cua bang Items khi khop
ITEM_TYPES = ["Áo thun", "Hoodie", "Áo khoác gió", "Mũ lưỡi trai", "Ly giữ nhiệt",
              "Bình nước", "Móc khóa", "Sticker set", "Túi tote", "Standee",
              "Gấu bông", "Figure PVC", "Tượng resin", "Tai nghe bluetooth", "Đèn ngủ 3D"]


def catalogue_data() -> tuple[str, dict]:
    """Doc bang Catalogue -> (text cho prompt, map ten->fields de ep gia)."""
    rows = fetch_all("Catalogue", [
        "Name", "Miêu tả sản phẩm", "Số lượng tối thiểu", "Đơn giá",
        "Thời gian lên mẫu", "Thời gian sản xuất", "Xuất xứ",
    ])
    lines, by_name = [], {}
    for r in rows:
        f = r["fields"]
        name = f.get("Name", "")
        if not name:
            continue
        by_name[name] = f
        gia = f.get("Đơn giá")
        desc = (f.get("Miêu tả sản phẩm") or "").replace("\n", " ")[:90]
        lines.append(
            f"- {name} | {gia:,}đ | MOQ {f.get('Số lượng tối thiểu', '?')} | "
            f"mẫu {f.get('Thời gian lên mẫu', '?')} | sx {f.get('Thời gian sản xuất', '?')} | "
            f"{f.get('Xuất xứ', '?')} | {desc}"
        )
    return "\n".join(lines), by_name


PROPOSAL_PROMPT = """Bạn là chuyên gia merchandise game 10 năm kinh nghiệm tại VNGGames.
Đề xuất bộ quà tặng (merch) cho đề bài dưới đây và trả về DUY NHẤT một JSON object.

ĐỀ BÀI:
{brief}

CATALOGUE SẢN PHẨM CÓ SẴN (giá cố định — nguồn giá DUY NHẤT; KHÔNG được sửa giá, KHÔNG bịa sản phẩm ngoài danh sách):
{catalogue}

YÊU CẦU:
1. Đề xuất 4-6 items phù hợp chủ đề / định vị / target audience.
2. Tỉ lệ định hướng ~80% từ CATALOGUE + ~20% CREATIVE (item tự sáng tạo, chỉ thêm nếu có ý tưởng hay). Ví dụ 5 món → ~4 catalogue + 1 creative. Đây là gợi ý mềm — ưu tiên hợp đề bài hơn là ép đúng tỉ lệ.
3. PHẢI có ít nhất 1 "item key": món điểm nhấn mang dấu ấn riêng của game (thường là item creative).
4. Item lấy từ catalogue: "nguon"="catalogue"; "ten" phải TRÙNG KHỚP TÊN trong catalogue; "don_gia" = đúng giá catalogue; "can_cu_gia"="Giá catalogue". "chat_lieu"/"kich_thuoc" rút từ mô tả catalogue.
5. Item creative (không có trong catalogue): "nguon"="creative"; "don_gia"=null; "can_cu_gia"="Item sáng tạo — chưa có giá, cần hỏi vendor". TUYỆT ĐỐI không bịa giá.
6. Tổng chi phí (đơn giá × số lượng, bỏ qua item giá null) phải ≤ budget. Lưu ý MOQ (Số lượng tối thiểu) của item catalogue — số lượng đề xuất nên ≥ MOQ; nếu nhỏ hơn thì ghi cảnh báo vào "can_cu_gia".
7. "loai": loại item; nếu khớp một trong [{item_types}] thì ghi ĐÚNG tên đó, không thì để chuỗi rỗng.
8. "nhan_xet": 2-3 câu về chiến lược bộ quà + lưu ý MOQ/lead time nếu liên quan. KHÔNG nêu con số tổng chi phí / số tiền còn dư trong nhan_xet — hệ thống tự tính và hiển thị riêng (model cộng tiền hay sai).

JSON schema: {{"items": [{{"ten": str, "nguon": "catalogue"|"creative", "loai": str, "chat_lieu": str, "kich_thuoc": str, "so_luong": int, "don_gia": int|null, "can_cu_gia": str, "item_key": bool}}], "tong_du_kien": int, "nhan_xet": str}}"""

PHAN_LOAI_ITEMS = {"Sản xuất mới", "Mua sẵn", "Giá trị cao >50tr"}


def _enforce_catalogue_price(proposal: dict, by_name: dict) -> None:
    """Chong bia gia: item catalogue PHAI lay gia that tu Catalogue.
    Ten khong khop catalogue -> ha xuong creative (gia null, can hoi vendor)."""
    for it in proposal.get("items", []):
        if it.get("nguon") == "catalogue":
            cat = by_name.get(it.get("ten", ""))
            if cat:
                it["don_gia"] = cat.get("Đơn giá")
            else:
                it["nguon"] = "creative"
                it["don_gia"] = None
                it["can_cu_gia"] = "Tên không khớp catalogue — coi như sáng tạo, cần hỏi vendor"


def proposal_total(proposal: dict) -> int:
    """Tinh tong bang code — khong tin con so model tu cong."""
    return sum((it.get("don_gia") or 0) * (it.get("so_luong") or 0)
               for it in proposal.get("items", []))


def propose_items_for(record: dict, feedback: str | None = None) -> dict:
    fields = record["fields"]
    code = fields.get("Mã project", record["id"])
    budget = fields.get("Budget (VND)") or 0
    catalogue_txt, by_name = catalogue_data()

    # Xoa item de xuat cu (neu co) -> tao lai sach, tranh nhan doi khi revise
    for it in fetch_items_of(record["id"]):
        if it["fields"].get("Status") == "Đề xuất":
            airtable("DELETE", f"Items/{it['id']}")

    base_prompt = PROPOSAL_PROMPT.format(
        brief=build_brief(fields),
        catalogue=catalogue_txt,
        item_types=", ".join(ITEM_TYPES),
    )
    if feedback:
        base_prompt += (f"\n\nFEEDBACK CỦA REQUESTER VỀ PROPOSAL TRƯỚC "
                        f"(điều chỉnh lại đúng theo ý này):\n{feedback}")
    proposal = ask_llm_json(base_prompt, max_tokens=2500)
    _enforce_catalogue_price(proposal, by_name)

    # Vong tu sua: vuot budget -> bat LLM dieu chinh, toi da 2 lan
    revisions = 0
    while budget and proposal_total(proposal) > budget and revisions < 2:
        revisions += 1
        fix_prompt = (
            f"{base_prompt}\n\nPROPOSAL TRƯỚC CỦA BẠN (tổng {proposal_total(proposal):,}đ "
            f"VƯỢT budget {budget:,}đ — KHÔNG chấp nhận được):\n{json.dumps(proposal, ensure_ascii=False)}\n\n"
            "Điều chỉnh lại để tổng (đơn giá × số lượng) ≤ budget: giảm số lượng item đắt, "
            "thay item đắt bằng item catalogue rẻ hơn, hoặc bỏ bớt item — nhưng vẫn giữ ít nhất 1 item key "
            "và 4 items tối thiểu. Vẫn tuân thủ mọi quy tắc về giá (giá catalogue cố định, creative giá null). "
            "Trả về JSON cùng schema."
        )
        proposal = ask_llm_json(fix_prompt, max_tokens=2500)
        _enforce_catalogue_price(proposal, by_name)

    item_records = []
    phan_loai_merch = set()
    for it in proposal["items"]:
        is_cat = it.get("nguon") == "catalogue"
        loai_item = "Mua sẵn" if is_cat else "Sản xuất mới"
        f = {
            "Tên item": ("⭐ " if it.get("item_key") else "") + it["ten"],
            "Project": [record["id"]],
            "Phân loại": loai_item,
            "Chất liệu": it.get("chat_lieu", ""),
            "Kích thước": it.get("kich_thuoc", ""),
            "Số lượng": it.get("so_luong"),
            "Status": "Đề xuất",
            "Ghi chú AI": f"[AI] {it.get('can_cu_gia', '')}",
        }
        if it.get("loai") in ITEM_TYPES:
            f["Loại"] = it["loai"]
        if it.get("don_gia"):
            f["Đơn giá dự kiến (VND)"] = it["don_gia"]
        item_records.append({"fields": f})

        phan_loai_merch.add(loai_item)
        if (it.get("don_gia") or 0) > 50_000_000:
            phan_loai_merch.add("Giá trị cao >50tr")

    airtable("POST", "Items", {"records": item_records, "typecast": True})

    total = proposal_total(proposal)
    n_cat = sum(1 for it in proposal["items"] if it.get("nguon") == "catalogue")
    n_cre = len(proposal["items"]) - n_cat
    old_note = fields.get("Phân tích AI", "")
    summary = (f"[AI {date.today():%d/%m}] PROPOSAL: {len(item_records)} items "
               f"({n_cat} catalogue + {n_cre} creative), tổng dự kiến {total:,}đ / budget {budget:,}đ"
               + (f" (đã tự điều chỉnh {revisions} lần để vào budget)" if revisions else "")
               + f".\n{proposal.get('nhan_xet', '')}")
    update_project(record["id"], {
        "Phân tích AI": f"{old_note}\n\n{summary}".strip(),
        "Phân loại merch": sorted(phan_loai_merch),
    })

    return {"project_code": code, "items_created": len(item_records),
            "total": total, "budget": budget, "revisions": revisions,
            "n_catalogue": n_cat, "n_creative": n_cre, "proposal": proposal}
