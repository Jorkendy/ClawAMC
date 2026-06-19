"""Diem AI #2 — proposal items tu Catalogue (gia co dinh) + item creative (gia null -> hoi vendor).

Tỉ lệ định hướng ~80% catalogue + ~20% creative (gợi ý mềm). Giá item catalogue lấy ĐÚNG
từ bảng Catalogue (code ép, chống bịa giá); item creative don_gia=null. Code tính tổng (không
tin số model tự cộng) + vòng tự sửa budget. Phân loại merch (project) suy ra từ items đã chọn.
"""
import base64
import json
import urllib.request

from airtable_client import airtable, fetch_all, fetch_items_of, update_project
from analysis import build_brief, deadline_status_of
from llm_client import ask_llm_grounded, ask_llm_json, generate_image

# Loai item — dung de map sang field "Loai" (singleSelect) cua bang Items khi khop
ITEM_TYPES = ["Áo thun", "Hoodie", "Áo khoác gió", "Mũ lưỡi trai", "Ly giữ nhiệt",
              "Bình nước", "Móc khóa", "Sticker set", "Túi tote", "Standee",
              "Gấu bông", "Figure PVC", "Tượng resin", "Tai nghe bluetooth", "Đèn ngủ 3D"]


def catalogue_data() -> tuple[str, dict]:
    """Doc bang Catalogue -> (text cho prompt, map ten->fields de ep gia)."""
    rows = fetch_all("Catalogue", [
        "Name", "Miêu tả sản phẩm", "Số lượng tối thiểu", "Đơn giá",
        "Thời gian lên mẫu", "Thời gian sản xuất", "Xuất xứ", "Hình ảnh mô tả",
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
{special_req_block}
YÊU CẦU:
1. Số lượng item LINH HOẠT (thường 3-6) tùy ngân sách mỗi bộ + độ phù hợp — KHÔNG nhồi cho đủ số; thà ít món chất hơn nhiều món gượng ép.
2. Ưu tiên item từ CATALOGUE trước (có giá thật, sản xuất nhanh); chỉ thêm CREATIVE để lấp món catalogue còn THIẾU cho hợp đối tượng. Số item creative KHÔNG vượt số catalogue (giữ proposal đa số có giá để chốt được, không quá nhiều món chờ báo giá).
3. PHẢI có ít nhất 1 "item key": món điểm nhấn mang dấu ấn riêng của game (thường là item creative).
4. Item lấy từ catalogue: "nguon"="catalogue"; "ten" phải TRÙNG KHỚP TÊN trong catalogue; "don_gia" = đúng giá catalogue; "can_cu_gia"="Giá catalogue". "chat_lieu"/"kich_thuoc" rút từ mô tả catalogue.
5. Item creative (không có trong catalogue): "nguon"="creative"; "don_gia"=null; "can_cu_gia"="Item sáng tạo — chưa có giá, cần hỏi vendor". TUYỆT ĐỐI không bịa giá. Điền "goi_y_anh" = mô tả hình minh hoạ NGẮN bằng TIẾNG ANH (hình dạng sản phẩm + yếu tố/màu chủ đạo của game) để hệ thống tự generate ảnh concept. Item catalogue để "goi_y_anh"=null (đã có ảnh thật).
6. Tổng chi phí (đơn giá × số lượng, bỏ qua item giá null) phải ≤ budget. Mặc định "so_luong" mỗi item = Số lượng (bộ/suất) ở đề bài. Lưu ý MOQ (Số lượng tối thiểu) của item catalogue — nếu Số lượng đề bài < MOQ thì nâng "so_luong" lên MOQ và ghi cảnh báo vào "can_cu_gia".
7. "loai": loại item; nếu khớp một trong [{item_types}] thì ghi ĐÚNG tên đó, không thì để chuỗi rỗng.
8. "nhan_xet": 2-3 câu về chiến lược bộ quà + lưu ý MOQ/lead time nếu liên quan. KHÔNG nêu con số tổng chi phí / số tiền còn dư trong nhan_xet — hệ thống tự tính và hiển thị riêng (model cộng tiền hay sai).
9. YÊU CẦU ĐẶC BIỆT của requester (nếu có ở khối phía trên) là RÀNG BUỘC BẮT BUỘC. Với MỖI yêu cầu, xác định "loai" rồi tự chấm "dap_ung":
   - "loai": "item-bat-buoc" (đòi 1 món cụ thể) | "design-co-san" (requester đưa link design sẵn) | "khac".
   - "design-co-san" → LUÔN "met": tạo 1 item creative tương ứng, điền "design_link" của item đó = link requester cung cấp (trích từ nội dung yêu cầu); item dùng design có sẵn, KHÔNG thiết kế mới; "don_gia"=null (hỏi vendor sau như mọi item creative) — KHÔNG đánh "unmet" chỉ vì chưa có giá.
   - "met" (các loại khác): đáp ứng được bằng item trong proposal (món có sẵn trong catalogue phù hợp, HOẶC creative khả thi rõ ràng và nằm trong budget).
   - "unmet": món custom requester ĐÒI (item-bat-buoc) NGOÀI catalogue (vd gấu bông, figure đặc thù) mà bạn KHÔNG chắc sản xuất được / chưa rõ giá / chưa rõ MOQ; vượt budget; mâu thuẫn brief. KHI NGHI NGỜ → để "unmet" (TUYỆT ĐỐI không tự nhận làm được). Lưu ý: "design-co-san" KHÔNG thuộc nhóm này.
10. Nếu có BẤT KỲ yêu cầu "unmet" → điền "cau_hoi_lam_ro": lời nhắn tiếng Việt ngắn gọn, lịch sự cho requester — nêu rõ TỪNG yêu cầu chưa đáp ứng + vì sao, rồi gợi ý 3 lựa chọn: (a) bỏ/nới yêu cầu đó, (b) tăng budget, (c) chấp nhận phương án thay thế. Nếu TẤT CẢ "met" (hoặc không có yêu cầu đặc biệt) → "cau_hoi_lam_ro"=null. ĐỪNG hỏi chung chung kiểu "còn yêu cầu nào khác không" — chỉ hỏi đúng cái đang unmet.
11. "yeu_cau_dac_biet_chot": chỉ điền khi có CÂU TRẢ LỜI LÀM RÕ ở dưới — ghi lại nội dung yêu cầu đặc biệt SAU khi đã áp dụng câu trả lời (vd requester bỏ gấu bông và không còn ràng buộc nào → ""; nếu đổi sang món khác → mô tả món mới). Đây là bản chốt để lưu, dùng cho các lần sau. Nếu KHÔNG có câu trả lời làm rõ → null.
12. "co_so_quyet_dinh": 2-4 câu tiếng Việt GIẢI TRÌNH vì sao chọn bộ này — cụ thể: vì sao số lượng & cơ cấu item (catalogue/creative) như vậy; insight game / đối tượng / phân khúc giá trị đã dẫn dắt thế nào; ràng buộc đã xét (deadline / MOQ / catalogue mỏng nếu có). Đây là phần để requester/sếp đánh giá chất lượng đề xuất.

JSON schema: {{"items": [{{"ten": str, "nguon": "catalogue"|"creative", "loai": str, "chat_lieu": str, "kich_thuoc": str, "so_luong": int, "don_gia": int|null, "can_cu_gia": str, "item_key": bool, "design_link": str|null, "goi_y_anh": str|null}}], "tong_du_kien": int, "nhan_xet": str, "co_so_quyet_dinh": str, "yeu_cau_dac_biet": [{{"noi_dung": str, "dap_ung": "met"|"unmet", "ly_do": str, "loai": str}}], "cau_hoi_lam_ro": str|null, "yeu_cau_dac_biet_chot": str|null}}"""

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


# BIZ RULE: phan khuc gia tri suy tu ngan sach MOI BO qua = Budget / So luong.
# Nguong [GIA DINH 19/06 — can validate thuc te VNGGames]: xem BUSINESS_RULES.md.
def value_tier(budget: int, quantity: int) -> tuple[str, int]:
    """Tra (tier, per_unit). per_unit = ngan sach moi bo qua = budget/so luong."""
    per_unit = int(budget / quantity) if (budget and quantity) else 0
    if not per_unit:
        return "(chưa xác định)", 0
    if per_unit < 100_000:
        return "Phổ thông", per_unit
    if per_unit <= 500_000:
        return "Tầm trung", per_unit
    return "Cao cấp", per_unit


_GAME_INSIGHT_CACHE: dict = {}

GAME_INSIGHT_PROMPT = """Bạn là chuyên gia merchandise game. Dựa trên thông tin web MỚI NHẤT về game "{game}", \
tóm tắt ngắn gọn (tiếng Việt, 5-8 gạch đầu dòng) để định hướng chọn quà tặng merch:
- Đối tượng người chơi chính (độ tuổi, giới tính, đặc điểm).
- Phong cách nghệ thuật / tông màu / nhân vật & biểu tượng đặc trưng.
- Loại merchandise cộng đồng game này ưa thích (nếu có thông tin).
Chỉ nêu điều có cơ sở; không chắc thì nói chung theo thể loại game. KHÔNG bịa."""


def game_insight(game: str) -> str:
    """Insight game tu web (grounding) -> dinh huong chon item khach quan (bot phu thuoc catalogue).
    Cache theo ten game trong 1 lan chay (revise khong goi lai)."""
    game = (game or "").strip()
    if not game:
        return ""
    if game not in _GAME_INSIGHT_CACHE:
        clean = game.split(" [")[0].strip()  # bo hau to ma noi bo "Nikki VN [199]" -> "Nikki VN"
        _GAME_INSIGHT_CACHE[game] = ask_llm_grounded(GAME_INSIGHT_PROMPT.format(game=clean))
    return _GAME_INSIGHT_CACHE[game]


def _url_to_data_uri(url: str) -> str | None:
    """Tai anh tu URL -> data URI base64 (nhung thang vao HTML, khong phu thuoc link het han)."""
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "image/png")
        return f"data:{ctype};base64,{base64.b64encode(data).decode('ascii')}"
    except Exception as e:  # noqa: BLE001
        print(f"[proposal] tải ảnh catalogue lỗi: {e}")
        return None


def _build_images(items: list, by_name: dict) -> dict:
    """Map {ten item -> data URI}: catalogue dung anh that (Hinh anh mo ta), creative generate concept.
    Loi/khong co anh -> bo qua (renderer fallback icon). Chi goi o ban proposal CUOI (sau cac cong chan)."""
    out = {}
    for it in items:
        name = it.get("ten", "")
        if not name:
            continue
        if it.get("nguon") == "catalogue":
            atts = (by_name.get(name) or {}).get("Hình ảnh mô tả") or []
            if atts:
                src = (atts[0].get("thumbnails", {}).get("large", {}).get("url")
                       or atts[0].get("url"))
                uri = _url_to_data_uri(src) if src else None
                if uri:
                    out[name] = uri
        else:  # creative -> generate anh concept/wireframe
            goi_y = (it.get("goi_y_anh") or "").strip()
            if goi_y:
                prompt = (f"{goi_y}. Style: rough concept sketch / wireframe mockup, "
                          "simple line art, minimal color, plain white background, "
                          "product visualization idea — not a final polished design.")
                b64 = generate_image(prompt)
                if b64:
                    out[name] = f"data:image/png;base64,{b64}"
    return out


def _special_req_block(special: str) -> str:
    if not special:
        return "\n(Không có yêu cầu đặc biệt — để \"yeu_cau_dac_biet\" = [] và \"cau_hoi_lam_ro\"=null.)\n"
    return ("\nYÊU CẦU ĐẶC BIỆT CỦA REQUESTER (ràng buộc BẮT BUỘC — phải thỏa hết, "
            "nếu không chắc thì đánh dấu \"unmet\" và hỏi lại, KHÔNG tự bịa là làm được):\n"
            f"{special}\n")


def propose_items_for(record: dict, feedback: str | None = None,
                      clarify: str | None = None) -> dict:
    fields = record["fields"]
    code = fields.get("Mã project", record["id"])
    budget = fields.get("Budget (VND)") or 0
    special = (fields.get("Yêu cầu đặc biệt") or "").strip()
    deadline_status = deadline_status_of(fields)
    catalogue_txt, by_name = catalogue_data()

    # Xoa item de xuat cu (neu co) -> tao lai sach, tranh nhan doi khi revise
    for it in fetch_items_of(record["id"]):
        if it["fields"].get("Status") == "Đề xuất":
            airtable("DELETE", f"Items/{it['id']}")

    base_prompt = PROPOSAL_PROMPT.format(
        brief=build_brief(fields),
        catalogue=catalogue_txt,
        special_req_block=_special_req_block(special),
        item_types=", ".join(ITEM_TYPES),
    )
    insight = game_insight(fields.get("Game", ""))
    if insight:
        base_prompt += ("\n\nINSIGHT GAME (research từ web — dùng để chọn item HỢP đối tượng & "
                        f"phong cách game, KHÔNG chỉ dựa catalogue):\n{insight}")
    quantity = fields.get("Số lượng (bộ/suất)") or 0
    tier, per_unit = value_tier(budget, quantity)
    if per_unit:
        base_prompt += (
            f"\n\nPHÂN KHÚC GIÁ TRỊ (tự tính): ngân sách mỗi bộ quà = {per_unit:,}đ "
            f"({budget:,}đ ÷ {quantity} bộ) → phân khúc \"{tier}\". "
            "Chọn item sao cho TỔNG đơn giá mỗi bộ ≈ ngân sách này (KHÔNG vượt): phân khúc cao "
            "→ ưu tiên item giá trị/thẩm mỹ cao để người nhận thấy xứng đáng; phổ thông → item hợp lý, "
            "thực dụng, có thể nhiều món. Dùng cả Định vị / Mục đích / Target audience để chọn LOẠI item phù hợp "
            "(vd đối tượng lớn tuổi → đồ thực dụng như bình giữ nhiệt/sổ tay; thu nhập cao → item giá trị cao).")
    if feedback:
        base_prompt += (f"\n\nFEEDBACK CỦA REQUESTER VỀ PROPOSAL TRƯỚC "
                        f"(điều chỉnh lại đúng theo ý này):\n{feedback}")
    if clarify:
        base_prompt += (
            "\n\nREQUESTER ĐÃ TRẢ LỜI LÀM RÕ YÊU CẦU ĐẶC BIỆT:\n"
            f"{clarify}\n"
            "Câu trả lời này là MỚI NHẤT và CÓ THẨM QUYỀN, được ƯU TIÊN HƠN nội dung 'Yêu cầu đặc biệt' gốc "
            "nếu mâu thuẫn. Nếu nó bỏ/nới/đổi một yêu cầu (vd 'bỏ X', 'thay X bằng Y', 'tăng budget') → "
            "COI yêu cầu đó đã được điều chỉnh theo câu trả lời, chấm 'met' và TIẾP TỤC ra proposal bình thường. "
            "Chỉ để 'unmet' nếu SAU câu trả lời VẪN còn ràng buộc thực sự chưa thỏa. "
            "Nhớ điền 'yeu_cau_dac_biet_chot' = yêu cầu sau điều chỉnh.")
    if deadline_status == "không khả thi":
        base_prompt += (
            "\n\nLƯU Ý — DEADLINE KHÔNG KHẢ THI (quá gấp so với timeline sản xuất): "
            "CHỈ đề xuất item từ CATALOGUE (hàng có sẵn, lead-time ngắn nhất); TUYỆT ĐỐI KHÔNG thêm item creative. "
            "Item key chọn từ catalogue (món nổi bật nhất). "
            "Trong 'nhan_xet' giải thích: vì deadline không khả thi nên chỉ đề xuất hàng có sẵn để rút ngắn thời gian, "
            "chưa kèm item creative (cần thêm thời gian thiết kế/sản xuất); và cảnh báo dù chỉ dùng hàng có sẵn "
            "vẫn rủi ro không kịp deadline.")
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
            "và 3 items tối thiểu, và GIỮ các item thỏa yêu cầu đặc biệt. "
            "Vẫn tuân thủ mọi quy tắc về giá (giá catalogue cố định, creative giá null). "
            "Trả về JSON cùng schema."
        )
        proposal = ask_llm_json(fix_prompt, max_tokens=2500)
        _enforce_catalogue_price(proposal, by_name)

    # Cong chan: con yeu cau dac biet chua dap ung -> KHONG chot proposal, hoi lai requester
    unmet = [r for r in (proposal.get("yeu_cau_dac_biet") or [])
             if r.get("dap_ung") == "unmet"]
    if unmet:
        msg = proposal.get("cau_hoi_lam_ro") or (
            "Một số yêu cầu đặc biệt chưa thể đáp ứng:\n"
            + "\n".join(f"- {r.get('noi_dung', '')}: {r.get('ly_do', '')}" for r in unmet)
            + "\n\nBạn muốn: (a) bỏ/nới yêu cầu, (b) tăng budget, hay (c) chấp nhận phương án thay thế?")
        return {"project_code": code, "blocked": True, "unmet": unmet,
                "clarify_message": msg, "proposal": proposal}

    # Cong chan budget: sau cac vong tu sua van vuot -> KHONG chot proposal, chuyen PIC
    total_check = proposal_total(proposal)
    if budget and total_check > budget:
        return {"project_code": code, "over_budget": True,
                "total": total_check, "budget": budget, "proposal": proposal}

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
        if it.get("design_link"):
            f["Design có sẵn (link)"] = it["design_link"]
            f["Ghi chú AI"] += " | Dùng design requester cung cấp, không thiết kế mới"
        item_records.append({"fields": f})

        phan_loai_merch.add(loai_item)
        if (it.get("don_gia") or 0) > 50_000_000:
            phan_loai_merch.add("Giá trị cao >50tr")

    airtable("POST", "Items", {"records": item_records, "typecast": True})

    total = proposal_total(proposal)
    n_cat = sum(1 for it in proposal["items"] if it.get("nguon") == "catalogue")
    n_cre = len(proposal["items"]) - n_cat
    # KHONG nhet summary vao "Phan tich AI" (de field do = phan tich de bai cua AI #1).
    # Proposal da the hien qua Items + File proposal.
    proj_updates = {"Phân loại merch": sorted(phan_loai_merch)}
    # Clarify resolve -> luu yeu cau da chot vao "Yeu cau dac biet" (de lan sau revise khong block lai
    # vi doc lai field cu mau thuan voi cau tra loi).
    if clarify:
        chot = proposal.get("yeu_cau_dac_biet_chot")
        proj_updates["Yêu cầu đặc biệt"] = (
            chot if chot is not None else f"{special}\n[Điều chỉnh theo trả lời] {clarify}")
    update_project(record["id"], proj_updates)

    images = _build_images(proposal["items"], by_name)

    return {"project_code": code, "blocked": False, "items_created": len(item_records),
            "total": total, "budget": budget, "revisions": revisions,
            "n_catalogue": n_cat, "n_creative": n_cre, "proposal": proposal, "images": images,
            "tier": tier, "per_unit": per_unit, "insight": insight}
