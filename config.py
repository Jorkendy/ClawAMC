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
