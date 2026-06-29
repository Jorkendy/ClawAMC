"""LLM client (OpenAI-compatible) — moi cuoc goi LLM deu di qua ask_llm_json.

Backend: LiteLLM self-host (llm.vinhpham.com.vn). Neu endpoint dat sau Cloudflare
Access thi gui kem 2 header service token (CF-Access-Client-Id / CF-Access-Client-Secret).
"""
import json
import logging
import threading
import time

from openai import (APIConnectionError, APITimeoutError, InternalServerError,
                    OpenAI, RateLimitError)

log = logging.getLogger("merch")

from config import (AI_IMAGES_ENABLED, CF_ACCESS_CLIENT_ID,
                    CF_ACCESS_CLIENT_SECRET, COST_CHAT_PER_1K_IN_VND,
                    COST_CHAT_PER_1K_OUT_VND, COST_GROUNDED_PER_CALL_VND,
                    COST_PER_IMAGE_VND, LLM_API_KEY, LLM_BASE_URL,
                    LLM_GROUNDING_MODEL, LLM_IMAGE_MODEL, LLM_KEY_ANALYSIS,
                    LLM_KEY_BRIEF, LLM_KEY_GROUNDING, LLM_KEY_IMAGE,
                    LLM_KEY_PROPOSAL, LLM_MODEL, LLM_MODEL_FALLBACK,
                    LLM_REASONING_EFFORT)

# --- Theo doi chi phi AI moi proposal ---
# Thread-local: moi luong xu ly 1 project rieng -> tranh lan chi phi khi analyze & decide
# chay song song (2 lock khac nhau). reset_cost() truoc khi dung 1 proposal, get_cost_summary() sau.
_cost = threading.local()


def reset_cost() -> None:
    _cost.d = {"chat_calls": 0, "chat_tok_in": 0, "chat_tok_out": 0,
               "grounded_calls": 0, "grounded_tok_in": 0, "grounded_tok_out": 0, "images": 0,
               "models": set()}


def _cost_d() -> dict:
    d = getattr(_cost, "d", None)
    if d is None:
        reset_cost()
        d = _cost.d
    return d


def _add_cost(**kw) -> None:
    d = _cost_d()
    for k, v in kw.items():
        d[k] = d.get(k, 0) + (v or 0)


def _usage(resp):
    u = getattr(resp, "usage", None)
    return (getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0) if u else (0, 0)


def get_cost_summary() -> dict:
    d = dict(_cost_d())
    d["models"] = sorted(d.get("models") or [])  # set -> list cho de dung/ghi
    return d


def cost_breakdown_vnd(s: dict) -> dict:
    """Tach chi phi VND theo loai (chat/image/grounded) — cho dashboard report. Don gia [GIA DINH] o config."""
    return {
        "chat": round(s.get("chat_tok_in", 0) / 1000 * COST_CHAT_PER_1K_IN_VND
                      + s.get("chat_tok_out", 0) / 1000 * COST_CHAT_PER_1K_OUT_VND),
        "image": round(s.get("images", 0) * COST_PER_IMAGE_VND),
        "grounded": round(s.get("grounded_calls", 0) * COST_GROUNDED_PER_CALL_VND),
    }


def estimate_cost_vnd(s: dict) -> int:
    """Tong chi phi VND (= sum cost_breakdown_vnd)."""
    b = cost_breakdown_vnd(s)
    return b["chat"] + b["image"] + b["grounded"]

# Loi API TAM THOI -> nen retry (Gemini 503 qua tai / 429 rate-limit / mat ket noi / timeout).
# Loi vinh vien (BadRequest model sai, Auth 401/403) KHONG nam day -> raise ngay, khong retry.
_TRANSIENT_ERRORS = (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError)

# User-Agent cua OpenAI SDK ("OpenAI/Python") bi Cloudflare "Block AI bots" chan (403).
# Ghi de UA trung tinh de qua WAF. (Fix chinh nen dat o Cloudflare: skip bot rule cho
# request co service token hop le — xem docs.)
_headers = {"User-Agent": "merch-agent/1.0"}
if CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET:
    _headers["CF-Access-Client-Id"] = CF_ACCESS_CLIENT_ID
    _headers["CF-Access-Client-Secret"] = CF_ACCESS_CLIENT_SECRET

# Virtual key theo function (moi chuc nang 1 key LiteLLM rieng -> budget/scope rieng).
# Thieu key (env trong) -> fallback LLM_API_KEY (khong vo khi chua cau hinh xong).
_FUNC_KEYS = {
    "analysis": LLM_KEY_ANALYSIS or LLM_API_KEY,
    "proposal": LLM_KEY_PROPOSAL or LLM_API_KEY,
    "brief": LLM_KEY_BRIEF or LLM_API_KEY,
    "grounding": LLM_KEY_GROUNDING or LLM_API_KEY,
    "image": LLM_KEY_IMAGE or LLM_API_KEY,
}
_clients: dict = {}


def _client_for(func: str | None) -> OpenAI:
    """OpenAI client dung virtual key cua function (func thieu/None -> LLM_API_KEY). Cache theo key."""
    key = _FUNC_KEYS.get(func or "", "") or LLM_API_KEY
    if key not in _clients:
        _clients[key] = OpenAI(api_key=key, base_url=LLM_BASE_URL, default_headers=_headers or None)
    return _clients[key]


