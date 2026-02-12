from enum import Enum


class GenderType(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
