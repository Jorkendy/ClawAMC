# Spec — Bước "Nhập design input" trước khi gen brief (Bước 5)

**Ngày:** 2026-06-26 · **Trạng thái:** Design (chờ duyệt) · **Loại:** thêm 1 bước thu thập input vào pipeline.

## 1. Vấn đề

Bước 5 sinh deck brief (`build_brief_content`) cần per-item **design_direction** + **brand assets** (Logo/KV/Source). Hiện:
- 3 field asset (`Logo game`, `Key Visual (KV)`, `Source material`) **tồn tại trên Projects và được code đọc**, nhưng **KHÔNG có bước nào thu thập** → gần như luôn rỗng.
- **design_direction 100% do AI bịa** → brief ra toàn `(AI gợi ý)`.

→ Có output (deck) nhưng không có input thật. Cần một **bước nhập design input** trước khi gen.

## 2. Quyết định (từ brainstorming 2026-06-26)

| Câu hỏi | Chốt |
|---|---|
| Ai nhập + khi nào | **Bước riêng SAU khi Duyệt items** (requester hoặc Merch PIC), trước "Bắt đầu design" |
| Thu thập gì | **Asset (tùy chọn) + định hướng chung** (collection-level), KHÔNG per-item |
| Bắt buộc? | **Hybrid**: định hướng chung **bắt buộc**; asset **tùy chọn** |
| Cơ chế chặn | **A — status riêng** `Chờ nhập design input` |
| References | **Gộp** trong ô "Định hướng design" (không tách field) |
| Cách đi xin input | **Chủ động**: vào trạng thái → **mail requester** kèm **link form** (Fillout) để requester tự nhập |
| Mail requester kèm gì | **CHỈ form** (KHÔNG đính plan — plan có chi phí/đợt chi nội bộ, chỉ PIC nhận như cũ) |
| Khi requester submit | **Auto-mail PIC** "đã có định hướng, vào review + Bắt đầu design" |
| Ai bấm Bắt đầu design | **Merch PIC** (review input rồi trigger) — không đổi |
| **Lưu asset** | **KHÔNG upload vào Airtable** (tránh phình storage). File ở **Google Drive** (requester upload + chia sẻ link, "anyone with the link"); Airtable chỉ giữ **URL text** |
| **Agent DÙNG asset** | **Logo**: tải nhúng cover. **KV**: agent **đọc** để (1) vision → mô tả brand cho phần chữ [Opt 1] + (2) làm **reference cho image-edit** → mockup bám KV [Opt 2]. **Source**: chỉ link cho M&D. → Logo + KV phải fetch được (Drive share + link tải thẳng) |
| **Model ảnh** | Có KV → **image-edit fal.ai `fal-ai/flux-pro/kontext`** (gọi **THẲNG fal qua `fal_client`**, KV làm reference — KHÔNG qua LiteLLM vì provider fal_ai của LiteLLM chỉ gen). Không KV → fallback **text-to-image `imagen-4-fast`** (qua LiteLLM) như cũ |

## 3. Luồng mới

```
Duyệt items → Status "Chờ nhập design input" + sinh plan Bước 4
   ├─ [Automation cũ] mail PIC kèm plan
   ├─ [Automation MỚI B] mail REQUESTER: mời nhập định hướng design + link form (KHÔNG kèm plan)
   ↓
Requester mở form (Fillout) → nhập Định hướng design (bắt buộc) + assets (tùy chọn) → Submit
   → Fillout ghi field vào project + set cờ "Đã nhập định hướng"
   ↓
[Automation MỚI C] mail PIC: "requester đã nhập định hướng — review + Bắt đầu design"
   ↓
PIC review (chỉnh nếu cần) → bấm "Bắt đầu design"
   → agent GÁC (định hướng phải có) → gen brief → Chờ duyệt brief → (Duyệt brief) → Chờ thiết kế
```

- `Chờ nhập design input` **thay thế** `Đã duyệt items` làm trạng thái sau khi duyệt.
- **Requester submit KHÔNG kích agent** — chỉ ghi field + bắn Automation C (mail PIC). Agent chỉ chạy khi **PIC** bấm "Bắt đầu design". Đúng mong muốn "PIC trigger dựa trên thông tin đó".
- Gác ở agent vẫn là **backstop** (lỡ PIC bấm trước khi có định hướng).

## 4. Dữ liệu (Projects)