# Client mac dinh (LLM_API_KEY) cho goi khong gan function.
llm = _client_for(None)


def _ask_json_once(model: str, prompt: str, max_tokens: int, func: str | None = None) -> dict:
    """Goi 1 model -> JSON dict. Retry transient (503/429/mang) + parse loi 4 lan; het -> ValueError."""
    kwargs = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    if LLM_REASONING_EFFORT:
        kwargs["reasoning_effort"] = LLM_REASONING_EFFORT

    client = _client_for(func)
    last_err = None
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(**kwargs)
            tin, tout = _usage(resp)
            _add_cost(chat_calls=1, chat_tok_in=tin, chat_tok_out=tout)
            _cost_d().setdefault("models", set()).add(getattr(resp, "model", "") or model)
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                raise ValueError("LLM trả về rỗng (content None/empty)")
            if raw.startswith("```"):
                raw = raw.split("```")[1].removeprefix("json").strip()
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError(f"LLM trả về không phải JSON object: {type(data).__name__}")
            return data
        except _TRANSIENT_ERRORS as e:
            last_err = e
            log.warning(f"[llm] {model} transient (lần {attempt + 1}/4): {type(e).__name__} — chờ rồi thử lại")
            time.sleep(2 * (attempt + 1))
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            log.warning(f"[llm] {model} parse lỗi (lần {attempt + 1}/4): {e}")
    raise ValueError(f"LLM không trả JSON hợp lệ sau 4 lần ({model}): {last_err}")


def ask_llm_json(prompt: str, max_tokens: int = 1500, func: str | None = None) -> dict:
    """Goi LLM_MODEL; neu fail (vd 503 do LiteLLM fallback hong) va co LLM_MODEL_FALLBACK -> thu model du phong.
    func = chuc nang goi (analysis/proposal/brief) -> chon virtual key tuong ung; None -> LLM_API_KEY.
    Loi vinh vien (model sai, auth) khong retry o _ask_json_once -> raise ngay -> pipeline escalate PIC."""
    try:
        return _ask_json_once(LLM_MODEL, prompt, max_tokens, func)
    except ValueError as e:
        if LLM_MODEL_FALLBACK and LLM_MODEL_FALLBACK != LLM_MODEL:
            log.warning(f"[llm] {LLM_MODEL} fail ({e}) -> thử fallback model {LLM_MODEL_FALLBACK}")
            return _ask_json_once(LLM_MODEL_FALLBACK, prompt, max_tokens, func)
        raise


def ask_llm_grounded(prompt: str, max_tokens: int = 3000) -> str:
    """Chat co Google Search grounding (Gemini doc web that) -> tra text.
    Loi -> '' (de flow khong bi chan neu grounding tat/loi).
    LUU Y: grounding ngon nhieu token -> max_tokens phai rong (700/2000 bi cat cut voi prompt insight, dung >=3000)."""
    for attempt in range(3):
        try:
            resp = _client_for("grounding").chat.completions.create(
                model=LLM_GROUNDING_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
                extra_body={"tools": [{"googleSearch": {}}]},
            )
            tin, tout = _usage(resp)
            _add_cost(grounded_calls=1, grounded_tok_in=tin, grounded_tok_out=tout)
            _cost_d().setdefault("models", set()).add(getattr(resp, "model", "") or LLM_GROUNDING_MODEL)
            return (resp.choices[0].message.content or "").strip()
        except _TRANSIENT_ERRORS as e:
            log.warning(f"[llm] grounded transient (lần {attempt + 1}/3): {type(e).__name__}")
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            log.error(f"[llm] ask_llm_grounded lỗi: {e}")
            return ""
    return ""


def generate_image(prompt: str, timeout: float | None = None) -> str | None:
    """Sinh 1 anh tu prompt -> base64 (b64_json). Loi -> None (de van render, fallback icon).
    timeout (giay): cap CUNG tong thoi gian — het gio -> None NGAY.
    LUU Y: timeout cua SDK chi cap MOI HTTP attempt, ma SDK OpenAI mac dinh tu retry 2 lan
    khi APITimeoutError => 1 anh cham co the treo 3x timeout (vd 60s -> 180s). Phai dat
    max_retries=0 khi co timeout de timeout thanh cap cung that, tranh block pipeline."""
    if not AI_IMAGES_ENABLED:
        log.warning("[llm] AI images TAT (AI_IMAGES_ENABLED=false) -> bo anh (tiet kiem chi phi test)")
        return None
    base = _client_for("image")
    client = base.with_options(max_retries=0, timeout=timeout) if timeout else base
    for attempt in range(3):
        try:
            resp = client.images.generate(model=LLM_IMAGE_MODEL, prompt=prompt)
            _add_cost(images=1)
            _cost_d().setdefault("models", set()).add(getattr(resp, "model", "") or LLM_IMAGE_MODEL)
            return resp.data[0].b64_json
        except APITimeoutError:
            log.warning(f"[llm] generate_image timeout ({timeout}s) -> bỏ ảnh")
            return None
        except _TRANSIENT_ERRORS as e:
            log.warning(f"[llm] generate_image transient (lần {attempt + 1}/3): {type(e).__name__}")
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            log.error(f"[llm] generate_image lỗi: {e}")
            return None
    return None
