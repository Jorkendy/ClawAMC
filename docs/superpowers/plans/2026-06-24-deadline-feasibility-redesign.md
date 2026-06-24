# Deadline Feasibility Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verdict deadline trung thực (floor toàn kho) + khi gấp đưa phương án nhanh (relevant∩feasible) cụ thể, mô tả bộ đầy đủ, và cho requester dời deadline để restore ĐÚNG bộ đã hứa (không re-roll).

**Architecture:** LLM chọn bộ lý tưởng (relevance); code lo toàn bộ feasibility — `catalogue_floor_days` (sàn thật), `_fit_within_deadline` (tách fast/slow bằng cách bỏ dần món chậm nhất), `_resolve_deadline` (3 kết cục ok/fast/adjust), snapshot bộ đầy đủ vào field hidden, restore deterministic qua `_publish_from_snapshot`.

**Tech Stack:** Python 3.13, FastAPI, OpenAI SDK (LiteLLM), Airtable REST, pytest (mới, dev-only).

## Global Constraints
- KHÔNG đổi string contract Airtable/LLM (tên field, key JSON, status values) — chỉ thêm field mới `Phương án đầy đủ (JSON)`.
- `fast` subset LUÔN là tập con của bộ LLM chọn (relevant) — KHÔNG pull món theo tốc độ thuần.
- Restore bộ đầy đủ = bê nguyên snapshot, KHÔNG gọi LLM.
- Giữ nguyên: budget gate, MOQ, clarify yêu cầu đặc biệt, revise minimal-diff, Bước-1 generic warning.
- Hằng số hiện có: `DEADLINE_OVERHEAD_WORKDAYS=27`, `WORKDAYS_TO_CALENDAR=1.4`, `DEADLINE_BUFFER=1.15`, `CREATIVE_LEADTIME_LEN_MAU=8`, `CREATIVE_LEADTIME_SAN_XUAT=25`.
- Test chạy bằng `./venv/bin/python -m pytest`; chỉ commit khi user yêu cầu (KHÔNG auto-push).

## File Structure
- `config.py` — thêm `MIN_FAST_ITEMS = 3`.
- `proposal.py` — thêm `catalogue_floor_days`, `_fit_within_deadline`; viết lại `_resolve_deadline`; sửa nhánh deadline trong `propose_items_for`.
- `proposal_render.py` — thêm khối "Phương án đầy đủ" (upgrade) vào HTML proposal.
- `pipeline.py` — `_route_result` 2 nhánh mới; `_publish_from_snapshot`; precedence restore trong `_scan_decisions` (Chờ duyệt items) + `_reevaluate_adjust` (Chờ điều chỉnh).
- `tests/test_deadline.py` — pytest cho hàm thuần (mới).
- Airtable Projects — field `Phương án đầy đủ (JSON)` (qua MCP `create_field`).
- Fillout — thêm field Deadline conditional (manual UI).

---

### Task 1: Setup — config const, Airtable field, pytest scaffold

**Files:**
- Modify: `config.py`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Airtable: tạo field qua MCP

- [ ] **Step 1: Thêm hằng số vào config.py**

Thêm dưới block deadline (gần `DEADLINE_BUFFER`):
```python
MIN_FAST_ITEMS = 3   # so item toi thieu de "phuong an nhanh" du tot (else -> hoi doi deadline)
```

- [ ] **Step 2: Cài pytest vào venv (dev-only, KHÔNG thêm vào requirements.txt)**

Run: `./venv/bin/pip install pytest`
Expected: `Successfully installed pytest-...`

- [ ] **Step 3: Tạo tests/__init__.py rỗng + tests/conftest.py**

`tests/__init__.py`: (file rỗng)

`tests/conftest.py`:
```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# tranh load_dotenv/airtable khi import config trong test thuan: chi can hang so
```

- [ ] **Step 4: Tạo field `Phương án đầy đủ (JSON)` trên Projects qua MCP**

Dùng `create_field` (baseId `appo1Oei5JvJ1EXAG`, tableId `tbltWsCRFMDAkpKKc`): type `multilineText`, name `Phương án đầy đủ (JSON)`, description "Snapshot bộ đầy đủ khi deadline gấp; restore khi requester dời deadline. Hidden, không cho user sửa."
Expected: trả về field id `fld...` — ghi lại.

- [ ] **Step 5: Commit**
```bash
git add config.py tests/__init__.py tests/conftest.py
git commit -m "chore: add MIN_FAST_ITEMS, pytest scaffold, full-option snapshot field"
```

