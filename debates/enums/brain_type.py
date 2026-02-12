from enum import Enum


class BrainType(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
