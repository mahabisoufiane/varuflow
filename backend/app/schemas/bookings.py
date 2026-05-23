"""Pydantic schemas for the booking router."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ── Services ────────────────────────────────────────────────────────


class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    duration_minutes: int = Field(..., gt=0, le=1440)
    price: Decimal = Field(default=Decimal("0"))
    category: str | None = Field(default=None, max_length=64)
    staff_id: uuid.UUID | None = None
    description: str | None = None


class ServiceOut(BaseModel):
    id: uuid.UUID
    name: str
    duration_minutes: int
    price: Decimal
    category: str | None
    staff_id: uuid.UUID | None
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ── Staff ───────────────────────────────────────────────────────────


class StaffCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=64)
    working_hours: dict | None = None
    break_times: list | None = None
    specialties: list | None = None
    gender: str | None = Field(default=None, max_length=16)


class StaffOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str | None
    working_hours: dict | None
    break_times: list | None
    specialties: list | None
    gender: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ── Appointments ────────────────────────────────────────────────────


class AppointmentCreate(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    start_time: datetime
    customer_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = None
    channel: str = Field(default="web", max_length=16)
    notes: str | None = None


class AppointmentOut(BaseModel):
    id: uuid.UUID
    service_id: uuid.UUID
    staff_id: uuid.UUID
    customer_id: uuid.UUID | None
    warehouse_id: uuid.UUID | None
    start_time: datetime
    end_time: datetime
    status: str
    channel: str
    notes: str | None
    loyalty_points_awarded: int

    model_config = {"from_attributes": True}


class AppointmentReschedule(BaseModel):
    start_time: datetime


class AppointmentStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(booked|confirmed|completed|cancelled|no_show)$")


# ── Slot availability ───────────────────────────────────────────────


class SlotQuery(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    day: datetime  # 00:00 of the requested day in the org's timezone


class SlotListOut(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    day: datetime
    slots: list[datetime]


# ── Waitlist ────────────────────────────────────────────────────────


class WaitlistJoin(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    start_time: datetime
    customer_id: uuid.UUID | None = None


# ── Walk-in queue ───────────────────────────────────────────────────


class WalkInEntry(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    notes: str | None = None