---

### Task 2: `catalogue_floor_days` — sàn thật toàn kho

**Files:**
- Modify: `proposal.py` (thêm hàm gần `deadline_days_needed`)
- Test: `tests/test_deadline.py`

**Interfaces:**
- Consumes: `item_leadtime`/`_parse_int` (sẵn có), `DEADLINE_OVERHEAD_WORKDAYS`, `WORKDAYS_TO_CALENDAR`.
- Produces: `catalogue_floor_days(by_name: dict) -> tuple[int, str]` — (số ngày lịch tối thiểu của 1 món catalogue nhanh nhất, tên món). Kho rỗng → `(0, "")`.

- [ ] **Step 1: Viết test thất bại**

`tests/test_deadline.py`:
```python
from proposal import catalogue_floor_days

def _cat(lm, sx):
    return {"Thời gian lên mẫu": lm, "Thời gian sản xuất": sx}

def test_floor_picks_fastest_item():
    by_name = {
        "Móc khóa": _cat("5", "10"),      # (27+5+10)*1.4 = 58.8 -> 59
        "Gấu bông": _cat("15", "60"),     # (27+15+60)*1.4 = 142.8 -> 143
    }
    days, name = catalogue_floor_days(by_name)
    assert name == "Móc khóa"
    assert days == 59

def test_floor_empty_catalogue():
    assert catalogue_floor_days({}) == (0, "")

def test_floor_uses_fallback_when_leadtime_missing():
    # thieu lead-time -> fallback 8/18 -> (27+8+18)*1.4 = 74.2 -> 74
    days, name = catalogue_floor_days({"X": {}})
    assert days == 74 and name == "X"
```

- [ ] **Step 2: Chạy test → fail**

Run: `./venv/bin/python -m pytest tests/test_deadline.py -v`
Expected: FAIL `ImportError: cannot import name 'catalogue_floor_days'`

- [ ] **Step 3: Implement**

Thêm vào `proposal.py` ngay sau `deadline_days_needed`:
```python
def catalogue_floor_days(by_name: dict) -> tuple[int, str]:
    """San tuyet doi: so ngay LICH toi thieu de lam 1 mon catalogue NHANH NHAT
    (bo lay max nen >= san nay). Tra (so_ngay, ten_mon). Kho rong -> (0, '')."""
    best = None
    for name, cat in by_name.items():
        lm = _parse_int(cat.get("Thời gian lên mẫu"))
        sx = _parse_int(cat.get("Thời gian sản xuất"))
        lm = lm if lm is not None else 8
        sx = sx if sx is not None else 18
        days = round((DEADLINE_OVERHEAD_WORKDAYS + lm + sx) * WORKDAYS_TO_CALENDAR)
        if best is None or days < best[0]:
            best = (days, name)
    return best if best else (0, "")
```

- [ ] **Step 4: Chạy test → pass**

Run: `./venv/bin/python -m pytest tests/test_deadline.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**
```bash
git add proposal.py tests/test_deadline.py
git commit -m "feat(proposal): catalogue_floor_days — honest fastest-in-catalogue floor"
```

---

### Task 3: `_fit_within_deadline` — tách fast/slow

**Files:**
- Modify: `proposal.py` (thêm gần `deadline_days_needed`)
- Test: `tests/test_deadline.py`

**Interfaces:**
- Consumes: `deadline_days_needed`, `item_leadtime` (sẵn có).
- Produces: `_fit_within_deadline(items: list, by_name: dict, days_left: int) -> tuple[list, list]` — `(fast, slow)`; bỏ dần item chậm nhất (max `lm+sx`) khỏi bộ tới khi `deadline_days_needed(fast) <= days_left`. `fast` giữ thứ tự gốc.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_deadline.py`:
```python
from proposal import _fit_within_deadline

def test_split_drops_slowest_until_fits():
    by_name = {
        "Móc khóa": _cat("5", "10"),    # lead 15 -> need (27+5+10)*1.4=59
        "Áo thun":  _cat("8", "20"),    # lead 28 -> need 77
    }
    items = [
        {"ten": "Móc khóa", "nguon": "catalogue"},
        {"ten": "Áo thun",  "nguon": "catalogue"},
        {"ten": "Khăn lụa", "nguon": "creative"}, # creative lead 8/25 -> need (27+8+25)*1.4=84
    ]
    # days_left=60: chi Móc khóa kip (59<=60); Áo thun(77) & creative(84) bi bo
    fast, slow = _fit_within_deadline(items, by_name, 60)
    assert [it["ten"] for it in fast] == ["Móc khóa"]
    assert {it["ten"] for it in slow} == {"Áo thun", "Khăn lụa"}

def test_split_all_fit():
    by_name = {"Móc khóa": _cat("5", "10")}
    items = [{"ten": "Móc khóa", "nguon": "catalogue"}]
    fast, slow = _fit_within_deadline(items, by_name, 200)
    assert len(fast) == 1 and slow == []
```

