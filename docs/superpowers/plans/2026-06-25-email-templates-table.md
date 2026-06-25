# Email Templates (bảng Airtable) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gom toàn bộ nội dung 7 email của merch agent về 1 bảng Airtable `Email Templates` để PO non-tech tự sửa không cần deploy; code/JS chỉ đọc template + thay biến + nối footer.

**Architecture:** Bảng `Email Templates` là nguồn nội dung duy nhất. Module `email_templates.py` cung cấp `render_email(kind, fields, core)` ghi `Email subject`/`Email body` vào record; 6 mail qua app gọi hàm này atomically cùng update sẵn có, mail #7 (scheduled) render bằng Run script JS đọc cùng bảng. Mọi automation gửi mail chỉ gửi `{Email subject}` + `{Email body}`.

**Tech Stack:** Python 3.10+ (stdlib `re`, `urllib`), pytest (dev-only), Airtable REST + MCP, Airtable Automation "Run script" (JS).

## Global Constraints

- pytest dev-only — **KHÔNG thêm vào requirements.txt**.
- Airtable "Send email" **KHÔNG render HTML** → email plain-text gọn; phần đẹp ở file đính kèm.
- Local `.env` `AIRTABLE_TOKEN` READ-ONLY → mọi write/live-verify chỉ chạy sau deploy (prod token ghi); local chỉ smoke import + pytest (không gọi mạng).
- Cú pháp biến: `{{ten_bien}}`. **Safe-substitute**: biến lạ → giữ nguyên `{{...}}`, KHÔNG raise.
- Render **không bao giờ chặn pipeline**: lỗi đọc bảng / thiếu kind → fallback hardcode + `log.warning`.
- Footer (dòng `footer`) **tự nối vào cuối mọi body**; PO sửa 1 chỗ.
- **9 biến** (chốt plan, đã bỏ `{{link}}` vì không có field nguồn rõ ràng — YAGNI): `ma_project`, `ten_project`, `game`, `ten_nguoi_gui`, `han_duyet`, `deadline_hang`, `noi_dung`, `ly_do`, `canh_bao_deadline`.
- Base Airtable: `appo1Oei5JvJ1EXAG`. Projects table: hằng `PROJECTS_TABLE` trong config.
- Thứ tự task bắt buộc: 1→2→3 an toàn (không đụng mail đang chạy); 4→5 mới cắt automation sang field mới; 6 verify.

---

## Nội dung seed (dùng nguyên văn ở Task 1)

**Cheatsheet — Description của bảng `Email Templates`:**
```
HƯỚNG DẪN SỬA EMAIL (cho PO)
- Mỗi dòng = 1 loại mail. Sửa cột Subject (tiêu đề) và Body (nội dung) thoải mái.
- Chèn biến bằng cú pháp {{ten_bien}} — hệ thống tự thay bằng dữ liệu dự án khi gửi.
- Gõ sai tên biến? Không sao — phần đó giữ nguyên, mail vẫn gửi (không lỗi).
- Footer (dòng Mã = footer) tự động nối vào CUỐI mọi mail — sửa 1 lần, áp dụng tất cả.
- Cột "Biến dùng được" liệt kê biến hợp lệ cho riêng từng mail.

DANH SÁCH BIẾN:
{{ma_project}}        Mã dự án, vd MERCH-021
{{ten_project}}       Tên dự án
{{game}}              Tên game
{{ten_nguoi_gui}}     Tên người gửi yêu cầu (trống -> "Anh/Chị")
{{han_duyet}}         Hạn duyệt proposal (dd/mm/yyyy)
{{deadline_hang}}     Deadline cần hàng (dd/mm/yyyy)
{{noi_dung}}          Nội dung động do AI soạn (chỉ mail bổ sung & trao đổi)
{{ly_do}}             Lý do chuyển PIC (chỉ mail pic)
{{canh_bao_deadline}} Cảnh báo deadline (chỉ mail proposal; trống -> bỏ qua)
```

**8 dòng (Mã | Tên | Subject | Body | Biến dùng được):**

1. `bo_sung` | Mail bổ sung thông tin | `[{{ma_project}}] {{ten_project}} — Cần bổ sung thông tin` |
```
Chào {{ten_nguoi_gui}},

Đề bài "{{ten_project}}" ({{game}}) cần bổ sung một số thông tin trước khi xử lý:

{{noi_dung}}

Vui lòng cập nhật trên Airtable rồi tích "Gửi phản hồi" để tiếp tục.
```
| `{{ma_project}}, {{ten_project}}, {{game}}, {{ten_nguoi_gui}}, {{noi_dung}}`