| Field | Kiểu | Bắt buộc | Trạng thái |
|---|---|---|---|
| **Định hướng design** | Long text | ✅ (agent gác) | **TẠO MỚI** — tone/màu/phong cách + must-have + link tham khảo gộp chung |
| Logo game (link) | **URL** | ⬜ | **ĐỔI từ Attachment → URL** (link Drive, agent tải nhúng cover) |
| Key Visual (link) | **URL** | ⬜ | **ĐỔI → URL** (link Drive, agent **đọc**: vision + reference image-edit) |
| Source material (link) | **URL** | ⬜ | **ĐỔI → URL** (link Drive, chỉ M&D mở) |

> 3 field asset hiện là **Attachment** (`fldDQFLogtbXzLzen` / `fldGnHaTuaIrTSfrK` / `fldZooXpWQKaCOiOz`) — đang trống nên đổi type sang **URL** an toàn. Lưu URL Drive thay vì file → **storage Airtable không phình**.
| **Đã nhập định hướng** | Checkbox | — | **TẠO MỚI** — Fillout set khi submit → trigger Automation C (mail PIC); untick sau khi mail để re-fire nếu submit lại |
| Status (option mới) | singleSelect | — | **TẠO MỚI option** `Chờ nhập design input` |
| **Link nhập định hướng** | Formula | — | **TẠO MỚI** — deep-link form Fillout (`FORM_URL & "?id=" & RECORD_ID()`) dùng trong mail B |

## 4b. Brief DÙNG asset thế nào — Opt 1 (chữ) + Opt 2 (mockup)

Mục tiêu: brief bám **asset thật** thay vì AI bịa. Hai tầng bổ trợ:

- **Opt 1 — Vision ground PHẦN CHỮ** (dùng `gemini-flash` đa phương thức, đã có): agent tải **logo + KV** → 1 call vision mô tả **màu/nhân vật/phong cách/tone** (text) → nhét vào `build_brief_content` (design_direction, chất liệu...) + vào prompt sinh mockup. Rẻ (~vài trăm đ/brief, đọc 1 lần). Asset rỗng → bỏ qua, dùng định hướng text của requester.
- **Opt 2 — Image-edit ground MOCKUP** (fal.ai `fal-ai/flux-pro/kontext`, gọi **THẲNG fal qua `fal_client`**, KV làm reference): mỗi item, nếu **có KV** → gọi image-edit (KV reference + prompt = sản phẩm + design_direction) → mockup **bám màu/phong cách KV**. **Không có KV** → fallback **text-to-image `imagen-4-fast`** (qua LiteLLM) như hiện tại.
- **Chi phí** [research 2026-06]: fal Kontext ~**$0.04 (~1.000₫)/ảnh** — chỉ ~2× hiện tại, dùng khi có KV. **Budget = số dư credit fal** (đã nạp $20) → trần cứng tự nhiên. Self-host GPU loại bỏ (volume thấp).
- **Lý do gọi thẳng fal (đã verify):** provider `fal_ai` của LiteLLM **chỉ wrap text-to-image** (`/images/generations`), **không có nhánh Kontext edit** → phải dùng `fal_client` trực tiếp. (BFL có provider edit trong LiteLLM nhưng cần key BFL khác → bỏ, để xài $20 fal đã trả.)
- ⚠️ **Giới hạn thành thật**: image-edit giúp mockup **bám nhận diện** nhưng **không đảm bảo tái hiện IP "y hệt"** — vẫn là concept cho M&D hoàn thiện.

## 5. Thay đổi code (`pipeline.py`, `brief.py`, `llm_client.py`)

Hằng số mới: `DESIGN_INPUT_STATUS = "Chờ nhập design input"`.

1. **`_approve_proposal`** (pipeline.py:523): Status `"Đã duyệt items"` → `DESIGN_INPUT_STATUS`. (Plan Bước 4 vẫn sinh như cũ.)
2. **`_scan_design_starts`** (pipeline.py:500): filter `Status='Đã duyệt items'` → `Status=DESIGN_INPUT_STATUS`. **Thêm gác**: đọc "Định hướng design"; nếu rỗng/toàn khoảng trắng → **KHÔNG gen**, `append_note` "Cần nhập Định hướng design trước khi bắt đầu", untick `Bắt đầu design` (tránh lặp mỗi webhook), giữ nguyên status. Nếu có → gen brief như cũ.
3. **`_scan_decisions` guard** (pipeline.py:665): điều kiện bỏ qua record `Status == "Đã duyệt items"` → đổi sang `DESIGN_INPUT_STATUS` (để record sau-duyệt không bị xử lý nhầm như đang chờ quyết định proposal).
4. **`_gather_brief_inputs`** (pipeline.py:455): (a) trả thêm `design_direction = fields.get("Định hướng design") or ""`; (b) đổi nguồn asset attachment → **URL field**: `asset_status` = URL có/không; tải **logo + KV** bytes: URL → helper `_drive_direct_url(url)` → `_download_bytes`. Tải lỗi/None → bỏ qua (brief vẫn chạy). Trả thêm `kv_bytes` (cho vision + image-edit).
   - Helper mới `_drive_direct_url` (thuần, test được): regex bắt FILE_ID từ các dạng link Drive (`/file/d/ID/view`, `open?id=ID`, `uc?id=ID`) → `uc?export=download&id=ID`; không khớp → trả nguyên URL.
