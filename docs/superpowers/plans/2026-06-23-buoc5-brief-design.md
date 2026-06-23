# Bước 5 — Brief Design Generator (deck PPTX) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sau khi requester duyệt items, PIC bấm nút "Bắt đầu design" → agent tự sinh deck PowerPoint brief design (enrich AI, fill gap + gắn nhãn nguồn) → upload + mail requester.

**Architecture:** Module mới `brief.py` (2 hàm thuần: `build_brief_content` gọi 1 LLM call enrich nội dung; `render_brief_pptx` dùng python-pptx render deck). Pipeline thêm `_scan_design_starts` (quét cờ checkbox) + `_generate_brief` (orchestrate). Tái dùng `game_insight`, image cache, `_upload_attachment` sẵn có.

**Tech Stack:** Python 3.13, FastAPI, python-pptx, openai SDK (LLM qua LiteLLM self-host), Airtable REST.

## Global Constraints

- Spec gốc: [docs/superpowers/specs/2026-06-23-buoc5-brief-design.md](../specs/2026-06-23-buoc5-brief-design.md) — đọc kèm.
- Base Airtable `appo1Oei5JvJ1EXAG`, Projects table `tbltWsCRFMDAkpKKc`.
- **Field-id đã tạo sẵn** (không cần tạo lại): `File brief design`=`fldfqeqkVAegySzZ5`, `Bắt đầu design`=`fldknUO4dtxgyRoLs`, `Logo game`=`fldDQFLogtbXzLzen`, `Key Visual (KV)`=`fldGnHaTuaIrTSfrK`, `Source material`=`fldZooXpWQKaCOiOz`.
- Agent đọc field Airtable **theo TÊN** (vd `fields.get("Logo game")`); field-id chỉ cần cho Upload Attachment API + config.
- Test: **isolation script** chạy `./venv/bin/python` từ thư mục `ClawAMC/` (repo KHÔNG dùng pytest). Stub network/LLM. Xoá script sau khi chạy.
- KHÔNG escalate PIC khi brief lỗi (brief không chặn luồng chính).
- Deck **không designer-grade** — bản nháp cho M&D. Item creative giá null vẫn ra brief (giá để vendor sau).
- Secrets: không in key; không đọc `.env` trực tiếp (đã `load_dotenv` trong config).
- Commit chỉ khi user yêu cầu — các step "Commit" bên dưới chạy khi user đã đồng ý commit.

---

### Task 1: Dependency + config field-id

**Files:**
- Modify: `requirements.txt`
- Modify: `config.py` (sau dòng `PLAN_FILE_FIELD_ID`)

**Interfaces:**
- Produces: `config.BRIEF_FILE_FIELD_ID: str`

- [ ] **Step 1: Thêm python-pptx vào requirements**

Sửa `requirements.txt`, thêm dòng cuối:
```
python-pptx
```

- [ ] **Step 2: Cài python-pptx vào venv (cho test local)**

Run: `./venv/bin/python -m pip install python-pptx -q`
Expected: cài xong, không lỗi.

- [ ] **Step 3: Thêm BRIEF_FILE_FIELD_ID vào config.py**

Sau dòng `PLAN_FILE_FIELD_ID = os.environ.get(...)`:
```python
# Field id "File brief design" (Buoc 5) — Airtable Upload Attachment API (base appo1Oei5JvJ1EXAG)
BRIEF_FILE_FIELD_ID = os.environ.get("BRIEF_FILE_FIELD_ID", "fldfqeqkVAegySzZ5")
```

- [ ] **Step 4: Verify import**

