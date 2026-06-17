"""LLM client (OpenAI-compatible) — moi cuoc goi LLM deu di qua ask_llm_json.

Backend: LiteLLM self-host (llm.vinhpham.com.vn). Neu endpoint dat sau Cloudflare
Access thi gui kem 2 header service token (CF-Access-Client-Id / CF-Access-Client-Secret).
"""
import json

from openai import OpenAI

from config import (CF_ACCESS_CLIENT_ID, CF_ACCESS_CLIENT_SECRET, LLM_API_KEY,
                    LLM_BASE_URL, LLM_MODEL, LLM_REASONING_EFFORT)

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

    # LLM co the tra JSON hong / bi cat (het max_tokens) / content rong / khong phai object.
    # Retry vai lan; van fail -> raise loi ro de pipeline danh dau record (khong nuot im lang).
    last_err = None
    for attempt in range(3):
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
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            print(f"[llm] parse lỗi (lần {attempt + 1}/3): {e}")
    raise ValueError(f"LLM không trả JSON hợp lệ sau 3 lần: {last_err}")
