"""Render proposal ra HTML + upload vao field 'File proposal' (Airtable Upload Attachment API).

Khung HTML do code dung (dang tin), phan loi (intro/nhan_xet) lay tu proposal cua AI #2.
So tien tong do code tinh — khong lay so model tu cong.
"""
import base64
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date

from config import (AIRTABLE_BASE_ID, AIRTABLE_TOKEN, BRIEF_FILE_FIELD_ID,
                    PLAN_FILE_FIELD_ID, PROPOSAL_FILE_FIELD_ID)


def _esc(s) -> str:
    """Escape & < > chong XSS khi nhet field/text nguoi dung vao HTML.
    quote=False -> KHONG escape dau ngoac kep -> text thuong hien thi y het (chi vo hieu hoa tag injection)."""
    return html.escape("" if s is None else str(s), quote=False)


def _md_inline(text: str) -> str:
    """Escape HTML (chong XSS) roi markdown inline: **bold** -> <strong>. Dung cho text AI/nguoi dung."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _esc(text))


def _md_to_html(md: str) -> str:
    """Convert markdown co ban (bullet *, -, **bold**) -> HTML. Dung cho text AI (insight...)
    vi LLM hay tra markdown ma HTML khong render duoc. Bullet long nhau -> lam phang 1 cap."""
    md = (md or "").strip()
    if not md:
        return ""
    out, in_list = [], False
    for raw in md.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^[\*\-]\s+(.*)", line)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_md_inline(m.group(1))}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{_md_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "".join(out)


def _money(n) -> str:
    return f"{n:,}đ" if isinstance(n, (int, float)) else "—"


_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#1a1a2e;background:#f4f5f7;padding:24px;line-height:1.5}
.wrap{max-width:860px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08)}
.head{background:linear-gradient(135deg,#ff6a00,#ff3d57);color:#fff;padding:28px 32px}
.head .code{display:inline-block;background:rgba(255,255,255,.22);padding:3px 12px;border-radius:20px;font-size:13px;font-weight:600;letter-spacing:.5px}
.head h1{font-size:26px;margin:10px 0 4px}
.head .sub{opacity:.92;font-size:14px}
.meta{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:#eceef1}
.meta div{background:#fff;padding:14px 20px}
.meta b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:#8a8f99;margin-bottom:3px}
.intro{padding:20px 32px;font-size:15px;color:#3a3f4b;background:#fffaf6;border-left:4px solid #ff6a00;margin:0}
.intro-warn{background:#fff4f0;border-left:5px solid #dc2626}
.intro-crit{background:#fdecec;border-left:6px solid #b91c1c}
.wline{color:#b91c1c;font-weight:700;font-size:14px;margin-bottom:10px;line-height:1.5}
.intro-crit .wline{font-weight:800}
.sec{padding:8px 32px 4px;font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:#8a8f99;font-weight:700;margin-top:8px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;padding:16px 32px}
.card{border:1px solid #e6e8ec;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card.key{border-color:#ff6a00;box-shadow:0 0 0 2px rgba(255,106,0,.15)}
.thumb{height:160px;background:linear-gradient(135deg,#eef1f5,#dfe3ea);display:flex;align-items:center;justify-content:center;color:#aab;font-size:34px}
.thumb.has-img{background:#fff;background-size:contain;background-repeat:no-repeat;background-position:center}
.card .body{padding:14px 16px;flex:1;display:flex;flex-direction:column}
.badge{align-self:flex-start;font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;margin-bottom:6px}
.imgnote{font-size:10px;color:#9aa0a8;font-style:italic;margin-bottom:6px}
.b-cat{background:#e6f4ea;color:#1a7f37}
.b-cre{background:#fff1e0;color:#c2410c}
.card h3{font-size:16px;margin-bottom:4px}
.card .spec{font-size:13px;color:#6b7280;flex:1}
.price{margin-top:10px;padding-top:10px;border-top:1px dashed #e6e8ec;display:flex;justify-content:space-between;align-items:baseline;font-size:13px}
.price .tt{font-size:16px;font-weight:700;color:#1a1a2e}
.price .quote{color:#c2410c;font-weight:600}
.sum{margin:8px 32px 24px;padding:18px 22px;background:#1a1a2e;color:#fff;border-radius:12px;display:flex;justify-content:space-between;align-items:center}
.sum .big{font-size:24px;font-weight:800}
.sum .ok{color:#4ade80}.sum .over{color:#f87171}
.foot{padding:18px 32px;border-top:1px solid #eee;font-size:13px;color:#8a8f99;text-align:center}
.decision{margin:0 32px 12px;padding:16px 20px;background:#f5f8ff;border:1px solid #dbe4ff;border-radius:12px;font-size:14px;color:#384}
.decision p{margin:0 0 8px;color:#33384a}
.decision b{color:#1a1a2e}
.decision details{margin-top:6px}
.decision summary{cursor:pointer;color:#3a5bd9;font-weight:600;font-size:13px}
.decision .ins{margin-top:8px;padding:10px 14px;background:#fff;border-radius:8px;font-size:13px;color:#4a5568;line-height:1.6}
.decision .ins ul{margin:4px 0;padding-left:18px}
.decision .ins li{margin:3px 0}
.decision .ins p{margin:4px 0}
.decision .ins strong{color:#1a1a2e}
.disclaimer{margin:0 32px 18px;font-size:12px;color:#9aa0a8;font-style:italic;line-height:1.5}
"""