Run: `./venv/bin/python -c "import config; print(config.BRIEF_FILE_FIELD_ID); import pptx; print('pptx', pptx.__version__)"`
Expected: in `fldfqeqkVAegySzZ5` + version pptx, không lỗi.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt config.py
git commit -m "feat(brief): add python-pptx dep + BRIEF_FILE_FIELD_ID config"
```

---

### Task 2: `brief.py` — enrichment LLM (`build_brief_content`)

**Files:**
- Create: `brief.py`
- Test: `_test_brief_content.py` (tạm, xoá sau)

**Interfaces:**
- Consumes: `proposal.game_insight(game) -> str`, `llm_client.ask_llm_json(prompt, max_tokens) -> dict`
- Produces: `brief.build_brief_content(fields: dict, items: list, asset_status: dict, insight: str) -> dict`
  - return `{"collection_name": str, "overview": str, "asset_status": str, "items": [{"ten","loai","idea","design_direction","chat_lieu","kich_thuoc","yeu_cau_dac_biet":[str],"print_spec","references":[str],"sources":{...}}]}`
  - `asset_status` param: `{"logo": bool, "kv": bool, "source": bool}`

- [ ] **Step 1: Viết test isolation (mock LLM)**

Tạo `_test_brief_content.py`:
```python
import brief
brief.game_insight = lambda game: "Insight: genZ, tông tím/đỏ, nhân vật agent."
brief.ask_llm_json = lambda prompt, max_tokens=2500: {
    "collection_name": "Bộ quà PUBG 2026",
    "overview": "Bộ quà streetwear cho genZ.",
    "asset_status": "Có logo, chưa có KV.",
    "items": [{
        "ten": "Áo thun cotton", "loai": "Áo thun",
        "idea": "Áo daily, vibe gaming.", "design_direction": "Tông tối, logo ngực trái.",
        "chat_lieu": "Cotton 2 chiều", "kich_thuoc": "Freesize",
        "yeu_cau_dac_biet": ["Thêu logo"], "print_spec": "In lụa 2 màu, file vector AI",
        "references": ["https://drive..."],
        "sources": {"idea": "ai", "design_direction": "ai", "chat_lieu": "requester",
                    "kich_thuoc": "ai", "print_spec": "ai"}
    }]
}
fields = {"Game": "PUBG", "Mục đích": "Tri ân", "Chủ đề": "5 năm", "Target audience": "genZ",
          "Yêu cầu đặc biệt": "Thêu logo"}
items = [{"ten": "Áo thun cotton", "loai": "Áo thun", "nguon": "catalogue",
          "chat_lieu": "Cotton 2 chiều", "kich_thuoc": "Freesize", "so_luong": 200,
          "yeu_cau_dac_biet": "Thêu logo", "goi_y_anh": None, "design_link": None, "item_key": True}]
b = brief.build_brief_content(fields, items, {"logo": True, "kv": False, "source": False}, brief.game_insight("PUBG"))
assert b["collection_name"], "thiếu collection_name"
assert len(b["items"]) == 1, "sai số item"
it = b["items"][0]
for k in ("ten","idea","design_direction","chat_lieu","kich_thuoc","yeu_cau_dac_biet","print_spec","references","sources"):
    assert k in it, f"thiếu key {k}"
assert isinstance(it["yeu_cau_dac_biet"], list) and isinstance(it["references"], list)
assert it["sources"].get("idea") in ("ai", "requester")
print("PASS build_brief_content")
```

- [ ] **Step 2: Chạy test — kỳ vọng FAIL (chưa có brief.py)**

Run: `cd /Users/vinhphamtrung/Personal/hackathon/ClawAMC && cp _test_brief_content.py . && ./venv/bin/python _test_brief_content.py`
Expected: FAIL `ModuleNotFoundError: No module named 'brief'`.

- [ ] **Step 3: Viết `brief.py` (phần content engine)**

Tạo `brief.py`:
```python
"""Buoc 5 — Brief Design generator. build_brief_content (enrich LLM) + render_brief_pptx (python-pptx).

AI nhap -> M&D hoan thien. Chu dong fill gap khi input ngheo + GAN NHAN nguon (requester|ai)
de M&D biet cai nao la gia dinh. Khong bia chi tiet logo/KV brand cu the.
"""
import io
import json

from llm_client import ask_llm_json
from proposal import game_insight