2. `clarify` | Mail trao đổi làm rõ | `[{{ma_project}}] {{ten_project}} — Cần trao đổi để hoàn thiện đề xuất` |
```
Chào {{ten_nguoi_gui}},

Để hoàn thiện đề xuất cho "{{ten_project}}" ({{game}}), bọn mình cần trao đổi thêm:

{{noi_dung}}

Vui lòng phản hồi trên Airtable rồi tích "Gửi phản hồi".
```
| `{{ma_project}}, {{ten_project}}, {{game}}, {{ten_nguoi_gui}}, {{noi_dung}}`

3. `proposal` | Mail mời duyệt proposal | `[{{ma_project}}] {{ten_project}} — Mời duyệt proposal` |
```
Chào {{ten_nguoi_gui}},

Proposal merch cho "{{ten_project}}" ({{game}}) đã sẵn sàng — xem file đính kèm.

{{canh_bao_deadline}}

Hạn duyệt: {{han_duyet}}. Vui lòng vào Airtable chọn Duyệt hoặc Cần sửa.
```
| `{{ma_project}}, {{ten_project}}, {{game}}, {{ten_nguoi_gui}}, {{han_duyet}}, {{canh_bao_deadline}}`

4. `plan` | Mail plan sản xuất (PIC) | `[{{ma_project}}] {{ten_project}} — Plan sản xuất đã sẵn sàng` |
```
Chào team Merch,

Plan sản xuất cho "{{ten_project}}" ({{game}}) đã được tạo — xem file đính kèm.
Deadline cần hàng: {{deadline_hang}}.
```
| `{{ma_project}}, {{ten_project}}, {{game}}, {{deadline_hang}}`

5. `brief` | Mail brief design | `[{{ma_project}}] {{ten_project}} — Brief design đã sẵn sàng` |
```
Chào {{ten_nguoi_gui}},

Brief design cho "{{ten_project}}" ({{game}}) đã sẵn sàng — xem file đính kèm. Dự án chuyển sang bước thiết kế.
Deadline cần hàng: {{deadline_hang}}.
```
| `{{ma_project}}, {{ten_project}}, {{game}}, {{ten_nguoi_gui}}, {{deadline_hang}}`

6. `pic` | Mail escalate Merch PIC | `[CẦN XỬ LÝ] {{ma_project}} {{ten_project}} — chuyển Merch PIC` |
```
Chào team Merch,

Dự án "{{ten_project}}" ({{game}}) cần xử lý thủ công.
Lý do: {{ly_do}}
```
| `{{ma_project}}, {{ten_project}}, {{game}}, {{ly_do}}`

7. `qua_han` | Mail quá hạn duyệt | `[{{ma_project}}] {{ten_project}} — Quá hạn duyệt proposal` |
```
Chào {{ten_nguoi_gui}},

Proposal cho "{{ten_project}}" ({{game}}) đã quá hạn duyệt ({{han_duyet}}) mà chưa được phản hồi.
Vui lòng vào Airtable duyệt sớm để dự án tiếp tục.
```
| `{{ma_project}}, {{ten_project}}, {{game}}, {{ten_nguoi_gui}}, {{han_duyet}}`

8. `footer` | Footer chung | *(Subject để trống)* |
```
—
📩 Email tự động từ Merch Agent — vui lòng thao tác trên Airtable, KHÔNG trả lời email này.
Hỗ trợ: merch-support@vng.com.vn
Merch Agent · AMC Team · VNGGames
🔒 Nội bộ VNGGames — không chia sẻ ra ngoài.
```
| *(footer — sửa đầu mối Hỗ trợ tại đây)*

---

## Task 1: Airtable infra — bảng + seed + buffer fields (manual qua MCP)

**Files:** Không có file code. Thao tác Airtable qua MCP (base `appo1Oei5JvJ1EXAG`).

**Interfaces:**
- Produces: bảng `Email Templates` (8 dòng như trên); 2 field `Email subject` (single line), `Email body` (long text) trên Projects. Module Task 2 đọc bảng theo tên `Email Templates`, key cột `Mã`/`Subject`/`Body`.

