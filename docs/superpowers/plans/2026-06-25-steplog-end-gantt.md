# Step Log `end` → Gantt + lead-time Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi dòng Step Log có `end` = start của bước kế → Timeline thành thanh (Gantt) + formula Lead-time (ngày) tự tính.

**Architecture:** 1 Airtable automation trên bảng Step Log (trigger record-created → Run script chốt `end` dòng bước trước theo `Mã project (text)`). Không code Python. Go-forward only.

**Tech Stack:** Airtable Automation "Run a script" (JS), Airtable Interface Timeline view.

## Global Constraints

- **Go-forward only** — KHÔNG backfill 25 dòng cũ.
- Match dòng theo **`Mã project (text)`** (`flddWRKoCpQxtoWyk`), KHÔNG theo link Project (link gãy khi project bị xoá).
- Script dùng **field ID** (tránh lệch tên): start=`fldSAEzlYntKYyHl3`, end=`fldHUH4OJOeV67zuc`, Mã project (text)=`flddWRKoCpQxtoWyk`. Table Step Log=`tblG4OGkyKAfUEfsj`.
- Lỗi script KHÔNG chặn nghiệp vụ (bọc try/catch; dòng Step Log đã tạo trước đó).
- Phủ cả 2 nguồn tạo dòng (agent `log_event` + automation "Status đổi → ghi Step Log") → trigger "record created".

---

## Task 1: Automation "Step Log: chốt end bước trước"

**Files:** Không có file code. Airtable UI > Automations (base `appo1Oei5JvJ1EXAG`).

**Interfaces:**
- Consumes: bảng Step Log (`tblG4OGkyKAfUEfsj`) fields start/end/Mã project (text).
- Produces: dòng "bước trước" có `end` được set → formula Lead-time tự tính.

- [ ] **Step 1: Tạo automation mới**
  - Create new automation. Tên: `Step Log: chốt end bước trước`.
  - Description: `Khi 1 dòng Step Log được tạo → set "end" của dòng bước TRƯỚC (cùng Mã project (text), start nhỏ hơn, gần nhất) = start dòng mới. Để Timeline vẽ thanh + Lead-time tự tính. Go-forward.`

- [ ] **Step 2: Trigger**
  - Trigger type: **When a record is created**.
  - Table: **Step Log**.

- [ ] **Step 3: Thêm action Run a script**
  - Add action → **Run a script**.
  - **Input variables** (Value lấy từ record của trigger "When a record is created"):
    - `maProject` → field **Mã project (text)**
    - `startMoi` → field **start**
    - `recordIdMoi` → **Airtable record ID** (của record trigger)

- [ ] **Step 4: Dán script** (dùng field ID, bọc try/catch)

```javascript
try {
  let cfg = input.config();
  let stepLog = base.getTable("tblG4OGkyKAfUEfsj");

  // fields: Mã project (text), start
  let q = await stepLog.selectRecordsAsync({ fields: ["flddWRKoCpQxtoWyk", "fldSAEzlYntKYyHl3"] });

  let prev = null;
  for (let r of q.records) {
    if (r.id === cfg.recordIdMoi) continue;                                  // bỏ chính dòng vừa tạo
    if (r.getCellValueAsString("flddWRKoCpQxtoWyk") !== cfg.maProject) continue; // khác dự án
    let s = r.getCellValue("fldSAEzlYntKYyHl3");                              // start
    if (!s) continue;
    if (new Date(s) >= new Date(cfg.startMoi)) continue;                      // chỉ lấy bước TRƯỚC
    if (!prev || new Date(s) > new Date(prev.getCellValue("fldSAEzlYntKYyHl3"))) prev = r; // start lớn nhất
  }

  if (prev) {
    await stepLog.updateRecordAsync(prev.id, { "fldHUH4OJOeV67zuc": cfg.startMoi }); // set end
  } else {
    console.log("Không có bước trước (dòng đầu của dự án) — bỏ qua.");
  }
} catch (e) {
  console.log("step-log chốt end lỗi: " + e);
}
```

- [ ] **Step 5: Test script**
  - Bấm **Test** → chọn 1 record Step Log là **bước thứ ≥2** của 1 dự án có sẵn (cùng Mã project (text) đã có ≥1 dòng start nhỏ hơn).
  - Kỳ vọng: chạy không lỗi; mở dòng bước trước → field `end` đã được set = start của dòng test; cột `Lead-time (ngày)` ra số.
  - Nếu chọn nhằm dòng đầu (không có bước trước) → log "bỏ qua", `end` không đổi (đúng).

- [ ] **Step 6: Bật + publish**
  - Turn automation **ON**. Bấm **Update**/publish nếu có banner unpublished.

---

## Task 2: Cấu hình Timeline + live verify

**Files:** Không có file code. Airtable Interface "Cổng Merch" > view Timeline "Step Log".

**Interfaces:**
- Consumes: field `end` (`fldHUH4OJOeV67zuc`) được Task 1 điền.

- [ ] **Step 1: Cấu hình Timeline dùng end**
  - Mở interface Cổng Merch → page/view Timeline "Step Log".
  - Trong cài đặt timeline: đặt **Start = `start`**, **End = `end`** (trước đây chỉ có start = chấm). Lưu → publish interface.

- [ ] **Step 2: Live verify end-to-end**
  - Đẩy 1 dự án thật (hoặc tạo tay) qua **≥2 status** để sinh ≥2 dòng Step Log cùng `Mã project (text)`.
  - Kỳ vọng:
    1. Dòng bước trước có `end` = start dòng kế (do Task 1 automation).
    2. `Lead-time (ngày)` ra số ngày.
    3. Timeline vẽ **thanh** (start→end) cho bước đã hoàn tất; bước hiện tại (chưa có bước kế) vẫn là chấm/đang diễn ra.

- [ ] **Step 3: Cập nhật memory**
  - Cập nhật [[merch-step-progress-plan]]: phần B (end/Gantt + lead-time) ĐÃ BUILD go-forward; còn lại chỉ mảng A (drive-steps/Bước 3+).

---

## Self-Review

**Spec coverage:** §3 automation+script → Task 1. §3 Timeline config → Task 2 Step 1. §1 go-forward (không backfill) → Global Constraints + không có task backfill. §2 match Mã project (text) + phủ 2 nguồn (trigger record-created) → Task 1. §5 edge (dòng đầu/bước hiện tại) → Task 1 script (no-op khi không prev; end trống khi chưa có bước kế). §6 try/catch → Task 1 Step 4. §7 test → Task 1 Step 5 + Task 2 Step 2. §8 field id `end` → đã resolve `fldHUH4OJOeV67zuc` (Global Constraints).

**Placeholder scan:** không có TBD/TODO; script đầy đủ.

**Type consistency:** field IDs nhất quán toàn plan (start fldSAEzlYntKYyHl3, end fldHUH4OJOeV67zuc, Mã project text flddWRKoCpQxtoWyk, table tblG4OGkyKAfUEfsj). Input vars maProject/startMoi/recordIdMoi khớp giữa Step 3 và script Step 4.
