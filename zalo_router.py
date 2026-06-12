"""Poller + routing tin nhan Zalo: phieu duyet (reply 1/2) uu tien, con lai la vendor tra gia."""
import time
from datetime import datetime

from airtable_client import airtable, append_note, update_project
from approval import PENDING_APPROVALS
from config import PROJECTS_TABLE
from rfq import PENDING_RFQ, handle_vendor_reply, send_rfq_for
from zalo_client import zalo_call, zalo_send


def handle_zalo_message(msg: dict) -> None:
    chat_id = (msg.get("chat") or {}).get("id", "")
    sender = msg.get("from") or {}
    text = (msg.get("text") or "").strip()

    # Routing: phieu duyet (reply 1/2) uu tien; con lai la vendor tra gia neu co RFQ cho
    pend = PENDING_APPROVALS.get(chat_id)
    if pend and text in ("1", "2"):
        now = datetime.now().strftime("%d/%m %H:%M")
        who = f"{sender.get('display_name', '?')} ({sender.get('id', '?')})"
        if text == "1":
            update_project(pend["record_id"], {"Status": "Đã duyệt items"})
            append_note(pend["record_id"], f"[APPROVAL {now}] ✅ DUYỆT bởi {who} qua Zalo.")
            zalo_send(chat_id, f"✅ Đã ghi nhận DUYỆT [{pend['code']}] — {who}, {now}.\n"
                               f"Status → Đã duyệt items. Đang gửi RFQ cho vendor...")
            del PENDING_APPROVALS[chat_id]
            # Auto-chain: duyet xong -> gui RFQ vendor ngay
            try:
                rec = airtable("GET", f"{PROJECTS_TABLE}/{pend['record_id']}")
                result = send_rfq_for(rec)
                if result.get("rfq_sent_to"):
                    zalo_send(chat_id, f"📨 Đã gửi RFQ [{pend['code']}] cho vendor: "
                                       f"{', '.join(result['rfq_sent_to'])}.")
            except Exception as e:  # noqa: BLE001
                print(f"[zalo] auto-RFQ error: {e}")
        else:
            append_note(pend["record_id"], f"[APPROVAL {now}] ❌ TỪ CHỐI bởi {who} qua Zalo — cần làm lại proposal.")
            zalo_send(chat_id, f"❌ Đã ghi nhận TỪ CHỐI [{pend['code']}] — {who}, {now}.\n"
                               f"Merch PIC sẽ điều chỉnh proposal và gửi lại.")
            del PENDING_APPROVALS[chat_id]
        return

    if chat_id in PENDING_RFQ:
        handle_vendor_reply(chat_id, msg)
        return

    if pend:
        zalo_send(chat_id, f"Phiếu [{pend['code']}] đang chờ — reply 1 để duyệt, 2 để từ chối.")


def zalo_poller() -> None:
    """Consumer DUY NHAT cua getUpdates (consume-on-read) — khong duoc chay script khac song song."""
    print("[zalo] poller started")
    while True:
        try:
            res = zalo_call("getUpdates", {"timeout": 25})
            result = res.get("result")
            msg = result.get("message") if isinstance(result, dict) else None
            if isinstance(msg, dict):
                handle_zalo_message(msg)
        except Exception as e:  # noqa: BLE001
            print(f"[zalo] poller error: {e}")
            time.sleep(5)
