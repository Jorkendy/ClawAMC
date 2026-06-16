# Cấu hình Airtable cho Bước 2 (D1) — phần làm trên UI, không phải code

Code đã xong + test E2E pass. Để luồng chạy production cần bật 3 thứ trên Airtable
(không tạo được qua API/MCP nên làm tay):

## 1. Lookup field "Email requester" (Projects)

Để Automation biết gửi mail cho ai.

- Projects → **+ Add field** → loại **Lookup**.
- Tên: `Email requester`.
- Linked record field: `Requester` → lookup giá trị `Email` (từ bảng Users).

## 2. Automation gửi mail proposal cho requester

Khi agent đẩy proposal xong, Status đổi thành **"Chờ duyệt items"** → gửi mail.

- Airtable → tab **Automations** → **Create automation**.
- **Trigger:** *When record matches conditions*
  - Table: `Projects`
  - Condition: `Status` is `Chờ duyệt items`
- **Action:** *Send email*
  - To: field `Email requester`
  - Subject: `[{Mã project}] Proposal merch — mời duyệt`
  - Body (gợi ý):
    > Chào bạn, proposal cho project **{Tên project}** đã sẵn sàng (xem file đính kèm).
    > Vui lòng mở record trên Airtable và chọn **Duyệt proposal?** = *Duyệt* nếu đồng ý,
    > hoặc *Cần sửa* + ghi rõ vào **Feedback proposal** nếu muốn chỉnh (tối đa 3 vòng).
    > Hạn duyệt: {Deadline phê duyệt}.
  - **Attachment:** chọn field `File proposal`.
  - (nên thêm link tới record/Interface để requester bấm vào duyệt)

## 3. Webhook fire trên thay đổi field "Duyệt proposal?"

Agent phản ứng feedback qua webhook. Webhook Airtable phải theo dõi **thay đổi field**, không chỉ record mới.

- Webhook watch các field: `Duyệt proposal?` (và `Status` cho luồng record mới).
- Mỗi lần field đổi → ping agent → agent quét `handle_proposal_decisions()`.

> Nếu chưa kịp dựng webhook field-change: tạm gọi tay action `{"action":"handle_proposal_decisions"}`
> để agent quét, hoặc để reminder loop quét định kỳ (chậm hơn).

---

## Luồng tổng (sau khi bật 3 cái trên)

```
Form submit → webhook → AI #1 phân tích
  └─ đủ thông tin → AI #2 proposal + render HTML → upload File proposal → Status "Chờ duyệt items"
        → Automation gửi mail requester (kèm file)
        → requester mở Airtable, set "Duyệt proposal?":
           ├─ Duyệt   → agent chốt items → "Đã duyệt items" → (Bước 3)
           └─ Cần sửa + Feedback → agent sửa lại proposal (đếm round, >3 → Cần PIC xử lý)
```
