# Chuẩn hoá Email qua bảng Airtable "Email Templates" — Design Spec

**Ngày:** 2026-06-25
**Trạng thái:** Đã duyệt thiết kế (3 phần) — chờ user review spec → writing-plans.
**Bối cảnh:** Pivot từ plan cũ `merch-email-templates-plan` (approach B = template-trong-code). Lý do pivot: approach B khiến PO phải sửa code + deploy mỗi lần đổi nội dung mail → mất self-service. Hướng C giữ được self-service.

---

## 1. Mục tiêu & ràng buộc

**Mục tiêu:** Gom toàn bộ nội dung email của merch agent về **1 nguồn chuẩn duy nhất**, đồng bộ subject/footer/chữ ký, mà **PO non-tech vẫn tự sửa nội dung được, KHÔNG cần code/deploy**.

**Vấn đề hiện tại:**
- Mỗi automation gửi mail mỗi kiểu subject; footer/chữ ký lệch nhau (mail bổ sung do LLM tự nhét "Merch Agent — VNGGames"; các mail khác không footer).
- Nội dung rải rác: một phần trong Automation UI, một phần do app sinh động vào field (`Mail bổ sung`, `Trao đổi yêu cầu`, `Lý do cần PIC`).

**Ràng buộc kỹ thuật (đã xác nhận):**
- Airtable "Send email" **KHÔNG render HTML** từ field → email là **plain/rich-text gọn**; phần đẹp vẫn ở File proposal/plan/brief đính kèm.
- Local `.env` AIRTABLE_TOKEN read-only → smoke-write chỉ verify được sau deploy (prod có token ghi).
- pytest dev-only — **KHÔNG thêm vào requirements.txt**.

---

## 2. Kiến trúc tổng

**Một cơ chế thống nhất:** mọi automation gửi mail đều giống hệt nhau — chỉ gửi `{Email subject}` + `{Email body}` của record, khác nhau đúng ở **người nhận** + **file đính kèm**. Nội dung luôn từ 2 field buffer này.