- [ ] **Step 2: Chạy test → fail**

Run: `./venv/bin/python -m pytest tests/test_deadline.py::test_split_drops_slowest_until_fits -v`
Expected: FAIL `cannot import name '_fit_within_deadline'`

- [ ] **Step 3: Implement**

Thêm vào `proposal.py` sau `deadline_days_needed`:
```python
def _fit_within_deadline(items: list, by_name: dict, days_left: int) -> tuple[list, list]:
    """Bo dan item cham nhat (max lm+sx) toi khi bo kip deadline.
    Tra (fast=giu lai kip, slow=bi bo). fast giu thu tu goc."""
    keep, slow = list(items), []
    while keep and deadline_days_needed(keep, by_name) > days_left:
        slowest = max(keep, key=lambda it: sum(item_leadtime(it, by_name)))
        keep.remove(slowest)
        slow.append(slowest)
    return keep, slow
```

- [ ] **Step 4: Chạy test → pass**

Run: `./venv/bin/python -m pytest tests/test_deadline.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**
```bash
git add proposal.py tests/test_deadline.py
git commit -m "feat(proposal): _fit_within_deadline — split relevant set into fast/slow"
```

---

### Task 4: Viết lại `_resolve_deadline` — 3 kết cục ok/fast/adjust

**Files:**
- Modify: `proposal.py` (thay thân `_resolve_deadline` hiện tại)
- Test: `tests/test_deadline.py`

**Interfaces:**
- Consumes: `days_to_deadline_of`, `deadline_days_needed`, `_fit_within_deadline`, `catalogue_floor_days`, `MIN_FAST_ITEMS`, `DEADLINE_BUFFER`.
- Produces: `_resolve_deadline(proposal: dict, fields: dict, by_name: dict, code: str) -> dict`:
  - `{"kind": "ok", "warn": str}` — bộ đầy đủ kịp (warn = ⚠️ sát hoặc "").
  - `{"kind": "fast", "fast": list, "full": list, "slow": list, "needed_full": int}`.
  - `{"kind": "adjust", "full": list, "needed_full": int, "days_left": int, "floor": int, "floor_name": str, "fast": list}`.
- (KHÔNG còn tự set `fields["Cảnh báo deadline"]` — caller lo.)

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_deadline.py`:
```python
from datetime import date, timedelta
from proposal import _resolve_deadline
import config

def _fields(days_from_today):
    d = date.today() + timedelta(days=days_from_today)
    return {"Deadline cần hàng": d.isoformat()}

CAT = {
    "Móc khóa": _cat("5", "10"),   # need 59
    "Áo thun":  _cat("8", "20"),   # need 77
    "Sticker":  _cat("4", "8"),    # need (27+4+8)*1.4=54.6->55
}

def test_ok_when_full_fits():
    items=[{"ten":"Áo thun","nguon":"catalogue"}]
    r=_resolve_deadline({"items":items}, _fields(200), CAT, "X")
    assert r["kind"]=="ok" and r["warn"]==""

def test_ok_sat_warning():
    items=[{"ten":"Áo thun","nguon":"catalogue"}]  # need 77
    r=_resolve_deadline({"items":items}, _fields(80), CAT, "X")  # 77<=80<77*1.15=88.5
    assert r["kind"]=="ok" and "sát" in r["warn"]

def test_fast_when_subset_fits(monkeypatch):
    monkeypatch.setattr(config,"MIN_FAST_ITEMS",2)
    # cung phai patch ca tham chieu da import trong proposal
    import proposal; monkeypatch.setattr(proposal,"MIN_FAST_ITEMS",2)
    items=[{"ten":"Móc khóa","nguon":"catalogue"},
           {"ten":"Sticker","nguon":"catalogue"},
           {"ten":"Áo thun","nguon":"catalogue"}]  # full need 77
    r=_resolve_deadline({"items":items}, _fields(60), CAT, "X")  # Móc(59)+Sticker(55) kip, Áo(77) bo
    assert r["kind"]=="fast"
    assert {i["ten"] for i in r["fast"]}=={"Móc khóa","Sticker"}
    assert {i["ten"] for i in r["slow"]}=={"Áo thun"}

def test_adjust_when_fast_too_thin():
    items=[{"ten":"Áo thun","nguon":"catalogue"}]  # need 77, fast rong khi days<77
    r=_resolve_deadline({"items":items}, _fields(40), CAT, "X")
    assert r["kind"]=="adjust"
    assert r["floor"]==55 and r["floor_name"]=="Sticker"  # mon nhanh nhat toan kho
```

