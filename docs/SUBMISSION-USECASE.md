# Mô tả Use Case — Merch Agent

**Team:** AMC
**Track:** [điền track BTC quy định]

---

## Bản mô tả (< 300 từ)

**Merch Agent** tự động hóa quy trình sản xuất merchandise (vật phẩm quảng bá) cho các tựa game của VNGGames — công việc hiện đang làm thủ công, rải rác qua email và chat, dễ sai sót và tốn thời gian điều phối.

**Vấn đề:** Mỗi chiến dịch game, các phòng Marketing gửi yêu cầu làm merch (áo, móc khóa, standee...). Merch PIC phải đọc từng đề bài, kiểm tra thiếu thông tin, ước lượng kịp deadline không, rồi tự nghĩ danh mục sản phẩm + báo giá. Quá trình qua lại nhiều vòng, không có dấu vết tập trung.

**Giải pháp:** Agent tiếp nhận yêu cầu qua form (Airtable) và xử lý 2 bước:

1. **Phân tích đề bài (AI):** tự kiểm tra đủ/thiếu thông tin, đánh giá deadline so với timeline sản xuất toàn trình (in/sản xuất/nhập kho), tự soạn email nhắc bổ sung nếu thiếu hoặc cảnh báo nếu deadline gấp.

2. **Đề xuất sản phẩm (AI):** dựa trên **catalogue sản phẩm có sẵn** (giá cố định, chống bịa giá) kết hợp ~20% ý tưởng sáng tạo do AI gợi ý, agent dựng **phiếu đề xuất HTML** trong ngân sách rồi gửi cho người yêu cầu. Người yêu cầu **duyệt / phản hồi ngay trên Airtable**; agent tự sửa theo feedback (tối đa 3 vòng), quá hạn thì tự báo Merch PIC xử lý.

**Công nghệ:** GreenNode AgentBase (Custom Agent), GreenNode LLM (qwen3), Airtable làm CSDL + giao diện duyệt, email native qua Airtable Automation.

**Giá trị:** rút ngắn thời gian từ yêu cầu đến chốt danh mục từ nhiều ngày xuống còn vài giờ, chuẩn hóa quy trình, kiểm soát ngân sách và để lại dấu vết đầy đủ cho mọi bên (Requester, Merch PIC, Procurement).

---

## Use case description (English, < 300 words)

**Merch Agent** automates the game merchandise production workflow at VNGGames — a process today handled manually across scattered emails and chats, prone to errors and slow coordination.

**Problem:** For every game campaign, Marketing teams request merch (T-shirts, keychains, standees, etc.). The Merch PIC must read each brief, check for missing information, estimate whether the deadline is feasible, then manually compile a product list and cost estimate. This goes back and forth over many rounds with no centralized trail.

**Solution:** The agent receives requests through an Airtable form and handles two stages:

1. **Brief analysis (AI):** automatically checks whether required information is complete, assesses the deadline against the full production timeline (printing, manufacturing, warehousing), and drafts a follow-up email if information is missing or the deadline is at risk.

2. **Product proposal (AI):** based on a fixed-price **catalogue** of ready-made products (prices enforced by code to prevent hallucination) combined with ~20% AI-generated creative ideas, the agent builds an **HTML proposal** within budget and sends it to the requester. The requester **reviews and responds directly in Airtable**; the agent revises per feedback (up to 3 rounds), then auto-escalates to the Merch PIC if no agreement is reached.

**Tech stack:** GreenNode AgentBase (Custom Agent), GreenNode LLM (Qwen 3), Airtable as database + review UI, native email via Airtable Automation, with auto-triggering through Airtable webhooks.

**Value:** cuts the time from request to a finalized product list from days to hours, standardizes the process, keeps spending within budget, and leaves a complete audit trail for all stakeholders (Requester, Merch PIC, Procurement).
