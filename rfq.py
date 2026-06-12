"""RFQ vendor qua Zalo + diem AI #3 — parse tin nhan bao gia viet tu do."""
from datetime import date, datetime

from airtable_client import append_note, fetch_all, fetch_items_of, update_items, update_project
from llm_client import ask_llm_json
from zalo_client import zalo_send

# RFQ dang cho vendor tra gia: {vendor_chat_id: {record_id, code, items: [...]}}
PENDING_RFQ: dict[str, dict] = {}


def send_rfq_for(record: dict) -> dict:
    fields = record["fields"]
    code = fields.get("Mã project", record["id"])
    vendors = {r["id"]: r["fields"] for r in fetch_all(
        "Vendors", ["Tên vendor", "Zalo ID"])}

    items = fetch_all("Items", ["Tên item", "Project", "Loại", "Chất liệu",
                                "Kích thước", "Số lượng", "Status", "Vendor"])
    items = [r for r in items if record["id"] in (r["fields"].get("Project") or [])
             and r["fields"].get("Status") in ("Đề xuất", "Chờ báo giá")]

    by_vendor: dict[str, list] = {}
    skipped = []
    for it in items:
        vids = it["fields"].get("Vendor") or []
        if vids and vendors.get(vids[0], {}).get("Zalo ID"):
            by_vendor.setdefault(vids[0], []).append(it)
        else:
            skipped.append(it["fields"].get("Tên item"))

    sent = []
    for vid, its in by_vendor.items():
        v = vendors[vid]
        chat_id = v["Zalo ID"]
        spec_lines = "\n".join(
            f"• {r['fields'].get('Tên item')}\n"
            f"  Chất liệu: {r['fields'].get('Chất liệu', '?')} | "
            f"Kích thước: {r['fields'].get('Kích thước', '?')} | "
            f"SL: {r['fields'].get('Số lượng', '?')}"
            for r in its)
        text = (
            f"📨 YÊU CẦU BÁO GIÁ [{code}]\n"
            f"Kính gửi {v.get('Tên vendor')},\n"
            f"VNGGames cần báo giá các items sau:\n————————————\n{spec_lines}\n————————————\n"
            f"Deadline cần hàng: {fields.get('Deadline cần hàng', '?')}\n"
            f"Vui lòng báo: đơn giá theo SL, MOQ, thời gian lên mẫu, thời gian sản xuất.\n"
            f"(Reply trực tiếp tin nhắn này — hệ thống tự ghi nhận)"
        )
        zalo_send(chat_id, text)
        entry = PENDING_RFQ.setdefault(chat_id, {
            "record_id": record["id"], "code": code, "items": []})
        entry["items"].extend(
            {"id": r["id"], "ten": r["fields"].get("Tên item"),
             "so_luong": r["fields"].get("Số lượng")} for r in its)
        update_items([{"id": r["id"], "fields": {"Status": "Chờ báo giá"}} for r in its])
        sent.append(v.get("Tên vendor"))

    if sent:
        update_project(record["id"], {"Status": "Chờ vendor báo giá"})
        note = f"[AI {date.today():%d/%m}] Đã gửi RFQ qua Zalo cho: {', '.join(sent)}."
        if skipped:
            note += f" Bỏ qua (chưa có vendor/Zalo): {', '.join(skipped)}."
        append_note(record["id"], note)
    return {"status": "success", "project_code": code,
            "rfq_sent_to": sent, "skipped": skipped}


RFQ_PARSE_PROMPT = """Bạn là trợ lý mua hàng. Vendor vừa reply báo giá qua Zalo. Phân tích và trả về DUY NHẤT một JSON object.

ITEMS ĐANG CHỜ BÁO GIÁ (id | tên | số lượng):
{items}

TIN NHẮN CỦA VENDOR:
{message}

YÊU CẦU:
- Khớp từng báo giá trong tin nhắn với item theo tên (khớp gần đúng). Item vendor không nhắc tới → bỏ qua.
- "don_gia" là VND/cái (vendor viết "115k" = 115000, "1tr2" = 1200000).
- "tu_choi": true CHỈ KHI vendor nói rõ không làm được / không kịp deadline. Nếu tin nhắn báo giá toàn items KHÔNG có trong danh sách (vendor có thể nhầm đơn khác) → "tu_choi": false, "items": [] và ghi chú "báo giá không khớp items đang chờ".
- "ghi_chu": tóm tắt các điều kiện khác vendor nêu (phí khuôn, cọc, điều kiện thanh toán...).

JSON schema: {{"tu_choi": bool, "items": [{{"id": str, "don_gia": int|null, "moq": int|null, "lead_time_mau": str|null, "lead_time_sx": str|null}}], "ghi_chu": str}}"""