- [ ] **Step 1: Tạo bảng `Email Templates`** (MCP `create_table`, base `appo1Oei5JvJ1EXAG`) với fields: `Mã` (singleLineText, primary), `Tên` (singleLineText), `Subject` (singleLineText), `Body` (multilineText), `Biến dùng được` (multilineText).

- [ ] **Step 2: Set Description bảng** = nội dung cheatsheet ở mục "Nội dung seed" (MCP `update_table` description).

- [ ] **Step 3: Thêm field description cho `Subject` và `Body`** (MCP `update_field`): text = `Dùng {{ten_bien}}. Xem mô tả bảng cho danh sách biến đầy đủ.`

- [ ] **Step 4: Seed 8 dòng** (MCP `create_records_for_table`) đúng nguyên văn 8 dòng ở mục "Nội dung seed" (Mã/Tên/Subject/Body/Biến dùng được).

- [ ] **Step 5: Thêm 2 field buffer trên Projects** (MCP `create_field`, table `PROJECTS_TABLE` = `tbltWsCRFMDAkpKKc`): `Email subject` (singleLineText), `Email body` (multilineText).

- [ ] **Step 6: Verify** — MCP `list_records_for_table` bảng `Email Templates`: đủ 8 dòng, `Mã` đúng tập `{bo_sung, clarify, proposal, plan, brief, pic, qua_han, footer}`. `get_table_schema` Projects: có `Email subject`, `Email body`.

---

## Task 2: `email_templates.py` + unit tests (TDD)

**Files:**
- Create: `ClawAMC/email_templates.py`
- Test: `ClawAMC/tests/test_email_templates.py`

**Interfaces:**
- Consumes: `airtable_client.airtable("GET", path)` → dict có `records`; `airtable_client.log` (logger "merch").
- Produces:
  - `render_email(kind: str, fields: dict, core: str | None = None) -> tuple[str, str]` — trả `(subject, body)`, body đã nối footer. Không raise.
  - `_fetch_templates() -> dict` — map `Mã -> (subject, body)`; lỗi → `{}`.
  - `DEFAULT_TEMPLATES: dict[str, tuple[str, str]]` — fallback (gồm key `"footer"`).

- [ ] **Step 1: Viết test thất bại** — `ClawAMC/tests/test_email_templates.py`:

```python
import email_templates as et


FAKE = {
    "bo_sung": ("[{{ma_project}}] {{ten_project}} — Cần bổ sung",
                "Chào {{ten_nguoi_gui}},\n\n{{noi_dung}}\n\nKết."),
    "footer": ("", "—\nMerch Agent · AMC Team · VNGGames"),
}

FIELDS = {
    "Mã project": "MERCH-021", "Tên project": "Áo PUBG", "Game": "PUBG",
    "Created by": {"name": "Vinh"}, "Deadline phê duyệt": "2026-07-01",
    "Deadline cần hàng": "2026-09-30", "Lý do cần PIC": "Quá 3 vòng",
    "Cảnh báo deadline": "⚠️ Deadline gấp",
}


def _patch(monkeypatch, mapping):
    monkeypatch.setattr(et, "_fetch_templates", lambda: mapping)


def test_substitutes_known_vars(monkeypatch):
    _patch(monkeypatch, FAKE)
    subject, body = et.render_email("bo_sung", FIELDS, core="Thiếu budget")
    assert subject == "[MERCH-021] Áo PUBG — Cần bổ sung"
    assert "Chào Vinh," in body
    assert "Thiếu budget" in body


def test_unknown_var_preserved(monkeypatch):
    _patch(monkeypatch, {"x": ("S", "{{khong_ton_tai}} end"), "footer": ("", "F")})
    _, body = et.render_email("x", FIELDS)
    assert "{{khong_ton_tai}}" in body


def test_footer_appended(monkeypatch):
    _patch(monkeypatch, FAKE)
    _, body = et.render_email("bo_sung", FIELDS, core="abc")
    assert body.rstrip().endswith("Merch Agent · AMC Team · VNGGames")


def test_missing_kind_uses_default(monkeypatch, caplog):
    _patch(monkeypatch, {"footer": ("", "F")})  # thiếu 'pic'
    import logging
    with caplog.at_level(logging.WARNING):
        subject, body = et.render_email("pic", FIELDS, core=None)
    assert subject  # fallback default, không rỗng
    assert "Quá 3 vòng" in body  # {{ly_do}} từ DEFAULT_TEMPLATES['pic']
    assert any("pic" in r.message for r in caplog.records)


def test_core_none_empty(monkeypatch):
    _patch(monkeypatch, FAKE)
    _, body = et.render_email("bo_sung", FIELDS, core=None)
    assert "{{noi_dung}}" not in body  # đã thay bằng rỗng


def test_creator_name_fallback(monkeypatch):
    _patch(monkeypatch, FAKE)
    fields = dict(FIELDS); fields["Created by"] = None
    _, body = et.render_email("bo_sung", fields, core="x")
    assert "Chào Anh/Chị," in body
```

