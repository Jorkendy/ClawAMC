"""Render email tu bang Airtable 'Email Templates' — 1 nguon noi dung duy nhat.
PO sua noi dung trong bang (khong can deploy). Loi KHONG duoc chan pipeline."""
import re
import urllib.parse
from datetime import datetime

from airtable_client import airtable, log

EMAIL_TEMPLATE_TABLE = "Email Templates"
_VAR_RE = re.compile(r"\{\{(\w+)\}\}")

# Fallback khi bang loi/thieu dong -> mail van gui duoc. Footer luu o key 'footer'.
_DEFAULT_FOOTER = ("", "—\n📩 Email tự động từ Merch Agent — thao tác trên Airtable, "
                       "KHÔNG trả lời email này.\nMerch Agent · AMC Team · VNGGames")
DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    "bo_sung": ("[{{ma_project}}] {{ten_project}} — Cần bổ sung thông tin",
                "Chào {{ten_nguoi_gui}},\n\n{{noi_dung}}\n\nVui lòng cập nhật trên Airtable rồi tích \"Gửi phản hồi\"."),
    "clarify": ("[{{ma_project}}] {{ten_project}} — Cần trao đổi để hoàn thiện đề xuất",
                "Chào {{ten_nguoi_gui}},\n\n{{noi_dung}}\n\nVui lòng phản hồi trên Airtable rồi tích \"Gửi phản hồi\"."),
    "proposal": ("[{{ma_project}}] {{ten_project}} — Mời duyệt proposal",
                 "Chào {{ten_nguoi_gui}},\n\nProposal cho \"{{ten_project}}\" đã sẵn sàng (xem file đính kèm).\n"
                 "{{canh_bao_deadline}}\nHạn duyệt: {{han_duyet}}. Vui lòng vào Airtable Duyệt/Cần sửa."),
    "plan": ("[{{ma_project}}] {{ten_project}} — Plan sản xuất đã sẵn sàng",
             "Chào team Merch,\n\nPlan sản xuất cho \"{{ten_project}}\" đã tạo (file đính kèm). "
             "Deadline cần hàng: {{deadline_hang}}."),
    "brief": ("[{{ma_project}}] {{ten_project}} — Brief design đã sẵn sàng",
              "Chào {{ten_nguoi_gui}},\n\nBrief design cho \"{{ten_project}}\" đã sẵn sàng (file đính kèm). "
              "Deadline cần hàng: {{deadline_hang}}."),
    "pic": ("[CẦN XỬ LÝ] {{ma_project}} {{ten_project}} — chuyển Merch PIC",
            "Chào team Merch,\n\nDự án \"{{ten_project}}\" ({{game}}) cần xử lý thủ công.\nLý do: {{ly_do}}"),
    "qua_han": ("[{{ma_project}}] {{ten_project}} — Quá hạn duyệt proposal",
                "Chào {{ten_nguoi_gui}},\n\nProposal cho \"{{ten_project}}\" đã quá hạn duyệt ({{han_duyet}}) "
                "mà chưa phản hồi. Vui lòng vào Airtable duyệt sớm."),
    "footer": _DEFAULT_FOOTER,
}


def _fetch_templates() -> dict:
    """Map Mã -> (Subject, Body). Loi/khong doc duoc -> {} (caller dung DEFAULT_TEMPLATES)."""
    try:
        path = urllib.parse.quote(EMAIL_TEMPLATE_TABLE)
        recs = airtable("GET", path).get("records", [])
        out = {}
        for r in recs:
            f = r.get("fields", {})
            ma = f.get("Mã")
            if ma:
                out[ma] = (f.get("Subject", ""), f.get("Body", ""))
        return out
    except Exception as e:  # noqa: BLE001
        log.warning(f"[email] đọc bảng template lỗi: {e}")
        return {}


def _fmt_date(val) -> str:
    """YYYY-MM-DD -> dd/mm/yyyy; rong -> ''; sai dinh dang -> nguyen ban."""
    if not val:
        return ""
    try:
        return datetime.strptime(val, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(val)


def _build_vars(fields: dict, core: str | None) -> dict:
    creator = fields.get("Created by")
    name = creator.get("name") if isinstance(creator, dict) else None
    return {
        "ma_project": fields.get("Mã project", ""),
        "ten_project": fields.get("Tên project", ""),
        "game": fields.get("Game", ""),
        "ten_nguoi_gui": name or "Anh/Chị",
        "han_duyet": _fmt_date(fields.get("Deadline phê duyệt")),
        "deadline_hang": _fmt_date(fields.get("Deadline cần hàng")),
        "noi_dung": core or "",
        "ly_do": fields.get("Lý do cần PIC", "") or "",
        "canh_bao_deadline": fields.get("Cảnh báo deadline", "") or "",
        "link": fields.get("Link form duyệt", "") or "",
        "link_proposal": fields.get("Link proposal", "") or "",
    }


def _sub(text: str, variables: dict) -> str:
    """Thay {{key}} bang variables[key]; key la -> giu nguyen (safe-substitute)."""
    return _VAR_RE.sub(
        lambda m: str(variables[m.group(1)]) if m.group(1) in variables else m.group(0),
        text or "",
    )


def render_email(kind: str, fields: dict, core: str | None = None) -> tuple[str, str]:
    """Tra (subject, body) da thay bien + noi footer. KHONG raise."""
    tpls = _fetch_templates()
    variables = _build_vars(fields, core)
    if kind in tpls:
        subject_tpl, body_tpl = tpls[kind]
    else:
        log.warning(f"[email] thiếu template '{kind}' trong bảng — dùng mặc định")
        subject_tpl, body_tpl = DEFAULT_TEMPLATES.get(kind, ("", ""))
    footer = (tpls.get("footer") or DEFAULT_TEMPLATES["footer"])[1]
    subject = _sub(subject_tpl, variables)
    body = _sub(body_tpl, variables).rstrip() + "\n\n" + _sub(footer, variables)
    return subject, body
