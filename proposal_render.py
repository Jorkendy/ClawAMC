"""Render proposal ra HTML + upload vao field 'File proposal' (Airtable Upload Attachment API).

Khung HTML do code dung (dang tin), phan loi (intro/nhan_xet) lay tu proposal cua AI #2.
So tien tong do code tinh — khong lay so model tu cong.
"""
import base64
import json
import urllib.request
from datetime import date

from config import AIRTABLE_BASE_ID, AIRTABLE_TOKEN, PROPOSAL_FILE_FIELD_ID


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
.warn{padding:14px 32px;font-size:14px;font-weight:600;color:#b45309;background:#fff4e5;border-left:4px solid #f59e0b;margin:0}
.sec{padding:8px 32px 4px;font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:#8a8f99;font-weight:700;margin-top:8px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;padding:16px 32px}
.card{border:1px solid #e6e8ec;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card.key{border-color:#ff6a00;box-shadow:0 0 0 2px rgba(255,106,0,.15)}
.thumb{height:120px;background:linear-gradient(135deg,#eef1f5,#dfe3ea);display:flex;align-items:center;justify-content:center;color:#aab;font-size:34px}
.card .body{padding:14px 16px;flex:1;display:flex;flex-direction:column}
.badge{align-self:flex-start;font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;margin-bottom:6px}
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
"""


def build_proposal_html(fields: dict, proposal: dict, total: int, images: dict | None = None) -> str:
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
        thumb = (f'<div class="thumb" style="background-image:url({img});background-size:cover"></div>'
                 if img else '<div class="thumb">🎁</div>')
        if unit:
            price = (f'<div class="price"><span>{_money(unit)} × {qty}</span>'
                     f'<span class="tt">{_money(unit * qty)}</span></div>')
        else:
            price = ('<div class="price"><span>Số lượng ' + str(qty) + '</span>'
                     '<span class="quote">Chờ báo giá vendor</span></div>')
        badge = ('<span class="badge b-cat">Có sẵn</span>' if is_cat
                 else '<span class="badge b-cre">Sáng tạo</span>')
        cards.append(
            f'<div class="card{" key" if is_key else ""}">{thumb}<div class="body">'
            f'{badge}<h3>{"⭐ " if is_key else ""}{name}</h3>'
            f'<div class="spec">{spec}</div>{price}</div></div>'
        )

    meta = ""
    for label, key in [("Game", "Game"), ("Mục đích", "Mục đích"),
                       ("Target audience", "Target audience"), ("Deadline cần hàng", "Deadline cần hàng")]:
        val = fields.get(key) or "—"
        meta += f"<div><b>{label}</b>{val}</div>"

    sum_class = "over" if over else "ok"
    sum_note = ("VƯỢT budget" if over else f"còn dư {_money(remain)}") if budget else "chưa có budget"

    warn_txt = (fields.get("Cảnh báo deadline") or "").strip()
    warn_html = f'<div class="warn">{warn_txt}</div>' if warn_txt else ""

    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Proposal {code}</title><style>{_CSS}</style></head><body><div class="wrap">
<div class="head"><span class="code">{code}</span>
<h1>{fields.get("Tên project", "Đề xuất Merchandise")}</h1>
<div class="sub">Bộ quà tặng đề xuất · {date.today():%d/%m/%Y}</div></div>
<div class="meta">{meta}<div><b>Budget</b>{_money(budget)}</div>
<div><b>Số lượng/bộ</b>{fields.get("Số lượng (bộ/suất)", "—")}</div></div>
{warn_html}
<p class="intro">{proposal.get("nhan_xet", "")}</p>
<div class="sec">Danh sách items đề xuất</div>
<div class="grid">{"".join(cards)}</div>
<div class="sum"><div>Tổng dự kiến<br><span style="font-size:12px;opacity:.7">(chưa gồm item chờ báo giá)</span></div>
<div style="text-align:right"><span class="big">{_money(total)}</span><br>
<span class="{sum_class}">{sum_note}</span></div></div>
<div class="foot">Proposal tạo tự động bởi <b>Merch Agent — VNGGames</b> · vui lòng phản hồi Duyệt / Cần sửa trên Airtable</div>
</div></body></html>"""


def upload_proposal(record_id: str, html: str, code: str) -> dict:
    """Upload HTML vao field 'File proposal' qua Airtable Upload Attachment API."""
    url = f"https://content.airtable.com/v0/{AIRTABLE_BASE_ID}/{record_id}/{PROPOSAL_FILE_FIELD_ID}/uploadAttachment"
    payload = {
        "contentType": "text/html",
        "filename": f"proposal_{code}.html",
        "file": base64.b64encode(html.encode("utf-8")).decode("ascii"),
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())
