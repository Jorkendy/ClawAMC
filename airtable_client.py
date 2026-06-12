"""Airtable REST helpers — moi truy cap data deu di qua day."""
import json
import urllib.parse
import urllib.request

from config import AIRTABLE_BASE_ID, AIRTABLE_TOKEN, PROJECTS_TABLE


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


def append_note(record_id: str, note: str) -> None:
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    old = rec.get("fields", {}).get("Phân tích AI", "")
    update_project(record_id, {"Phân tích AI": f"{old}\n\n{note}".strip()})


def users_map() -> dict:
    rows = fetch_all("Users", ["Tên", "Zalo ID", "Vai trò"])
    return {r["id"]: {"name": r["fields"].get("Tên", "?"),
                      "zalo": r["fields"].get("Zalo ID", "")} for r in rows}


def fetch_items_of(record_id: str) -> list[dict]:
    rows = fetch_all("Items", ["Tên item", "Project", "Số lượng",
                               "Đơn giá dự kiến (VND)", "Status"])
    return [r for r in rows if record_id in (r["fields"].get("Project") or [])]
