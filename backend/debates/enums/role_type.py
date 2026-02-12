from enum import Enum


class RoleType(str, Enum):
    EXPERT = "expert"
    SCHOLAR = "scholar"
    GENERAL_KNOWLEDGE = "general_knowledge"
    ILLITERATE = "illiterate"