- [ ] **Step 2: Chạy test → fail**

Run: `./venv/bin/python -m pytest tests/test_deadline.py -k resolve -v`
Expected: FAIL (logic cũ trả tuple, không có "kind")

- [ ] **Step 3: Implement — thay thân `_resolve_deadline`**

Thay TOÀN BỘ hàm `_resolve_deadline` hiện tại bằng:
```python
def _resolve_deadline(proposal: dict, fields: dict, by_name: dict, code: str) -> dict:
    """Cong chan DEADLINE (deterministic). Tra dict kind=ok|fast|adjust (xem spec)."""
    full = proposal.get("items", [])
    days_left = days_to_deadline_of(fields)
    if days_left is None:
        return {"kind": "ok", "warn": ""}
    needed_full = deadline_days_needed(full, by_name)
    if needed_full <= days_left:
        warn = ""
        if days_left < needed_full * DEADLINE_BUFFER:
            warn = (f"⚠️ Deadline sát: cần ~{needed_full} ngày, còn {days_left} ngày — "
                    f"rủi ro nếu duyệt mẫu chậm / mùa cao điểm.")
        return {"kind": "ok", "warn": warn}
    fast, slow = _fit_within_deadline(full, by_name, days_left)
    if len(fast) >= MIN_FAST_ITEMS:
        if not any(it.get("item_key") for it in fast):
            fast[0]["item_key"] = True
        return {"kind": "fast", "fast": fast, "full": full, "slow": slow,
                "needed_full": needed_full}
    floor, floor_name = catalogue_floor_days(by_name)
    return {"kind": "adjust", "full": full, "needed_full": needed_full,
            "days_left": days_left, "floor": floor, "floor_name": floor_name, "fast": fast}
```
Thêm import: `from config import ... MIN_FAST_ITEMS` (bổ sung vào dòng import config sẵn có trong proposal.py).

- [ ] **Step 4: Chạy test → pass**

Run: `./venv/bin/python -m pytest tests/test_deadline.py -v`
Expected: tất cả passed

- [ ] **Step 5: Commit**
```bash
git add proposal.py tests/test_deadline.py
git commit -m "feat(proposal): rewrite _resolve_deadline into ok/fast/adjust verdicts"
```

---

### Task 5: Wire `_resolve_deadline` vào `propose_items_for` (FAST/ADJUST + snapshot)

**Files:**
- Modify: `proposal.py` (`propose_items_for`)
- Verify: live smoke ở Task 9 (cần Airtable/LLM)

**Interfaces:**
- Consumes: `_resolve_deadline`.
- Produces: `propose_items_for(...)` trả thêm:
  - ADJUST: `{"project_code", "adjust_deadline": True, "full_snapshot": list, "needed": int, "days_left": int, "floor": int, "floor_name": str, "proposal": dict}`.
  - FAST: result thường (như happy) + `"deadline_fast": True, "full_snapshot": list, "slow": list, "needed_full": int`. `proposal["items"]` ĐÃ = fast; field `Cảnh báo deadline` set mô tả nâng cấp; `Phương án đầy đủ (JSON)` set snapshot.
  - OK: như hiện tại + `Cảnh báo deadline` = warn.

- [ ] **Step 1: Thay đoạn gọi `_resolve_deadline` cũ trong `propose_items_for`**

