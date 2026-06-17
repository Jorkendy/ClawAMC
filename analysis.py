"""Diem AI #1 — phan tich de bai: cham du/thieu thong tin, danh gia deadline, phan loai."""
from datetime import date, datetime

from airtable_client import airtable, update_project
from config import PIPELINE_WORKDAYS, PROJECTS_TABLE, REQUIRED_FIELDS, WORKDAYS_TO_CALENDAR
from llm_client import ask_llm_json

ANALYSIS_PROMPT = """Bạn là chuyên gia sản xuất merchandise cho game với 10 năm kinh nghiệm tại VNGGames.
Phân tích đề bài sản xuất merch dưới đây và trả về DUY NHẤT một JSON object (không markdown, không giải thích ngoài JSON).

ĐỀ BÀI:
{brief}

THÔNG TIN BỔ TRỢ (đã tính sẵn, dùng nguyên — không tự tính lại ngày tháng):
- Hôm nay: {today}
- Số ngày (lịch) từ hôm nay đến deadline cần hàng: {days_to_deadline}
- Đánh giá deadline (máy đã so với timeline sản xuất toàn trình): {deadline_status}
- Các trường thông tin đang THIẾU (đã kiểm tra sẵn): {missing_fields}

YÊU CẦU PHÂN TÍCH:
1. "tom_tat": 2-3 câu tóm tắt đề bài + nhận định chuyên môn (gợi ý hướng item phù hợp target audience).
2. "muc_do_uu_tien": "cao" | "trung bình" | "thấp" — dựa trên độ gấp của deadline và quy mô budget.
3. "ly_do_deadline": 1-2 câu (tiếng Việt) giải thích đánh giá deadline ở trên (vì sao gấp / không khả thi / ổn). KHÔNG tự tính lại số ngày — dùng đúng đánh giá máy đã đưa.
4. "mail_bo_sung": nếu missing_fields không rỗng HOẶC deadline "gấp"/"không khả thi" → soạn email tiếng Việt ngắn gọn, chuyên nghiệp gửi requester: chào theo tên, nêu rõ từng thông tin thiếu cần bổ sung (giải thích vì sao cần); nếu deadline gấp/không khả thi thì cảnh báo và đề xuất hướng (lùi deadline / ưu tiên hàng có sẵn cho nhanh). Kết thúc bằng chữ ký "Merch Agent — VNGGames". Nếu đủ thông tin và deadline ổn → null.

JSON schema: {{"tom_tat": str, "muc_do_uu_tien": str, "ly_do_deadline": str, "mail_bo_sung": str|null}}"""


def assess_deadline(days_to_deadline) -> str:
    """May danh gia deadline so voi timeline san xuat toan trinh (critical path)."""
    if not isinstance(days_to_deadline, int):
        return "chưa có"
    min_cal = round(PIPELINE_WORKDAYS["min"] * WORKDAYS_TO_CALENDAR)
    avg_cal = round(PIPELINE_WORKDAYS["avg"] * WORKDAYS_TO_CALENDAR)
    if days_to_deadline < min_cal:
        return "không khả thi"
    if days_to_deadline < avg_cal:
        return "gấp"
    return "ổn"


def build_brief(fields: dict) -> str:
    lines = []
    label_map = {
        "Tên project": "Tên project", "Mã project": "Mã", "Game": "Game",
        "Mục đích": "Mục đích", "Chủ đề": "Chủ đề", "Định vị": "Định vị",
        "Target audience": "Target audience", "Số lượng (bộ/suất)": "Số lượng",
        "Deadline cần hàng": "Deadline cần hàng", "Budget (VND)": "Budget (VND)",
        "Yêu cầu đặc biệt": "Yêu cầu đặc biệt (ràng buộc)",
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
    deadline_status = assess_deadline(days_to_deadline)

    prompt = ANALYSIS_PROMPT.format(
        brief=build_brief(fields),
        today=date.today().isoformat(),
        days_to_deadline=days_to_deadline,
        deadline_status=deadline_status,
        missing_fields=missing or "(không thiếu gì)",
    )
    analysis = ask_llm_json(prompt, max_tokens=1500)

    # Buoc 1 CHI canh bao deadline — status chi phu thuoc thieu thong tin
    new_status = "Chờ duyệt items" if not missing else "Thiếu thông tin"

    deadline_label = {
        "ổn": "✅ ổn", "gấp": "⚠️ gấp/rủi ro",
        "không khả thi": "⚠️ KHÔNG khả thi", "chưa có": "chưa có",
    }[deadline_status]
    note_parts = [
        f"[AI {date.today():%d/%m}] {analysis['tom_tat']}",
        f"Ưu tiên: {analysis['muc_do_uu_tien']}",
        f"Deadline: {deadline_label} — {analysis['ly_do_deadline']}",
    ]
    if missing:
        note_parts.append(f"Thiếu thông tin: {', '.join(missing)}")
    if analysis.get("mail_bo_sung"):
        note_parts.append("--- DRAFT MAIL GỬI REQUESTER ---\n" + analysis["mail_bo_sung"])

    update_fields = {
        "Phân tích AI": "\n".join(note_parts),
        "Status": new_status,
    }
    update_project(record["id"], update_fields)

    return {
        "project_code": code,
        "new_status": new_status,
        "missing": missing,
        "deadline_status": deadline_status,
        "analysis": analysis,
    }
