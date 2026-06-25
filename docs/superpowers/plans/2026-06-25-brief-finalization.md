# Bước 5 Brief Finalization + Kho Tài liệu dự án — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm vòng duyệt brief (Duyệt / Cần sửa / tự upload) + kho "Tài liệu dự án" chung (proposal/plan/brief, có version, lưu copy) + tracking mọi sự kiện; duyệt xong bàn giao Status "Chờ thiết kế".

**Architecture:** Mirror vòng duyệt proposal. Kho tài liệu = bảng con + helper `log_document` hook vào `proposal_render` upload (DRY cho cả 3 doc). Brief loop trong pipeline (mirror `_scan_decisions`/`_revise_or_escalate`). Email qua hệ template Airtable sẵn.

**Tech Stack:** Python (pipeline/airtable_client/proposal_render/brief/config), pytest dev-only, Airtable (MCP + Automation + Fillout + Interface), hệ Email Templates.

## Global Constraints

- pytest dev-only — KHÔNG thêm vào requirements.txt. Chạy bằng `venv/bin/python -m pytest`.
- Local AIRTABLE_TOKEN READ-ONLY → code-write chỉ verify sau deploy; local chỉ smoke import + pytest (no network).
- **MAX_BRIEF_ROUNDS = 3** → quá thì Status "Chờ Merch PIC" (mirror MAX_PROPOSAL_ROUNDS).
- Code dùng **tên field** (REST qua `airtable()`); field ID chỉ cần cho thao tác MCP (Task 1).
- Mọi ghi kho/log KHÔNG chặn nghiệp vụ (try/except → log.warning).
- **"Duyệt brief" = cổng bàn giao duy nhất.** Tự upload chỉ thay file active.
- Tái dùng cờ `Gửi phản hồi` (route theo Status). Status mới: `Chờ duyệt brief`, `Chờ thiết kế`.
- Ranh giới: dừng ở "Chờ thiết kế" (Bước 6 tách sau).
- Base `appo1Oei5JvJ1EXAG`; Projects `tbltWsCRFMDAkpKKc`; Status field `fldvIT2CbcSbJmO3O`; Nhóm mốc (Step Log) `fldgCjaTMMm1VzLpk`.

---

## Task 1: Airtable schema (manual qua MCP)

**Files:** Không có code.

**Interfaces:**
- Produces: bảng `Tài liệu dự án`; Projects fields `Duyệt brief?`/`Feedback brief`/`Brief tự upload`/`Số round brief`; Status options `Chờ duyệt brief`/`Chờ thiết kế`; Nhóm mốc option `Thiết kế`.

- [ ] **Step 1: Tạo bảng `Tài liệu dự án`** (`create_table`, base `appo1Oei5JvJ1EXAG`) fields:
  - `Loại` (singleSelect: Proposal, Plan, Brief, Khác) — primary
  - `Project` (multipleRecordLinks → `tbltWsCRFMDAkpKKc`)
  - `Mã project (text)` (singleLineText)
  - `Nguồn` (singleSelect: AI, Requester)
  - `Phiên bản` (number, precision 0)
  - `File` (multipleAttachments)
  - `Ghi chú` (multilineText)
  - *(Created time: dùng cột `Created` mặc định Airtable, hoặc thêm field createdTime tên `Thời gian`)*
- [ ] **Step 2: Thêm 4 field trên Projects** (`create_field`, `tbltWsCRFMDAkpKKc`):
  - `Duyệt brief?` (singleSelect: Duyệt, Cần sửa)
  - `Feedback brief` (multilineText)
  - `Brief tự upload` (multipleAttachments)
  - `Số round brief` (number, precision 0)
- [ ] **Step 3: Thêm 2 option vào Status** (`update_field` field `fldvIT2CbcSbJmO3O`, giữ toàn bộ choices cũ + thêm): `Chờ duyệt brief`, `Chờ thiết kế`.
- [ ] **Step 4: Thêm option `Thiết kế` vào `Nhóm mốc`** (Step Log, field `fldgCjaTMMm1VzLpk`) — màu vd `tealLight2` (cho status "Chờ thiết kế").
- [ ] **Step 5: Verify** — `get_table_schema`/`list_records_for_table` xác nhận bảng + fields + options tồn tại. Ghi lại field IDs của bảng `Tài liệu dự án` (cho code dùng tên, nhưng lưu lại để debug).

---

## Task 2: `log_document` + wire vào upload (code)

