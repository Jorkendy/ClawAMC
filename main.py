"""Merch Agent — HTTP server (FastAPI), self-host (Coolify/VPS).

Endpoints:
  POST /invocations  — Airtable webhook (payload co "webhook"+"base") hoac action thu cong
  GET  /health       — healthcheck (200)

Actions (JSON body cua POST /invocations):
  {"action": "analyze_new"}                                  quet record moi -> phan tich
  {"action": "analyze_project", "project_code": "MERCH-001"} phan tich 1 project
  {"action": "propose_items", "project_code": "..."}         sinh proposal items
  {"action": "send_proposal", "project_code": "..."}         propose + render + upload + Cho duyet
  {"action": "handle_proposal_decisions"}                    xu ly requester duyet/sua

Module:
  config.py          env + hang so nghiep vu
  airtable_client.py Airtable REST helpers
  llm_client.py      LiteLLM (OpenAI-compatible) + ask_llm_json
  analysis.py        AI #1: phan tich de bai
  proposal.py        AI #2: proposal tu Catalogue
  proposal_render.py render HTML + upload Airtable
  pipeline.py        auto-chain tu webhook Airtable
"""
import threading

from fastapi import FastAPI, Request

from airtable_client import fetch_projects
from analysis import analyze_one
from pipeline import first_send, handle_proposal_decisions, on_webhook
from proposal import propose_items_for

app = FastAPI(title="Merch Agent")


def handle(payload: dict) -> dict:
    # Airtable webhook ping (co "webhook"+"base", khong co "action") -> xu ly nen, tra 200 ngay
    if "webhook" in payload and "base" in payload:
        threading.Thread(target=on_webhook, daemon=True).start()
        return {"status": "accepted", "trigger": "airtable_webhook"}

    action = payload.get("action", "analyze_new")

    if action == "analyze_new":
        records = fetch_projects("OR({Status} = 'Mới tiếp nhận', {Status} = BLANK())")
        return {"status": "success", "count": len(records),
                "results": [analyze_one(r) for r in records]}

    if action == "analyze_project":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return {"status": "success", "results": [analyze_one(records[0])]}

    if action == "propose_items":
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        return {"status": "success", "results": [propose_items_for(records[0])]}

    if action == "send_proposal":  # propose + render HTML + upload + Status "Cho duyet items"
        code = payload.get("project_code", "")
        records = fetch_projects(f"{{Mã project}} = '{code}'")
        if not records:
            return {"status": "error", "message": f"Khong tim thay project {code}"}
        first_send(records[0]["id"])
        return {"status": "success", "project_code": code}

    if action == "handle_proposal_decisions":  # quet "Gui phan hoi" -> chot / sua
        handle_proposal_decisions()
        return {"status": "success"}

    return {"status": "error", "message": f"Unknown action: {action}"}


@app.post("/invocations")
async def invocations(request: Request) -> dict:
    payload = await request.json()
    return handle(payload)


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
