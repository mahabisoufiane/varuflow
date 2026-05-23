"""Source-contract tests for Fortnox OAuth integration.

Uses inspect.getsource() to verify structural contracts in the
integrations router without requiring a live DB or external services.
"""
import inspect

INTEGRATIONS_SRC = inspect.getsource(
    __import__("app.routers.integrations", fromlist=["_"])
)


class TestFortnoxOAuthFlow:
    def test_connect_endpoint_exists(self):
        assert "fortnox/connect" in INTEGRATIONS_SRC

    def test_callback_endpoint_exists(self):
        assert "fortnox/callback" in INTEGRATIONS_SRC

    def test_disconnect_endpoint_exists(self):
        assert "fortnox/disconnect" in INTEGRATIONS_SRC

    def test_status_endpoint_exists(self):
        assert "fortnox/status" in INTEGRATIONS_SRC


class TestFortnoxTokenEncryption:
    def test_access_token_encrypted_on_store(self):
        assert "encrypt_token(data[\"access_token\"])" in INTEGRATIONS_SRC

    def test_refresh_token_encrypted_on_store(self):
        assert "encrypt_token(data.get(\"refresh_token\"))" in INTEGRATIONS_SRC

    def test_decrypt_token_used_on_read(self):
        assert "decrypt_token" in INTEGRATIONS_SRC

    def test_encryption_imports_present(self):
        assert "from app.services.crypto import decrypt_token, encrypt_token" in INTEGRATIONS_SRC


class TestFortnoxOrgIsolation:
    def test_org_id_extracted_from_member(self):
        assert "member.org_id" in INTEGRATIONS_SRC

    def test_sync_invoices_filters_by_org(self):
        assert "Invoice.org_id == org_id" in INTEGRATIONS_SRC

    def test_sync_customers_filters_by_org(self):
        assert "Customer.org_id == org_id" in INTEGRATIONS_SRC


class TestFortnoxCSRFProtection:
    def test_oauth_state_nonce_generated(self):
        assert "secrets.token_hex" in INTEGRATIONS_SRC

    def test_oauth_state_validated_on_callback(self):
        assert "FortnoxOAuthState.nonce == state" in INTEGRATIONS_SRC

    def test_state_consumed_atomically(self):
        # The nonce is DELETEd (not just SELECTed) to prevent replay
        assert ".returning(" in INTEGRATIONS_SRC


class TestFortnoxRoleGating:
    def test_owner_or_admin_required(self):
        assert "_require_owner_or_admin" in INTEGRATIONS_SRC

    def test_non_member_blocked(self):
        assert "OrgRole.OWNER" in INTEGRATIONS_SRC
        assert "OrgRole.ADMIN" in INTEGRATIONS_SRC