- **6 mail qua app** (#1–6): app `render_email()` → ghi `Email subject`/`Email body` vào record **atomically cùng update sẵn có** → automation gửi.
- **1 mail scheduled** (#7 quá hạn): không qua app → automation tự render bằng **Run script** (JS) đọc cùng bảng template → ghi 2 field → gửi.

**Nguồn nội dung duy nhất:** bảng Airtable `Email Templates` (PO sửa). Code/JS chỉ làm 1 việc ổn định: đọc template + thay biến + nối footer.

---

## 3. Bảng `Email Templates` (Airtable, cùng base `appo1Oei5JvJ1EXAG`)

Mỗi dòng = 1 loại mail. **8 dòng:** 7 kind + 1 dòng `footer`.

| Cột | Kiểu | Vai trò |
|---|---|---|
| `Mã` | Single line text (primary) | khoá loại: `bo_sung`, `clarify`, `proposal`, `plan`, `brief`, `pic`, `qua_han`, `footer` |
| `Tên` | Single line text | nhãn người đọc, vd "Mail mời duyệt proposal" |
| `Subject` | Single line text | có biến; vd `[{{ma_project}}] {{ten_project}} — Mời duyệt proposal` (dòng `footer` để trống) |
| `Body` | Long text | có biến; mail động có `{{noi_dung}}`. Dòng `footer` chứa text footer. |
| `Biến dùng được` | Long text | cheatsheet RIÊNG của dòng: liệt kê biến hợp lệ cho mail đó |

### 3.1 Cheatsheet (discoverability cho PO non-tech) — 3 lớp

1. **Tổng — Description của bảng `Email Templates`:** chứa bảng liệt kê TẤT CẢ biến + ý nghĩa + ví dụ, quy tắc `{{ten_bien}}`, safe-substitute, lưu ý footer tự nối + sửa ở dòng `footer`. (Nội dung đầy đủ ở §4.)
2. **Riêng từng mail — cột `Biến dùng được`:** chỉ biến hợp lệ của dòng đó (vd `brief` không có `{{ly_do}}`).
3. **Nhắc nhanh — field description cột `Subject`/`Body`:** "Dùng {{ten_bien}}. Xem mô tả bảng cho danh sách đầy đủ."

---

## 4. Biến (cú pháp `{{ten_bien}}`, tiếng Việt cho PO)

| Biến | Nguồn (field Projects) | Dùng cho mail |
|---|---|---|
| `{{ma_project}}` | `Mã project` | tất cả |
| `{{ten_project}}` | `Tên project` | tất cả |
| `{{game}}` | `Game` | tất cả |
| `{{ten_nguoi_gui}}` | `Created by` → name; fallback `"Anh/Chị"` nếu trống | mail →requester |
| `{{han_duyet}}` | `Deadline phê duyệt` (dd/mm/yyyy) | proposal, qua_han |
| `{{deadline_hang}}` | `Deadline cần hàng` (dd/mm/yyyy) | proposal, plan, brief |
| `{{noi_dung}}` | lõi động (LLM/code) truyền qua `core` | bo_sung, clarify |
| `{{ly_do}}` | `Lý do cần PIC` | pic |
| `{{canh_bao_deadline}}` | `Cảnh báo deadline` (rỗng → bỏ qua) | proposal |
| `{{link}}` | link tương ứng (proposal/plan/PIC view) | proposal, plan, pic |

**Quy tắc thay biến:**
- **Safe-substitute:** biến không có trong dict (PO gõ sai / dùng nhầm) → **giữ nguyên `{{...}}`, KHÔNG crash, KHÔNG KeyError**.
- Giá trị `None`/rỗng → thay bằng chuỗi rỗng (riêng `{{ten_nguoi_gui}}` fallback "Anh/Chị").
- **Footer tự nối** vào cuối mọi `Body` (lấy từ dòng `footer`). PO không cần chèn footer thủ công.

> Mọi mapping field-name ở bảng trên được verify lại lúc writing-plans (đặc biệt nguồn `{{ten_nguoi_gui}}` từ collaborator field `Created by` — app đọc `fields["Created by"]["name"]`).

---

## 5. Module code `email_templates.py`

**Interface công khai duy nhất:**
```python
def render_email(kind: str, fields: dict, core: str | None = None) -> tuple[str, str]:
    """Trả (subject, body). Đọc bảng Email Templates, thay biến, nối footer.
    Lỗi đọc bảng / thiếu dòng kind -> fallback template hardcode + log.warning (KHÔNG raise)."""
```

**Hành vi:**
1. Fetch bảng `Email Templates` **tươi mỗi lần gọi** (volume thấp — vài mail/ngày; để PO sửa có hiệu lực ngay; KHÔNG cache → tránh stale).
2. Dựng dict biến từ `fields` + `core` (§4).
3. Safe-substitute vào `Subject` + `Body` của dòng `kind`; nối `Body` của dòng `footer`.
4. Trả `(subject, body)`.

**Fallback (không bao giờ chặn pipeline):**
- Đọc bảng lỗi HOẶC thiếu dòng `kind` → dùng **template mặc định hardcode** trong module cho kind đó → `log.warning` → vẫn trả `(subject, body)` hợp lệ.
- Module giữ dict `DEFAULT_TEMPLATES` (kind → subject, body) + footer mặc định, đủ để mọi mail gửi được kể cả khi bảng trống.

**Phụ thuộc:** `airtable_client.airtable()` (GET bảng), `log` (module logger `merch`).

---

## 6. Wiring 7 email

### 6.1 Sáu mail qua app

| # | Mail | Người nhận | Chỗ sửa code | `core` (→`{{noi_dung}}`) | Trigger giữ nguyên |
|---|---|---|---|---|---|
| 1 | bo_sung | requester | `analysis.py` (chỗ set cờ `Gửi mail bổ sung`) | LLM core (xem §6.3) | cờ `Gửi mail bổ sung` |
| 2 | clarify | requester | `pipeline._request_adjust` | `message` | cờ `Gửi mail làm rõ` |
| 3 | proposal | requester | `_publish_proposal` + `_publish_from_snapshot` | — | attach File proposal |
| 4 | plan | PIC | `_generate_plan` | — | attach File plan sản xuất |
| 5 | brief | requester | `_generate_brief` | — | attach File brief design |
| 6 | pic | PIC | `_mark_ai_error` + các chỗ escalate PIC | `Lý do cần PIC` | `Cần PIC xử lý`/Status |

Mỗi chỗ: gọi `subject, body = render_email(kind, fields, core)` rồi **thêm** `"Email subject": subject, "Email body": body` vào dict `update_project(...)` **sẵn có** (cùng lúc set cờ/đổi status → atomic, không đua ghi; pipeline đã serialize qua `_run_guarded`).

### 6.2 Mail #7 (quá hạn duyệt) — Run script

Automation scheduled `Quá hạn duyệt → báo requester` có repeating group (mỗi record tìm được). Thêm **1 step "Run script"** TRONG group, TRƯỚC step Send email:
- Script JS: query bảng `Email Templates` (dòng `qua_han` + `footer`), đọc field record → safe-substitute → `update` ghi `Email subject`/`Email body` vào record.
- Step Send email đổi sang gửi `{Email subject}` + `{Email body}`.

**Đánh đổi (đã chấp nhận):** đây là **chỗ DUY NHẤT logic render bị lặp** (Python `email_templates.py` + JS Airtable) — vì scheduled automation không gọi app được. Script JS ngắn (~20 dòng), viết sẵn trong plan. Đổi lại: footer/subject đồng bộ 100% cả 7 mail.

### 6.3 Đổi prompt LLM (analysis.py)

`mail_bo_sung` (hiện soạn TOÀN BỘ email) → đổi để LLM chỉ sinh **nội dung lõi** (thiếu gì + vì sao + cảnh báo deadline nếu có), **bỏ** câu chào "Chào…" và chữ ký "Merch Agent — VNGGames" (tránh trùng footer + greeting của template). Lõi này đổ vào `core` → `{{noi_dung}}`.

### 6.4 Field cũ
- `Trao đổi yêu cầu`, `Lý do cần PIC`: **GIỮ** (interface PIC/requester đọc + feed `{{noi_dung}}`/`{{ly_do}}`).
- `Mail bổ sung`: **ngừng ghi** (orphan do thay đổi này) → bỏ dòng set field trong `analysis.py`. Field Airtable để trống, KHÔNG xoá (tránh đụng; user xoá tay sau nếu muốn).

---

## 7. Xử lý lỗi

- **Render lỗi/thiếu template:** fallback hardcode + `log.warning`; mail vẫn gửi. Nguyên tắc: render KHÔNG bao giờ chặn nghiệp vụ.
- **Biến lạ/sai:** safe-substitute giữ nguyên, không crash.
- **Atomic write:** `Email subject/body` ghi cùng update hiện có → không đua. Pipeline đã serialize.
- **Script #7 lỗi:** bọc try/catch trong JS; lỗi → log + để send-email gửi nội dung tối thiểu (hoặc skip record đó, không chặn các record khác).

---

## 8. Test

- **Unit (pytest dev-only)** cho `render_email`:
  1. Thay biến đúng (subject + body).
  2. Biến lạ → giữ nguyên `{{x}}`, không raise.
  3. Footer được nối vào cuối body.
  4. Thiếu dòng kind → fallback template, có log.warning.
  5. `{{noi_dung}}` đổ đúng `core`; `core=None` → rỗng.
  6. `{{ten_nguoi_gui}}` trống → fallback "Anh/Chị".
- **Live smoke từng kind:** cô lập bằng Status ≠ Mới tiếp nhận/BLANK (cách phiên 24/06) → kiểm mail thật: subject/body/footer đúng.
- **Mail #7:** test script trong Airtable automation (Run script có nút test riêng).

---

## 9. Thứ tự triển khai (không gãy giữa chừng)

1. Tạo bảng `Email Templates` + seed 8 dòng + cheatsheet (description/cột) + 2 field buffer `Email subject`/`Email body` trên Projects (qua MCP). *(Chưa ai dùng → an toàn.)*
2. Code `email_templates.py` + unit test (pytest).
3. Wire 6 mail trong code + đổi prompt LLM bo_sung → deploy. *(Automation vẫn đọc field cũ → mail đang chạy không gãy.)*
4. Rewire 6 automation Airtable sang `Email subject/body` — **từng cái một**.
5. Run script + đổi send-email cho automation #7.
6. Live smoke 7 mail.

**An toàn:** bước 1–3 không ảnh hưởng mail đang chạy. Cắt sang field mới ở bước 4 (từng automation), rollback dễ (đổi lại 1 automation về field cũ).

---

## 10. Còn cần input khi build
- Giá trị footer (đầu mối liên hệ support/PIC): **không chặn** — seed mặc định, PO sửa trong dòng `footer`.
- Verify field-name mapping ở §4 (đặc biệt `{{ten_nguoi_gui}}` ← `Created by`) lúc writing-plans.
- Nội dung seed cụ thể (subject/body 7 kind + footer): soạn trong plan (không placeholder).