BRIEF_PROMPT = """Bạn là chuyên gia brief design merchandise game. Soạn BRIEF DESIGN cho bộ quà dưới đây \
để đội M&D/đối tác design. Đây là BẢN NHÁP định hướng — bạn CHỦ ĐỘNG đề xuất khi thiếu thông tin, \
nhưng PHẢI gắn nhãn nguồn từng phần: "requester" (lấy từ dữ liệu requester cung cấp) hoặc "ai" (bạn suy luận/đề xuất).

QUY TẮC:
- Định hướng visual suy từ INSIGHT GAME + loại item. TUYỆT ĐỐI KHÔNG bịa chi tiết logo/KV/brand cụ thể \
(màu mã hex thật, vị trí logo chính xác) — chỉ gợi ý hướng, đánh "ai".
- Trường nào requester đã ghi rõ (chất liệu, kích thước, yêu cầu đặc biệt) → giữ nguyên, đánh "requester".
- "print_spec": gợi ý vùng in / số màu / định dạng file cần (vd "file vector AI", "file mockup") theo loại item.
- "references": gom link requester đưa (trong yêu cầu/design_link) + loại tài liệu tham khảo nên có (đánh "ai").
- Tiếng Việt, ngắn gọn, đúng trọng tâm cho designer.

THÔNG TIN BỘ QUÀ:
- Game: {game}
- Mục đích: {muc_dich}
- Chủ đề: {chu_de}
- Đối tượng: {target}
- Yêu cầu đặc biệt chung: {yeu_cau}
- Trạng thái asset: {asset_status}

INSIGHT GAME (định hướng visual khách quan):
{insight}

CÁC ITEM ĐÃ CHỐT:
{items_block}

JSON schema (CHỈ trả JSON, không text thừa):
{{"collection_name": str, "overview": str, "asset_status": str, "items": [{{"ten": str, "loai": str, \
"idea": str, "design_direction": str, "chat_lieu": str, "kich_thuoc": str, "yeu_cau_dac_biet": [str], \
"print_spec": str, "references": [str], "sources": {{"idea": "requester"|"ai", "design_direction": "requester"|"ai", \
"chat_lieu": "requester"|"ai", "kich_thuoc": "requester"|"ai", "print_spec": "requester"|"ai"}}}}]}}"""


def _items_block(items: list) -> str:
    lines = []
    for it in items:
        key = " ⭐" if it.get("item_key") else ""
        lines.append(
            f"- {it.get('ten','')}{key} | loại: {it.get('loai','')} | nguồn: {it.get('nguon','')} "
            f"| chất liệu: {it.get('chat_lieu') or '(chưa có)'} | kích thước: {it.get('kich_thuoc') or '(chưa có)'} "
            f"| SL: {it.get('so_luong') or '?'} | yêu cầu: {it.get('yeu_cau_dac_biet') or '(không)'} "
            f"| design link: {it.get('design_link') or '(không)'}")
    return "\n".join(lines)


def _asset_status_text(asset_status: dict) -> str:
    parts = []
    parts.append("Logo: " + ("đã có" if asset_status.get("logo") else "CHƯA có"))
    parts.append("KV: " + ("đã có" if asset_status.get("kv") else "CHƯA có"))
    parts.append("Source: " + ("đã có" if asset_status.get("source") else "CHƯA có"))
    return " · ".join(parts)


def build_brief_content(fields: dict, items: list, asset_status: dict, insight: str) -> dict:
    """Goi 1 LLM call enrich noi dung brief. Tra dict theo schema (xem docstring module/spec)."""
    prompt = BRIEF_PROMPT.format(
        game=fields.get("Game") or "(chưa rõ)",
        muc_dich=fields.get("Mục đích") or "(chưa rõ)",
        chu_de=fields.get("Chủ đề") or "(chưa rõ)",
        target=fields.get("Target audience") or "(chưa rõ)",
        yeu_cau=fields.get("Yêu cầu đặc biệt") or "(không)",
        asset_status=_asset_status_text(asset_status),
        insight=insight or "(không có insight)",
        items_block=_items_block(items),
    )
    data = ask_llm_json(prompt, max_tokens=3000)
    # chuan hoa toi thieu (chong thieu key lam vo render)
    data.setdefault("collection_name", fields.get("Chủ đề") or "Bộ quà merch")
    data.setdefault("overview", "")
    data.setdefault("asset_status", _asset_status_text(asset_status))
    out_items = []
    for it in data.get("items", []):
        it.setdefault("ten", "")
        it.setdefault("loai", "")
        for k in ("idea", "design_direction", "chat_lieu", "kich_thuoc", "print_spec"):
            it.setdefault(k, "")
        if not isinstance(it.get("yeu_cau_dac_biet"), list):
            it["yeu_cau_dac_biet"] = []
        if not isinstance(it.get("references"), list):
            it["references"] = []
        if not isinstance(it.get("sources"), dict):
            it["sources"] = {}
        out_items.append(it)
    data["items"] = out_items
    return data
