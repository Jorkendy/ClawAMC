# Trang /guide — Hướng dẫn sử dụng agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm trang web tĩnh `/guide` hướng dẫn vận hành merch-agent theo quy trình Bước 1→5 (cho requester + PO/Merch PIC), và link chéo 2 chiều với 3 trang doc sẵn có.

**Architecture:** 1 file HTML tĩnh `docs/guide.html` (inline CSS, không JS bắt buộc) + 1 route `@app.get("/guide")` trong `main.py` (copy y khuôn route `/rules`). Thêm 1 nút "→ Hướng dẫn" (href `/guide`) vào 3 trang `flowchart.html`, `proposal-rules.html`, `email-guide.html`. Không đụng logic nghiệp vụ. Verify bằng pytest + FastAPI TestClient (đã có sẵn trong venv).

**Tech Stack:** Python 3.13, FastAPI 0.137 (`FileResponse`), pytest, `fastapi.testclient.TestClient`. HTML/CSS tĩnh.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-06-25-guide-page-design.md` — mọi tên field/status/email/ngưỡng trong trang **phải khớp** `config.py` / `pipeline.py` / `email_templates.py`, KHÔNG bịa giá trị.
- Ngôn ngữ: chỉ tiếng Việt. Không screenshot (dùng tên nút/field bằng chữ).
- Style: tái dùng `<style>` của `docs/proposal-rules.html` (dòng 7–37) để đồng bộ; bổ sung chip màu vai.
- Trục nội dung: theo **Bước (timeline 1→5)**; mỗi bước khuôn 6 phần (🎯 Mục tiêu → 🤖 Agent → 🟢 Requester → 🔵 PO/PIC → ✉️ Email → ⚠️ Ngoại lệ).
- Quy ước màu: 🟢 requester, 🔵 PO/PIC, 🤖 agent, ⚠️ ngoại lệ, ✉️ email.
- Bước 6 design review: ngoài phạm vi — chỉ ghi 1 dòng "sắp có".
- Commit message: kết thúc bằng dòng `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Lệnh test chạy bằng `venv/bin/python -m pytest` (pytest chỉ dùng cho dev, không nằm trong requirements.txt).
- Mọi đường dẫn file tính từ thư mục `ClawAMC/`.

**Giá trị thật phải xuất hiện trong trang (đã verify từ code):**
- Routes: `/proposal/{record_id}`, `/flowchart`, `/rules`, `/email-guide`, `/guide`.
- Email kinds: `clarify`, `bo_sung`, `proposal`, `qua_han`, `plan`, `brief`, `handoff_design`, `pic`.
- Statuses: `Chờ làm rõ yêu cầu`, `Chờ điều chỉnh`, `Chờ duyệt items`, `Đã duyệt items`, `Chờ duyệt brief`, `Chờ thiết kế`, `Chờ Merch PIC`, `Cần PIC xử lý`, `Đã duyệt`.
- Field người bấm: `Gửi phản hồi`, `Duyệt proposal?`, `Feedback proposal`, `Bắt đầu design`, `Duyệt brief?`, `Feedback brief`, `Brief tự upload`.
- Ngưỡng (đều mặc định 3): `MAX_CLARIFY_ROUNDS`, `MAX_PROPOSAL_ROUNDS`, `MAX_BRIEF_ROUNDS`, `PROPOSAL_APPROVAL_DAYS`.

---

### Task 1: Route `/guide` + trang `docs/guide.html` (nội dung đầy đủ)

**Files:**
- Create: `docs/guide.html`
- Modify: `main.py` (thêm route sau khối `/email-guide`, quanh dòng 110–117)
- Test: `tests/test_guide_page.py`

**Interfaces:**
- Consumes: `main.app` (FastAPI app đã khởi tạo), pattern `FileResponse(path, media_type="text/html")`.
- Produces: route `GET /guide` → 200 HTML; file `docs/guide.html` chứa toàn bộ giá trị thật ở Global Constraints.

- [ ] **Step 1: Viết test trước (smoke + đối chiếu nội dung)**

Tạo `tests/test_guide_page.py`:

```python
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

# Mọi giá trị dưới đây phải xuất hiện trong trang /guide — chống bịa/sót.
REQUIRED = [
    # anchors mục lục (7 mục)
    'id="buoc1"', 'id="buoc2"', 'id="buoc3"', 'id="buoc4"', 'id="buoc5"',
    'id="theo-doi"', 'id="faq"',
    # link chéo đầu trang
    'href="/flowchart"', 'href="/rules"', 'href="/email-guide"',
    # routes nhắc trong nội dung
    '/proposal/',
    # email kinds
    'clarify', 'bo_sung', 'proposal', 'qua_han', 'plan', 'brief',
    'handoff_design', 'pic',
    # statuses
    'Chờ làm rõ yêu cầu', 'Chờ điều chỉnh', 'Chờ duyệt items',
    'Đã duyệt items', 'Chờ duyệt brief', 'Chờ thiết kế',
    'Chờ Merch PIC', 'Cần PIC xử lý',
    # field người bấm
    'Gửi phản hồi', 'Duyệt proposal?', 'Feedback proposal',
    'Bắt đầu design', 'Duyệt brief?', 'Feedback brief', 'Brief tự upload',
    # ngưỡng
    'MAX_CLARIFY_ROUNDS', 'MAX_PROPOSAL_ROUNDS', 'MAX_BRIEF_ROUNDS',
    'PROPOSAL_APPROVAL_DAYS',
]


def test_guide_route_ok():
    r = client.get("/guide")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_guide_has_required_content():
    html = client.get("/guide").text
    missing = [s for s in REQUIRED if s not in html]
    assert not missing, f"Thiếu trong /guide: {missing}"
```

