"""Cau hinh chung: env vars + hang so nghiep vu."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Config ---
AIRTABLE_BASE_ID = "app46fhZ5wAv9LSzC"
PROJECTS_TABLE = "Projects"
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3-5-27b")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

ZALO_TOKEN = os.environ.get("ZALO_BOT_TOKEN", "")
ZALO_BASE = "https://bot-api.zapps.me/bot{token}/{method}"

# Field id "File proposal" (bang Projects) — dung cho Airtable Upload Attachment API
PROPOSAL_FILE_FIELD_ID = "fldFlkZzbRIX9Um48"

# Proposal duyet (Buoc 2 — D1: requester duyet tren Airtable)
PROPOSAL_APPROVAL_DAYS = 3   # han requester duyet proposal (ngay)
MAX_PROPOSAL_ROUNDS = 3      # so round sua toi da -> escalate Merch PIC

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
