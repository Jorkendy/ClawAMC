"""Cau hinh chung: env vars + hang so nghiep vu."""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

# --- Config ---
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "app46fhZ5wAv9LSzC")
PROJECTS_TABLE = os.environ.get("AIRTABLE_PROJECTS_TABLE", "Projects")
# Bang log chi phi AI (1 dong/lan dung AI). Dung table ID (ten co dau cach -> tranh encode).
AI_COST_LOG_TABLE = os.environ.get("AI_COST_LOG_TABLE", "tblssSLXoyXZiEjwG")
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://llm.vinhpham.com.vn/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
# Model du phong khi LLM_MODEL fail (vd LiteLLM fallback hong -> 503). Vd "claude-sonnet". "" = tat.
LLM_MODEL_FALLBACK = os.environ.get("LLM_MODEL_FALLBACK", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_IMAGE_MODEL = os.environ.get("LLM_IMAGE_MODEL", "gemini/imagen-4.0-fast-generate-001")
# Cong tac gen anh AI (proposal + brief). Tat (false) khi test nhieu de khoi ton chi phi anh.
# Default true (prod co anh); dat AI_IMAGES_ENABLED=false tren sandbox de test re.
AI_IMAGES_ENABLED = os.environ.get("AI_IMAGES_ENABLED", "true").strip().lower() not in ("false", "0", "no", "off")
# Model cho insight game (grounding Google Search) — can Gemini 2.x, tach khoi LLM_MODEL chinh.
LLM_GROUNDING_MODEL = os.environ.get("LLM_GROUNDING_MODEL", "gemini-flash")

# Cloudflare Access service token — neu LLM endpoint dat sau Cloudflare Access (OTP).
# Tao tai Zero Trust > Access > Service Auth > Service Tokens; gan policy cho phep token nay.
CF_ACCESS_CLIENT_ID = os.environ.get("CF_ACCESS_CLIENT_ID", "")
CF_ACCESS_CLIENT_SECRET = os.environ.get("CF_ACCESS_CLIENT_SECRET", "")

# reasoning_effort gui LLM. "disable" = tat thinking (Gemini/Claude reasoning models) de
# khong dot het max_tokens vao reasoning lam JSON bi cat. De trong neu model khong ho tro.
LLM_REASONING_EFFORT = os.environ.get("LLM_REASONING_EFFORT", "disable")

# Field id "File proposal" (bang Projects) — dung cho Airtable Upload Attachment API (base-specific)
PROPOSAL_FILE_FIELD_ID = os.environ.get("PROPOSAL_FILE_FIELD_ID", "fldFlkZzbRIX9Um48")
# Field id "File plan san xuat" (Buoc 4) — Airtable Upload Attachment API (base appo1Oei5JvJ1EXAG)
PLAN_FILE_FIELD_ID = os.environ.get("PLAN_FILE_FIELD_ID", "fldYBX6NoMbTOqatf")
# Field id "File brief design" (Buoc 5) — Airtable Upload Attachment API (base appo1Oei5JvJ1EXAG)
BRIEF_FILE_FIELD_ID = os.environ.get("BRIEF_FILE_FIELD_ID", "fldfqeqkVAegySzZ5")

# URL form Fillout phan hoi (seat-free). De trong -> route /proposal khong chen nut "Phan hoi".
# Link tao = FILLOUT_FORM_URL + "?id=" + record_id (khop pre-fetch + update record cua Fillout).
FILLOUT_FORM_URL = os.environ.get("FILLOUT_FORM_URL", "")

# Proposal duyet (Buoc 2 — D1: requester duyet tren Airtable)
PROPOSAL_APPROVAL_DAYS = 3   # han requester duyet proposal (ngay)
MAX_PROPOSAL_ROUNDS = 3      # so round sua toi da -> escalate Merch PIC
MAX_CLARIFY_ROUNDS = 3       # so vong lam ro yeu cau dac biet toi da -> escalate Merch PIC
MAX_SUPPLEMENT_ROUNDS = 3    # so lan re-analyze (bo sung thong tin) toi da -> escalate PIC (chong spam mail)

# Don gia uoc tinh chi phi AI (VND) — [GIA DINH] cap nhat theo bang gia thuc te de "chung minh"
# chi phi van hanh. Anh + grounding la phan dat; chat self-host re.
COST_PER_IMAGE_VND = 520           # imagen-4-fast ~ $0.02 (truoc gemini-flash-image ~$0.039=1000)
COST_GROUNDED_PER_CALL_VND = 900   # grounding Google Search ~ $0.035/call (gop ca token)
COST_CHAT_PER_1K_IN_VND = 2        # chat input (gemini-flash) ~
COST_CHAT_PER_1K_OUT_VND = 8       # chat output ~

# Timeline du kien toan trinh intake -> hang ve kho, theo critical path
# (buoc 1+2+5+6+10+11+13+14). Don vi: NGAY LAM VIEC.
# So lieu [GIA DINH] — can validate bang 10-15 project history.
PIPELINE_WORKDAYS = {"min": 31, "avg": 53, "max": 68}
WORKDAYS_TO_CALENDAR = 1.4  # 5 ngay lam viec ~ 7 ngay lich

# Deadline theo LEAD-TIME ITEM (Buoc 2 — chinh xac hon ro cung generic; tinh sau khi chon item).
# Ngay can (LV) = OVERHEAD + max(Thoi gian len mau) + max(Thoi gian san xuat)  [san xuat song song -> max]
# [GIA DINH 19/06 — validate bang gantt/project that]
DEADLINE_OVERHEAD_WORKDAYS = 27   # overhead co dinh ngoai item = Head 18 + Duyet mau 7 + Giao hang 2
# Chi tiet overhead (de ve timeline tung giai doan o plan san xuat Buoc 4); tong = DEADLINE_OVERHEAD_WORKDAYS
OVERHEAD_HEAD_WORKDAYS = 18           # chuan bi: brief, ke hoach, chot NCC
OVERHEAD_REVIEW_SAMPLE_WORKDAYS = 7   # duyet mau
OVERHEAD_DELIVERY_WORKDAYS = 2        # giao hang & nghiem thu
CREATIVE_LEADTIME_LEN_MAU = 8     # item creative (chua co trong catalogue) -> gia dinh thoi gian len mau
CREATIVE_LEADTIME_SAN_XUAT = 25   # ... san xuat (lay dau phuc tap vi creative thuong lau)
DEADLINE_BUFFER = 1.15            # con lai < ngay_can*buffer -> canh bao "sat nut" (van chay)
MIN_FAST_ITEMS = 3               # so item toi thieu de "phuong an nhanh" du tot (else -> hoi doi deadline)

REQUIRED_FIELDS = {
    "Mục đích": "Mục đích sản xuất",
    "Chủ đề": "Chủ đề",
    "Định vị": "Định vị",
    "Target audience": "Target audience",
    "Số lượng (bộ/suất)": "Số lượng items",
    "Deadline cần hàng": "Deadline",
    "Budget (VND)": "Budget",
}
