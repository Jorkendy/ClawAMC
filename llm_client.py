"""LLM client (OpenAI-compatible) — moi cuoc goi LLM deu di qua ask_llm_json.

Backend: LiteLLM self-host (llm.vinhpham.com.vn). Neu endpoint dat sau Cloudflare
Access thi gui kem 2 header service token (CF-Access-Client-Id / CF-Access-Client-Secret).
"""
import json
import time

from openai import (APIConnectionError, APITimeoutError, InternalServerError,
                    OpenAI, RateLimitError)

from config import (CF_ACCESS_CLIENT_ID, CF_ACCESS_CLIENT_SECRET, LLM_API_KEY,
                    LLM_BASE_URL, LLM_GROUNDING_MODEL, LLM_IMAGE_MODEL, LLM_MODEL,
                    LLM_REASONING_EFFORT)

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

llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL,
             default_headers=_headers or None)


def ask_llm_json(prompt: str, max_tokens: int = 1500) -> dict:
    kwargs = dict(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    if LLM_REASONING_EFFORT:
        kwargs["reasoning_effort"] = LLM_REASONING_EFFORT

    # Retry: (a) lỗi API transient (503/429/mạng) -> chờ rồi thử lại; (b) JSON hỏng/rỗng/không object.
    # Lỗi vĩnh viễn (model sai, auth) KHÔNG bắt -> raise ngay -> pipeline escalate PIC nhanh.
    last_err = None
    for attempt in range(4):
        try:
            resp = llm.chat.completions.create(**kwargs)
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
            print(f"[llm] API transient (lần {attempt + 1}/4): {type(e).__name__} — chờ rồi thử lại")
            time.sleep(2 * (attempt + 1))
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            print(f"[llm] parse lỗi (lần {attempt + 1}/4): {e}")
    raise ValueError(f"LLM không trả JSON hợp lệ sau 4 lần: {last_err}")


def ask_llm_grounded(prompt: str, max_tokens: int = 3000) -> str:
    """Chat co Google Search grounding (Gemini doc web that) -> tra text.
    Loi -> '' (de flow khong bi chan neu grounding tat/loi).
    LUU Y: grounding ngon nhieu token -> max_tokens phai rong (700/2000 bi cat cut voi prompt insight, dung >=3000)."""
    for attempt in range(3):
        try:
            resp = llm.chat.completions.create(
                model=LLM_GROUNDING_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
                extra_body={"tools": [{"googleSearch": {}}]},
            )
            return (resp.choices[0].message.content or "").strip()
        except _TRANSIENT_ERRORS as e:
            print(f"[llm] grounded transient (lần {attempt + 1}/3): {type(e).__name__}")
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            print(f"[llm] ask_llm_grounded lỗi: {e}")
            return ""
    return ""


def generate_image(prompt: str) -> str | None:
    """Sinh 1 anh tu prompt -> base64 (b64_json). Loi -> None (de proposal van render, fallback icon)."""
    for attempt in range(3):
        try:
            resp = llm.images.generate(model=LLM_IMAGE_MODEL, prompt=prompt)
            return resp.data[0].b64_json
        except _TRANSIENT_ERRORS as e:
            print(f"[llm] generate_image transient (lần {attempt + 1}/3): {type(e).__name__}")
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            print(f"[llm] generate_image lỗi: {e}")
            return None
    return None
