"""Request-ID middleware.

Generates or preserves an `X-Request-ID` header on every request so logs,
Sentry events and client-side error reports can all be correlated back to
the same HTTP transaction.

Behaviour:
  • If the client sent a syntactically valid `X-Request-ID`, reuse it.
  • Otherwise generate a fresh UUID-v4.
  • Store on `request.state.request_id` for downstream handlers.
  • Store in a ``ContextVar`` so service-layer code (audit logger,
    observability helper) can read it without threading ``Request``
    through every function. Item 30 added the contextvar so
    ``log_security_event`` emits correlation IDs even from callers
    deep in the stack.
  • Echo on the response as `X-Request-ID`.
  • Tag the Sentry scope (when Sentry is configured).

Register AFTER CORSMiddleware so the header passes through preflight,
and BEFORE the logging middleware so the ID is available when logging.
"""
from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Tolerate any plausible client-supplied id (UUID, ULID, etc.) but reject
# anything that could be used for header injection or log-forging.
_VALID_ID = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")


# Populated by the middleware on every request. Default is None so code
# that runs outside an HTTP context (scheduler jobs, management scripts)
# observes "no request id" rather than a stale one from a previous call.
# ContextVars are safe across concurrent asyncio tasks — each request
# gets its own context and writes never leak sideways.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_current_request_id() -> str | None:
    """Return the current request's ID or None outside an HTTP context.

    Service-layer helpers can call this to stamp correlation IDs on log
    lines without having to accept a ``Request`` parameter everywhere.
    Returns None during scheduler jobs and tests that bypass the
    middleware, which downstream loggers handle by omitting the field.
    """
    return request_id_ctx.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex

        request.state.request_id = request_id
        # ContextVar.set returns a token that could be used to reset the
        # var to its previous value; we deliberately don't reset it at
        # the end of the request because each asyncio task gets its own
        # context — the value is garbage-collected with the task.
        request_id_ctx.set(request_id)

        # Tag Sentry scope if the SDK is initialized — no-ops otherwise.
        try:
            import sentry_sdk

            sentry_sdk.set_tag("request_id", request_id)
        except Exception:
            pass

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