**Files:**
- Modify: `ClawAMC/airtable_client.py` (thêm `log_document`)
- Modify: `ClawAMC/proposal_render.py` (`upload_proposal`/`upload_plan`/`upload_brief`)
- Test: `ClawAMC/tests/test_log_document.py`

**Interfaces:**
- Consumes: `airtable()` (GET/POST).
- Produces: `log_document(record_id, code, loai, nguon, attachments, note="") -> None`; `_next_doc_version(records, loai) -> int`.

- [ ] **Step 1: Viết test thất bại** — `tests/test_log_document.py`:

```python
import airtable_client as ac


def test_next_version_empty():
    assert ac._next_doc_version([], "Brief") == 1


def test_next_version_counts_same_loai():
    rows = [
        {"fields": {"Loại": "Brief"}},
        {"fields": {"Loại": "Proposal"}},
        {"fields": {"Loại": "Brief"}},
    ]
    assert ac._next_doc_version(rows, "Brief") == 3
    assert ac._next_doc_version(rows, "Proposal") == 2
    assert ac._next_doc_version(rows, "Plan") == 1
```

- [ ] **Step 2: Chạy test → fail**

Run: `cd ClawAMC && venv/bin/python -m pytest tests/test_log_document.py -v`
Expected: FAIL `AttributeError: _next_doc_version`.

- [ ] **Step 3: Implement** — thêm vào `airtable_client.py` (sau `log_event`):

```python
DOCS_TABLE = "Tài liệu dự án"  # kho tai lieu chung (proposal/plan/brief + requester upload)


def _next_doc_version(records: list[dict], loai: str) -> int:
    """So phien ban ke tiep cho 1 loai trong project = (so dong cung Loai) + 1."""
    return sum(1 for r in records if r.get("fields", {}).get("Loại") == loai) + 1


def log_document(record_id: str, code: str, loai: str, nguon: str,
                 attachments: list[dict], note: str = "") -> None:
    """Ghi 1 ban tai lieu vao kho 'Tai lieu du an'. attachments = list {url, filename}
    (copy file). Loi KHONG chan nghiep vu."""
    try:
        qs = urllib.parse.urlencode({"filterByFormula": f"{{Mã project (text)}}='{code}'"})
        existing = airtable("GET", f"{urllib.parse.quote(DOCS_TABLE)}?{qs}").get("records", [])
        version = _next_doc_version(existing, loai)
        airtable("POST", urllib.parse.quote(DOCS_TABLE), {"records": [{"fields": {
            "Loại": loai,
            "Project": [record_id],
            "Mã project (text)": code,
            "Nguồn": nguon,
            "Phiên bản": version,
            "File": [{"url": a["url"], "filename": a["filename"]} for a in attachments],
            "Ghi chú": note,
        }}], "typecast": True})
    except Exception as e:  # noqa: BLE001
        log.warning(f"[docs] không ghi được kho '{loai}/{nguon}' cho {code}: {e}")
```

- [ ] **Step 4: Chạy test → pass**

Run: `cd ClawAMC && venv/bin/python -m pytest tests/test_log_document.py -v`
Expected: 3 passed.

- [ ] **Step 5: Wire vào `proposal_render.py`** — thêm import + helper + gọi trong 3 upload:

Thêm import đầu file: `from airtable_client import log, log_document` (nếu đã import `log` thì chỉ thêm `log_document`).

Thêm helper sau `_upload_attachment`:
```python
def _attachments_from_resp(resp: dict, field_id: str) -> list[dict]:
    """Lay [{url, filename}] cua file vua upload tu response uploadAttachment."""
    atts = (resp.get("fields", {}) or {}).get(field_id, []) or []
    return [{"url": a["url"], "filename": a.get("filename", "file")} for a in atts if a.get("url")]
```

Trong `upload_proposal` (thay `return _upload_attachment(...)`):
```python
def upload_proposal(record_id: str, html: str, code: str) -> dict:
    """Upload HTML vao field 'File proposal' + ghi kho tai lieu (AI)."""
    resp = _upload_attachment(record_id, PROPOSAL_FILE_FIELD_ID, "text/html",
                              f"proposal_{code}.html", html.encode("utf-8"))
    log_document(record_id, code, "Proposal", "AI", _attachments_from_resp(resp, PROPOSAL_FILE_FIELD_ID))
    return resp
```
Tương tự `upload_plan` (loai="Plan", field PLAN_FILE_FIELD_ID) và `upload_brief` (loai="Brief", field BRIEF_FILE_FIELD_ID) — giữ nguyên phần `_upload_attachment`, gán vào `resp`, gọi `log_document`, `return resp`.

