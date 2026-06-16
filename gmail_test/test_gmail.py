"""Go/no-go test Gmail (SMTP gui + IMAP doc) cho merch agent.

Chuan bi:
  1. Tao Gmail rieng cho bot (vd merch.agent.demo@gmail.com)
  2. Bat 2-Step Verification: https://myaccount.google.com/security
  3. Tao App Password: https://myaccount.google.com/apppasswords
  4. Them vao ClawAMC/.env:
       GMAIL_USER=merch.agent.demo@gmail.com
       GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx   (16 ky tu, bo khoang trang)
  5. Chay tu ClawAMC:  ./venv/bin/python gmail_test/test_gmail.py

Cac buoc test:
  B1  SMTP login + tu gui 1 mail [MERCH-TEST-xxx] cho chinh minh
  B2  IMAP login + poll inbox tim dung mail do, doc body (chieu agent doc mail)
  B3  (tuy chon) doi mail tu account khac (dong vai vendor reply) — Enter de bo qua
"""
import email
import imaplib
import os
import smtplib
import sys
import time
from email.header import decode_header
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

USER = os.environ.get("GMAIL_USER", "")
PASS = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")

if not USER or not PASS:
    sys.exit("FAIL: thieu GMAIL_USER / GMAIL_APP_PASSWORD trong ClawAMC/.env")

TAG = f"[MERCH-TEST-{int(time.time())}]"


def decode_subject(raw) -> str:
    parts = decode_header(raw or "")
    return "".join(p.decode(enc or "utf-8") if isinstance(p, bytes) else p
                   for p, enc in parts)


def body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
        return "(khong co phan text/plain)"
    return msg.get_payload(decode=True).decode(
        msg.get_content_charset() or "utf-8", errors="replace")


def poll_inbox(subject_contains: str, timeout_s: int, only_unseen: bool = True):
    """Poll IMAP moi 5s, tra ve (from, subject, body) cua mail khop dau tien."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(USER, PASS)
        imap.select("INBOX")
        criteria = "(UNSEEN)" if only_unseen else "ALL"
        _, data = imap.search(None, criteria)
        for num in (data[0].split() if data and data[0] else []):
            _, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            subject = decode_subject(msg.get("Subject"))
            if subject_contains in subject:
                imap.logout()
                return msg.get("From", "?"), subject, body_text(msg).strip()
        imap.logout()
        print(f"  ... chua thay, poll lai sau 5s (con {int(deadline - time.time())}s)")
        time.sleep(5)
    return None


# --- B1: SMTP gui ---
print(f"B1) SMTP gui mail {TAG} tu {USER} -> {USER} ...")
mail = MIMEText(f"Mail test tu merch agent.\nTag: {TAG}\n\n"
                f"Vendor co the bao gia bang cach reply mail nay.", _charset="utf-8")
mail["Subject"] = f"{TAG} Test gui mail merch agent"
mail["From"] = USER
mail["To"] = USER
try:
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(USER, PASS)
        smtp.send_message(mail)
    print("B1) PASS — SMTP login + gui OK")
except Exception as e:  # noqa: BLE001
    sys.exit(f"B1) FAIL — {e}\n"
             "    Kiem tra: app password dung chua? 2-Step Verification da bat chua?")

# --- B2: IMAP doc lai dung mail vua gui ---
print(f"B2) IMAP poll inbox tim {TAG} (toi da 60s) ...")
found = poll_inbox(TAG, timeout_s=60)
if not found:
    sys.exit("B2) FAIL — khong thay mail tu gui trong 60s (kiem tra tab Spam/Categories)")
frm, subject, body = found
print(f"B2) PASS — doc duoc mail: from={frm}\n    subject={subject}\n    body={body[:120]!r}")

# --- B3 (tuy chon): chieu vendor -> agent ---
print(f"\nB3) TUY CHON — tu account KHAC, gui mail toi {USER}")
print(f"    voi subject chua tag: {TAG}")
print("    (gia lap vendor reply bao gia, vd body: 'ao thun 115k/cai, giao 1 tuan')")
try:
    input("    Nhan Enter SAU KHI da gui (hoac Ctrl+C de bo qua B3)... ")
except KeyboardInterrupt:
    print("\nB3) SKIP. Tong ket: B1 PASS, B2 PASS — Gmail go/no-go: GO ✅")
    sys.exit(0)

print("B3) Poll inbox cho mail vendor (toi da 120s) ...")
found = poll_inbox(TAG, timeout_s=120)
if not found:
    sys.exit("B3) FAIL — khong nhan duoc mail vendor trong 120s")
frm, subject, body = found
print(f"B3) PASS — nhan mail vendor: from={frm}\n    body={body[:200]!r}")
print(f"\nTong ket: B1 + B2 + B3 PASS — Gmail go/no-go: GO ✅")
print("Buoc tiep: ghep vao agent (gmail_client.py adapter + poller thread 30-60s,")
print("match ma [MERCH-xxx] trong subject -> parse bang LLM nhu handle_vendor_reply).")
