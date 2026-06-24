"""Airtable REST helpers — moi truy cap data deu di qua day."""
import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from config import AIRTABLE_BASE_ID, AIRTABLE_TOKEN, PROJECTS_TABLE

log = logging.getLogger("merch")

VN_TZ = timezone(timedelta(hours=7))  # gio Viet Nam, dung cho timestamp log
STEP_LOG_TABLE = "tblG4OGkyKAfUEfsj"  # bang Step Log (nhat ky tien do)


def airtable(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {AIRTABLE_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_projects(formula: str) -> list[dict]:
    qs = urllib.parse.urlencode({"filterByFormula": formula})
    return airtable("GET", f"{PROJECTS_TABLE}?{qs}").get("records", [])


def update_project(record_id: str, fields: dict) -> dict:
    return airtable("PATCH", f"{PROJECTS_TABLE}/{record_id}", {"fields": fields})


def fetch_all(table: str, fields: list[str]) -> list[dict]:
    """Lay het record cua 1 bang (toi da ~100, du cho MVP)."""
    qs = urllib.parse.urlencode([("fields[]", f) for f in fields])
    return airtable("GET", f"{urllib.parse.quote(table)}?{qs}").get("records", [])


def update_items(records: list[dict]) -> None:
    airtable("PATCH", "Items", {"records": records, "typecast": True})


def append_note(record_id: str, note: str, field: str = "Phân tích AI") -> None:
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    old = rec.get("fields", {}).get(field, "")
    stamp = datetime.now(VN_TZ).strftime("[%d/%m %H:%M]")
    update_project(record_id, {field: f"{old}\n\n{stamp} {note}".strip()})


def log_event(record_id: str, code: str, label: str) -> None:
    """Ghi 1 dong Step Log cho su kien KHONG doi Status (feedback round / plan / brief...).
    Cac lan doi Status da co Automation Airtable lo. Loi KHONG duoc chan nghiep vu."""
    try:
        airtable("POST", STEP_LOG_TABLE, {"records": [{"fields": {
            "Mã log": f"{code} · {label}",
            "Project": [record_id],
            "Bước": label,
            "start": datetime.now(VN_TZ).isoformat(),
            "Mã project (text)": code,
        }}]})
    except Exception as e:  # noqa: BLE001
        log.warning(f"[step-log] không ghi được '{label}' cho {code}: {e}")


def fetch_items_of(record_id: str) -> list[dict]:
    rows = fetch_all("Items", ["Tên item", "Project", "Số lượng",
                               "Đơn giá dự kiến (VND)", "Status"])
    return [r for r in rows if record_id in (r["fields"].get("Project") or [])]
