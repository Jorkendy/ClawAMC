#!/usr/bin/env python3
"""Test go/no-go Zalo Bot Platform cho flow approval merch.

3 cau hoi can tra loi:
  1. Gui duoc message 1-1 khong?          -> sendMessage
  2. Gui duoc message co nut bam khong?    -> thu 2 kieu payload (Telegram-style / Messenger-style)
  3. Bam nut co tra callback + user_id?    -> poll getUpdates, in raw event

Cach dung:
  1. Tao bot tai https://bot.zaloplatforms.com (dang nhap bang Zalo cua ban)
  2. Lay BOT_TOKEN (dang 123456:abc...)
  3. Mo Zalo, tim bot vua tao, nhan cho no 1 tin bat ky (de bot biet chat_id)
  4. Chay:  python3 test_zalo_bot.py <BOT_TOKEN>
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://bot-api.zapps.me/bot{token}/{method}"


def call(token: str, method: str, payload: dict | None = None) -> dict:
    url = BASE.format(token=token, method=method)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode(errors="replace")}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def pretty(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def extract_updates(res: dict) -> list[dict]:
    """result co the la list (kieu Telegram) hoac dict (schema rieng cua Zalo)."""
    result = res.get("result")
    if isinstance(result, list):
        return [u for u in result if isinstance(u, dict)]
    if isinstance(result, dict):
        # co the la 1 update don le, hoac dict boc list ben trong
        for key in ("updates", "messages", "events"):
            inner = result.get(key)
            if isinstance(inner, list):
                return [u for u in inner if isinstance(u, dict)]
        return [result]
    return []


def next_offset(update: dict, current):
    for key in ("update_id", "event_id", "id"):
        val = update.get(key)
        if isinstance(val, int):
            return val + 1
    return current


def find_chat_id(update: dict):
    """Thu moi duong co the chua chat/user id trong update (schema chua ro)."""
    candidates = [update]
    for key in ("message", "event_data", "result"):
        if isinstance(update.get(key), dict):
            candidates.append(update[key])
    for msg in candidates:
        for path in (
            ("chat", "id"),
            ("from", "id"),
            ("sender", "id"),
            ("user_id",),
            ("chat_id",),
        ):
            node = msg
            for key in path:
                node = node.get(key) if isinstance(node, dict) else None
                if node is None:
                    break
            if node is not None:
                return node
    return None


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    token = sys.argv[1]
    results: dict[str, str] = {}

    print("=== B0. getMe (kiem tra token) ===")
    res = call(token, "getMe")
    print(pretty(res))
    results["token hop le"] = "PASS" if res.get("ok") else "FAIL"

    print("\n=== B1. getUpdates — can ban da nhan tin cho bot truoc ===")
    chat_id = None
    offset = None
    for attempt in range(12):  # ~60s
        payload = {"timeout": 5}
        if offset is not None:
            payload["offset"] = offset
        res = call(token, "getUpdates", payload)
        updates = extract_updates(res)
        if updates:
            print("-- raw response getUpdates:")
            print(pretty(res))
        for u in updates:
            offset = next_offset(u, offset)
            cid = find_chat_id(u)
            if cid is not None:
                chat_id = cid
        if chat_id is not None:
            break
        print(f"  ... chua thay tin nhan nao (lan {attempt + 1}/12). "
              "Mo Zalo va nhan tin cho bot ngay nhe.")
        time.sleep(5)
    results["nhan duoc update + chat_id"] = "PASS" if chat_id else "FAIL"
    if chat_id is None:
        print("\nKhong lay duoc chat_id — dung tai day. Kiem tra: da nhan tin cho bot chua?")
        print_summary(results)
        return
    print(f"\n>>> chat_id = {chat_id}")

    print("\n=== B2. sendMessage text 1-1 ===")
    res = call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "[TEST B2] Bot merch day. Neu ban thay tin nay la sendMessage OK.",
    })
    print(pretty(res))
    results["gui text 1-1"] = "PASS" if res.get("ok") else "FAIL"

    print("\n=== B3a. Button kieu Telegram (reply_markup/inline_keyboard) ===")
    res_a = call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "[TEST B3a] Phieu duyet MERCH-001 — bam thu 1 nut:",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": "approve:MERCH-001"},
                {"text": "❌ Reject", "callback_data": "reject:MERCH-001"},
            ]]
        },
    })
    print(pretty(res_a))

    print("\n=== B3b. Button kieu Messenger (template/postback) ===")
    res_b = call(token, "sendTemplate", {
        "chat_id": chat_id,
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": "[TEST B3b] Phieu duyet MERCH-001 — bam thu 1 nut:",
                "buttons": [
                    {"type": "postback", "title": "✅ Approve", "payload": "approve:MERCH-001"},
                    {"type": "postback", "title": "❌ Reject", "payload": "reject:MERCH-001"},
                ],
            },
        },
    })
    print(pretty(res_b))
    button_sent = res_a.get("ok") or res_b.get("ok")
    results["gui duoc message co nut"] = "PASS" if button_sent else "FAIL"

    print("\n=== B4. Cho callback — BAM NUT tren dien thoai trong 90s ===")
    print("(moi event nhan duoc se in raw de xem schema + user_id)")
    saw_callback = False
    deadline = time.time() + 90
    while time.time() < deadline:
        payload = {"timeout": 5}
        if offset is not None:
            payload["offset"] = offset
        res = call(token, "getUpdates", payload)
        updates = extract_updates(res)
        if updates:
            print("-- raw response getUpdates:")
            print(pretty(res))
        for u in updates:
            offset = next_offset(u, offset)
            raw = json.dumps(u)
            if "approve:MERCH-001" in raw or "reject:MERCH-001" in raw \
                    or "callback" in raw or "postback" in raw:
                saw_callback = True
        if saw_callback:
            break
        time.sleep(3)
    results["callback mang payload + user_id"] = "PASS" if saw_callback else "FAIL"

    print_summary(results)


def print_summary(results: dict[str, str]) -> None:
    print("\n" + "=" * 46)
    print("KET QUA GO/NO-GO ZALO BOT:")
    for name, status in results.items():
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {name}: {status}")
    print("=" * 46)
    print("PASS het B2-B4  -> GO: demo approval bang Zalo.")
    print("Fail B3/B4      -> NO-GO button: fallback Telegram hoac Airtable Interface.")


if __name__ == "__main__":
    main()