- [ ] **Step 2: Chạy test → fail**

Run: `cd ClawAMC && python -m pytest tests/test_email_templates.py -v`
Expected: FAIL với `ModuleNotFoundError: No module named 'email_templates'` (hoặc AttributeError).

- [ ] **Step 3: Implement** — `ClawAMC/email_templates.py`:

```python
"""Render email tu bang Airtable 'Email Templates' — 1 nguon noi dung duy nhat.
PO sua noi dung trong bang (khong can deploy). Loi KHONG duoc chan pipeline."""
import re
import urllib.parse
from datetime import datetime

from airtable_client import airtable, log

EMAIL_TEMPLATE_TABLE = "Email Templates"
_VAR_RE = re.compile(r"\{\{(\w+)\}\}")

# Fallback khi bang loi/thieu dong -> mail van gui duoc. Footer luu o key 'footer'.
_DEFAULT_FOOTER = ("", "—\n📩 Email tự động từ Merch Agent — thao tác trên Airtable, "
                       "KHÔNG trả lời email này.\nMerch Agent · AMC Team · VNGGames")
DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    "bo_sung": ("[{{ma_project}}] {{ten_project}} — Cần bổ sung thông tin",
                "Chào {{ten_nguoi_gui}},\n\n{{noi_dung}}\n\nVui lòng cập nhật trên Airtable rồi tích \"Gửi phản hồi\"."),
    "clarify": ("[{{ma_project}}] {{ten_project}} — Cần trao đổi để hoàn thiện đề xuất",
                "Chào {{ten_nguoi_gui}},\n\n{{noi_dung}}\n\nVui lòng phản hồi trên Airtable rồi tích \"Gửi phản hồi\"."),
    "proposal": ("[{{ma_project}}] {{ten_project}} — Mời duyệt proposal",
                 "Chào {{ten_nguoi_gui}},\n\nProposal cho \"{{ten_project}}\" đã sẵn sàng (xem file đính kèm).\n"
                 "{{canh_bao_deadline}}\nHạn duyệt: {{han_duyet}}. Vui lòng vào Airtable Duyệt/Cần sửa."),
    "plan": ("[{{ma_project}}] {{ten_project}} — Plan sản xuất đã sẵn sàng",
             "Chào team Merch,\n\nPlan sản xuất cho \"{{ten_project}}\" đã tạo (file đính kèm). "
             "Deadline cần hàng: {{deadline_hang}}."),
    "brief": ("[{{ma_project}}] {{ten_project}} — Brief design đã sẵn sàng",
              "Chào {{ten_nguoi_gui}},\n\nBrief design cho \"{{ten_project}}\" đã sẵn sàng (file đính kèm). "
              "Deadline cần hàng: {{deadline_hang}}."),
    "pic": ("[CẦN XỬ LÝ] {{ma_project}} {{ten_project}} — chuyển Merch PIC",
            "Chào team Merch,\n\nDự án \"{{ten_project}}\" ({{game}}) cần xử lý thủ công.\nLý do: {{ly_do}}"),
    "qua_han": ("[{{ma_project}}] {{ten_project}} — Quá hạn duyệt proposal",
                "Chào {{ten_nguoi_gui}},\n\nProposal cho \"{{ten_project}}\" đã quá hạn duyệt ({{han_duyet}}) "
                "mà chưa phản hồi. Vui lòng vào Airtable duyệt sớm."),
    "footer": _DEFAULT_FOOTER,
}


def _fetch_templates() -> dict:
    """Map Mã -> (Subject, Body). Loi/khong doc duoc -> {} (caller dung DEFAULT_TEMPLATES)."""
    try:
        path = urllib.parse.quote(EMAIL_TEMPLATE_TABLE)
        recs = airtable("GET", path).get("records", [])
        out = {}
        for r in recs:
            f = r.get("fields", {})
            ma = f.get("Mã")
            if ma:
                out[ma] = (f.get("Subject", ""), f.get("Body", ""))
        return out
    except Exception as e:  # noqa: BLE001
        log.warning(f"[email] đọc bảng template lỗi: {e}")
        return {}


def _fmt_date(val) -> str:
    """YYYY-MM-DD -> dd/mm/yyyy; rong/sai -> '' hoac nguyen ban."""
    if not val:
        return ""
    try:
        return datetime.strptime(val, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(val)


def _build_vars(fields: dict, core: str | None) -> dict:
    creator = fields.get("Created by")
    name = creator.get("name") if isinstance(creator, dict) else None
    return {
        "ma_project": fields.get("Mã project", ""),
        "ten_project": fields.get("Tên project", ""),
        "game": fields.get("Game", ""),
        "ten_nguoi_gui": name or "Anh/Chị",
        "han_duyet": _fmt_date(fields.get("Deadline phê duyệt")),
        "deadline_hang": _fmt_date(fields.get("Deadline cần hàng")),
        "noi_dung": core or "",
        "ly_do": fields.get("Lý do cần PIC", "") or "",
        "canh_bao_deadline": fields.get("Cảnh báo deadline", "") or "",
    }


def _sub(text: str, variables: dict) -> str:
    """Thay {{key}} bang variables[key]; key la -> giu nguyen (safe)."""
    return _VAR_RE.sub(
        lambda m: str(variables[m.group(1)]) if m.group(1) in variables else m.group(0),
        text or "",
    )


def render_email(kind: str, fields: dict, core: str | None = None) -> tuple[str, str]:
    """Tra (subject, body) da thay bien + noi footer. KHONG raise."""
    tpls = _fetch_templates()
    variables = _build_vars(fields, core)
    if kind in tpls:
        subject_tpl, body_tpl = tpls[kind]
    else:
        log.warning(f"[email] thiếu template '{kind}' trong bảng — dùng mặc định")
        subject_tpl, body_tpl = DEFAULT_TEMPLATES.get(kind, ("", ""))
    footer = (tpls.get("footer") or DEFAULT_TEMPLATES["footer"])[1]
    subject = _sub(subject_tpl, variables)
    body = _sub(body_tpl, variables).rstrip() + "\n\n" + _sub(footer, variables)
    return subject, body
```