Đoạn hiện tại:
```python
    deadline_warn, infeasible = _resolve_deadline(proposal, fields, by_name, code)
    if infeasible:
        return infeasible
    fields["Cảnh báo deadline"] = deadline_warn  # accurate hoa (de-override canh bao generic cua Buoc 1)
```
Thay bằng:
```python
    dl = _resolve_deadline(proposal, fields, by_name, code)
    if dl["kind"] == "adjust":
        need_date = (date.today() + timedelta(days=dl["needed_full"])).isoformat()
        fields["Cảnh báo deadline"] = (
            f"🔴 Deadline KHÔNG đủ: bộ đề xuất cần ~{dl['needed_full']} ngày, còn {dl['days_left']} ngày. "
            f"Kể cả món nhanh nhất trong kho ({dl['floor_name']}) cần tối thiểu ~{dl['floor']} ngày."
            if dl["floor"] and dl["days_left"] < dl["floor"]
            else f"🔴 Deadline gấp: các món phù hợp cần ~{dl['needed_full']} ngày, còn {dl['days_left']} ngày.")
        return {"project_code": code, "adjust_deadline": True,
                "full_snapshot": dl["full"], "needed": dl["needed_full"],
                "days_left": dl["days_left"], "floor": dl["floor"],
                "floor_name": dl["floor_name"], "need_date": need_date, "proposal": proposal}
    deadline_fast = (dl["kind"] == "fast")
    if deadline_fast:
        proposal["items"] = dl["fast"]
        need_date = (date.today() + timedelta(days=dl["needed_full"])).isoformat()
        slow_names = ", ".join(it.get("ten", "") for it in dl["slow"])
        fields["Cảnh báo deadline"] = (
            f"✅ Phương án nhanh kịp deadline hiện tại. 💡 Bộ đầy đủ (thêm: {slow_names}) "
            f"cần dời 'Deadline cần hàng' tới ≥ {need_date} (~{dl['needed_full']} ngày).")
    else:
        fields["Cảnh báo deadline"] = dl["warn"]
```
(`date`, `timedelta` đã import sẵn ở đầu proposal? — NẾU CHƯA, thêm `from datetime import date, timedelta`. Kiểm tra: proposal.py hiện KHÔNG import datetime → **thêm** `from datetime import date, timedelta` ở đầu file.)

- [ ] **Step 2: Ghi snapshot vào `proj_updates` khi FAST**

Tìm `proj_updates = {...}` ở cuối `propose_items_for`, thêm sau khi tạo dict:
```python
    if deadline_fast:
        proj_updates["Phương án đầy đủ (JSON)"] = json.dumps(dl["full"], ensure_ascii=False)
```
(đặt NGAY trước `update_project(record["id"], proj_updates)`.)

- [ ] **Step 3: Thêm cờ vào return cuối**

Trong `return {...}` cuối hàm, thêm khi FAST:
```python
        "deadline_fast": deadline_fast,
        "full_snapshot": dl["full"] if deadline_fast else None,
        "slow": dl["slow"] if deadline_fast else None,
        "needed_full": dl.get("needed_full") if deadline_fast else None,
```

- [ ] **Step 4: Smoke import**

Run: `./venv/bin/python -c "import proposal; print('ok')"`
Expected: `ok` (no syntax/import error)

- [ ] **Step 5: Commit**
```bash
git add proposal.py
git commit -m "feat(proposal): emit FAST/ADJUST outcomes + full-option snapshot from propose_items_for"
```

---

### Task 6: HTML proposal — khối "Phương án đầy đủ" (upgrade)

**Files:**
- Modify: `proposal_render.py` (`build_proposal_html`)
- Verify: live smoke ở Task 9

**Interfaces:**
- Consumes: `fields["Cảnh báo deadline"]` đã chứa mô tả nâng cấp (set ở Task 5) — render qua khối `intro`/banner sẵn có (đã hỗ trợ `🔴`/`⚠️`/✅ prefix).
- Produces: không API mới; chỉ đảm bảo prefix `✅` render như banner thường (không vỡ).

- [ ] **Step 1: Kiểm tra render banner với prefix ✅**

Trong `build_proposal_html`, đoạn xử lý `warn_txt`:
```python
    warn_txt = (fields.get("Cảnh báo deadline") or "").strip()
    ...
    if warn_txt:
        sev = "intro-crit" if warn_txt.startswith("🔴") else "intro-warn"
```
Sửa để `✅` ra style nhẹ (xanh) thay vì cam:
```python
    if warn_txt:
        if warn_txt.startswith("🔴"):
            sev = "intro-crit"
        elif warn_txt.startswith("✅"):
            sev = "intro"        # nhe, khong canh bao do/cam
        else:
            sev = "intro-warn"
        intro_block = (f'<div class="intro {sev}"><div class="wline">{_md_inline(warn_txt)}</div>{nhan_xet}</div>')
    else:
        intro_block = f'<p class="intro">{nhan_xet}</p>'
```
(thay nguyên đoạn `if warn_txt: ... else: ...` hiện tại.)

