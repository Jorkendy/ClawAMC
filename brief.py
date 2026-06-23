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
