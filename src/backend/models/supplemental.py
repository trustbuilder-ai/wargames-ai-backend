from json import tool
from typing import Optional
from pydantic import BaseModel
from strenum import StrEnum

from backend.database.models import (
    Badges,
    Challenges,
    Tournaments,
    UserChallengeContexts,
)
from backend.models.evaluation import EvalResult
from backend.models.llm import ToolCall


class UserInfo(BaseModel):
    """
    Represents a user's information including active tournaments, challenges,
    and badges.
    """

    user_id: int
    email: str | None = None
    active_tournaments: list[Tournaments]
    active_challenge_contexts: list[UserChallengeContexts]
    badges: list[Badges]
    eval_results: list[EvalResult] = []

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True  # Allow using SQLModel types directly


class Message(BaseModel):
    role: str
    content: str
    is_tool_call: bool = False
    tool_name: str | None = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: str | None = None


class ChallengeContextResponse(BaseModel):
    """
    Represents the full message context for a challenge, including user challenge context
    and messages.
    """
    user_challenge_context: UserChallengeContexts
    messages: list[Message] = []
    eval_result: Optional[EvalResult] = None
    remaining_message_count: int = 0


class SelectionFilter(StrEnum):
    PAST_ONLY = "PAST"
    ACTIVE_ONLY = "ACTIVE"
    FUTURE_ONLY = "FUTURE"
    PAST_AND_ACTIVE = "PAST_AND_ACTIVE"
    ACTIVE_AND_FUTURE = "ACTIVE_AND_FUTURE"


class ChallengeContextLLMResponse(BaseModel):
    """
    Represents a response from the LLM call.
    """
    remaining_message_count: int
    messages: list[Message]


class ChallengesPublic(BaseModel):
    challenge: Challenges
    tournament_name: str