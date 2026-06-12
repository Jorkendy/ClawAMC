"""Phieu duyet items qua Zalo (reply 1/2) — approval matrix nam trong bang Users."""
from datetime import date

from airtable_client import append_note, fetch_all, fetch_items_of, update_project, users_map
from zalo_client import zalo_send

# Phieu duyet dang cho: {approver_zalo_id: {record_id, code, approver_name}}
# Luu y MVP: in-memory, mat khi restart — production se chuyen sang bang Airtable rieng
PENDING_APPROVALS: dict[str, dict] = {}


def request_approval_for(record: dict) -> dict:
    fields = record["fields"]
    code = fields.get("Mã project", record["id"])
    approver_ids = fields.get("Approver") or []
    if not approver_ids:
        # Fallback: form khong chon Approver -> lay quan ly truc tiep cua Requester
        users = fetch_all("Users", ["Tên", "Zalo ID", "Quản lý trực tiếp", "Vai trò"])
        by_id = {r["id"]: r["fields"] for r in users}
        by_name = {r["fields"].get("Tên"): r["id"] for r in users}
        req_ids = fields.get("Requester") or []
        mgr_name = by_id.get(req_ids[0], {}).get("Quản lý trực tiếp", "") if req_ids else ""
        if mgr_name and by_name.get(mgr_name):
            approver_ids = [by_name[mgr_name]]
            reason = f"tự gán {mgr_name} (quản lý của requester) theo approval matrix"
        else:
            pic = next((r for r in users if r["fields"].get("Vai trò") == "Merch PIC"), None)
            if not pic:
                append_note(record["id"], f"[AI {date.today():%d/%m}] ⚠️ KHÔNG gửi được phiếu duyệt: "
                                          f"thiếu Approver/Requester và không có Merch PIC trong Users.")
                return {"status": "error", "message": f"{code} chua co Approver"}
            approver_ids = [pic["id"]]
            reason = f"form không có Requester/Approver — phiếu chuyển về Merch PIC ({pic['fields'].get('Tên')}) triage"
        update_project(record["id"], {"Approver": approver_ids})
        append_note(record["id"], f"[AI {date.today():%d/%m}] {reason}.")
    approver = users_map().get(approver_ids[0], {})
    if not approver.get("zalo"):
        return {"status": "error", "message": f"Approver {approver.get('name')} chua co Zalo ID"}

    items = [r for r in fetch_items_of(record["id"])
             if r["fields"].get("Status") == "Đề xuất"]
    total = sum((r["fields"].get("Đơn giá dự kiến (VND)") or 0)
                * (r["fields"].get("Số lượng") or 0) for r in items)
    item_lines = "\n".join(
        f"• {r['fields'].get('Tên item')} — SL {r['fields'].get('Số lượng')}"
        + (f" × {r['fields'].get('Đơn giá dự kiến (VND)'):,}đ"
           if r['fields'].get('Đơn giá dự kiến (VND)') else " (chờ vendor báo giá)")
        for r in items)

    text = (
        f"📋 PHIẾU DUYỆT ITEMS [{code}]\n"
        f"{fields.get('Tên project', '')}\n"
        f"————————————\n{item_lines}\n————————————\n"
        f"Tổng dự kiến: {total:,}đ / Budget: {fields.get('Budget (VND)', 0):,}đ\n\n"
        f"Reply 1 ✅ Duyệt | Reply 2 ❌ Từ chối"
    )
    zalo_send(approver["zalo"], text)
    PENDING_APPROVALS[approver["zalo"]] = {
        "record_id": record["id"], "code": code, "approver_name": approver["name"],
    }
    return {"status": "success", "project_code": code,
            "sent_to": approver["name"], "items": len(items), "total": total}