def build_proposal_html(fields: dict, proposal: dict, total: int, images: dict | None = None,
                        decision: dict | None = None) -> str:
    images = images or {}
    code = fields.get("Mã project", "")
    budget = fields.get("Budget (VND)") or 0
    remain = budget - total
    over = total > budget if budget else False

    cards = []
    for it in proposal.get("items", []):
        is_cat = it.get("nguon") == "catalogue"
        name = it.get("ten", "")
        is_key = bool(it.get("item_key"))
        qty = it.get("so_luong") or 0
        unit = it.get("don_gia")
        spec_bits = [b for b in [it.get("chat_lieu"), it.get("kich_thuoc")] if b]
        spec = " · ".join(spec_bits) or it.get("can_cu_gia", "")
        img = images.get(name)
        thumb = (f'<div class="thumb has-img" style="background-image:url({img})"></div>'
                 if img else '<div class="thumb">🎁</div>')
        if unit:
            price = (f'<div class="price"><span>{_money(unit)} × {qty}</span>'
                     f'<span class="tt">{_money(unit * qty)}</span></div>')
        else:
            price = ('<div class="price"><span>Số lượng ' + str(qty) + '</span>'
                     '<span class="quote">Chờ báo giá vendor</span></div>')
        badge = ('<span class="badge b-cat">Có sẵn</span>' if is_cat
                 else '<span class="badge b-cre">Sáng tạo</span>')
        img_note = ('<div class="imgnote">Hình minh hoạ ý tưởng — AI tạo, chưa phải mẫu cuối</div>'
                    if (img and not is_cat) else '')
        cards.append(
            f'<div class="card{" key" if is_key else ""}">{thumb}<div class="body">'
            f'{badge}<h3>{"⭐ " if is_key else ""}{_esc(name)}</h3>'
            f'{img_note}<div class="spec">{_esc(spec)}</div>{price}</div></div>'
        )

    meta = ""
    for label, key in [("Game", "Game"), ("Mục đích", "Mục đích"),
                       ("Target audience", "Target audience"), ("Deadline cần hàng", "Deadline cần hàng")]:
        val = fields.get(key) or "—"
        meta += f"<div><b>{label}</b>{_esc(val)}</div>"

    sum_class = "over" if over else "ok"
    sum_note = ("VƯỢT budget" if over else f"còn dư {_money(remain)}") if budget else "chưa có budget"

    # Gop canh bao deadline (do) VAO chung khoi mo ta (nhan_xet) — 1 khoi, khong tach banner rieng.
    warn_txt = (fields.get("Cảnh báo deadline") or "").strip()
    nhan_xet = _md_inline(proposal.get("nhan_xet", ""))
    if warn_txt:
        sev = "intro-crit" if warn_txt.startswith("🔴") else "intro-warn"
        intro_block = (f'<div class="intro {sev}"><div class="wline">{_md_inline(warn_txt)}</div>{nhan_xet}</div>')
    else:
        intro_block = f'<p class="intro">{nhan_xet}</p>'

    # Mục "Cơ sở quyết định": tier (code tính) + giải trình AI + insight game (web) -> requester/sếp đánh giá.
    dec = decision or {}
    tier, per_unit = dec.get("tier"), dec.get("per_unit")
    rationale = (dec.get("rationale") or "").strip()
    insight = (dec.get("insight") or "").strip()
    rows = []
    if tier and per_unit:
        rows.append(f'<p><b>Phân khúc:</b> {_esc(tier)} — ngân sách ~{_money(per_unit)}/bộ quà '
                    f'(tự tính: {_money(budget)} ÷ {_esc(fields.get("Số lượng (bộ/suất)", "?"))} bộ)</p>')
    if rationale:
        rows.append(f'<p><b>Vì sao bộ này:</b> {_md_inline(rationale)}</p>')
    if insight:
        rows.append('<details><summary>Insight game (nguồn web)</summary>'
                    f'<div class="ins">{_md_to_html(insight)}</div></details>')
    decision_html = (f'<div class="sec">📋 Cơ sở quyết định</div><div class="decision">{"".join(rows)}</div>'
                     if rows else "")
    disclaimer = ('<div class="disclaimer">Ảnh chỉ mang tính minh hoạ: item có sẵn là ảnh tham khảo kiểu dáng, '
                  'item sáng tạo là concept do AI tạo. Thành phẩm sẽ được THIẾT KẾ RIÊNG theo nhận diện của game '
                  '(màu sắc, nhân vật, logo) sau khi chốt đề xuất.</div>')

    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Proposal {_esc(code)}</title><style>{_CSS}</style></head><body><div class="wrap">
