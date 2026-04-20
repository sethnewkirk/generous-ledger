from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SubjectKind = Literal["person", "commitment", "domain", "note"]
ClaimType = Literal["fact", "obligation", "preference", "pattern", "idea"]
ClaimStatus = Literal["active", "provisional", "superseded"]
Sensitivity = Literal["public", "personal", "sensitive"]
RetentionPolicy = Literal["ephemeral", "summary_only", "excerpt_ok"]


@dataclass(frozen=True)
class SubjectRef:
    kind: SubjectKind
    title: str
    path: str
    wikilink: str


@dataclass
class SignalEnvelope:
    signal_id: str
    source_type: str
    source_ref: str
    captured_at: str
    occurred_at: str | None
    time_range: str | None
    subjects: list[SubjectRef]
    sensitivity: Sensitivity
    retention_policy: RetentionPolicy
    raw_path: str
    summary: str
    excerpt: str | None = None
    full_text: str = ""
    subject_hints: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ClaimCandidate:
    claim_type: ClaimType
    claim_slot: str
    statement: str
    subjects: list[SubjectRef]
    supporting_event_wikilinks: list[str]
    status: ClaimStatus = "active"
    confidence: float = 0.7
    valid_from: str | None = None
    valid_to: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class CompileReport:
    signals_seen: int = 0
    promoted_signals: int = 0
    events_created: int = 0
    claims_created: int = 0
    claims_updated: int = 0
    claims_superseded: int = 0
    index_rebuilt: bool = False
    health_report_written: bool = False
    unresolved_signals: int = 0
    unlinked_contacts: int = 0
    ambiguous_aliases: int = 0
    orphan_events: int = 0
    orphan_claims: int = 0
    stale_active_claims: int = 0
    conflicting_active_claim_slots: int = 0


@dataclass
class RetrievalDocument:
    path: str
    doc_type: str
    title: str
    summary: str
    subjects: list[str]
    wikilinks: list[str]
    occurred_at: str | None = None
    claim_type: str | None = None
    status: str | None = None
    source_type: str | None = None
    sensitivity: str | None = None
    score: float = 0.0


@dataclass
class RetrievalResult:
    workflow: str
    subject_titles: list[str]
    documents: list[RetrievalDocument]
    used_search_fallback: bool = False
