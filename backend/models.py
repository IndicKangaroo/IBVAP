"""SQLAlchemy models — Phase 4.

Mirrors the guide's section 6 schema, trimmed to what the MVP actually
needs to make an intrusion alert real: cameras, events, incidents.
`detections`/`tracks`/`anpr_results` aren't modelled yet — the guide
itself calls the detections table "optional detailed model output",
and ANPR is Phase 5.
"""
from __future__ import annotations

import uuid
from datetime import datetime,timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String, primary_key=True)  # e.g. "CAM-01" — matches the AI node's camera_id
    name = Column(String, nullable=True)
    location_label = Column(String, nullable=True)
    status = Column(String, default="ONLINE")
    stream_url = Column(String, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Event(Base):
    __tablename__ = "events"

    # Uses the AI node's own event_id as the primary key (not a fresh
    # one here) so an event has exactly one identity end to end —
    # from EventEngine's evidence filename through to this DB row.
    id = Column(String, primary_key=True, default=_uuid)
    camera_id = Column(String, ForeignKey("cameras.id"), nullable=False)
    zone_id = Column(String, nullable=True)
    zone_name = Column(String, nullable=True)
    track_id = Column(Integer, nullable=True)
    type = Column(String, default="INTRUSION")
    cls = Column(String, nullable=True)          # "person" | "vehicle"
    confidence = Column(Float, nullable=True)
    timestamp = Column(Float, nullable=False)    # unix epoch seconds, set by the AI node
    evidence_path = Column(String, nullable=True)
    created_at = Column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc)
)
    incident = relationship("Incident", back_populates="event", uselist=False)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=_uuid)
    event_id = Column(String, ForeignKey("events.id"), nullable=False, unique=True)
    severity = Column(String, default="MEDIUM")
    status = Column(String, default="ACTIVE")   # ACTIVE -> ACKNOWLEDGED -> RESOLVED
    created_at = Column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc)
)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    event = relationship("Event", back_populates="incident")


class ANPRResult(Base):
    __tablename__ = "anpr_results"

    id = Column(String, primary_key=True, default=_uuid)
    camera_id = Column(String, ForeignKey("cameras.id"), nullable=False)
    track_id = Column(Integer, nullable=True)
    plate_text = Column(String, nullable=True)   # NULL means "nothing readable" — not an error
    confidence = Column(Float, default=0.0)
    plausible = Column(Boolean, default=False)
    timestamp = Column(Float, nullable=False)
    evidence_path = Column(String, nullable=True)
    created_at = Column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc)
)