- [ ] **Step 6: Smoke import**

Run: `cd ClawAMC && venv/bin/python -c "import airtable_client, proposal_render" && venv/bin/python -m pytest tests/ -q`
Expected: import OK, tất cả test pass.

- [ ] **Step 7: Commit**

```bash
cd ClawAMC && git add airtable_client.py proposal_render.py tests/test_log_document.py
git commit -m "feat(docs): log_document + wire kho Tài liệu dự án vào upload proposal/plan/brief"
```

---

## Task 3: config + brief feedback param (code)

**Files:**
- Modify: `ClawAMC/config.py` (MAX_BRIEF_ROUNDS)
- Modify: `ClawAMC/brief.py` (`build_brief_content` thêm `feedback`)

**Interfaces:**
- Produces: `MAX_BRIEF_ROUNDS = 3`; `build_brief_content(fields, items, asset_status, insight, feedback=None)`.

- [ ] **Step 1: config.py** — thêm cạnh `MAX_PROPOSAL_ROUNDS`:
```python
MAX_BRIEF_ROUNDS = int(os.environ.get("MAX_BRIEF_ROUNDS", "3"))  # so vong sua brief truoc khi escalate PIC
```
- [ ] **Step 2: brief.py** — đổi chữ ký + chèn feedback vào prompt:
```python
def build_brief_content(fields: dict, items: list, asset_status: dict, insight: str,
                        feedback: str | None = None) -> dict:
```
Sau dòng `prompt = BRIEF_PROMPT.format(...)` (trước `data = ask_llm_json(...)`):
```python
    if feedback:
        prompt += (f"\n\nGÓP Ý CỦA REQUESTER — sửa brief theo đúng các ý sau: {feedback}")
```
- [ ] **Step 3: Smoke import**

Run: `cd ClawAMC && venv/bin/python -c "import config, brief" && venv/bin/python -m pytest tests/ -q`
Expected: import OK, test pass.

- [ ] **Step 4: Commit**

```bash
cd ClawAMC && git add config.py brief.py
git commit -m "feat(brief): MAX_BRIEF_ROUNDS + build_brief_content nhận feedback"
```

---

## Task 4: pipeline brief loop (code)

**Files:**
- Modify: `ClawAMC/pipeline.py`
- Test: `ClawAMC/tests/test_brief_decision.py`

**Interfaces:**
- Consumes: `render_email`, `log_event`, `log_document` (gián tiếp qua upload), `MAX_BRIEF_ROUNDS`, `build_brief_content(..., feedback=)`.
- Produces: `_brief_action(fields) -> str`, `_generate_brief` (sửa), `_revise_brief`, `_handoff_design`, `_handle_brief_decision`; nhánh mới trong `_scan_decisions`.

- [ ] **Step 1: Viết test thất bại** — `tests/test_brief_decision.py` (test hàm quyết định thuần):

```python
import pipeline


def test_action_upload_priority():
    f = {"Brief tự upload": [{"url": "x"}], "Duyệt brief?": "Duyệt"}
    assert pipeline._brief_action(f) == "upload"


def test_action_approve():
    assert pipeline._brief_action({"Duyệt brief?": "Duyệt"}) == "approve"


def test_action_revise():
    assert pipeline._brief_action({"Duyệt brief?": "Cần sửa", "Feedback brief": "đổi màu"}) == "revise"


def test_action_revise_no_feedback_ignored():
    assert pipeline._brief_action({"Duyệt brief?": "Cần sửa"}) == "ignore"


def test_action_ignore():
    assert pipeline._brief_action({}) == "ignore"
```

- [ ] **Step 2: Chạy test → fail**

Run: `cd ClawAMC && venv/bin/python -m pytest tests/test_brief_decision.py -v`
Expected: FAIL `AttributeError: _brief_action`.

- [ ] **Step 3: Implement** — thêm vào `pipeline.py`. Thêm import `MAX_BRIEF_ROUNDS` vào dòng `from config import (...)`.

Hàm quyết định thuần (gần `_scan_decisions`):
```python
def _brief_action(f: dict) -> str:
    """Quyet dinh xu ly brief tu fields. Uu tien upload (thay file active) truoc."""
    if f.get("Brief tự upload"):
        return "upload"
    decision = f.get("Duyệt brief?")
    if decision == "Duyệt":
        return "approve"
    if decision == "Cần sửa" and (f.get("Feedback brief") or "").strip():
        return "revise"
    return "ignore"
```

