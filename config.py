"""Cau hinh chung: env vars + hang so nghiep vu."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Config ---
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "app46fhZ5wAv9LSzC")
PROJECTS_TABLE = os.environ.get("AIRTABLE_PROJECTS_TABLE", "Projects")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://llm.vinhpham.com.vn/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

# Cloudflare Access service token — neu LLM endpoint dat sau Cloudflare Access (OTP).
# Tao tai Zero Trust > Access > Service Auth > Service Tokens; gan policy cho phep token nay.
CF_ACCESS_CLIENT_ID = os.environ.get("CF_ACCESS_CLIENT_ID", "")
CF_ACCESS_CLIENT_SECRET = os.environ.get("CF_ACCESS_CLIENT_SECRET", "")

# reasoning_effort gui LLM. "disable" = tat thinking (Gemini/Claude reasoning models) de
# khong dot het max_tokens vao reasoning lam JSON bi cat. De trong neu model khong ho tro.
LLM_REASONING_EFFORT = os.environ.get("LLM_REASONING_EFFORT", "disable")

# Field id "File proposal" (bang Projects) — dung cho Airtable Upload Attachment API (base-specific)
PROPOSAL_FILE_FIELD_ID = os.environ.get("PROPOSAL_FILE_FIELD_ID", "fldFlkZzbRIX9Um48")

# Proposal duyet (Buoc 2 — D1: requester duyet tren Airtable)
PROPOSAL_APPROVAL_DAYS = 3   # han requester duyet proposal (ngay)
MAX_PROPOSAL_ROUNDS = 3      # so round sua toi da -> escalate Merch PIC
MAX_CLARIFY_ROUNDS = 3       # so vong lam ro yeu cau dac biet toi da -> escalate Merch PIC

# Timeline du kien toan trinh intake -> hang ve kho, theo critical path
# (buoc 1+2+5+6+10+11+13+14). Don vi: NGAY LAM VIEC.
# So lieu [GIA DINH] — can validate bang 10-15 project history.
PIPELINE_WORKDAYS = {"min": 31, "avg": 53, "max": 68}
WORKDAYS_TO_CALENDAR = 1.4  # 5 ngay lam viec ~ 7 ngay lich

REQUIRED_FIELDS = {
    "Mục đích": "Mục đích sản xuất",
    "Chủ đề": "Chủ đề",
    "Định vị": "Định vị",
    "Target audience": "Target audience",
    "Số lượng (bộ/suất)": "Số lượng items",
    "Deadline cần hàng": "Deadline",
    "Budget (VND)": "Budget",
}
