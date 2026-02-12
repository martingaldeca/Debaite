from enum import Enum


class AttitudeType(str, Enum):
    CALM = "calm"
    STRICT = "strict"
    FAIR = "fair"
    AGGRESSIVE = "aggressive"
    PASSIVE = "passive"
    SARCASTIC = "sarcastic"