Sửa cuối `_generate_brief` — thay khối `update_project(..., {"File brief design": [], ...})` + sau upload, set Status "Chờ duyệt brief". Cụ thể đổi đuôi hàm (sau `upload_brief(...)`):
```python
    upload_brief(record_id, pptx, code)
    e_subject, e_body = render_email("brief", fields)
    update_project(record_id, {"Bắt đầu design": False, "Status": "Chờ duyệt brief",
                               "Số round brief": 0, "Duyệt brief?": None, "Feedback brief": None,
                               "Email subject": e_subject, "Email body": e_body})
    append_note(record_id, f"[AI] Đã sinh brief design ({len(brief_data.get('items', []))} item) — chờ requester duyệt.",
                field=HISTORY_FIELD)
    log_event(record_id, code, "Sinh brief design")
    _log_cost(record_id, code, time.monotonic() - t0, step="Brief")
    log.info(f"[brief] {code} -> brief design uploaded -> Chờ duyệt brief")
```
(Bỏ 2 dòng cũ: `update_project(... "File brief design": [] ...)` đặt TRƯỚC upload vẫn giữ để clear bản cũ; và bỏ dòng `update_project(record_id, {"Bắt đầu design": False})` cũ vì đã gộp ở trên. Giữ dòng render_email + clear File brief design trước upload.)

> Lưu ý implementer: `_generate_brief` hiện có `update_project({"File brief design": [], Email subject/body})` TRƯỚC `upload_brief`, rồi `update_project({"Bắt đầu design": False})` SAU. Gộp lại: clear `File brief design` trước upload (giữ), còn set Status/round/cờ làm SAU upload như khối trên.

Hàm revise + handoff + decision handler:
```python
def _revise_brief(record_id: str, code: str, feedback: str) -> None:
    """Requester yeu cau sua brief -> sinh lai theo feedback; qua MAX_BRIEF_ROUNDS -> PIC."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    fields = rec.get("fields", {})
    rounds = int(fields.get("Số round brief") or 0) + 1
    if rounds > MAX_BRIEF_ROUNDS:
        reason = f"Brief sửa {MAX_BRIEF_ROUNDS} vòng vẫn chưa duyệt. Feedback gần nhất: {feedback}"
        e_subject, e_body = render_email("pic", fields, core=reason)
        update_project(record_id, {"Status": PIC_STATUS, "Cần PIC xử lý": True, "Gửi phản hồi": False,
                                   "Duyệt brief?": None, "Lý do cần PIC": reason,
                                   "Email subject": e_subject, "Email body": e_body})
        append_note(record_id, f"[AI] {reason} — chuyển Merch PIC.", field=HISTORY_FIELD)
        log_event(record_id, code, f"Brief quá {MAX_BRIEF_ROUNDS} vòng → PIC")
        log.info(f"[brief] {code} quá {MAX_BRIEF_ROUNDS} vòng -> PIC")
        return
    items, asset_status, insight, logo_png = _gather_brief_inputs(fields, record_id)
    brief_data = build_brief_content(fields, items, asset_status, insight, feedback=feedback)
    images = gather_brief_images(brief_data["items"], fields.get("Game") or "")
    project = {
        "code": fields.get("Mã project") or code, "name": fields.get("Tên project") or "",
        "game": fields.get("Game") or "", "so_luong": fields.get("Số lượng (bộ/suất)") or "?",
        "deadline": (str(fields.get("Deadline cần hàng"))[:10] if fields.get("Deadline cần hàng") else "?"),
        "logo_png": logo_png,
    }
    pptx = render_brief_pptx(brief_data, images, project)
    update_project(record_id, {"File brief design": []})  # clear ban cu truoc upload
    upload_brief(record_id, pptx, code)  # tu log_document(Brief, AI) version++
    e_subject, e_body = render_email("brief", fields)
    update_project(record_id, {"Status": "Chờ duyệt brief", "Số round brief": rounds,
                               "Duyệt brief?": None, "Feedback brief": None, "Gửi phản hồi": False,
                               "Email subject": e_subject, "Email body": e_body})
    append_note(record_id, f"[AI] Sửa brief round {rounds} theo feedback: {feedback}", field=HISTORY_FIELD)
    log_event(record_id, code, f"Sửa brief round {rounds}")
    log.info(f"[brief] {code} CẦN SỬA -> brief round {rounds} đã gửi lại")


def _handoff_design(record_id: str, code: str) -> None:
    """Requester duyet brief -> ban giao thiet ke: Status 'Cho thiet ke' + mail PIC+requester."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    fields = rec.get("fields", {})
    e_subject, e_body = render_email("handoff_design", fields)
    update_project(record_id, {"Status": "Chờ thiết kế", "Gửi phản hồi": False, "Duyệt brief?": None,
                               "Email subject": e_subject, "Email body": e_body})
    append_note(record_id, "[AI] Requester DUYỆT brief — bàn giao sang thiết kế.", field=HISTORY_FIELD)
    log_event(record_id, code, "Duyệt brief → bàn giao thiết kế")
    log.info(f"[brief] {code} DUYỆT brief -> Chờ thiết kế")


def _snapshot_requester_brief(record_id: str, code: str, fields: dict) -> None:
    """Requester tu upload brief -> dat lam active 'File brief design' + ghi kho (Requester)."""
    atts = fields.get("Brief tự upload") or []
    files = [{"url": a["url"], "filename": a.get("filename", f"brief_requester_{code}")}
             for a in atts if a.get("url")]
    if not files:
        return
    update_project(record_id, {"File brief design": files, "Brief tự upload": []})
    log_document(record_id, code, "Brief", "Requester", files, note="Requester tự upload")
    append_note(record_id, "[AI] Requester tự upload brief — đặt làm bản active.", field=HISTORY_FIELD)
    log_event(record_id, code, "Requester tự upload brief")


def _handle_brief_decision(record_id: str, code: str, f: dict) -> None:
    """Xu ly tick Gui phan hoi tai Status 'Cho duyet brief'."""
    action = _brief_action(f)
    if action == "upload":
        _snapshot_requester_brief(record_id, code, f)
        update_project(record_id, {"Gửi phản hồi": False})  # da thay file active, cho bam Duyet sau
    elif action == "approve":
        _handoff_design(record_id, code)
    elif action == "revise":
        _revise_brief(record_id, code, (f.get("Feedback brief") or "").strip())
    else:
        update_project(record_id, {"Gửi phản hồi": False})
        log.info(f"[brief] {code} tick Gửi nhưng thiếu quyết định brief -> bỏ qua")
```
Cần import `log_document` ở pipeline: thêm vào dòng `from airtable_client import (...)`.