- [ ] **Step 2: Smoke import**

Run: `./venv/bin/python -c "import proposal_render; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**
```bash
git add proposal_render.py
git commit -m "feat(render): show full-option upgrade banner (✅ style) in proposal HTML"
```

---

### Task 7: Pipeline — routing FAST/ADJUST + restore từ snapshot

**Files:**
- Modify: `pipeline.py`

**Interfaces:**
- Consumes: result FAST/ADJUST từ `propose_items_for`; `proposal._build_item_records`, `_build_images`, `proposal_total`, `catalogue_data`, `deadline_days_needed` (import từ proposal); `build_proposal_html`, `upload_proposal` (sẵn có); `days_to_deadline_of` (từ analysis).
- Produces: `_publish_from_snapshot(record_id, code, snapshot_items)`; nhánh restore trong `_scan_decisions`/`_reevaluate_adjust`.

- [ ] **Step 1: Import bổ sung ở đầu pipeline.py**

Thêm vào import từ proposal (dòng `from proposal import game_insight, propose_items_for`):
```python
from proposal import (game_insight, propose_items_for, _build_item_records,
                      _build_images, proposal_total, catalogue_data, deadline_days_needed)
```
Thêm `from analysis import analyze_one, days_to_deadline_of` (analyze_one đã import; thêm days_to_deadline_of). Và `from datetime import date, timedelta` (đã có).

- [ ] **Step 2: `_route_result` — thêm 2 nhánh FAST/ADJUST**

Trong `_route_result`, thêm Ở ĐẦU (trước các nhánh blocked/over_budget):
```python
    if result.get("adjust_deadline"):
        _enter_adjust_deadline(record_id, result)
        update_project(record_id, {"Phương án đầy đủ (JSON)":
                                   json.dumps(result["full_snapshot"], ensure_ascii=False)})
        return
    if result.get("deadline_fast"):
        _publish_proposal(record_id, result, html, reset_round=reset_round)
        return
```
(FAST: `_publish_proposal` đã upload html + set Status; snapshot đã được `propose_items_for` ghi vào `Phương án đầy đủ (JSON)` ở Task 5 Step 2.)

- [ ] **Step 3: Sửa `_enter_adjust_deadline` dùng message mới**

`_enter_adjust_deadline` hiện build message generic. Thay phần `msg` bằng dùng dữ liệu result:
```python
def _enter_adjust_deadline(record_id, result):
    need, left = result.get("needed", "?"), result.get("days_left", "?")
    nd = result.get("need_date", "?")
    floor, floor_name = result.get("floor"), result.get("floor_name")
    extra = (f" Kể cả món nhanh nhất trong kho ({floor_name}) cần tối thiểu ~{floor} ngày."
             if floor and isinstance(left, int) and left < floor else "")
    msg = (f"Deadline hiện KHÔNG đủ: bộ đề xuất cần ~{need} ngày, còn {left} ngày.{extra} "
           f"Vui lòng dời 'Deadline cần hàng' tới ≥ {nd} rồi tick \"Gửi phản hồi\" để lấy bộ đầy đủ "
           f"(hoặc xác nhận chấp nhận rủi ro).")
    _request_adjust(record_id, ADJUST_STATUS, msg,
                    f"Deadline không khả thi (cần ~{need}d/còn {left}d).",
                    f"deadline không đủ (cần ~{need}d/còn {left}d)")