- [ ] **Step 4: Chạy test → pass**

Run: `cd ClawAMC && python -m pytest tests/test_email_templates.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd ClawAMC && git add email_templates.py tests/test_email_templates.py
git commit -m "feat(email): render_email từ bảng Airtable template + unit tests"
```

---

## Task 3: Wire 6 mail trong code + đổi prompt LLM bo_sung

**Files:**
- Modify: `ClawAMC/analysis.py` (prompt `mail_bo_sung` + chỗ set field bo_sung ~26, ~146-148)
- Modify: `ClawAMC/pipeline.py` (import; clarify ~212; proposal ~144-158 & ~181-187; plan ~411-415; brief ~464; pic ~81, ~204, ~352, ~516)

**Interfaces:**
- Consumes: `email_templates.render_email(kind, fields, core)`.
- Produces: tại mỗi transition, record có `Email subject`/`Email body` đã render (đặt cùng update sẵn có).

- [ ] **Step 1: analysis.py — đổi prompt `mail_bo_sung` thành chỉ viết LÕI**

Thay mục 4 trong `ANALYSIS_PROMPT` (dòng ~26):

```python
4. "mail_bo_sung": nếu missing_fields không rỗng HOẶC deadline "gấp"/"không khả thi" → soạn PHẦN NỘI DUNG LÕI (tiếng Việt, ngắn gọn, chuyên nghiệp): nêu rõ từng thông tin thiếu cần bổ sung (giải thích vì sao cần); nếu deadline gấp/không khả thi thì cảnh báo và đề xuất hướng (lùi deadline / ưu tiên hàng có sẵn). KHÔNG viết lời chào ("Chào…") và KHÔNG viết chữ ký — hệ thống tự thêm. Nếu đủ thông tin và deadline ổn → null.
```

- [ ] **Step 2: analysis.py — import + ghi Email subject/body cho bo_sung**

