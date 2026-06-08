"""JWT authentication dependency for FastAPI routes.

Verifies Supabase-issued JWTs and resolves the current user + org context.
In local dev (ENV=development) requests without a token are served as the
built-in dev user, so the app works end-to-end without a live Supabase project.
"""
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.auth import AuthUser
from app.models.organization import (
    Organization,
    OrganizationMember,
    OrgIpAllowlistEntry,
    OrgRole,
)
from app.services.ip_allowlist import ip_matches_allowlist
from app.services.mfa_enforcement import is_mfa_required_for_owner

# auto_error=False so we can return a 401 ourselves (and allow dev bypass)
_bearer = HTTPBearer(auto_error=False)


class MemberCtx(tuple):
    """Backward-compatible wrapper returned by get_current_member.

    Supports BOTH the new tuple-unpacking style used by modern routers::

        _user, member = ctx
        org_id = member.org_id

    AND the old dict-subscript style still used by ~40 legacy files::

        org_id = member["org_id"]
        role   = member.get("role", "MEMBER")
    """

    def __new__(cls, user: dict, member, plan=None):
        return super().__new__(cls, (user, member))

    def __init__(self, user: dict, member, plan=None):
        # tuple.__init__ is no-op; stash extras as attrs
        self._user = user
        self._member = member
        self._plan = plan

    # ── dict-style subscript ──────────────────────────────────────────────
    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(key)
        _map = {
            "org_id":   self._member.org_id,
            "user_id":  self._user.get("user_id"),
            "email":    self._user.get("email", ""),
            "role":     (self._member.role.value
                         if hasattr(self._member.role, "value")
                         else str(self._member.role)),
            "plan":     self._plan,
            "staff_id": None,
        }
        if key in _map:
            return _map[key]
        return self._user.get(key)

    def get(self, key, default=None):
        try:
            val = self[key]
            return val if val is not None else default
        except Exception:
            return default

    def __contains__(self, key):
        return key in ("org_id", "user_id", "email", "role", "plan", "staff_id")


