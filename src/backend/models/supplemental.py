from pydantic import BaseModel
from strenum import StrEnum

from backend.database.models import (
    Badges,
    Challenges,
    Tournaments,
    UserChallengeContexts,
)


class UserInfo(BaseModel):
    """
    Represents a user's information including active tournaments, challenges,
    and badges.
    """

    user_id: int
    email: str | None = None
    active_tournaments: list[Tournaments]
    active_challenges: list[Challenges]
    badges: list[Badges]

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True  # Allow using SQLModel types directly


class Message(BaseModel):
    role: str
    content: str
    is_tool_call: bool = False
    tool_name: str | None = None


class ChallengeContextResponse(BaseModel):
    user_challenge_context: UserChallengeContexts
    messages: list[Message] = []


class SelectionFilter(StrEnum):
    PAST_ONLY = "PAST"
    ACTIVE_ONLY = "ACTIVE"
    FUTURE_ONLY = "FUTURE"
    PAST_AND_ACTIVE = "PAST_AND_ACTIVE"
    ACTIVE_AND_FUTURE = "ACTIVE_AND_FUTURE"
