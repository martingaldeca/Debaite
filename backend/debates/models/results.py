from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UsageStats(BaseModel):
    input_tokens: int
    output_tokens: int
    cost: float


class TranscriptEntry(BaseModel):
    participant_name: str
    participant_position: str
    confidence: float
    text: str
    usage: UsageStats


class PositionChangeEntry(BaseModel):
    name: str
    from_position: str = Field(alias="from")
    to_position: str = Field(alias="to")
    round_when_changed: int
    debate_id: Optional[str] = None


class InterventionReference(BaseModel):
    id: int
    participant: str
    text: str


class ParticipantScore(BaseModel):
    voter: str
    winner: Optional[str] = None
    best_intervention: Optional[InterventionReference] = None
    worst_intervention: Optional[InterventionReference] = None
    scores: Dict[str, float]


class GlobalOutcome(BaseModel):
    winner_name: str
    winner_position: str
    vote_distribution: Dict[str, int]
    average_scores: Dict[str, float]
    best_intervention: Optional[InterventionReference] = None
    worst_intervention: Optional[InterventionReference] = None


class ModeratorStats(BaseModel):
    interventions: int
    sanctions: int
    skips: int
    vetos: int
    stops: int
    limits: int


class DebateMetadata(BaseModel):
    id: str
    session_id: str
    topic: str
    description: str
    date: str
    total_rounds_configured: int
    total_turns_configured: int
    allowed_positions: List[str]
    total_estimated_cost_usd: float


class ParticipantEntry(BaseModel):
    name: str
    role: str
    attitude_type: str
    brain: str
    initial_brain: str
    original_position: str
    final_position: Optional[str]
    gender: str
    ethnic_group: str
    tolerant: bool
    insults_allowed: bool
    lies_allowed: bool
    is_vetoed: bool
    veto_reason: Optional[str]
    strikes: int
    skip_next_turn: bool
    total_cost: float
    order_in_debate: int
    confidence_history: List[float]
    final_confidence: float


class EvaluationSection(BaseModel):
    participants: List[ParticipantScore]
    moderator: Optional[Dict[str, Any]] = None
    global_outcome: Optional[GlobalOutcome] = None


class DebateResult(BaseModel):
    metadata: DebateMetadata
    participants: List[ParticipantEntry]
    moderator: Optional[Dict[str, Any]] = None
    moderator_stats: ModeratorStats
    position_changes: List[PositionChangeEntry]
    transcript: List[TranscriptEntry]
    evaluation: EvaluationSection


class SessionSummary(BaseModel):
    total_debates: int
    total_cost_usd: float
    total_rounds: int
    total_participants: int
    global_avg_score: float
    date_generated: str


class WinnerDetail(BaseModel):
    debate_id: str
    winner_name: str
    winner_position: str


class PositionStat(BaseModel):
    count: int
    mean_initial_confidence: float
    mean_final_confidence: float
    percentage: float


class ScoreStat(BaseModel):
    mean: float
    max: float
    min: float
    count: int


class HighlightTurn(BaseModel):
    debate_id: str
    type: str
    text: str
    participant_name: str
    participant_position: str
    participant_confidence: float


class FinalSummaryResult(BaseModel):
    session_summary: SessionSummary
    moderator_summary: Dict[str, int]
    winners_by_position: Dict[str, int]
    winners_details: List[WinnerDetail]
    position_changes: List[PositionChangeEntry]
    final_position_distribution: Dict[str, PositionStat]
    mean_scores: Dict[str, ScoreStat]
    highlight_turns: List[HighlightTurn]