# Stable dev identities — only used when ENV=development and no token is sent
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_ORG_ID  = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _decode_token(token: str) -> dict:
    """Decode and verify a Supabase JWT.

    Default behaviour: verify HS256 signature against SUPABASE_JWT_SECRET.
    The unverified fallback only fires in local development when both
    ENFORCE_JWT_SIGNATURE=False AND ENV=development. Production must always
    verify — a missing secret raises rather than silently accepting forged
    tokens.
    """
    if settings.ENFORCE_JWT_SIGNATURE:
        if not settings.SUPABASE_JWT_SECRET:
            raise JWTError(
                "SUPABASE_JWT_SECRET is required when ENFORCE_JWT_SIGNATURE=True"
            )
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )

    # Unverified decode — only reachable when ENFORCE_JWT_SIGNATURE=False.
    # Guard against accidental production use: refuse unless ENV=development
    # AND ALLOW_DEV_BYPASS is explicitly True.
    if settings.ENV != "development" or not settings.ALLOW_DEV_BYPASS:
        raise JWTError(
            "Unverified JWT decode is not allowed outside development mode"
        )
    # nosemgrep: python.jwt.security.unverified-jwt-decode.unverified-jwt-decode
    return jwt.decode(  # nosemgrep: python.jwt.security.unverified-jwt-decode.unverified-jwt-decode
        token,
        "",
        algorithms=["HS256"],
        options={"verify_signature": False, "verify_aud": False},  # dev-only  # nosemgrep: python.jwt.security.unverified-jwt-decode.unverified-jwt-decode
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Return basic user info from the JWT payload.

    In development mode (ENV=development or DEBUG=True):
    - No token → dev user
    - Invalid/expired token → dev user (handles stale localStorage sessions)
    """
    # Dev bypass requires BOTH ENV=development AND ALLOW_DEV_BYPASS=True.
    # This prevents a single misconfigured env var (e.g. ENV accidentally
    # set to "development" on Railway) from disabling authentication.
    dev_bypass = settings.ENV == "development" and settings.ALLOW_DEV_BYPASS

    if not credentials:
        if dev_bypass:
            return {"user_id": DEV_USER_ID, "email": "dev@varuflow.local"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = _decode_token(credentials.credentials)
    except JWTError:
        # In dev bypass mode, fall through rather than blocking everything
        # when localStorage holds a stale token. Production always rejects.
        if dev_bypass:
            return {"user_id": DEV_USER_ID, "email": "dev@varuflow.local"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Block portal tokens from accessing internal routes
    if payload.get("type") == "portal":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Portal tokens cannot be used on internal routes",
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    # Guard the UUID cast. Supabase issues UUID subs today, but a crafted
    # or future-format token with a non-UUID `sub` would otherwise raise
    # ValueError at this line and 500 the request — easily triggered by
    # any attacker sending a self-signed HS256 token.
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        )

    return {
        "user_id": uid,
        "email": payload.get("email", ""),
    }


async def get_current_member(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> "MemberCtx":
    """Return user info + their OrganizationMember row.

    Supports ``X-Branch-Org-Id`` header for country workspace switching.
    When present, validates the user has membership in that branch org
    before resolving it as the active org context.

    In development mode, auto-creates the dev org + member on first request.
    """
    # Country workspace: honour X-Branch-Org-Id if the user has access.
    branch_org_header = request.headers.get("X-Branch-Org-Id")
    if branch_org_header:
        try:
            branch_org_id = uuid.UUID(branch_org_header)
            branch_result = await db.execute(
                select(OrganizationMember)
                .where(
                    OrganizationMember.user_id == current_user["user_id"],
                    OrganizationMember.org_id == branch_org_id,
                )
                .limit(1)
            )
            branch_member = branch_result.scalar_one_or_none()
            if branch_member:
                return (current_user, branch_member)
        except (ValueError, AttributeError):
            pass  # Invalid UUID — fall through to default resolution

    # A user may legitimately belong to multiple organizations (they've been
    # invited to a partner's org in addition to their own). There is no
    # org-switch UI yet, so we deterministically pick the earliest-joined
    # membership. ``scalar_one_or_none()`` would raise MultipleResultsFound
    # and 500 the user out of the app entirely \u2014 picking .first() on a
    # stable ordering keeps them logged in while we build the switcher.
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == current_user["user_id"])
        .order_by(OrganizationMember.created_at.asc(), OrganizationMember.id.asc())
        .limit(1)
    )
    member = result.scalar_one_or_none()

    if not member:
        if (
            settings.ENV == "development"
            and settings.ALLOW_DEV_BYPASS
            and current_user["user_id"] == DEV_USER_ID
        ):
            # First-run: seed the dev organization and owner member
            from app.models.organization import OrgPlan
            org = Organization(
                id=DEV_ORG_ID,
                name="Varuflow Demo AB",
                org_number="556123-4567",
                plan=OrgPlan.PRO,
            )
            member = OrganizationMember(
                org_id=DEV_ORG_ID,
                user_id=DEV_USER_ID,
                role=OrgRole.OWNER,
            )
            db.add(org)
            db.add(member)
            await db.commit()
            await db.refresh(member)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found. Complete onboarding first.",
            )
# Item 25: enforce the org-level IP allowlist. Presence semantics —
    # an org with zero entries is "allowlist disabled" (allow-by-default);
    # one or more entries is "deny by default, allow only matching".
    # The check runs after member resolution so the per-request cost is
    # one extra SELECT (bounded by rows-per-org ≤ a few dozen in
    # practice) and so dev-bypass tenants with no entries stay free.
    # We read the raw CIDR list directly rather than loading full ORM
    # rows to keep the hot path O(1) Python-side work.
    cidrs_res = await db.execute(
        select(OrgIpAllowlistEntry.cidr).where(
            OrgIpAllowlistEntry.org_id == member.org_id
        )
    )
    cidrs = [row[0] for row in cidrs_res.all()]
    if cidrs:
        from app.services.audit import get_client_ip
        client_ip = get_client_ip(request)
        if not ip_matches_allowlist(client_ip, cidrs):
            # Structured detail so the frontend can route the user to
            # a dedicated "access denied" screen if desired — matches
            # the pattern established by MFA_REQUIRED in Item 23.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "IP_NOT_ALLOWED",
                    "message": (
                        "Your IP address is not on this organization's "
                        "allowlist. Contact your administrator."
                    ),
                },
            )

    
    # Load org plan for backward-compat dict access (member["plan"])
    _plan = None
    try:
        _org = await db.get(Organization, member.org_id)
        if _org is not None:
            _plan = _org.plan
    except Exception:
        pass

    return MemberCtx(current_user, member, _plan)


async def require_mfa_if_enforced(
    ctx: tuple[dict, OrganizationMember] = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> tuple[dict, OrganizationMember]:
    """Gate owner-only mutations behind TOTP when enforcement applies.

    Non-owners pass straight through — enforcement is an owner-account
    hardening control, not a generic auth barrier. (An ADMIN who tried
    to hit a billing route would already be 403'd by the route's own
    ``role != OWNER`` guard; layering MFA on top would only confuse the
    error surface.)

    For owners we fetch the org's plan and a fresh member count, feed
    both into the pure ``is_mfa_required_for_owner()`` rule, and — when
    required — verify that the owner's local ``AuthUser`` row has
    ``totp_enabled=True``. The 403 carries a machine-readable
    ``code: MFA_REQUIRED`` so the frontend can route the user to
    ``/settings/security`` instead of showing a generic permissions
    error.

    Users authenticated via Supabase-only (no local ``AuthUser`` row)
    are treated as not-enrolled — they must migrate to local auth to
    satisfy the rule. This is the documented posture: once an org
    trips the enforcement threshold, the owner's account gets moved
    to the local auth system as part of the upgrade flow.
    """
    current_user, member = ctx

    # Enforcement scope: owners only. ADMIN/MEMBER mutations are
    # out-of-scope for Item 23 and the route-level role checks already
    # block them from the sensitive actions we gate here.
    if member.role != OrgRole.OWNER:
        return ctx

    org = await db.get(Organization, member.org_id)
    if not org:
        # Should never happen — get_current_member already resolved an
        # org-scoped member. Fall through defensively to avoid turning
        # a data-integrity bug into a cryptic 403.
        return ctx

    member_count = await db.scalar(
        select(func.count())
        .select_from(OrganizationMember)
        .where(OrganizationMember.org_id == member.org_id)
    ) or 0

    if not is_mfa_required_for_owner(org.plan, int(member_count)):
        return ctx

    user_id = current_user.get("user_id")
    # user_id may be a str (JWT claim) or a UUID (tests / overrides).
    # ``db.get`` accepts both; no explicit cast needed.
    auth_user = await db.get(AuthUser, user_id) if user_id else None
    if auth_user and auth_user.totp_enabled:
        return ctx

    # Dedicated machine-readable error so the frontend can redirect the
    # owner to /settings/security without brittle string matching.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "MFA_REQUIRED",
            "message": (
                "Two-factor authentication is required for owners on this "
                "plan. Enable TOTP from Settings → Security to continue."
            ),
        },
    )


# --------------------------------------------------------------------------- #
# Session-version validation (Item 24 / migration v44).
#
# Password resets, TOTP disables, and future "log out everywhere" events
# bump ``AuthUser.session_version``. Every access token minted by
# ``auth_service._mint_access_token`` carries the user's version at mint
# time as a ``ver`` claim. The helper below compares the two and raises
# 401 when the token is stale, giving us immediate invalidation without
# waiting for the JWT TTL.
#
# Compromises accepted:
#   • Tokens minted *before* v44 shipped carry no ``ver`` claim; we treat
#     a missing claim as legacy-pass so we don't log the whole user base
#     out on deploy. Such tokens retire naturally as their TTL elapses
#     (≤ _ACCESS_TOKEN_EXPIRE_MINUTES) and any subsequent login mints a
#     v44-aware token.
#   • The helper performs no DB read itself — it expects the caller
#     (who has already loaded ``AuthUser`` for other reasons) to pass
#     the row in. This keeps the hot path cheap.
# --------------------------------------------------------------------------- #

def verify_session_version(payload: dict, user) -> None:  # noqa: ANN001
    """Raise 401 if the token's ``ver`` claim is lower than the DB column.

    Accepts a decoded JWT payload + the already-loaded ``AuthUser``.
    Returns ``None`` silently on pass. The caller must handle the
    raised :class:`HTTPException` exactly once.
    """
    ver_claim = payload.get("ver")
    if ver_claim is None:
        # Legacy token (minted pre-v44). Let it through — it will retire
        # via its exp claim on the next mint/refresh.
        return
    current = getattr(user, "session_version", None) or 1
    try:
        ver_int = int(ver_claim)
    except (TypeError, ValueError):
        # Malformed claim — treat as stale so an attacker can't bypass
        # the check by sending ``"ver": "∞"`` or similar.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been invalidated. Please sign in again.",
        )
    if ver_int < current:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been invalidated. Please sign in again.",
        )


# ═══════════════════════════════════════════════════════════════════
# API developer-key authentication (Item 45)
# ═══════════════════════════════════════════════════════════════════
#
# ENTERPRISE tenants may call the API with a ``vk_`` key instead of a
# Supabase JWT. The key flow bypasses JWT verification entirely — the
# middleware looks the key up by its public prefix, verifies the SHA-
# 256 hash in constant time, and returns the key's org context. JWT
# routes remain the default; endpoints that opt into machine-to-
# machine access declare ``Depends(resolve_api_key_caller)``.

async def resolve_api_key_caller(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> tuple[dict, OrganizationMember]:
    """Authenticate a request using an ``Authorization: Bearer vk_*``
    header. Returns ``(pseudo_user, member)`` compatible with the
    JWT path so downstream handlers don't need to care which auth
    method was used.

    Scope enforcement is the caller's responsibility — use
    :func:`app.services.developer_key_service.has_scope` against the
    returned member's context.
    """
    from app.services import developer_key_service as _svc

    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )
    plaintext = auth[7:].strip()
    try:
        prefix, _ = _svc.parse_key(plaintext)
    except _svc.ApiKeyValidationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    row = await _svc.lookup_active_key(db, prefix=prefix)
    if row is None or not _svc.verify_key(plaintext, row.key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Resolve the issuing user's org membership (falls back to the
    # earliest admin/owner if the original issuer has since left).
    member = await db.scalar(
        select(OrganizationMember)
        .where(OrganizationMember.org_id == row.org_id)
        .order_by(OrganizationMember.created_at.asc())
        .limit(1)
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key org has no members",
        )
    pseudo_user = {
        "user_id": member.user_id,
        "email": "api-key@varuflow.local",
        "api_key_id": row.id,
        "api_key_scopes": list(row.scopes or []),
    }
    # Record usage best-effort (don't block the request on audit).
    try:
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() \
            or (request.client.host if request.client else None)
        await _svc.record_usage(
            db,
            key_id=row.id,
            method=request.method,
            path=str(request.url.path),
            status_code=None,
            ip=client_ip,
        )
        await db.commit()
    except Exception:
        await db.rollback()
    return pseudo_user, member
