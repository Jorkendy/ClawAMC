"""Test chon virtual key theo function trong llm_client (khong network)."""
import llm_client


def test_unknown_func_falls_back_to_default():
    # func la / khong khop -> dung LLM_API_KEY (cung client voi None)
    assert llm_client._client_for("nonexistent") is llm_client._client_for(None)


def test_distinct_keys_give_distinct_clients(monkeypatch):
    monkeypatch.setattr(llm_client, "_FUNC_KEYS", {"a": "sk-aaa", "b": "sk-bbb"})
    monkeypatch.setattr(llm_client, "_clients", {})
    ca, cb = llm_client._client_for("a"), llm_client._client_for("b")
    assert ca is not cb
    assert ca.api_key == "sk-aaa" and cb.api_key == "sk-bbb"
    # cache: cung func -> cung client object
    assert llm_client._client_for("a") is ca


def test_same_key_shares_one_client(monkeypatch):
    monkeypatch.setattr(llm_client, "_FUNC_KEYS", {"a": "sk-x", "b": "sk-x"})
    monkeypatch.setattr(llm_client, "_clients", {})
    assert llm_client._client_for("a") is llm_client._client_for("b")


def test_all_five_functions_registered():
    for f in ("analysis", "proposal", "brief", "grounding", "image"):
        assert f in llm_client._FUNC_KEYS


def test_cost_breakdown_prefers_real_usd():
    s = {"usd_chat": 0.01, "usd_image": 0.08, "usd_grounded": 0.04,
         "chat_tok_in": 9999, "chat_tok_out": 9999, "images": 9, "grounded_calls": 9}
    b = llm_client.cost_breakdown_vnd(s)
    assert b["chat"] == round(0.01 * llm_client.USD_TO_VND)
    assert b["image"] == round(0.08 * llm_client.USD_TO_VND)
    assert b["grounded"] == round(0.04 * llm_client.USD_TO_VND)


def test_cost_breakdown_falls_back_when_no_real():
    s = {"usd_chat": 0.0, "usd_image": 0.0, "usd_grounded": 0.0,
         "images": 2, "grounded_calls": 1, "chat_tok_in": 1000, "chat_tok_out": 1000}
    b = llm_client.cost_breakdown_vnd(s)
    assert b["image"] == 2 * llm_client.COST_PER_IMAGE_VND
    assert b["grounded"] == 1 * llm_client.COST_GROUNDED_PER_CALL_VND
