"""Nhac qua han duyet + escalate len quan ly (thread 6h/lan)."""
import time
from datetime import date, datetime

from airtable_client import append_note, fetch_all, update_project
from zalo_client import zalo_send


def check_reminders() -> dict:
    """Quet project qua han duyet -> nhac approver, qua 3 ngay -> escalate manager."""
    today = date.today()
    users = fetch_all("Users", ["Tên", "Zalo ID", "Quản lý trực tiếp"])
    by_id = {r["id"]: r["fields"] for r in users}
    by_name = {r["fields"].get("Tên"): r["fields"] for r in users}

    projs = fetch_all("Projects", ["Mã project", "Tên project", "Status",
                                   "Deadline phê duyệt", "Approver"])
    reminded, escalated = [], []
    for p in projs:
        f = p["fields"]
        if f.get("Status") not in ("Chờ duyệt items", "Quá hạn duyệt"):
            continue
        if not f.get("Deadline phê duyệt"):
            continue
        overdue = (today - datetime.strptime(f["Deadline phê duyệt"], "%Y-%m-%d").date()).days
        if overdue <= 0:
            continue

        code = f.get("Mã project", "?")
        approver = by_id.get((f.get("Approver") or [None])[0], {})
        if f.get("Status") != "Quá hạn duyệt":
            update_project(p["id"], {"Status": "Quá hạn duyệt"})
        if approver.get("Zalo ID"):
            zalo_send(approver["Zalo ID"],
                      f"⏰ NHẮC DUYỆT [{code}] {f.get('Tên project', '')}\n"
                      f"Phiếu duyệt items đã quá hạn {overdue} ngày "
                      f"(deadline {f['Deadline phê duyệt']}). Vui lòng xử lý sớm.")
            reminded.append(code)
        if overdue >= 3:
            mgr = by_name.get(approver.get("Quản lý trực tiếp", ""), {})
            if mgr.get("Zalo ID"):
                zalo_send(mgr["Zalo ID"],
                          f"🚨 ESCALATION [{code}] {f.get('Tên project', '')}\n"
                          f"Phiếu duyệt quá hạn {overdue} ngày, approver "
                          f"{approver.get('Tên', '?')} chưa phản hồi sau nhiều lần nhắc. "
                          f"Kính chuyển anh/chị xử lý.")
                escalated.append(code)
        append_note(p["id"], f"[REMINDER {today:%d/%m}] Nhắc duyệt lần nữa (quá hạn {overdue} ngày)"
                             + (" + escalate lên quản lý." if overdue >= 3 else "."))
    return {"status": "success", "reminded": reminded, "escalated": escalated}


def reminder_scheduler() -> None:
    while True:
        time.sleep(6 * 3600)
        try:
            check_reminders()
        except Exception as e:  # noqa: BLE001
            print(f"[reminder] error: {e}")
