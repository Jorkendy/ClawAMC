"""Merch Agent — phan tich de bai merchandise VNGGames.

Agent chay tren GreenNode AgentBase (Custom framework):
- HTTP server: GreenNodeAgentBaseApp (POST /invocations, GET /health)
- LLM: GreenNode AI Platform (OpenAI-compatible), model qwen/qwen3-5-27b
- Data: Airtable base "Merch Automation MVP"

Actions (payload JSON cua POST /invocations):
  {"action": "analyze_project", "project_code": "MERCH-001"}
  {"action": "analyze_new"}   # quet tat ca record status "Moi tiep nhan"

To chuc module:
  config.py          env vars + hang so nghiep vu
  airtable_client.py Airtable REST helpers
  llm_client.py      GreenNode LLM + ask_llm_json
  analysis.py        AI #1: phan tich de bai
  proposal.py        AI #2: proposal items + bao gia du kien
  zalo_client.py     Zalo Bot API transport
  approval.py        phieu duyet Zalo (PENDING_APPROVALS)
  rfq.py             RFQ vendor + AI #3: parse bao gia (PENDING_RFQ)
  zalo_router.py     poller + routing tin nhan Zalo
  reminders.py       nhac qua han + escalate
  pipeline.py        auto-chain tu webhook Airtable
"""
import threading

from greennode_agentbase import GreenNodeAgentBaseApp, PingStatus, RequestContext

from airtable_client import fetch_projects
from analysis import analyze_one
from approval import request_approval_for
from config import ZALO_TOKEN
from pipeline import analyze_new_async
from proposal import propose_items_for
from reminders import check_reminders, reminder_scheduler
from rfq import send_rfq_for
from zalo_router import zalo_poller

app = GreenNodeAgentBaseApp()


# --- Entrypoint ---
@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    # Airtable webhook ping (khong co "action", co "webhook"/"base") -> xu ly nen, tra 200 ngay
    if "webhook" in payload and "base" in payload:
        threading.Thread(target=analyze_new_async, daemon=True).start()
        return {"status": "accepted", "trigger": "airtable_webhook"}

    action = payload.get("action", "analyze_new")

    if action == "analyze_project":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return {"status": "success", "results": [analyze_one(records[0])]}

    if action == "analyze_new":
        records = fetch_projects("OR({Status} = 'Mới tiếp nhận', {Status} = BLANK())")
        results = [analyze_one(r) for r in records]
        return {"status": "success", "count": len(results), "results": results}

    if action == "propose_items":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return {"status": "success", "results": [propose_items_for(records[0])]}

    if action == "check_reminders":
        return check_reminders()

    if action == "send_rfq":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return send_rfq_for(records[0])

    if action == "request_approval":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return request_approval_for(records[0])

    return {"status": "error", "message": f"Unknown action: {action}"}


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    if ZALO_TOKEN:
        threading.Thread(target=zalo_poller, daemon=True).start()
        threading.Thread(target=reminder_scheduler, daemon=True).start()
    else:
        print("[zalo] ZALO_BOT_TOKEN chua co trong .env — approval flow tat")
    app.run(port=8080, host="0.0.0.0")
