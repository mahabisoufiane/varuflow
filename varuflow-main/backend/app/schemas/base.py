"""Shared base for client-input Pydantic schemas.

CLAUDE.md / production audit (H3): request schemas must reject unknown
fields. Pydantic's default is ``extra="ignore"`` — a client can submit
fields the schema doesn't declare and they are silently dropped. That's
fine for forward-compatible parsing, but it also means a field a
developer *intended* to be read-only/server-controlled (e.g. ``org_id``,
``is_admin``, ``status``) only stays that way as long as no router
ever introduces a model_dump(**body.dict()) that forwards the whole
payload — there's nothing here, today, that would catch a mass-
assignment / over-posting bug at the schema layer.

Use this for any schema that parses a client-supplied request body
(``*Create``, ``*Update``, ``*In``, ``*Request`` — anything bound to a
FastAPI parameter that reads JSON from the wire). Do NOT use it for
response/output schemas (``*Out``, ``*Summary``, ``*Report``) — those
are constructed server-side via ``model_validate(orm_obj)`` and gain
nothing from rejecting extra fields.

    from app.schemas.base import StrictModel

    class WidgetCreate(StrictModel):
        name: str

A request with an unexpected field now gets a 422 instead of having
the field silently dropped.
"""
from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
