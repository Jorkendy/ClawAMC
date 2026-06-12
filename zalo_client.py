"""Zalo Bot API transport thuan — gui/nhan qua bot-api.zapps.me."""
import json
import urllib.request

from config import ZALO_BASE, ZALO_TOKEN


def zalo_call(method: str, payload: dict | None = None) -> dict:
    url = ZALO_BASE.format(token=ZALO_TOKEN, method=method)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode())


def zalo_send(chat_id: str, text: str) -> None:
    zalo_call("sendMessage", {"chat_id": chat_id, "text": text})