```

- [ ] **Step 4: Chạy test — kỳ vọng PASS**

Run: `./venv/bin/python _test_brief_content.py`
Expected: `PASS build_brief_content`.

- [ ] **Step 5: Dọn test + commit**

```bash
rm -f _test_brief_content.py
git add brief.py
git commit -m "feat(brief): add build_brief_content enrichment LLM"
```

---

### Task 3: `brief.py` — render deck (`render_brief_pptx` + gather images)

**Files:**
- Modify: `brief.py`
- Test: `_test_brief_render.py` (tạm, xoá sau)

**Interfaces:**
- Consumes: `proposal.catalogue_data() -> (str, dict)`, `proposal._build_images(items, by_name) -> dict` (map ten→data-URI)
- Produces:
  - `brief.gather_images(items: list) -> dict[str, bytes]` (map ten item → PNG bytes)
  - `brief.render_brief_pptx(brief_data: dict, images: dict, project: dict) -> bytes`
    - `project`: `{"code","name","game","so_luong","deadline","logo_png": bytes|None}`

- [ ] **Step 1: Viết test isolation render**

Tạo `_test_brief_render.py`:
```python
import brief
brief_data = {
    "collection_name": "Bộ quà PUBG 2026", "overview": "Streetwear genZ.",
    "asset_status": "Logo: đã có · KV: CHƯA có · Source: CHƯA có",
    "items": [
        {"ten": "Áo thun cotton", "loai": "Áo thun", "idea": "Áo daily.",
         "design_direction": "Tông tối, logo ngực.", "chat_lieu": "Cotton", "kich_thuoc": "Freesize",
         "yeu_cau_dac_biet": ["Thêu logo"], "print_spec": "In lụa 2 màu, file vector AI",
         "references": ["https://drive.example"],
         "sources": {"idea": "ai", "design_direction": "ai", "chat_lieu": "requester",
                     "kich_thuoc": "ai", "print_spec": "ai"}},
        {"ten": "Móc khóa Spike", "loai": "Móc khóa", "idea": "Quà nhỏ.",
         "design_direction": "Hình Spike 3D.", "chat_lieu": "PVC", "kich_thuoc": "5cm",
         "yeu_cau_dac_biet": [], "print_spec": "File AI", "references": [],
         "sources": {"idea": "ai", "design_direction": "ai", "chat_lieu": "ai",
                     "kich_thuoc": "requester", "print_spec": "ai"}},
    ],
}
project = {"code": "MERCH-T1", "name": "[TEST] PUBG", "game": "PUBG", "so_luong": 200,
           "deadline": "2026-10-31", "logo_png": None}
data = brief.render_brief_pptx(brief_data, {}, project)
assert data[:2] == b"PK", "không phải file pptx (zip)"
open("/tmp/brief_test.pptx", "wb").write(data)
from pptx import Presentation
prs = Presentation("/tmp/brief_test.pptx")
# cover + 2 item = 3 slide
assert len(prs.slides._sldIdLst) == 3, f"sai số slide: {len(prs.slides._sldIdLst)}"
print("PASS render_brief_pptx, slides =", len(prs.slides._sldIdLst))
```

- [ ] **Step 2: Chạy test — kỳ vọng FAIL (chưa có render_brief_pptx)**

Run: `cp _test_brief_render.py . && ./venv/bin/python _test_brief_render.py`
Expected: FAIL `AttributeError: module 'brief' has no attribute 'render_brief_pptx'`.

- [ ] **Step 3: Thêm imports + gather_images + render_brief_pptx vào `brief.py`**

Đầu file `brief.py`, thêm vào khối import:
```python
import base64

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from proposal import _build_images, catalogue_data
```

Cuối file `brief.py`, thêm:
```python
# ---------- gather images (tai dung cache proposal) ----------
def gather_images(items: list) -> dict:
    """Map {ten item -> PNG bytes}. Tai dung proposal._build_images (data-URI) roi tach bytes."""
    _, by_name = catalogue_data()
    uri_map = _build_images(items, by_name)  # {ten -> "data:image/...;base64,..." hoac data-uri}
    out = {}
    for name, uri in uri_map.items():
        try:
            b64 = uri.split(",", 1)[1] if "," in uri else uri
            out[name] = base64.b64decode(b64)
        except Exception:
            continue
    return out


