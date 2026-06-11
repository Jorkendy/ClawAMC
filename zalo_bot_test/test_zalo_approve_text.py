#!/usr/bin/env python3
"""Test flow approval bang REPLY LENH tren Zalo Bot (thay cho button).

Flow:
  1. Bot gui "phieu duyet" MERCH-001 vao chat 1-1: reply 1 = duyet, 2 = tu choi
  2. Ban reply "1" hoac "2" tren dien thoai
  3. Script doc from.id tu event, so voi APPROVER_ID, gui xac nhan lai

Cach dung:
  python3 test_zalo_approve_text.py <BOT_TOKEN> <CHAT_ID>
  (CHAT_ID lay tu lan test truoc, vd: 74d10c9bebd802865bc9)

Test "sai nguoi duyet": doi APPROVER_ID ben duoi thanh id khac roi chay lai.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://bot-api.zapps.me/bot{token}/{method}"

# Doi gia tri nay de gia lap dung/sai nguoi duyet
APPROVER_ID = None  # None = lay chinh chat_id lam approver (happy path)


def call(token, method, payload=None):
    url = BASE.format(token=token, method=method)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
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


def extract_message(res):
    """Tra ve dict message tu response getUpdates (schema Zalo: result.message)."""
    result = res.get("result")
    if isinstance(result, dict) and isinstance(result.get("message"), dict):
        return result["message"]
    if isinstance(result, list):
        for u in result:
            if isinstance(u, dict) and isinstance(u.get("message"), dict):
                return u["message"]
    return None


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    token, chat_id = sys.argv[1], sys.argv[2]
    approver_id = APPROVER_ID or chat_id

    print("=== Gui phieu duyet ===")
    res = call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": (
            "📋 PHIẾU DUYỆT [MERCH-001]\n"
            "Project Merch Tết Võ Lâm Chi Mộng 2027\n"
            "5 items — tổng dự kiến 245.000.000₫\n"
            "————————————\n"
            "Reply 1 ✅ Duyệt\n"
            "Reply 2 ❌ Từ chối"
        ),
    })
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok"):
        print("Gui phieu that bai — dung.")
        return

    print("\n=== Cho reply trong 180s — long-poll lien tuc, KHONG co khe ngu ===")
    print("(quan trong: dam bao khong co script nao khac dang goi getUpdates cung luc)")
    sent_at = time.time()
    deadline = sent_at + 180
    while time.time() < deadline:
        res = call(token, "getUpdates", {"timeout": 25})
        if res.get("result"):
            print("-- raw response:")
            print(json.dumps(res, ensure_ascii=False, indent=2))
        msg = extract_message(res)
        if msg:
            text = (msg.get("text") or "").strip()
            sender = msg.get("from") or {}
            sender_id = sender.get("id")
            sender_name = sender.get("display_name", "?")
            if text not in ("1", "2"):
                print(f"  (bo qua text khong phai 1/2: {text!r})")
                continue
            print("\n-- reply nhan duoc:")
            print(json.dumps(msg, ensure_ascii=False, indent=2))

            decision = "APPROVED ✅" if text == "1" else "REJECTED ❌"
            if sender_id == approver_id:
                reply = (
                    f"Đã ghi nhận: {decision}\n"
                    f"Người duyệt: {sender_name} ({sender_id})\n"
                    f"→ Airtable MERCH-001 sẽ chuyển status tương ứng."
                )
                verdict = "PASS — danh tinh khop approver, flow approval hoat dong"
            else:
                reply = (
                    f"⛔ Bạn không phải người duyệt của MERCH-001.\n"
                    f"Người duyệt được chỉ định: {approver_id}"
                )
                verdict = "PASS — chan dung nguoi sai (authorization hoat dong)"
            call(token, "sendMessage", {"chat_id": chat_id, "text": reply})
            print(f"\nKET QUA: {verdict}")
            return
    print("\nKET QUA: FAIL — khong nhan duoc reply trong 180s")


if __name__ == "__main__":
    main()
