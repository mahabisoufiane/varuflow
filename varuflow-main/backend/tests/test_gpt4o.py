"""Source-contract tests for GPT-4o AI chat integration.

Uses inspect.getsource() to verify structural contracts:
- OpenAI calls live only in integrations.py (never ai_engine.py)
- Chat endpoint has try/except with fallback
- Proper error handling patterns
"""
import inspect

INTEGRATIONS_SRC = inspect.getsource(
    __import__("app.features.integrations.integrations", fromlist=["_"])
)
AI_ENGINE_SRC = inspect.getsource(
    __import__("app.features.ai.ai_engine", fromlist=["_"])
)


class TestOpenAIIsolation:
    def test_no_openai_import_in_ai_engine(self):
        """CLAUDE.md Rule 10: ai_engine.py must have zero OpenAI imports."""
        assert "import openai" not in AI_ENGINE_SRC

    def test_no_openai_client_in_ai_engine(self):
        assert "openai.AsyncOpenAI" not in AI_ENGINE_SRC
        assert "openai.OpenAI" not in AI_ENGINE_SRC

    def test_openai_used_in_integrations(self):
        assert "import openai" in INTEGRATIONS_SRC

    def test_gpt4o_model_in_integrations(self):
        assert "gpt-4o" in INTEGRATIONS_SRC


class TestChatEndpoint:
    def test_chat_route_exists(self):
        assert "/ai/chat" in INTEGRATIONS_SRC

    def test_chat_has_try_except(self):
        # The OpenAI call must be wrapped in try/except
        assert "except Exception" in INTEGRATIONS_SRC

    def test_chat_returns_fallback_on_failure(self):
        assert "AI service temporarily unavailable" in INTEGRATIONS_SRC

    def test_chat_requires_auth(self):
        assert "get_current_member" in INTEGRATIONS_SRC

    def test_chat_requires_pro_plan(self):
        assert "require_plan(OrgPlan.PRO)" in INTEGRATIONS_SRC


class TestChatSafety:
    def test_openai_api_key_from_settings(self):
        assert "settings.OPENAI_API_KEY" in INTEGRATIONS_SRC

    def test_no_hardcoded_api_key(self):
        assert "sk-" not in INTEGRATIONS_SRC

    def test_max_tokens_capped(self):
        assert "max_tokens=" in INTEGRATIONS_SRC

    def test_user_message_length_capped(self):
        assert "max_length=2000" in INTEGRATIONS_SRC