- [ ] **Step 2: Chạy test → xác nhận FAIL**

Run: `venv/bin/python -m pytest tests/test_guide_page.py -v`
Expected: FAIL — `test_guide_route_ok` trả 404 (chưa có route), `test_guide_has_required_content` lỗi vì 404 không có nội dung.

- [ ] **Step 3: Thêm route `/guide` vào `main.py`**

Chèn ngay sau khối route `/email-guide` (sau dòng `return FileResponse(_EMAIL_GUIDE, ...)`), trước `def _feedback_button`:

```python
_GUIDE = os.path.join(os.path.dirname(__file__), "docs", "guide.html")


@app.get("/guide")
def guide() -> FileResponse:
    """Huong dan su dung agent theo quy trinh (Buoc 1->5) cho requester + PO/PIC."""
    return FileResponse(_GUIDE, media_type="text/html")
```

- [ ] **Step 4: Tạo `docs/guide.html` — đầy đủ nội dung**

Tạo file HTML tĩnh. **Khuôn bắt buộc:**

1. `<!doctype html><html lang="vi"><head>` + `<meta charset>` + viewport + `<title>Merch Agent — Hướng dẫn sử dụng (Quy trình)</title>`.
2. `<style>`: **copy nguyên `<style>` block từ `docs/proposal-rules.html` (dòng 7–37)** rồi thêm các class chip vai:

```css
  .role{display:inline-block;padding:2px 9px;border-radius:6px;font-size:12px;font-weight:700;margin-right:6px}
  .r-req{background:#e6f4ea;color:#1a7f37}      /* requester */
  .r-pic{background:#e7eefc;color:#1d4ed8}      /* PO/PIC */
  .r-bot{background:#eef0f3;color:#475569}      /* agent */
  .r-warn{background:#fdecec;color:#b91c1c}     /* ngoại lệ */
  .r-mail{background:#f3e8ff;color:#7c3aed}     /* email */
  .toc{padding:14px 26px;font-size:14px}
  .toc a{color:#1d4ed8;text-decoration:none;margin-right:14px}
  .navtop a{display:inline-block;margin:10px 10px 0 0;background:rgba(255,255,255,.22);color:#fff;padding:6px 14px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600}
  .box{border:1px solid #e6e8ec;border-radius:10px;padding:12px 16px;margin:10px 0;background:#fafbfc}
  .box b{color:#1d4ed8}
```

3. `<header>`: tag "VNGGames · Merch Automation", `<h1>Hướng dẫn sử dụng Merch Agent</h1>`, đoạn "Trang này dành cho **requester** (người đặt merch) và **PO / Merch PIC** (vận hành)" + chú giải 5 chip vai, và hàng nút `.navtop` link: `href="/flowchart"` (Sơ đồ logic), `href="/rules"` (Quy tắc & ngưỡng), `href="/email-guide"` (Chỉnh email).
4. `<nav class="toc">`: 7 link neo `#buoc1`…`#buoc5`, `#theo-doi`, `#faq`.
5. **5 `<section>`** (id `buoc1`..`buoc5`), mỗi section dùng `.shead h2` + `.body`, theo khuôn 6 phần. Nội dung bám đúng spec mục "Thân bài" — dùng `.role` chip + `.box` cho hộp thao tác. Phải chứa các giá trị thật tương ứng từng bước:
   - **buoc1 Tiếp nhận & phân tích:** 7 field cốt lõi (REQUIRED_FIELDS), `Gửi phản hồi`, email `clarify`, Status `Chờ làm rõ yêu cầu`, `MAX_CLARIFY_ROUNDS`, escalate `Chờ Merch PIC`.
   - **buoc2 Đề xuất khả thi:** vòng điều chỉnh budget/deadline, Status `Chờ điều chỉnh`, email `bo_sung`, `MAX_PROPOSAL_ROUNDS`.
   - **buoc3 Duyệt proposal:** link `/proposal/{record_id}` (hộp thao tác), field `Duyệt proposal?` + `Feedback proposal`, email `proposal` + `qua_han`, `PROPOSAL_APPROVAL_DAYS`, kết `Đã duyệt items`, Status `Chờ duyệt items`.
   - **buoc4 Plan sản xuất:** mô tả đầy đủ — agent sinh Excel plan + lead-time (song song → max), email `plan`.
   - **buoc5 Brief design & bàn giao:** nút `Bắt đầu design`, Status `Chờ duyệt brief`, field `Duyệt brief?` `Feedback brief` `Brief tự upload`, email `brief` → `handoff_design` (PIC+requester), `MAX_BRIEF_ROUNDS`, kết `Chờ thiết kế` + 1 dòng "Bước 6 design review sắp có".
