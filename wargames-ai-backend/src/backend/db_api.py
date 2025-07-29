import datetime
from functools import cache
from typing import Optional

from sqlalchemy.orm import Session
from backend.database.models import UserBadges, Users, UserTournamentEnrollments, Challenges, Badges, UserChallengeContexts, Tournaments
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Session, select, and_, or_
from sqlalchemy.orm import selectinload
from uuid import UUID

from backend.models.supplemental import UserInfo


# Bind between sub and local user id should be persistent enough to justify
# caching.
@cache
def ensure_user_exists(session: Session, user_sub: str) -> Users:
    """
    Ensure the user exists in the database. If not, create a new user.
    Returns the user object.
    """
    user = session.exec(select(Users).where(Users.sub_id == user_sub)).first()
    if not user:
        user = Users(sub_id=user_sub)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def get_user_info(session: Session, user_sub: str) -> Optional[UserInfo]:
    """
    Get user active tournaments, badges, and active challenges.
    If the user isn't in the postgres db for joining, add the user, and
    return the user data.
    """
    now = datetime.now(timezone.utc)
    user: Users = ensure_user_exists(session, user_sub)
    active_tournaments = session.exec(
        select(Tournaments).join(UserTournamentEnrollments)
        .where(
            and_(
                UserTournamentEnrollments.user_id == user.id,
                Tournaments.start_date <= now,
                Tournaments.end_date >= now
            )
        )
    ).all()
    active_challenges = session.exec(
        select(Challenges).join(UserChallengeContexts)
        .where(
            and_(
                UserChallengeContexts.user_id == user.id,
                Challenges.tournament_id.in_([t.id for t in active_tournaments])
            )
        )
    ).all()
    badges = session.exec(
        select(Badges).join(UserBadges)
        .where(UserBadges.user_id == user.id)
    ).all()

    return UserInfo(
        user_id=user.id,
        email=None,  # Email is not stored in the Users model
        active_tournaments=active_tournaments,
        active_challenges=active_challenges,
        badges=badges
    )