- [ ] **Step 4: Thêm nhánh vào `_scan_decisions`** — sau nhánh `if f.get("Status") == "Thiếu thông tin":` (và trước phần đọc `feedback`/`decision` proposal), chèn:
```python
            if f.get("Status") == "Chờ duyệt brief":
                _handle_brief_decision(r["id"], code, f)
                continue
```

- [ ] **Step 5: Chạy test + smoke**

Run: `cd ClawAMC && venv/bin/python -m pytest tests/test_brief_decision.py -v && venv/bin/python -c "import pipeline" && venv/bin/python -m pytest tests/ -q`
Expected: 5 passed (brief_decision) + import OK + toàn bộ test pass.

- [ ] **Step 6: Commit + deploy**

```bash
cd ClawAMC && git add pipeline.py tests/test_brief_decision.py
git commit -m "feat(brief): vòng duyệt brief (Duyệt/Cần sửa/tự upload) + bàn giao Chờ thiết kế"
git push origin develop
```

---

## Task 5: Email templates (manual qua MCP)

**Files:** Bảng `Email Templates` (`tbl6kw6clJfDsrY0u`).

- [ ] **Step 1: Sửa dòng `brief`** (record `recS2bzNsudVEtd5A`) → Subject/Body thành "mời duyệt": nội dung báo brief sẵn sàng + CTA Duyệt / Cần sửa (nhập Feedback brief) / Tự upload trên Airtable. Giữ biến hợp lệ ({{ten_nguoi_gui}}, {{ten_project}}, {{game}}, {{deadline_hang}}).
- [ ] **Step 2: Thêm dòng `handoff_design`** (`create_records_for_table`): Mã=`handoff_design`, Tên="Mail bàn giao thiết kế", Subject=`[{{ma_project}}] {{ten_project}} — Brief đã duyệt, chuyển thiết kế`, Body chào + "Brief đã được duyệt (đính kèm), dự án chuyển sang bước thiết kế." + Biến dùng được liệt kê.
- [ ] **Step 3: Verify** — `list_records_for_table` bảng Email Templates: có dòng `handoff_design`, dòng `brief` đã đổi.

---

## Task 6: Airtable automations (manual)

**Files:** Airtable Automations.