Thêm import (dòng ~4, sau import airtable_client):
```python
from email_templates import render_email
```
Thay block (dòng ~146-148):
```python
        if notify_missing and analysis.get("mail_bo_sung"):
            update_fields["Mail bổ sung"] = analysis["mail_bo_sung"]
            update_fields["Gửi mail bổ sung"] = True
```
bằng:
```python
        if notify_missing and analysis.get("mail_bo_sung"):
            subject, body = render_email("bo_sung", fields, core=analysis["mail_bo_sung"])
            update_fields["Email subject"] = subject
            update_fields["Email body"] = body
            update_fields["Gửi mail bổ sung"] = True
```
(Bỏ ghi `Mail bổ sung` — field orphan, để trống trên Airtable, không xoá.)

- [ ] **Step 3: pipeline.py — import**

Thêm (cụm import đầu file, gần dòng 35-38):
```python
from email_templates import render_email
```

- [ ] **Step 4: pipeline.py — clarify (`_request_adjust`, nhánh hỏi requester ~212-219)**

Trong dict `update_project(record_id, {...})` của nhánh else (sau `CLARIFY_MAIL_FLAG: True`), thêm 2 dòng:
```python
        **dict(zip(("Email subject", "Email body"),
                   render_email("clarify", f, core=message))),
```
(`f` = `rec["fields"]` đã có sẵn ở dòng ~199; `message` là tham số hàm.)

- [ ] **Step 5: pipeline.py — proposal (`_publish_proposal` ~144 & `_publish_from_snapshot` ~181)**

`_publish_proposal`: hàm chỉ nhận `record_id, result, html`. Lấy fields để render — thêm ngay đầu hàm (sau dòng `deadline = ...`):
```python
    fields_now = airtable("GET", f"{PROJECTS_TABLE}/{record_id}").get("fields", {})
    fields_now["Deadline phê duyệt"] = deadline  # vừa set, GET cũ chưa có
    e_subject, e_body = render_email("proposal", fields_now)
```
Thêm vào dict `fields` (trước `update_project(record_id, fields)`):
```python
    fields["Email subject"] = e_subject
    fields["Email body"] = e_body
```

`_publish_from_snapshot`: dict `update_project` (dòng ~181) đã có `fields` của record (biến `fields` dòng ~169) + `deadline`. Thêm vào dict đó:
```python
        **dict(zip(("Email subject", "Email body"),
                   render_email("proposal", {**fields, "Deadline phê duyệt": deadline}))),
```

- [ ] **Step 6: pipeline.py — plan (`_generate_plan` ~411-415)**

Trước `upload_plan(...)` (dòng ~415) thêm:
```python
    e_subject, e_body = render_email("plan", fields)
    update_project(record_id, {"Email subject": e_subject, "Email body": e_body})
```

- [ ] **Step 7: pipeline.py — brief (`_generate_brief` ~464)**

Dòng ~464 hiện: `update_project(record_id, {"File brief design": []})`. Đổi thành:
```python
    e_subject, e_body = render_email("brief", fields)
    update_project(record_id, {"File brief design": [], "Email subject": e_subject, "Email body": e_body})
```
(`fields` đã có ở đầu `_generate_brief`.)

- [ ] **Step 8: pipeline.py — pic (4 chỗ escalate)**

Mỗi chỗ set `"Lý do cần PIC": <reason>` trong update_project, thêm 2 dòng render ngay trước và 2 key vào dict. Vì `render_email` cần `fields` có `Lý do cần PIC`, build reason trước rồi truyền `core`:

(a) `_mark_ai_error` (~80-82) — hàm chỉ có `record_id`. Thay block update:
```python
        reason = f"Lỗi AI ({stage}): {err}"
        rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}").get("fields", {})
        e_subject, e_body = render_email("pic", rec, core=reason)
        update_project(record_id, {"Status": PIC_STATUS, "Cần PIC xử lý": True, "Gửi phản hồi": False,
                                   "Lý do cần PIC": reason,
                                   "Email subject": e_subject, "Email body": e_body})
```

(b) `_request_adjust` over-cap (~203-207): trong dict đã có `f` (fields, dòng ~199) và `pic_reason`. Thêm vào dict:
```python
            **dict(zip(("Email subject", "Email body"),
                       render_email("pic", f, core=pic_reason))),
```

(c) `_reanalyze` over-cap (~352-357): có `rec` (dòng ~334) → `rec["fields"]`; reason là chuỗi `f"Requester bổ sung..."`. Tính reason vào biến trước dict, rồi:
```python
            **dict(zip(("Email subject", "Email body"),
                       render_email("pic", rec["fields"], core=reason))),
```