<div class="head"><span class="code">{_esc(code)}</span>
<h1>{_esc(fields.get("Tên project", "Đề xuất Merchandise"))}</h1>
<div class="sub">Bộ quà tặng đề xuất · {date.today():%d/%m/%Y}</div></div>
<div class="meta">{meta}<div><b>Budget</b>{_money(budget)}</div>
<div><b>Số lượng/bộ</b>{_esc(fields.get("Số lượng (bộ/suất)", "—"))}</div></div>
{intro_block}
<div class="sec">Danh sách items đề xuất</div>
<div class="grid">{"".join(cards)}</div>
<div class="sum"><div>Tổng dự kiến<br><span style="font-size:12px;opacity:.7">(chưa gồm item chờ báo giá)</span></div>
<div style="text-align:right"><span class="big">{_money(total)}</span><br>
<span class="{sum_class}">{sum_note}</span></div></div>
{decision_html}
{disclaimer}
<div class="foot">Proposal tạo tự động bởi <b>Merch Agent — VNGGames</b> · vui lòng phản hồi Duyệt / Cần sửa trên Airtable</div>
</div></body></html>"""


def _upload_attachment(record_id: str, field_id: str, content_type: str,
                       filename: str, raw: bytes) -> dict:
    """Upload 1 file vao field attachment qua Airtable Upload Attachment API.
    Retry 3 lan: upload hay dinh loi transient (403/429/5xx, mang) -> tranh _scan_new bat
    exception roi escalate PIC OAN cho 1 hiccup tam thoi."""
    url = f"https://content.airtable.com/v0/{AIRTABLE_BASE_ID}/{record_id}/{field_id}/uploadAttachment"
    data = json.dumps({
        "contentType": content_type,
        "filename": filename,
        "file": base64.b64encode(raw).decode("ascii"),
    }).encode()
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last_err = e
            print(f"[upload] lỗi {filename} (lần {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise last_err


def upload_proposal(record_id: str, html: str, code: str) -> dict:
    """Upload HTML vao field 'File proposal'."""
    return _upload_attachment(record_id, PROPOSAL_FILE_FIELD_ID, "text/html",
                              f"proposal_{code}.html", html.encode("utf-8"))


def upload_plan(record_id: str, xlsx: bytes, code: str) -> dict:
    """Upload file Excel plan san xuat (Buoc 4) vao field 'File plan san xuat'."""
    return _upload_attachment(
        record_id, PLAN_FILE_FIELD_ID,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        f"plan_san_xuat_{code}.xlsx", xlsx)


def upload_brief(record_id: str, pptx: bytes, code: str) -> dict:
    """Upload deck brief design (.pptx) vao field 'File brief design' (Buoc 5)."""
    return _upload_attachment(
        record_id, BRIEF_FILE_FIELD_ID,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        f"brief_design_{code}.pptx", pptx)
