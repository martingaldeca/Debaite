from enum import Enum


class ModeratorAction(str, Enum):
    NONE = "NONE"
    INTERVENE = "INTERVENE"
    SKIP = "SKIP"
    VETO = "VETO"
    STOP = "STOP"
    SANCTION = "SANCTION"
    LIMIT = "LIMIT"
