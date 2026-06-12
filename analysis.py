"""Diem AI #1 — phan tich de bai: cham du/thieu thong tin, danh gia deadline, phan loai."""
from datetime import date, datetime

from airtable_client import airtable, update_project
from config import PROJECTS_TABLE, REQUIRED_FIELDS
from llm_client import ask_llm_json

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
