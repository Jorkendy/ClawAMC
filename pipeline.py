"""Auto-chain tu webhook Airtable: form submit -> phan tich -> proposal -> phieu duyet Zalo."""
import threading

from airtable_client import airtable, fetch_projects
from analysis import analyze_one
from approval import request_approval_for
from config import PROJECTS_TABLE
from proposal import propose_items_for

_ANALYZE_LOCK = threading.Lock()


def analyze_new_async() -> None:
    """Form submit -> phan tich -> (neu du thong tin) propose -> gui phieu duyet Zalo."""
    if not _ANALYZE_LOCK.acquire(blocking=False):
        return  # dang co lan quet khac chay
    try:
        records = fetch_projects("OR({Status} = 'Mới tiếp nhận', {Status} = BLANK())")
        for r in records:
            try:
                result = analyze_one(r)
                print(f"[webhook] analyzed {result['project_code']} -> {result['new_status']}")
                if result["new_status"] == "Chờ duyệt items":
                    rec = airtable("GET", f"{PROJECTS_TABLE}/{r['id']}")
                    prop = propose_items_for(rec)
                    print(f"[webhook] proposed {prop['items_created']} items "
                          f"({prop['total']:,}d / {prop['budget']:,}d, {prop['revisions']} revisions)")
                    rec = airtable("GET", f"{PROJECTS_TABLE}/{r['id']}")
                    appr = request_approval_for(rec)
                    print(f"[webhook] approval sent to {appr.get('sent_to')}")
            except Exception as e:  # noqa: BLE001
                print(f"[webhook] pipeline error: {e}")
    finally:
        _ANALYZE_LOCK.release()