- [ ] **Step 1: Brief "mời duyệt"** — automation `Gửi brief cho requester` (hiện trigger File brief design đính kèm) → đảm bảo gửi `{Email subject}`/`{Email body}` (đã làm ở phần email templates trước) + người nhận requester. Kiểm trigger vẫn hợp lý khi brief upload ở Status "Chờ duyệt brief".
- [ ] **Step 2: Tạo automation `Gửi bàn giao thiết kế`** — Description: `Trigger: Status = Chờ thiết kế → gửi {Email subject}/{Email body} cho PIC phụ trách + requester, đính kèm File brief design. Nội dung: Email Templates Mã=handoff_design.` Trigger When record matches (Status = Chờ thiết kế); Send email: To = `PIC phụ trách` + `Created by → Email`, Subject `{Email subject}`, Message `{Email body}`, attach `File brief design`. Bật ON.
- [ ] **Step 3: Test** chạy thử automation với 1 record Status "Chờ thiết kế".

---

## Task 7: Fillout + Interface (manual)

**Files:** Fillout form + Interface Cổng Merch.

- [ ] **Step 1: Fillout "Update form"** — thêm section điều kiện Status `Chờ duyệt brief`: field `Duyệt brief?` (Duyệt/Cần sửa), `Feedback brief` (text, hiện khi Cần sửa), `Brief tự upload` (file upload). Submit → set `Gửi phản hồi` = true (qua automation Fillout submit hiện có / hoặc thêm điều kiện).
- [ ] **Step 2: Interface Cổng Merch** — thêm nút/section duyệt brief (mirror nút proposal) ở page phù hợp + page list/grid bảng `Tài liệu dự án` (xem lịch sử tài liệu theo project).
- [ ] **Step 3: Publish interface.**

---

## Task 8: Live smoke + cleanup + memory

- [ ] **Step 1: Live smoke** (sau deploy Task 4) — đẩy 1 dự án thật tới brief:
  1. Bắt đầu design → Status "Chờ duyệt brief" + mail mời duyệt + kho có Brief v1 (AI).
  2. Cần sửa + Feedback → brief v2 (AI) trong kho, Số round brief=1, vẫn Chờ duyệt brief.
  3. Tự upload file → File brief design = file requester, kho có Brief (Requester), vẫn Chờ duyệt brief.
  4. Duyệt → Status "Chờ thiết kế" + mail PIC+requester (kèm brief).
  5. Step Log có đủ sự kiện (Sinh/Sửa/Upload/Duyệt) + Timeline/Gantt vẽ; kho `Tài liệu dự án` đủ bản.
- [ ] **Step 2: Cleanup** xoá dự án test + dòng kho/Step Log test.
- [ ] **Step 3: Memory** — cập nhật [[merch-brief-finalization-plan]] (DONE), [[merch-step-progress-plan]] (Bước 5 xong, còn Bước 6), [[merch-architecture]] (bảng Tài liệu dự án + log_document).

---

## Self-Review

**Spec coverage:** §4.1 bảng → T1S1. §4.2 fields → T1S2. §4.3 status → T1S3. §5 state machine → T4 (_generate_brief/_revise_brief/_handoff/_handle_brief_decision/_scan branch). §6.1 log_document → T2S3. §6.2 wire uploads → T2S5. §6.3 pipeline → T4. §6.4 brief feedback → T3S2. §7 email → T5. §8 Fillout/interface → T7. §9 tracking (log_event) → T4 (mỗi hàm có log_event). §10 error → T2/T4 try/except + cap. §11 test → T2/T4 unit + T8 live. §12: Nhóm mốc "Thiết kế" → T1S4; URL attachment → T2 (note re-upload nếu fail, verify T8); PIC recipient → T6S2.

**Placeholder scan:** code đầy đủ; "verify lúc plan" đã resolve (Nhóm mốc Thiết kế, recipient PIC phụ trách). Rủi ro còn: URL-attachment-copy có thể cần re-upload bytes nếu Airtable không nhận URL → nêu rõ ở T8 để bắt khi live.

**Type consistency:** `log_document(record_id, code, loai, nguon, attachments, note)` đồng nhất (T2 def ↔ T4 _snapshot gọi). `_brief_action -> str` ("upload"/"approve"/"revise"/"ignore") khớp test + _handle_brief_decision. `build_brief_content(..., feedback=None)` khớp T3 def ↔ T4 _revise_brief gọi. Field tên nhất quán ("Duyệt brief?"/"Feedback brief"/"Brief tự upload"/"Số round brief"/"Chờ duyệt brief"/"Chờ thiết kế").