```
(Giữ chữ ký gọi `_request_adjust` như cũ; chỉ đổi nội dung msg + nhận `result` thay vì dict cũ.)

- [ ] **Step 4: Thêm `_publish_from_snapshot`**

Thêm hàm mới (gần `_publish_proposal`):
```python
def _publish_from_snapshot(record_id: str, code: str, snapshot_items: list) -> None:
    """Restore bộ đầy đủ ĐÚNG y snapshot (KHÔNG gọi LLM) khi requester dời deadline đủ.
    Xoá items 'Đề xuất' cũ -> tạo lại từ snapshot -> render -> upload -> clear snapshot."""
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    fields = rec["fields"]
    for it in fetch_items_of(record_id):
        if it["fields"].get("Status") == "Đề xuất":
            airtable("DELETE", f"Items/{it['id']}")
    item_records, merch_categories = _build_item_records({"items": snapshot_items}, record_id)
    airtable("POST", "Items", {"records": item_records, "typecast": True})
    _, by_name = catalogue_data()
    images = _build_images(snapshot_items, by_name)
    total = proposal_total({"items": snapshot_items})
    html = build_proposal_html(fields, {"items": snapshot_items, "nhan_xet": "",
                                        "co_so_quyet_dinh": ""}, total, images=images)
    deadline = (date.today() + timedelta(days=PROPOSAL_APPROVAL_DAYS)).isoformat()
    update_project(record_id, {
        "Status": "Chờ duyệt items", "Deadline phê duyệt": deadline,
        "File proposal": [], "Duyệt proposal?": None, "Gửi phản hồi": False,
        "Feedback proposal": None, "Phân loại merch": sorted(merch_categories),
        "Proposal JSON": json.dumps(snapshot_items, ensure_ascii=False),
        "Phương án đầy đủ (JSON)": "", "Cảnh báo deadline": "",
    })
    upload_proposal(record_id, html, code)
    append_note(record_id, "[AI] Requester dời deadline → khôi phục bộ đầy đủ như đã đề xuất.",
                field=HISTORY_FIELD)
    print(f"[deadline] {code} restored full option from snapshot")
```

- [ ] **Step 5: Thêm helper `_try_restore_full` + cắm vào `_scan_decisions` (Chờ duyệt items) và `_reevaluate_adjust`**

Thêm helper:
```python
def _try_restore_full(record_id: str, code: str, fields: dict) -> bool:
    """Nếu có snapshot bộ đầy đủ & deadline mới đủ -> restore. Tra True nếu đã restore."""
    raw = fields.get("Phương án đầy đủ (JSON)")
    if not raw:
        return False
    try:
        snap = json.loads(raw)
    except Exception:
        return False
    if not snap:
        return False
    _, by_name = catalogue_data()
    if days_to_deadline_of(fields) is None:
        return False
    if deadline_days_needed(snap, by_name) > days_to_deadline_of(fields):
        # doi chua du
        need = deadline_days_needed(snap, by_name)
        update_project(record_id, {"Gửi phản hồi": False,
            "Trao đổi yêu cầu": f"Deadline mới vẫn chưa đủ cho bộ đầy đủ (cần ~{need} ngày, "
                                f"còn {days_to_deadline_of(fields)} ngày). Vui lòng dời thêm."})
        print(f"[deadline] {code} dời chưa đủ cho bộ đầy đủ")
        return True   # đã xử lý (báo lại), không chạy nhánh khác
    _publish_from_snapshot(record_id, code, snap)
    return True
```

Trong `_scan_decisions`, tại nhánh Status `Chờ duyệt items` — TRƯỚC khi đọc `decision`/`feedback`, chèn (sau khi đã loại Cần-sửa-có-feedback? thực ra theo precedence: Cần sửa thắng). Đặt logic:
```python
            feedback = (f.get("Feedback proposal") or "").strip()
            decision = f.get("Duyệt proposal?")
            # precedence: Cần sửa + feedback -> revise (re-roll); else dời deadline đủ -> restore full
            if decision == "Cần sửa" and feedback:
                _revise_or_escalate(r["id"], code, f)
            elif _try_restore_full(r["id"], code, f):
                pass  # đã restore hoặc báo "dời chưa đủ"
            elif decision == "Duyệt":
                _approve_proposal(r["id"], code)
            else:
                update_project(r["id"], {"Gửi phản hồi": False})
                print(f"[proposal] {code} tick Gửi nhưng thiếu decision/feedback -> bỏ qua")
```
(thay đoạn xử lý decision hiện tại trong `_scan_decisions` cho nhánh mặc định bằng block trên.)

Trong `_reevaluate_adjust` (Status `Chờ điều chỉnh`): thử restore trước, nếu không thì re-roll như cũ:
```python
def _reevaluate_adjust(record_id, code):
    rec = airtable("GET", f"{PROJECTS_TABLE}/{record_id}")
    if _try_restore_full(record_id, code, rec["fields"]):
        return
    result, html = _make_proposal(record_id)
    _route_result(record_id, result, html, reset_round=True)
    print(f"[proposal] {code} tính lại sau điều chỉnh")
```

- [ ] **Step 6: Smoke import**

Run: `./venv/bin/python -m py_compile pipeline.py proposal.py proposal_render.py && ./venv/bin/python -c "import pipeline; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**
```bash
git add pipeline.py
git commit -m "feat(pipeline): route FAST/ADJUST, restore full option from snapshot on deadline extend"
```