5. **`build_brief_content`** (brief.py:74) + **`BRIEF_PROMPT`**: nhận `design_direction` **+ `brand_desc`** (mô tả brand từ vision, xem 6); thêm khối **"ĐỊNH HƯỚNG DESIGN (người yêu cầu cung cấp — BÁM SÁT)"** + **"NHẬN DIỆN TỪ KV (do đọc ảnh)"**; AI suy design_direction từng item TỪ 2 nguồn đó + gắn `sources.design_direction = "requester"` khi grounded; `"ai"` chỉ cho phần AI bổ sung. Cả hai rỗng → hành vi cũ.
6. **[Opt 1] Vision đọc asset** — helper mới `llm_client.describe_image(img_bytes) -> str`: gọi model đa phương thức (`gemini-flash`) với message chứa ảnh → trả mô tả brand (màu/nhân vật/phong cách). `_gather_brief_inputs` gọi cho KV (và/hoặc logo) → `brand_desc` đưa vào (5). Lỗi/không ảnh → `""`.
7. **[Opt 2] Image-edit mockup** — helper mới `llm_client.edit_image(prompt, ref_bytes, timeout) -> bytes|None`: gọi **THẲNG fal.ai qua `fal_client`** (model `fal-ai/flux-pro/kontext`, upload KV làm reference, timeout cap cứng). KHÔNG qua LiteLLM. `gather_brief_images` (brief.py): mỗi item — **có `kv_bytes`** → `edit_image(prompt=sản phẩm + design_direction, ref=kv)`; **không** → `generate_image` text-to-image (LiteLLM) như cũ. Lỗi/budget → fallback text-to-image → fallback icon (log rõ mỗi lần tụt tầng). Cache key thêm cờ "edit/kv". **Dep mới:** `fal_client`; **env agent mới:** `FAL_KEY`, `LLM_IMAGE_EDIT_MODEL=fal-ai/flux-pro/kontext`.

> Kết quả: phần chữ brief hiển thị `(Từ requester)`/bám KV; mockup **bám màu–phong cách KV** khi có KV. Hết cảnh toàn `(AI gợi ý)`.

## 6. UI nhập liệu + mail (Fillout + Automation native)

- **Form Fillout "Nhập định hướng design"** (edit-existing-record theo `?id=`): ghi `Định hướng design` (bắt buộc trong form) + 3 **link asset Drive** (ô URL, tùy chọn — KHÔNG upload file) ngược vào project; submit set cờ `Đã nhập định hướng`=checked. (Form Fillout thứ 2 — URL riêng, KHÁC `FILLOUT_FORM_URL` phản hồi proposal.) Form ghi chú requester: chia sẻ Drive **"anyone with the link"** (nhất là logo để agent tải được).
- **Automation B (mail requester)** — trigger `Status = "Chờ nhập design input"` → To = Created by, body mời nhập định hướng + `{Link nhập định hướng}`. KHÔNG đính plan.
- **Automation C (mail PIC)** — trigger `Đã nhập định hướng is checked` → To = `{PIC phụ trách}` (fallback default), body "requester đã nhập định hướng — review + Bắt đầu design" + link record; **untick** `Đã nhập định hướng` sau khi gửi (re-fire nếu submit lại).
- "Bắt đầu design" = button set cờ sẵn có (PIC bấm sau review).

→ Cả 2 mail là **Automation native thuần** (body tĩnh + field/formula) — **agent KHÔNG soạn, KHÔNG thêm code**.

## 7. Test (isolation, mock LLM)

- `build_brief_content` có `design_direction` → per-item `design_direction` bám input + `sources.design_direction == "requester"`; rỗng → fallback "ai".
- `_scan_design_starts` gác: định hướng rỗng → KHÔNG gọi gen + có note + untick; có định hướng → gọi gen.
- `_drive_direct_url`: các dạng link Drive (`/file/d/ID/view`, `open?id=ID`, `uc?id=ID`) → ra `uc?export=download&id=ID`; URL không phải Drive → giữ nguyên.
- `gather_brief_images` branch (mock 2 helper): item có `kv_bytes` → gọi `edit_image`; không có → gọi `generate_image`; `edit_image` lỗi → fallback `generate_image`.
- `describe_image` → `build_brief_content` nhận `brand_desc` (mock LLM): khẳng định brand_desc được nhét vào prompt.
- Regression: `_approve_proposal` set đúng `DESIGN_INPUT_STATUS`; `_scan_decisions` bỏ qua record ở status mới.