(d) proposal rounds over-cap (~516-518): chỗ này có fields? Đọc lại — nếu không có sẵn fields, GET trước. Build reason, rồi thêm:
```python
            **dict(zip(("Email subject", "Email body"),
                       render_email("pic", <fields_var>, core=<reason_var>))),
```
(Implementer xác định biến fields/reason cục bộ tại site (d); nếu chưa có fields → `airtable("GET", f"{PROJECTS_TABLE}/{record_id}").get("fields", {})`.)

- [ ] **Step 9: Smoke import + pytest**

Run: `cd ClawAMC && python -c "import analysis, pipeline, email_templates" && python -m pytest tests/ -v`
Expected: import OK, không lỗi; toàn bộ test pass (gồm test_email_templates 6 passed + test deadline cũ).

- [ ] **Step 10: Commit + deploy**

```bash
cd ClawAMC && git add analysis.py pipeline.py
git commit -m "feat(email): wire 6 mail qua render_email + prompt bo_sung chỉ viết lõi"
git push   # develop -> Coolify auto-deploy sandbox
```
(Bước 1-3 + Task 2 chưa cắt automation → mail đang chạy KHÔNG gãy: automation cũ vẫn đọc field cũ. Field `Email subject/body` được ghi nhưng chưa ai đọc tới Task 4.)

---

## Task 4: Rewire 6 automation Airtable → đọc `Email subject/body` (manual)

**Files:** Không có code. Airtable UI > Automations. Làm **từng automation một** (rollback dễ).

**Interfaces:**
- Consumes: field `Email subject`/`Email body` (Task 1) đã được code (Task 3, đã deploy) ghi.

- [ ] **Step 1:** `Gửi proposal cho requester` — step Send email: Subject = `{Email subject}`, Body = `{Email body}`. Giữ recipient (Created by → Email) + attach File proposal. Test gửi thử 1 record `Chờ duyệt items`.
- [ ] **Step 2:** `Gửi brief cho requester` — tương tự, attach File brief design.
- [ ] **Step 3:** `Gửi plan cho PIC` — Subject/Body = field mới; recipient = PIC; attach File plan sản xuất.
- [ ] **Step 4:** `Báo PIC` — Subject/Body = field mới; recipient = PIC.
- [ ] **Step 5:** Automation gửi mail **bổ sung** + **clarify** (automation `Cần phản hồi để tiếp tục` hoặc tương đương phát hiện cờ `Gửi mail bổ sung`/`Gửi mail làm rõ`) — đổi Send email sang `{Email subject}`/`{Email body}`. **Xác minh đúng automation** trước khi sửa (mở xem trigger đọc cờ nào).
- [ ] **Step 6: Verify** — với mỗi automation: chạy thử (hoặc trigger live ở Task 6) → mail nhận được dùng subject/body/footer mới, đúng người nhận + đính kèm.

---

## Task 5: Mail #7 (quá hạn) — Run script trong automation scheduled (manual)

**Files:** Airtable UI > Automation `Quá hạn duyệt → báo requester`.

**Interfaces:**
- Consumes: bảng `Email Templates` (dòng `qua_han` + `footer`); field record (`Mã project`, `Tên project`, `Game`, `Created by`, `Deadline phê duyệt`).
- Produces: ghi `Email subject`/`Email body` vào từng record found trước khi Send email.

- [ ] **Step 1:** Trong repeating group (mỗi record found), thêm step **"Run script"** TRƯỚC step Send email. Input variable: `recordId` = id record hiện tại của group.

- [ ] **Step 2:** Script (dán nguyên, sửa tên table/field nếu khác):

