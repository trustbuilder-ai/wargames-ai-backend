

from typing import Optional
from pydantic import BaseModel

from backend.database.models import Badges, Challenges, Tournaments


class UserInfo(BaseModel):
    """
    Represents a user's information including active tournaments, challenges, and badges.
    """
    user_id: int
    email: Optional[str] = None
    active_tournaments: list[Tournaments]
    active_challenges: list[Challenges]
    badges: list[Badges]

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True  # Allow using SQLModel types directly