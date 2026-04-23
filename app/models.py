from sqlalchemy import Column, String, Integer, DateTime, Text, Float, JSON, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
import uuid


class Base(DeclarativeBase):
    pass


# ── SQLAlchemy ORM Models ──────────────────────────────────────────────────────

class ScanRun(Base):
    __tablename__ = "scan_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    regions = Column(JSON)
    total_found = Column(Integer, default=0)
    active_count = Column(Integer, default=0)
    status = Column(String, default="running")  # running, completed, failed
    triggered_by = Column(String, nullable=True)


class Lead(Base):
    __tablename__ = "leads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_run_id = Column(String, ForeignKey("scan_runs.id"))
    title = Column(String)
    institution = Column(String)
    country = Column(String)
    type = Column(String)           # tender, rfq, news, regulation, consulting, partnership
    summary = Column(Text)
    relevance_score = Column(Integer)
    relevance_reason = Column(Text)
    deadline = Column(String, nullable=True)
    published_date = Column(String, nullable=True)
    freshness = Column(String)      # active, stale, outdated, expired, unknown
    freshness_reason = Column(Text, nullable=True)
    contact_info = Column(Text, nullable=True)
    follow_up_action = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)
    urgency = Column(String)        # high, medium, low
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    lead_status = Column(String, default="new")  # new, contacted, qualified, closed
    assigned_to = Column(String, nullable=True)
    notes = Column(Text, nullable=True)


class TargetInstitution(Base):
    __tablename__ = "target_institutions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String, ForeignKey("leads.id"))
    scan_run_id = Column(String, ForeignKey("scan_runs.id"), nullable=True)
    country = Column(String)
    market_tier = Column(String)          # core, expansion, greenfield
    institution_name = Column(String)
    type = Column(String)                 # commercial_bank, microfinance_institution, etc.
    ownership_summary = Column(Text, nullable=True)
    shareholders = Column(JSON, nullable=True)                # list of equity investors/owners
    international_stakeholders = Column(JSON, nullable=True)  # list of lenders, guarantors, other stakeholders
    dfi_backed = Column(Boolean, nullable=True)
    estimated_asset_size = Column(String, nullable=True)
    business_model_summary = Column(Text, nullable=True)
    lending_focus = Column(JSON, nullable=True)               # list of strings
    auditor = Column(String, nullable=True)
    big4_audited = Column(Boolean, nullable=True)
    ifrs9_status = Column(String, nullable=True)              # adopted, in_progress, not_yet, unknown
    source_url = Column(String, nullable=True)
    relevance_notes = Column(Text, nullable=True)
    lead_title = Column(String, nullable=True)
    lead_type = Column(String, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="New")   # New, Contacted, Qualified, Closed
    notes = Column(Text, nullable=True)


# ── Pydantic Response Schemas ──────────────────────────────────────────────────

class ScanRunResponse(BaseModel):
    id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    regions: Optional[list] = None
    total_found: int = 0
    active_count: int = 0
    status: str
    triggered_by: Optional[str] = None

    model_config = {"from_attributes": True}


class LeadResponse(BaseModel):
    id: str
    scan_run_id: Optional[str] = None
    title: Optional[str] = None
    institution: Optional[str] = None
    country: Optional[str] = None
    type: Optional[str] = None
    summary: Optional[str] = None
    relevance_score: Optional[int] = None
    relevance_reason: Optional[str] = None
    deadline: Optional[str] = None
    published_date: Optional[str] = None
    freshness: Optional[str] = None
    freshness_reason: Optional[str] = None
    contact_info: Optional[str] = None
    follow_up_action: Optional[str] = None
    source_url: Optional[str] = None
    urgency: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    lead_status: str = "new"
    assigned_to: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class ScanRunDetailResponse(ScanRunResponse):
    leads: List[LeadResponse] = []


class TargetInstitutionResponse(BaseModel):
    id: str
    lead_id: Optional[str] = None
    scan_run_id: Optional[str] = None
    country: Optional[str] = None
    market_tier: Optional[str] = None
    institution_name: Optional[str] = None
    type: Optional[str] = None
    ownership_summary: Optional[str] = None
    shareholders: Optional[list] = None
    international_stakeholders: Optional[list] = None
    dfi_backed: Optional[bool] = None
    estimated_asset_size: Optional[str] = None
    business_model_summary: Optional[str] = None
    lending_focus: Optional[list] = None
    auditor: Optional[str] = None
    big4_audited: Optional[bool] = None
    ifrs9_status: Optional[str] = None
    source_url: Optional[str] = None
    relevance_notes: Optional[str] = None
    lead_title: Optional[str] = None
    lead_type: Optional[str] = None
    discovered_at: Optional[datetime] = None
    status: str = "New"
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class UpdateTargetRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class StartScanRequest(BaseModel):
    regions: List[str]

    @classmethod
    def validate_regions(cls, regions: List[str]) -> List[str]:
        from app.scanner.regions import REGIONS
        invalid = [r for r in regions if r not in REGIONS]
        if invalid:
            raise ValueError(f"Unknown regions: {invalid}. Valid regions: {list(REGIONS.keys())}")
        return regions

    def model_post_init(self, __context):
        self.validate_regions(self.regions)


class UpdateLeadRequest(BaseModel):
    lead_status: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
