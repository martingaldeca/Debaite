from pydantic import BaseModel


class PositionChangeCheck(BaseModel):
    has_changed: bool
    new_position: str
    reasoning: str
