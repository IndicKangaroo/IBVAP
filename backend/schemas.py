# """Pydantic request/response schemas — Phase 4."""
# from __future__ import annotations

# from datetime import datetime
# from typing import List, Optional

# from pydantic import BaseModel, ConfigDict


# class EventIn(BaseModel):
#     """What the AI node POSTs when a zone crossing fires. Field names
#     intentionally match vision.event_engine.engine.IntrusionEvent so
#     the pipeline can send it almost as-is — see scripts/run_phase4_demo.py."""
#     event_id: str
#     type: str = "INTRUSION"
#     camera_id: str
#     zone_id: Optional[str] = None
#     zone_name: Optional[str] = None
#     track_id: Optional[int] = None
#     cls: Optional[str] = None
#     confidence: Optional[float] = None
#     timestamp: float
#     evidence_path: Optional[str] = None


# class EventOut(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     id: str
#     camera_id: str
#     zone_id: Optional[str] = None
#     zone_name: Optional[str] = None
#     track_id: Optional[int] = None
#     type: str
#     cls: Optional[str] = None
#     confidence: Optional[float] = None
#     timestamp: float
#     evidence_path: Optional[str] = None
#     created_at: datetime


# class IncidentOut(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     id: str
#     event_id: str
#     severity: str
#     status: str
#     created_at: datetime
#     resolved_at: Optional[datetime] = None
#     event: EventOut


# class IncidentStatusUpdate(BaseModel):
#     status: str  # "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED"


# class CameraOut(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     id: str
#     name: Optional[str] = None
#     location_label: Optional[str] = None
#     status: str
#     last_seen_at: Optional[datetime] = None


# class ANPRResultIn(BaseModel):
#     """What the AI node POSTs when a vehicle crosses an ANPR trigger
#     zone. Field names match anpr.engine.ANPRResult. plate_text=None is
#     a valid, expected result — "nothing legible", not an error."""
#     result_id: str
#     camera_id: str
#     track_id: Optional[int] = None
#     plate_text: Optional[str] = None
#     confidence: float = 0.0
#     plausible: bool = False
#     timestamp: float
#     evidence_path: Optional[str] = None


# class ANPRResultOut(BaseModel):
#     model_config = ConfigDict(from_attributes=True)
#     id: str
#     camera_id: str
#     track_id: Optional[int] = None
#     plate_text: Optional[str] = None
#     confidence: float
#     plausible: bool
#     timestamp: float
#     evidence_path: Optional[str] = None
#     created_at: datetime


# class ZoneCreateRequest(BaseModel):
#     """Submitted by the web-based zone editor (replaces scripts/draw_zone.py's
#     OpenCV window for anyone who can't/won't run that locally)."""
#     camera_id: str
#     kind: str  # "intrusion" | "anpr"
#     zone_id: str = "restricted-1"
#     name: str = "Restricted Zone"
#     polygon: List[List[float]]  # [[x,y], [x,y], ...], at least 3 points


# class PipelineStartRequest(BaseModel):
#     camera_id: str
#     source: str  # file path under data/sample_videos/, or a webcam index as a string ("0")
#     zones_path: Optional[str] = None
#     anpr_zones_path: Optional[str] = None
#     device: str = "auto"
#     ocr_gpu: str = "auto"


# class PipelineOut(BaseModel):
#     camera_id: str
#     source: str
#     running: bool
#     pid: int
#     started_at: float

"""Pydantic request/response schemas — Phase 4."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class UTCTimestampMixin(BaseModel):
    """SQLite drops tzinfo on read even for DateTime(timezone=True)
    columns, so values coming out of the DB are naive-but-actually-UTC.
    Without this, .isoformat() serializes them with no offset/Z, and
    the frontend's `new Date(...)` then parses them as local time
    (IST) instead of UTC — a ~5.5h error. Re-attach UTC before
    serializing so the wire format is always unambiguous."""

    @field_serializer("*", when_used="json")
    def _ensure_utc(self, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc).isoformat()
        return v


class EventIn(BaseModel):
    """What the AI node POSTs when a zone crossing fires. Field names
    intentionally match vision.event_engine.engine.IntrusionEvent so
    the pipeline can send it almost as-is — see scripts/run_phase4_demo.py."""
    event_id: str
    type: str = "INTRUSION"
    camera_id: str
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    track_id: Optional[int] = None
    cls: Optional[str] = None
    confidence: Optional[float] = None
    timestamp: float
    evidence_path: Optional[str] = None


class EventOut(UTCTimestampMixin):
    model_config = ConfigDict(from_attributes=True)
    id: str
    camera_id: str
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    track_id: Optional[int] = None
    type: str
    cls: Optional[str] = None
    confidence: Optional[float] = None
    timestamp: float
    evidence_path: Optional[str] = None
    created_at: datetime


class IncidentOut(UTCTimestampMixin):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_id: str
    severity: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    event: EventOut


class IncidentStatusUpdate(BaseModel):
    status: str  # "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED"


class CameraOut(UTCTimestampMixin):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: Optional[str] = None
    location_label: Optional[str] = None
    status: str
    last_seen_at: Optional[datetime] = None


class ANPRResultIn(BaseModel):
    """What the AI node POSTs when a vehicle crosses an ANPR trigger
    zone. Field names match anpr.engine.ANPRResult. plate_text=None is
    a valid, expected result — "nothing legible", not an error. Same
    for vehicle_color=None — a low-confidence/ambiguous color read."""
    result_id: str
    camera_id: str
    track_id: Optional[int] = None
    vehicle_type: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_color_confidence: float = 0.0
    plate_text: Optional[str] = None
    confidence: float = 0.0
    plausible: bool = False
    timestamp: float
    evidence_path: Optional[str] = None


class ANPRResultOut(UTCTimestampMixin):
    model_config = ConfigDict(from_attributes=True)
    id: str
    camera_id: str
    track_id: Optional[int] = None
    vehicle_type: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_color_confidence: float = 0.0
    plate_text: Optional[str] = None
    confidence: float
    plausible: bool
    timestamp: float
    evidence_path: Optional[str] = None
    created_at: datetime


class ZoneCreateRequest(BaseModel):
    """Submitted by the web-based zone editor (replaces scripts/draw_zone.py's
    OpenCV window for anyone who can't/won't run that locally)."""
    camera_id: str
    kind: str  # "intrusion" | "anpr"
    zone_id: str = "restricted-1"
    name: str = "Restricted Zone"
    polygon: List[List[float]]  # [[x,y], [x,y], ...], at least 3 points


class PipelineStartRequest(BaseModel):
    camera_id: str
    source: str  # file path under data/sample_videos/, or a webcam index as a string ("0")
    zones_path: Optional[str] = None
    anpr_zones_path: Optional[str] = None
    device: str = "auto"
    ocr_gpu: str = "auto"


class PipelineOut(BaseModel):
    camera_id: str
    source: str
    running: bool
    pid: int
    started_at: float