## 8. Việc tay (Airtable / Fillout) — CẦN trước khi deploy

1. Tạo field **"Định hướng design"** (Long text), **"Đã nhập định hướng"** (Checkbox), **"Link nhập định hướng"** (Formula deep-link form) trên Projects. **Đổi 3 field asset Attachment → URL** (Logo/KV/Source — đang trống nên đổi an toàn).
2. Tạo **option Status** `Chờ nhập design input` (singleSelect) — `update_project` KHÔNG typecast → thiếu option sẽ 422 làm kẹt sau Duyệt. **Phải tạo trước.**
3. **Form Fillout** "Nhập định hướng design" (edit-record theo `?id=`): ghi Định hướng design + assets + set `Đã nhập định hướng`. Lấy URL form → gắn vào formula "Link nhập định hướng".
4. **Automation B** (mail requester khi vào `Chờ nhập design input`, kèm `{Link nhập định hướng}`, KHÔNG plan).
5. **Automation C** (mail PIC khi `Đã nhập định hướng` checked → untick sau gửi).
6. **Rà filter interface/Automation nào đang khoá theo `Đã duyệt items`** → đổi sang `Chờ nhập design input` (gồm nút "Bắt đầu design").
7. **Image-edit = fal-direct (KHÔNG qua LiteLLM):** image-edit gọi thẳng fal.ai `fal-ai/flux-pro/kontext` qua `fal_client` (provider fal_ai của LiteLLM chỉ gen). → Env agent: **`FAL_KEY`** (key fal đã có) + **`LLM_IMAGE_EDIT_MODEL=fal-ai/flux-pro/kontext`**; thêm dep `fal_client` vào requirements. **Budget** = số dư credit fal ($20 đã nạp).
8. **LiteLLM = 5 virtual key** (chat: analysis/proposal/brief; grounding; image-gen) — **KHÔNG có key image-edit** (vì edit đi fal-direct). Env agent: `LLM_KEY_ANALYSIS/PROPOSAL/BRIEF/GROUNDING/IMAGE`. Model trên LiteLLM giữ nguyên (gemini-flash, imagen-4-fast) — **không cần thêm flux-kontext vào LiteLLM**.

## 9. Ngoài phạm vi (YAGNI)

- KHÔNG per-item design direction (chỉ collection-level).
- KHÔNG tách field references (gộp trong định hướng).
- KHÔNG bắt buộc asset.
- KHÔNG vòng duyệt design-input riêng (đã có vòng "Chờ duyệt brief" sau gen).
- KHÔNG lưu file vào Airtable (chỉ URL Drive).
- **KHÔNG self-host model ảnh (GPU)** — volume thấp, dùng API qua LiteLLM (fal.ai/BFL) rẻ hơn.
- **KHÔNG kỳ vọng mockup tái hiện IP "y hệt"** — image-edit chỉ bám nhận diện, M&D vẫn hoàn thiện bản cuối.
- KHÔNG per-item KV (1 KV chung cho cả bộ).

## 10. Verify khi review

1. Đổi `Đã duyệt items` → `Chờ nhập design input` có còn chỗ nào tham chiếu chuỗi cũ (interface/Automation) bị sót không.
2. Wording status: `Chờ nhập design input` ổn hay đổi (vd `Chờ định hướng design`).
3. Form Fillout thứ 2: dùng URL riêng hay tái dùng form hiện có (ảnh hưởng formula link + có thể cần env/field cho URL).
4. (tùy chọn sau) Requester không submit lâu → có cần Automation nhắc lại sau N ngày không (chưa đưa vào MVP).
5. **Logo + KV qua Drive:** agent giờ tải **cả logo lẫn KV** → cả hai cần "anyone with the link" + file không quá lớn (Drive chèn trang quét virus với file lớn → chặn tải thẳng). Nếu hay lỗi tải → cân nhắc Fillout-hosted cho 2 asset này.
6. **Chọn provider image-edit:** fal.ai (`FAL_AI_API_KEY`, giá phẳng $0.04) hay BFL (`BFL_API_KEY`, Kontext native) — chốt 1 để cấu hình LiteLLM.
7. **Verify runtime image-edit** trên LiteLLM 1.90.0 (curl `/v1/images/edits` không 404) trước khi code nhánh Opt 2.