---

### Task 8: Airtable Fillout + field — cấu hình UI (manual)

**Files:** (không phải code — hướng dẫn vận hành, ghi trong plan để không quên)

- [ ] **Step 1: Xác nhận field `Phương án đầy đủ (JSON)` đã tạo (Task 1).**
- [ ] **Step 2: Fillout "Update form" — section Status `Chờ duyệt items`:** thêm field `Deadline cần hàng` (map Update record, prefill `@project.Deadline cần hàng`), **conditional show khi `Phương án đầy đủ (JSON)` ≠ rỗng**, helper text "Muốn bộ đầy đủ? Dời ngày này tới ≥ ngày ghi trong email rồi Submit." Publish lại form.
- [ ] **Step 3: Xác nhận section `Chờ điều chỉnh` vẫn cho sửa Deadline (đã có).**

---

### Task 9: Live smoke E2E + cleanup

**Files:**
- Create (tạm): script smoke trong `/tmp` hoặc chạy inline (KHÔNG commit).

**Mục tiêu:** verify 3 luồng thật trên sandbox (cô lập, tạo record Status="Chờ duyệt items" để agent deployed bỏ qua; gọi hàm trực tiếp local với env override `AIRTABLE_BASE_ID=appo1Oei5JvJ1EXAG PROPOSAL_FILE_FIELD_ID=fldvAjsSsyCSZw9IJ AI_IMAGES_ENABLED=false`).

- [ ] **Step 1: FAST outcome** — tạo record game thật (vd Gunny) Budget đủ, Deadline gấp (vd +60 ngày). Gọi `propose_items_for(rec)`. Kỳ vọng: `deadline_fast=True`, `proposal["items"]`=fast (ít hơn full), `Phương án đầy đủ (JSON)` có snapshot, `Cảnh báo deadline` chứa "Phương án nhanh… 💡 Bộ đầy đủ…".
- [ ] **Step 2: Restore consistency** — patch record Deadline = +200 ngày, gọi `_try_restore_full(rec_id, code, fields)`. Kỳ vọng: True; Items = ĐÚNG snapshot (so khớp tên/giá với `Phương án đầy đủ (JSON)` đã lưu Step 1); `Phương án đầy đủ (JSON)` clear; Status `Chờ duyệt items`; KHÔNG gọi LLM (so cost log không tăng dòng proposal mới).
- [ ] **Step 3: ADJUST hard** — record Deadline rất gấp (+10 ngày, < floor). Gọi `propose_items_for`. Kỳ vọng `adjust_deadline=True`; `_enter_adjust_deadline` message nêu món nhanh nhất + floor.
- [ ] **Step 4: Regression** — record Deadline xa (+250 ngày). Kỳ vọng `kind=ok`, publish bộ đầy đủ, `Cảnh báo deadline` rỗng (hoặc ⚠️ sát nếu sát).
- [ ] **Step 5: Cleanup** — xoá mọi record/items/cost-log test đã tạo (như các lần trước).
- [ ] **Step 6: Chạy lại unit tests** — `./venv/bin/python -m pytest tests/ -v` → all pass.

---

## Self-Review

**Spec coverage:** §4.1 field→T1; §4.2 floor→T2, split→T3, _resolve_deadline→T4; §4.3 propose wiring→T5; §4.4 routing/restore→T7; §4.5 render→T6 + message→T5/T7; §4.6 Fillout→T8; §5 flow→T7; §6 edge (dời chưa đủ/Cần sửa thắng/clear snapshot/no-deadline)→T4+T7; §8 testing→T2-4 unit + T9 smoke. ✓ Không gap.

**Placeholder scan:** không có TBD/TODO; mọi step có code/command thật. ✓

**Type consistency:** `_resolve_deadline` trả dict `kind` dùng nhất quán T4↔T5; `full_snapshot`/`Phương án đầy đủ (JSON)` nhất quán T5↔T7; `_publish_from_snapshot(record_id, code, snapshot_items)` ↔ gọi trong `_try_restore_full`. `_build_item_records({"items": ...}, record_id)` khớp chữ ký Tier-2 (`proposal`, `record_id`). ✓

## Follow-up NON-CODE
- Validate hằng số lead-time với 10-15 dự án thật (đạt độ tin 70-80%).
- Cập nhật Qase (suite "Bước 2 — Deadline") + memory test-cases sau khi merge.
</content>
