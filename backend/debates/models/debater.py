from typing import Optional

from debates.models.participant import Participant


class Debater(Participant):
    order_in_debate: int | None
    is_vetoed: bool = False
    veto_reason: Optional[str] = None

    strikes: int = 0
    skip_next_turn: bool = False

    next_turn_char_limit: Optional[int] = None
