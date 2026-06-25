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
import os
import threading
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse

from airtable_client import airtable, fetch_projects
from config import FILLOUT_FORM_URL, PROJECTS_TABLE
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


_FLOWCHART = os.path.join(os.path.dirname(__file__), "docs", "flowchart.html")


@app.get("/flowchart")
def flowchart() -> FileResponse:
    """So do logic Merch Agent (demo cho stakeholder) — update file docs/flowchart.html roi redeploy."""
    return FileResponse(_FLOWCHART, media_type="text/html")


_RULES = os.path.join(os.path.dirname(__file__), "docs", "proposal-rules.html")


@app.get("/rules")
def rules() -> FileResponse:
    """Quy tac ra proposal (deadline + item/creative) — tham chieu giai trinh cho stakeholder."""
    return FileResponse(_RULES, media_type="text/html")


_EMAIL_GUIDE = os.path.join(os.path.dirname(__file__), "docs", "email-guide.html")


@app.get("/email-guide")
def email_guide() -> FileResponse:
    """Huong dan Email Templates (PO sua noi dung + admin setup automation)."""
    return FileResponse(_EMAIL_GUIDE, media_type="text/html")


def _feedback_button(record_id: str) -> str:
    """Nut noi (link sang form Fillout phan hoi, kem ?id=) — chi hien neu da set FILLOUT_FORM_URL."""
    if not FILLOUT_FORM_URL:
        return ""
    href = f"{FILLOUT_FORM_URL}?id={record_id}"
    return (f'<a href="{href}" style="position:fixed;bottom:24px;right:24px;z-index:9999;'
            'background:#ff3d57;color:#fff;padding:14px 26px;border-radius:30px;'
            "font:600 15px -apple-system,'Segoe UI',Roboto,Arial;text-decoration:none;"
            'box-shadow:0 4px 16px rgba(0,0,0,.25)">Phản hồi / Duyệt →</a>')


@app.get("/proposal/{record_id}")
def proposal(record_id: str) -> HTMLResponse:
    """Serve proposal HTML cho requester (seat-free, link public theo record-id) + nut phan hoi Fillout.
    Lay file tu attachment 'File proposal' (URL Airtable het han nhanh -> fetch luc request)."""
    try:
        rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    except Exception:  # noqa: BLE001
        return HTMLResponse("<h3 style='font-family:sans-serif'>Không tìm thấy dự án.</h3>", status_code=404)
    btn = _feedback_button(record_id)
    atts = rec.get("fields", {}).get("File proposal") or []
    if not atts:  # chua co proposal (vd dang Cho dieu chinh/lam ro) -> trang nhac phan hoi
        return HTMLResponse(
            "<body style='font-family:-apple-system,Segoe UI,Roboto,Arial;padding:48px;color:#1a1a2e'>"
            "<h2>Dự án đang chờ bạn phản hồi</h2>"
            "<p>Chưa có đề xuất để xem (đang chờ điều chỉnh / làm rõ). Vui lòng dùng nút phản hồi.</p>"
            f"{btn}</body>")
    try:
        with urllib.request.urlopen(atts[0]["url"], timeout=30) as r:
            html_str = r.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return HTMLResponse("<h3 style='font-family:sans-serif'>Không tải được proposal, thử lại sau.</h3>",
                            status_code=502)
    if btn:
        html_str = html_str.replace("</body>", btn + "</body>")
    return HTMLResponse(html_str)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