```javascript
let inputConfig = input.config();
let projects = base.getTable("Projects");
let templates = base.getTable("Email Templates");

// đọc template qua_han + footer
let tq = await templates.selectRecordsAsync({fields: ["Mã", "Subject", "Body"]});
let map = {};
for (let r of tq.records) map[r.getCellValueAsString("Mã")] = {
  s: r.getCellValueAsString("Subject"), b: r.getCellValueAsString("Body")
};
let tpl = map["qua_han"] || {s: "[{{ma_project}}] Quá hạn duyệt", b: "Proposal quá hạn duyệt."};
let footer = (map["footer"] && map["footer"].b) || "Merch Agent · AMC Team · VNGGames";

// đọc record
let proj = await projects.selectRecordsAsync({
  fields: ["Mã project", "Tên project", "Game", "Created by", "Deadline phê duyệt"]
});
let rec = proj.getRecord(inputConfig.recordId);

function fmtDate(v){ if(!v) return ""; let d=new Date(v); return isNaN(d)?String(v):
  ("0"+d.getDate()).slice(-2)+"/"+("0"+(d.getMonth()+1)).slice(-2)+"/"+d.getFullYear(); }
let creator = rec.getCellValue("Created by");
let vars = {
  ma_project: rec.getCellValueAsString("Mã project"),
  ten_project: rec.getCellValueAsString("Tên project"),
  game: rec.getCellValueAsString("Game"),
  ten_nguoi_gui: (creator && creator.name) || "Anh/Chị",
  han_duyet: fmtDate(rec.getCellValue("Deadline phê duyệt")),
};
function sub(t){ return (t||"").replace(/\{\{(\w+)\}\}/g, (m,k)=> (k in vars)? vars[k] : m); }

let subject = sub(tpl.s);
let body = sub(tpl.b).trimEnd() + "\n\n" + sub(footer);
await projects.updateRecordAsync(inputConfig.recordId, {
  "Email subject": subject, "Email body": body
});
```

- [ ] **Step 3:** Step Send email đổi sang Subject = `{Email subject}`, Body = `{Email body}`; recipient giữ (Created by → Email).

- [ ] **Step 4: Test** — nút Test của Run script (chọn 1 record có Deadline phê duyệt quá khứ) → kiểm `Email subject/body` được ghi → Send email step preview đúng.

---

## Task 6: Live smoke 7 mail + cleanup

**Files:** Không có code. Sandbox (đã deploy Task 3).

- [ ] **Step 1:** Tạo các project test (game thật, vd PUBG/Gunny) đẩy lần lượt qua 7 trạng thái để bắn từng mail:
  - bo_sung: tạo project thiếu field → nhận mail bổ sung.
  - clarify: yêu cầu đặc biệt unmet → mail trao đổi.
  - proposal: đủ field → mail mời duyệt (kèm file).
  - plan: duyệt items → mail plan cho PIC (kèm file).
  - brief: bấm Bắt đầu design → mail brief (kèm file).
  - pic: ép escalate (vượt cap) → mail Báo PIC.
  - qua_han: set Deadline phê duyệt quá khứ → automation scheduled (hoặc test step) → mail quá hạn.
- [ ] **Step 2:** Với mỗi mail nhận được, verify: subject đúng format, body thay biến đúng, footer xuất hiện 1 lần, không còn chữ ký "Merch Agent — VNGGames" trùng lặp trong thân.
- [ ] **Step 3:** Sửa thử 1 dòng trong bảng `Email Templates` (vd Subject proposal) → re-trigger → mail phản ánh thay đổi (xác nhận PO self-service hoạt động, không cần deploy).
- [ ] **Step 4: Cleanup** — xoá project test. Cập nhật memory `merch-email-templates-plan` (DONE) + `merch-architecture` (thêm bảng Email Templates + cơ chế render). Cân nhắc xoá field `Mail bổ sung` (orphan) nếu chắc.

---

## Self-Review

**Spec coverage:**
- §3 bảng + 5 cột → Task 1. §3.1 cheatsheet 3 lớp → Task 1 Step 2/3/4. §4 biến + safe-substitute → Task 2 (`_build_vars`, `_sub`). §5 module + fallback → Task 2. §6.1 wiring 6 mail → Task 3. §6.2 #7 script → Task 5. §6.3 prompt LLM → Task 3 Step 1. §6.4 field cũ → Task 3 Step 2 (bỏ ghi Mail bổ sung) + Task 6 cleanup. §7 lỗi → Task 2 fallback/safe-sub. §8 test → Task 2 unit + Task 6 live. §9 thứ tự → Task 1→6. §10 footer seed + link → resolved (link dropped, ghi Global Constraints).
- Gap đã xử lý: `{{link}}` bỏ (Global Constraints). `{{ten_nguoi_gui}}` ← `Created by`.name (Task 2 `_build_vars`).

**Placeholder scan:** không có TBD/TODO. Site (d) Task 3 Step 8 để implementer xác định biến cục bộ — kèm hướng dẫn cụ thể (GET fields nếu thiếu), không phải placeholder mơ hồ.

**Type consistency:** `render_email(kind, fields, core) -> (str, str)` dùng nhất quán mọi call site; `_fetch_templates() -> dict[Mã->(subj,body)]`; key cột `Mã`/`Subject`/`Body` khớp Task 1 seed.
