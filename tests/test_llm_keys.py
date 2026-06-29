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
