from app.config import settings
from app.services.agent import planning


def test_provider_picks_groq_when_only_groq_configured(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-groq-key")
    monkeypatch.setattr(settings, "azure_openai_endpoint", None)
    monkeypatch.setattr(settings, "azure_openai_api_key", None)
    monkeypatch.setattr(settings, "azure_openai_deployment", None)
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    provider = planning._provider()

    assert isinstance(provider, planning.GroqProvider)


def test_provider_prefers_groq_over_azure_and_anthropic(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-groq-key")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://example.com")
    monkeypatch.setattr(settings, "azure_openai_api_key", "azure-key")
    monkeypatch.setattr(settings, "azure_openai_deployment", "deployment")
    monkeypatch.setattr(settings, "anthropic_api_key", "anthropic-key")

    provider = planning._provider()

    assert isinstance(provider, planning.GroqProvider)


def test_provider_falls_back_to_azure_when_groq_unset(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://example.com")
    monkeypatch.setattr(settings, "azure_openai_api_key", "azure-key")
    monkeypatch.setattr(settings, "azure_openai_deployment", "deployment")
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    provider = planning._provider()

    assert isinstance(provider, planning.AzureOpenAIProvider)


def test_provider_returns_none_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "azure_openai_endpoint", None)
    monkeypatch.setattr(settings, "azure_openai_api_key", None)
    monkeypatch.setattr(settings, "azure_openai_deployment", None)
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    assert planning._provider() is None


def test_groq_request_omits_response_format(monkeypatch):
    # openai/gpt-oss-20b (a reasoning model) rejects response_format=json_object with
    # a 400 "json_validate_failed" error for this prompt, so the request must rely on
    # the SYSTEM_PROMPT instruction plus _parse_decision's own JSON extraction instead.
    monkeypatch.setattr(settings, "groq_api_key", "test-groq-key")
    captured = {}

    def fake_post(url, **kwargs):
        captured["json"] = kwargs["json"]

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": '{"destination": "Kyoto", "confidence": 0.9, "rationale": "test", "interests": "Food"}'}}]}

        return FakeResponse()

    monkeypatch.setattr(planning, "_post_agent_request", fake_post)

    decision = planning.GroqProvider().resolve("a trip brief", ["Kyoto"])

    assert "response_format" not in captured["json"]
    assert decision.destination == "Kyoto"


def test_groq_request_sets_low_reasoning_effort(monkeypatch):
    # gpt-oss reasoning models can burn most of max_tokens on hidden reasoning and
    # truncate the actual JSON answer mid-string; reasoning_effort=low keeps enough
    # budget free for the full response (observed: 1226/1400 reasoning tokens without
    # this, dropping to ~115 with it).
    monkeypatch.setattr(settings, "groq_api_key", "test-groq-key")
    captured = {}

    def fake_post(url, **kwargs):
        captured["json"] = kwargs["json"]

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": '{"destination": "Kyoto", "confidence": 0.9, "rationale": "test", "interests": ["Food"]}'}}]}

        return FakeResponse()

    monkeypatch.setattr(planning, "_post_agent_request", fake_post)

    planning.GroqProvider().resolve("a trip brief", ["Kyoto"])

    assert captured["json"]["reasoning_effort"] == "low"


def test_normalize_decision_coerces_bare_string_interests():
    decision = planning._parse_decision('{"destination": "Kyoto", "confidence": 0.9, "rationale": "test", "interests": "Food"}')

    assert decision.interests == ["Food"]
