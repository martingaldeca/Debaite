from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from debates.models.participant import Participant


class Intervention(BaseModel):
    participant: Optional["Participant"] = None
    answer: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    participant_snapshot_position: str = "Unknown"