# ---------- render pptx ----------
_C_BG = RGBColor(0x1A, 0x1A, 0x2E)
_C_ACCENT = RGBColor(0xFF, 0x3D, 0x57)
_C_REQ = RGBColor(0x1A, 0x7F, 0x37)     # xanh = requester
_C_AI = RGBColor(0xD9, 0x77, 0x06)      # cam = AI goi y
_C_TEXT = RGBColor(0x1A, 0x1A, 0x2E)
_C_MUTE = RGBColor(0x6B, 0x72, 0x80)


def _tag(source: str) -> tuple:
    return ("(Từ requester)", _C_REQ) if source == "requester" else ("(AI gợi ý)", _C_AI)


def _section(tf, heading: str, body: str, source: str | None, first: bool = False):
    """Them 1 muc vao text frame: heading dam + tag nguon mau + body."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    r = p.add_run(); r.text = heading + "  "
    r.font.bold = True; r.font.size = Pt(12); r.font.color.rgb = _C_TEXT
    if source:
        label, color = _tag(source)
        rt = p.add_run(); rt.text = label
        rt.font.size = Pt(9); rt.font.color.rgb = color; rt.font.italic = True
    pb = tf.add_paragraph()
    rb = pb.add_run(); rb.text = body or "—"
    rb.font.size = Pt(11); rb.font.color.rgb = _C_TEXT
    pb.space_after = Pt(6)


def _cover(prs, brief_data: dict, project: dict):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    band = s.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(2.2))
    band.fill.solid(); band.fill.fore_color.rgb = _C_BG; band.line.fill.background()
    tf = band.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.6); tf.margin_top = Inches(0.4)
    p = tf.paragraphs[0]; r = p.add_run(); r.text = brief_data.get("collection_name", "Brief Design")
    r.font.size = Pt(30); r.font.bold = True; r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    p2 = tf.add_paragraph(); r2 = p2.add_run()
    r2.text = f"BRIEF DESIGN · {project.get('game','')} · {project.get('code','')}"
    r2.font.size = Pt(13); r2.font.color.rgb = RGBColor(0xFF, 0xC1, 0xC9)

    box = s.shapes.add_textbox(Inches(0.6), Inches(2.5), Inches(12), Inches(4.5))
    tf2 = box.text_frame; tf2.word_wrap = True
    info = [
        ("Tổng quan", brief_data.get("overview", "")),
        ("Thông tin", f"Số lượng: {project.get('so_luong','?')} · Deadline: {project.get('deadline','?')}"),
        ("Trạng thái asset", brief_data.get("asset_status", "")),
    ]
    first = True
    for h, b in info:
        _section(tf2, h, b, None, first=first); first = False
    pl = tf2.add_paragraph(); pl.space_before = Pt(10)
    rl = pl.add_run(); rl.text = "Chú giải:  "
    rl.font.size = Pt(10); rl.font.bold = True
    r_req = pl.add_run(); r_req.text = "(Từ requester) "; r_req.font.size = Pt(10); r_req.font.color.rgb = _C_REQ
    r_ai = pl.add_run(); r_ai.text = " (AI gợi ý)"; r_ai.font.size = Pt(10); r_ai.font.color.rgb = _C_AI
    if project.get("logo_png"):
        try:
            s.shapes.add_picture(io.BytesIO(project["logo_png"]), Inches(10.8), Inches(0.4),
                                 height=Inches(1.3))
        except Exception:
            pass


def _item_slide(prs, it: dict, img: bytes | None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bar = s.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(0.9))
    bar.fill.solid(); bar.fill.fore_color.rgb = _C_ACCENT; bar.line.fill.background()
    tf = bar.text_frame; tf.margin_left = Inches(0.5)
    p = tf.paragraphs[0]; r = p.add_run()
    r.text = f"{it.get('ten','')}   ·   {it.get('loai','')}"
    r.font.size = Pt(20); r.font.bold = True; r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    has_img = bool(img)
    text_w = Inches(7.4) if has_img else Inches(12.2)
    box = s.shapes.add_textbox(Inches(0.5), Inches(1.2), text_w, Inches(5.9))
    bt = box.text_frame; bt.word_wrap = True
    src = it.get("sources", {})
    _section(bt, "IDEA", it.get("idea", ""), src.get("idea"), first=True)
    _section(bt, "ĐỊNH HƯỚNG DESIGN", it.get("design_direction", ""), src.get("design_direction"))
    _section(bt, "Chất liệu", it.get("chat_lieu", ""), src.get("chat_lieu"))
    _section(bt, "Kích thước", it.get("kich_thuoc", ""), src.get("kich_thuoc"))
    yc = it.get("yeu_cau_dac_biet") or []
    _section(bt, "Yêu cầu đặc biệt", ("; ".join(yc) if yc else "Không"), None)
    _section(bt, "Print spec / file cần", it.get("print_spec", ""), src.get("print_spec"))
    refs = it.get("references") or []
    _section(bt, "References", ("\n".join(refs) if refs else "—"), None)

    if has_img:
        try:
            s.shapes.add_picture(io.BytesIO(img), Inches(8.1), Inches(1.3), width=Inches(4.7))
            cap = s.shapes.add_textbox(Inches(8.1), Inches(6.1), Inches(4.7), Inches(0.5))
            rc = cap.text_frame.paragraphs[0].add_run()
            rc.text = "Hình minh hoạ ý tưởng — AI tạo, chưa phải mẫu cuối"
            rc.font.size = Pt(8); rc.font.italic = True; rc.font.color.rgb = _C_MUTE
        except Exception:
            pass


def render_brief_pptx(brief_data: dict, images: dict, project: dict) -> bytes:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    _cover(prs, brief_data, project)
    for it in brief_data.get("items", []):
        _item_slide(prs, it, (images or {}).get(it.get("ten", "")))
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Chạy test — kỳ vọng PASS**

Run: `./venv/bin/python _test_brief_render.py`
Expected: `PASS render_brief_pptx, slides = 3`.

- [ ] **Step 5: Dọn + commit**

```bash
rm -f _test_brief_render.py
git add brief.py
git commit -m "feat(brief): add render_brief_pptx + gather_images"
```

---

### Task 4: `upload_brief` trong proposal_render.py

**Files:**
- Modify: `proposal_render.py` (import + thêm hàm cạnh `upload_plan`)

**Interfaces:**
- Consumes: `proposal_render._upload_attachment(record_id, field_id, content_type, filename, raw) -> dict`, `config.BRIEF_FILE_FIELD_ID`
- Produces: `proposal_render.upload_brief(record_id: str, pptx: bytes, code: str) -> dict`

- [ ] **Step 1: Thêm BRIEF_FILE_FIELD_ID vào import config**

Sửa dòng import config trong `proposal_render.py`:
```python
from config import (AIRTABLE_BASE_ID, AIRTABLE_TOKEN, BRIEF_FILE_FIELD_ID,
                    PLAN_FILE_FIELD_ID, PROPOSAL_FILE_FIELD_ID)
```

- [ ] **Step 2: Thêm hàm upload_brief (sau upload_plan)**

```python
def upload_brief(record_id: str, pptx: bytes, code: str) -> dict:
    """Upload deck brief design (.pptx) vao field 'File brief design' (Buoc 5)."""
    return _upload_attachment(
        record_id, BRIEF_FILE_FIELD_ID,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        f"brief_design_{code}.pptx", pptx)
```

- [ ] **Step 3: Verify import**

Run: `./venv/bin/python -c "import proposal_render; print(hasattr(proposal_render,'upload_brief'))"`
Expected: `True`.

- [ ] **Step 4: Commit**

```bash
git add proposal_render.py
git commit -m "feat(brief): add upload_brief attachment helper"
```

---

### Task 5: Pipeline wiring — `_generate_brief` + `_scan_design_starts`

**Files:**
- Modify: `pipeline.py` (imports + helpers + hook vào handle_proposal_decisions)
- Test: `_test_brief_pipeline.py` (tạm, xoá sau)

**Interfaces:**
- Consumes: `brief.build_brief_content`, `brief.render_brief_pptx`, `brief.gather_images`, `proposal.game_insight`, `proposal_render.upload_brief`, `airtable`, `fetch_projects`, `update_project`, `append_note`
- Produces: `pipeline._gather_brief_inputs(fields, record_id) -> tuple(items, asset_status, insight, logo_png)`, `pipeline._generate_brief(record_id, code)`, `pipeline._scan_design_starts()`

- [ ] **Step 1: Test isolation cho _gather_brief_inputs (mock)**

Tạo `_test_brief_pipeline.py`:
```python
import json
import pipeline
# stub network deps
pipeline.game_insight = lambda g: "insight stub"
pipeline._download_bytes = lambda url: b"PNGSTUB" if url else None
fields = {
    "Proposal JSON": json.dumps([{"ten": "Áo", "loai": "Áo thun", "nguon": "catalogue",
                                  "so_luong": 100, "don_gia": 50000}], ensure_ascii=False),
    "Game": "PUBG",
    "Logo game": [{"url": "http://x/logo.png"}],
    "Key Visual (KV)": [],
}
items, asset_status, insight, logo = pipeline._gather_brief_inputs(fields, "rec1")
assert len(items) == 1 and items[0]["ten"] == "Áo", "items sai"
assert asset_status == {"logo": True, "kv": False, "source": False}, asset_status
assert insight == "insight stub"
assert logo == b"PNGSTUB", "logo bytes sai"
print("PASS _gather_brief_inputs")
```

- [ ] **Step 2: Chạy — kỳ vọng FAIL (chưa có hàm)**

Run: `cp _test_brief_pipeline.py . && ./venv/bin/python _test_brief_pipeline.py`
Expected: FAIL `AttributeError ... _gather_brief_inputs`.

- [ ] **Step 3: Thêm imports vào pipeline.py**

Sửa khối import:
```python
import urllib.request
```
(thêm cạnh các import chuẩn nếu chưa có) và thêm:
```python
from brief import build_brief_content, gather_images, render_brief_pptx
from proposal import game_insight, propose_items_for
from proposal_render import build_proposal_html, upload_brief, upload_plan, upload_proposal
```
(gộp `game_insight` vào dòng `from proposal import ...` hiện có; gộp `upload_brief` vào dòng `from proposal_render import ...`.)

- [ ] **Step 4: Thêm helpers + scan vào pipeline.py (sau `_generate_plan`)**

```python
def _download_bytes(url: str) -> bytes | None:
    """Tai 1 file ve bytes (logo asset). Loi -> None (khong chan brief)."""
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.read()
    except Exception as e:
        print(f"[brief] tải asset lỗi: {e}")
        return None


def _gather_brief_inputs(fields: dict, record_id: str):
    """Gom input cho brief: items (Proposal JSON -> fallback Items), trang thai asset, insight, logo bytes."""
    items = _plan_items_from_fields(fields, record_id)
    asset_status = {
        "logo": bool(fields.get("Logo game")),
        "kv": bool(fields.get("Key Visual (KV)")),
        "source": bool(fields.get("Source material")),
    }
    insight = game_insight(fields.get("Game") or "")
    logo_atts = fields.get("Logo game") or []
    logo_png = _download_bytes(logo_atts[0].get("url")) if logo_atts else None
    return items, asset_status, insight, logo_png


def _generate_brief(record_id: str, code: str) -> None:
    """Buoc 5: sinh deck brief design -> upload -> clear co. Loi KHONG escalate PIC."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    fields = rec.get("fields", {})
    items, asset_status, insight, logo_png = _gather_brief_inputs(fields, record_id)
    brief_data = build_brief_content(fields, items, asset_status, insight)
    images = gather_images(items)
    project = {
        "code": fields.get("Mã project") or code, "name": fields.get("Tên project") or "",
        "game": fields.get("Game") or "", "so_luong": fields.get("Số lượng (bộ/suất)") or "?",
        "deadline": (str(fields.get("Deadline cần hàng"))[:10] if fields.get("Deadline cần hàng") else "?"),
        "logo_png": logo_png,
    }
    pptx = render_brief_pptx(brief_data, images, project)
    upload_brief(record_id, pptx, code)
    update_project(record_id, {"Bắt đầu design": False})
    append_note(record_id, f"[AI] Đã sinh brief design ({len(brief_data.get('items', []))} item).",
                field=HISTORY_FIELD)
    print(f"[brief] {code} -> brief design uploaded")