def handle_vendor_reply(chat_id: str, msg: dict) -> None:
    pend = PENDING_RFQ[chat_id]
    text = (msg.get("text") or "").strip()
    items_desc = "\n".join(f"- {i['id']} | {i['ten']} | SL {i['so_luong']}"
                           for i in pend["items"])
    parsed = ask_llm_json(RFQ_PARSE_PROMPT.format(items=items_desc, message=text),
                          max_tokens=1200)

    now = datetime.now().strftime("%d/%m %H:%M")
    sender = (msg.get("from") or {}).get("display_name", "vendor")
    if parsed.get("tu_choi"):
        append_note(pend["record_id"],
                    f"[VENDOR {now}] ⚠️ Vendor TỪ CHỐI/không kịp ({sender}): {parsed.get('ghi_chu', '')}")
        zalo_send(chat_id, f"Đã ghi nhận phản hồi cho [{pend['code']}]. "
                           f"Merch PIC sẽ liên hệ lại phương án thay thế.")
        del PENDING_RFQ[chat_id]
        return

    # Bao gia khong khop item nao -> hoi lai vendor, GIU phien cho (khong dong)
    if not parsed.get("items"):
        ten_items = ", ".join(i["ten"] for i in pend["items"])
        zalo_send(chat_id,
                  f"⚠️ Báo giá có vẻ chưa khớp items đang chờ của [{pend['code']}]: {ten_items}.\n"
                  f"Anh/chị kiểm tra lại giúp và báo giá theo đúng các items trên nhé.")
        return

    updates, quoted = [], []
    valid_ids = {i["id"] for i in pend["items"]}
    for q in parsed.get("items", []):
        if q.get("id") not in valid_ids or not q.get("don_gia"):
            continue
        note = (f"[Báo giá vendor {now}] {q['don_gia']:,}đ/c"
                + (f" | MOQ {q['moq']}" if q.get("moq") else "")
                + (f" | mẫu {q['lead_time_mau']}" if q.get("lead_time_mau") else "")
                + (f" | sx {q['lead_time_sx']}" if q.get("lead_time_sx") else ""))
        updates.append({"id": q["id"], "fields": {
            "Đơn giá dự kiến (VND)": q["don_gia"],
            "Status": "Đã có báo giá",
            "Ghi chú AI": note,
        }})
        quoted.append(q["id"])
    if updates:
        update_items(updates)

    remaining = [i for i in pend["items"] if i["id"] not in quoted]
    summary = (f"[VENDOR {now}] Nhận báo giá từ {sender}: {len(quoted)}/{len(pend['items'])} items."
               + (f" Ghi chú: {parsed.get('ghi_chu')}" if parsed.get("ghi_chu") else "")
               + (f" Còn chờ: {', '.join(i['ten'] for i in remaining)}" if remaining else ""))
    append_note(pend["record_id"], summary)
    zalo_send(chat_id, f"✅ Đã ghi nhận báo giá [{pend['code']}] — {len(quoted)} items "
                       f"cập nhật vào hệ thống. Cảm ơn {sender}!")
    if remaining:
        pend["items"] = remaining
    else:
        del PENDING_RFQ[chat_id]

    # Du bao gia TOAN PROJECT (moi vendor co the tra loi luc khac nhau) -> chuyen status
    all_items = fetch_items_of(pend["record_id"])
    waiting = [r for r in all_items
               if r["fields"].get("Status") in ("Đề xuất", "Chờ báo giá")]
    if not waiting:
        update_project(pend["record_id"], {"Status": "Chờ duyệt mẫu"})
        append_note(pend["record_id"],
                    f"[AI {now}] ✅ Đủ báo giá toàn bộ items — Status → Chờ duyệt mẫu. "
                    f"Bước tiếp: chốt vendor, yêu cầu lên mẫu.")
        pic_zalo = next((u["fields"].get("Zalo ID") for u in fetch_all("Users", ["Vai trò", "Zalo ID"])
                         if u["fields"].get("Vai trò") == "Merch PIC"), None)
        if pic_zalo:
            zalo_send(pic_zalo, f"📊 [{pend['code']}] đã đủ báo giá toàn bộ items. "
                                f"Status → Chờ duyệt mẫu. Vào Airtable chốt vendor và yêu cầu lên mẫu nhé.")