6. **`<section id="theo-doi">` 📊 Theo dõi tiến độ:** đọc trạng thái qua interface Kanban (theo Status) / Stepper / Timeline (Gantt theo Step Log) + kho "Tài liệu dự án" (version).
7. **`<section id="faq">` 🛠 Sự cố thường gặp:** dùng class `.faq` (đã có sẵn trong style). Tối thiểu 4 mục: mail không tới; LLM lỗi → `Cần PIC xử lý` (email `pic`, field `Lý do cần PIC`); link Fillout sai `?id=`; bảng nghĩa các Status (liệt kê đủ status ở Global Constraints, gồm `Đã duyệt`).
8. `<footer>`: "VNGGames Merch Automation · cập nhật 25/06/2026" + link lại `/rules`, `/email-guide`.

Đóng `</div></body></html>`.

- [ ] **Step 5: Chạy test → xác nhận PASS**

Run: `venv/bin/python -m pytest tests/test_guide_page.py -v`
Expected: PASS cả 2 test (nếu `test_guide_has_required_content` báo `missing`, bổ sung đúng chuỗi còn thiếu vào `docs/guide.html`).

- [ ] **Step 6: Chạy full suite (không hồi quy)**

Run: `venv/bin/python -m pytest -q`
Expected: tất cả test cũ vẫn PASS + 2 test mới PASS.

- [ ] **Step 7: Commit**

```bash
git add docs/guide.html main.py tests/test_guide_page.py
git commit -m "$(printf 'feat(guide): trang /guide huong dan quy trinh Buoc 1-5 + smoke test\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 2: Link chéo 2 chiều — nút "→ Hướng dẫn" ở 3 trang doc

**Files:**
- Modify: `docs/flowchart.html`, `docs/proposal-rules.html`, `docs/email-guide.html`
- Test: `tests/test_guide_page.py` (mở rộng)

**Interfaces:**
- Consumes: 3 file HTML tĩnh sẵn có.
- Produces: mỗi file chứa `href="/guide"` để điều hướng về hub.

- [ ] **Step 1: Mở rộng test — xác nhận FAIL**

Thêm vào cuối `tests/test_guide_page.py`:

```python
import os

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")


def test_cross_links_to_guide():
    for name in ("flowchart.html", "proposal-rules.html", "email-guide.html"):
        with open(os.path.join(DOCS, name), encoding="utf-8") as f:
            assert 'href="/guide"' in f.read(), f"{name} thiếu link → /guide"
```

Run: `venv/bin/python -m pytest tests/test_guide_page.py::test_cross_links_to_guide -v`
Expected: FAIL — 3 file chưa có `href="/guide"`.

- [ ] **Step 2: Thêm nút "→ Hướng dẫn" vào mỗi trang**

Vào phần header/đầu thân của từng file, thêm 1 link `href="/guide"` nhãn "→ Hướng dẫn sử dụng". Bám style sẵn có của mỗi trang:
- `docs/proposal-rules.html`: trong `header`, ngay sau dòng `.meta` (dùng cùng kiểu link trắng nền mờ như header). Ví dụ chèn vào `<div class="meta">…</div>` thêm `· <a href="/guide" style="color:#fff;text-decoration:underline">→ Hướng dẫn sử dụng</a>`.
- `docs/email-guide.html`: thêm tương tự trong header (link inline `href="/guide"`).
- `docs/flowchart.html`: trong header/meta (đã có link `/rules` ở dòng 45 — thêm cạnh đó `· <a href="/guide" style="color:#fff;text-decoration:underline">→ Hướng dẫn</a>`).

Chỉ thêm 1 link mỗi file — không sửa nội dung khác (surgical).

- [ ] **Step 3: Chạy test → PASS**

Run: `venv/bin/python -m pytest tests/test_guide_page.py -v`
Expected: cả 3 test PASS.

- [ ] **Step 4: Full suite**

Run: `venv/bin/python -m pytest -q`
Expected: toàn bộ PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/flowchart.html docs/proposal-rules.html docs/email-guide.html tests/test_guide_page.py
git commit -m "$(printf 'feat(guide): link cheo -> /guide tu flowchart/rules/email-guide\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Deploy (sau khi 2 task xong)

`/guide` là route + file tĩnh → deploy như mọi thay đổi khác: `git push origin develop` → Coolify build (~1–3 phút) → mở `https://<sandbox-host>/guide` kiểm tra hiển thị + click 3 nút link chéo + nút "→ Hướng dẫn" ở 3 trang kia. Đây là bước thủ công, không tự động.

## Notes thực thi

- Test `test_guide_has_required_content` là **lưới an toàn chống bịa/sót** — nếu sau này đổi tên status/field/ngưỡng trong code mà quên cập nhật trang, test này (cùng list REQUIRED) sẽ nhắc. Khi đổi giá trị thật, cập nhật cả `docs/guide.html` lẫn list `REQUIRED`.
- Không thêm dependency mới (fastapi/pytest/testclient đã có trong venv).