def _scan_design_starts() -> None:
    """Quet record bam nut 'Bat dau design' (co=TRUE + Da duyet items) -> sinh brief."""
    for r in fetch_projects("AND({Bắt đầu design} = TRUE(), {Status} = 'Đã duyệt items')"):
        f = r["fields"]
        code = f.get("Mã project", r["id"])
        try:
            _generate_brief(r["id"], code)
        except Exception as e:
            update_project(r["id"], {"Bắt đầu design": False})
            append_note(r["id"], f"[AI] Sinh brief design lỗi (đã clear cờ, bấm lại được): {e}",
                        field=HISTORY_FIELD)
            print(f"[brief] {code} sinh brief lỗi: {e}")
```

- [ ] **Step 5: Hook `_scan_design_starts` vào handle_proposal_decisions**

Trong `handle_proposal_decisions` (hàm `_run_guarded(_decide_lock, _decide_again, _scan_decisions)`), đổi để chạy thêm scan design. Sửa:
```python
def handle_proposal_decisions() -> None:
    def _work():
        _scan_decisions()
        _scan_design_starts()
    _run_guarded(_decide_lock, _decide_again, _work)
```
(Nếu `handle_proposal_decisions` hiện gọi trực tiếp `_scan_decisions`, bọc lại bằng `_work` như trên để 2 scan dùng chung guard serialize.)

- [ ] **Step 6: Chạy test _gather — kỳ vọng PASS**

Run: `./venv/bin/python _test_brief_pipeline.py`
Expected: `PASS _gather_brief_inputs`.

- [ ] **Step 7: Smoke import pipeline**

Run: `./venv/bin/python -c "import pipeline; print('import OK'); print(hasattr(pipeline,'_scan_design_starts'), hasattr(pipeline,'_generate_brief'))"`
Expected: `import OK` + `True True`.

- [ ] **Step 8: Compile toàn bộ**

Run: `./venv/bin/python -m py_compile config.py brief.py proposal.py proposal_render.py pipeline.py && echo COMPILE_OK`
Expected: `COMPILE_OK`.

- [ ] **Step 9: Dọn + commit**

```bash
rm -f _test_brief_pipeline.py
git add pipeline.py
git commit -m "feat(brief): wire _scan_design_starts + _generate_brief into pipeline"
```

---

### Task 6: Manual steps (Airtable + deploy) — KHÔNG code

**Files:** (không)

- [ ] **Step 1: Redeploy Coolify** (cài `python-pptx` + code mới).

- [ ] **Step 2: Tạo nút "Bắt đầu design"** trên interface/Projects: button set field checkbox `Bắt đầu design` = checked (qua automation hoặc button run-automation). Hiển thị khi `Status = "Đã duyệt items"`.

- [ ] **Step 3: Tạo Automation "Gửi brief cho requester":**
  - Trigger: *When record matches conditions* → `File brief design` **is not empty**.
  - Action: Send email → To = `{Created by}`; Subject `[Merch] Brief design — {Mã project}`; body ngắn + **tick đính kèm file từ field "File brief design"**.

- [ ] **Step 4: (tuỳ) Thêm field asset vào form intake** để requester nạp Logo/KV/Source khi tạo project.

- [ ] **Step 5: E2E test** 1 project: duyệt items → bấm "Bắt đầu design" → kiểm deck `.pptx` upload + mail requester có đính kèm.

---

## Self-Review

**Spec coverage:**
- §3 kiến trúc `brief.py` 2 hàm → Task 2 + 3 ✓
- §4 trigger nút/cờ + scan → Task 5 (`_scan_design_starts`) ✓
- §5 input handling (Proposal JSON + asset + insight) → Task 5 (`_gather_brief_inputs`, dùng lại `_plan_items_from_fields`) ✓
- §6 enrich LLM schema + nhãn nguồn → Task 2 ✓
- §7 output pptx (cover + slide/item + mockup + badge) → Task 3 ✓
- §7 distribution upload + clear cờ → Task 5 (`_generate_brief`); email = Task 6 (manual) ✓
- §8 error: lỗi → clear cờ + note, không escalate → Task 5 (`_scan_design_starts` try/except) ✓
- §9 Airtable fields → đã tạo trước (Global Constraints) + config Task 1 ✓
- §10 testing isolation → Task 2/3/5 ✓

**Placeholder scan:** không còn TBD/TODO; mọi step có code/command thật.

**Type consistency:** `build_brief_content(fields, items, asset_status, insight)` đồng nhất Task 2 ↔ Task 5; `render_brief_pptx(brief_data, images, project)` đồng nhất Task 3 ↔ Task 5; `gather_images(items)->dict[str,bytes]`, `upload_brief(record_id,pptx,code)` đồng nhất. `_plan_items_from_fields` tái dùng từ Bước 4 (đã có trong pipeline.py).

**Lưu ý reviewer:** `_download_bytes` được stub trong test Task 5 (network). `gather_images` gọi `catalogue_data()` (network) — không unit-test riêng, chỉ qua render test với map rỗng + E2E.
