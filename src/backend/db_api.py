from datetime import UTC, datetime
from functools import cache
import json
from typing import Iterable, Literal, Optional

from sqlmodel import Session, and_, select

from backend.database.models import (
    Badges,
    ChallengeEvaluations,
    Challenges,
    Tournaments,
    UserBadges,
    UserChallengeContextMessages,
    UserChallengeContexts,
    Users,
    UserTournamentEnrollments,
)
from backend.models.evaluation import EvalStatus
from backend.util.log import logger

from backend.exceptions import NotFoundError
from backend.llm.shim import map_chat_entries_to_messages
from backend.models.llm import ChatEntry, ChatMessageWithTools, ChatRequest, ChatResponse, ChatResponseWithTools
from backend.models.supplemental import ChallengeContextResponse, Message, SelectionFilter, UserInfo


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


def get_user_info(session: Session, user_sub: str) -> UserInfo | None:
    """
    Get user active tournaments, badges, and active challenges.
    If the user isn't in the postgres db for joining, add the user, and
    return the user data.
    """
    now = datetime.now(UTC)
    user: Users = ensure_user_exists(session, user_sub)
    active_tournaments = session.exec(
        select(Tournaments)
        .join(UserTournamentEnrollments)
        .where(
            and_(
                UserTournamentEnrollments.user_id == user.id,
                Tournaments.start_date <= now,
                Tournaments.end_date >= now,
            )
        )
    ).all()

    active_challenges = session.exec(
        select(Challenges)
        .join(UserChallengeContexts)
        .where(
            and_(
                UserChallengeContexts.user_id == user.id,
                Challenges.tournament_id.in_(
                    [tournament.id for tournament in active_tournaments]
                ),
            )
        )
    ).all()
    badges = session.exec(
        select(Badges).join(UserBadges).where(UserBadges.user_id == user.id)
    ).all()

    return UserInfo(
        user_id=user.id,
        email=None,  # Email is not stored in the Users model
        active_tournaments=active_tournaments,
        active_challenges=active_challenges,
        badges=badges,
    )

def add_message_to_challenge(
    session: Session, user_id: int, challenge_id: int, model: str, message: str, role: Literal["user", "assistant", "system"] = "user"
) -> int:
    # Add message if it can be added to the context. It will be followed up by a processed
    # at message.
    user_challenge_context = session.exec(
        select(UserChallengeContexts).where(
            and_(
                UserChallengeContexts.user_id == user_id,
                UserChallengeContexts.challenge_id == challenge_id,
            )
        )
    ).first()
    if not user_challenge_context:
        raise NotFoundError("User challenge context not found")
    user_challenge_context_id = user_challenge_context.id
    if not user_challenge_context.can_contribute:
        raise ValueError("User cannot contribute to this challenge context")

    if not user_challenge_context_id:
        raise NotFoundError("User challenge context not found")

    chat_message: ChatMessageWithTools = ChatMessageWithTools(
                role=role,
                content=message
    )

    context_message: UserChallengeContextMessages = UserChallengeContextMessages(
        user_challenge_context_id=user_challenge_context_id,
        content= chat_message.model_dump_json(),
        created_at=datetime.now(UTC),
        content_type= chat_message.__class__.__name__,
        model=model,
        role=role,
        is_user_provided=True,
    )
    session.add(context_message)
    session.commit()
    return user_challenge_context_id


def add_chat_entries_to_challenge_no_checks(
    session: Session,
    user_challenge_context_id: int,
    chat_entries: list[ChatEntry],
):
    """
    Bulk add messages to a challenge context without checks.
    This assumes that the caller has already called add_message_to_challenge
    or similar to ensure the context exists and is valid.
    """
    for chat_entry in chat_entries:
        if not isinstance(chat_entry, (ChatResponseWithTools, ChatMessageWithTools, ChatResponse)): # type: ignore[reportUnnecessaryIsInstance]
            raise ValueError("Messages must be ChatResponseWithTools or ChatMessageWithTools")
        if isinstance(chat_entry, (ChatResponse, ChatResponseWithTools)):
            role: str = "assistant"
        elif isinstance(chat_entry, ChatMessageWithTools): # type: ignore[reportUnnecessaryIsInstance]
            role = chat_entry.role
        else:
            raise ValueError(f"Invalid chat entry type: {type(chat_entry)}")
        context_message: UserChallengeContextMessages = UserChallengeContextMessages(
            user_challenge_context_id=user_challenge_context_id,
            content=chat_entry.model_dump_json(),
            created_at=datetime.now(UTC),
            content_type=chat_entry.__class__.__name__,
            role=role,
            is_user_provided=True,
        )
        session.add(context_message)
    session.commit()


def get_challenge_context_response(
    session: Session, user_id: int, challenge_id: int
) -> ChallengeContextResponse:
    """
    Get the challenge context response for a user and challenge.
    Returns the ChallengeContextResponse object.
    """
    context = session.exec(
        select(UserChallengeContexts).where(
            and_(
                UserChallengeContexts.user_id == user_id,
                UserChallengeContexts.challenge_id == challenge_id,
            )
        )
    ).first()
    
    if not context:
        raise NotFoundError("User challenge context not found")

    messages = session.exec(
        select(UserChallengeContextMessages).where(
            UserChallengeContextMessages.user_challenge_context_id == context.id
        )
    ).all()
    return ChallengeContextResponse(
        user_challenge_context=context,
        # XXX: This should not be so inefficient.
        messages=list(map_chat_entries_to_messages(list(_instantiate_challenge_context_messages(messages)))),
    )


def start_challenge(
    session: Session, user_id: int, challenge_id: int
) -> UserChallengeContexts:
    """
    Start a challenge for the user. If the user is not enrolled in the tournament,
    they will be enrolled automatically.
    Returns the UserChallengeContexts object.
    """
    # Check if challenge exists

    # Check if user already has a context for this challenge
    # Check if challenge exists
    # Check if user already has a context for this challenge
    existing_context = session.exec(
        select(UserChallengeContexts).where(
            and_(
                UserChallengeContexts.user_id == user_id,
                UserChallengeContexts.challenge_id == challenge_id,
            )
        )
    ).first()

    if existing_context:
        raise ValueError(
            f"User {user_id} already has a context for challenge {challenge_id}."
        )

    # Create new challenge context
    context = UserChallengeContexts(
        user_id=user_id,
        challenge_id=challenge_id,
        started_at=datetime.now(UTC),
        can_contribute=True,
    )

    evaluation: ChallengeEvaluations = ChallengeEvaluations(
        user_challenge_context_id=context.id,
        created_at=datetime.now(UTC),
    )

    session.add(context)
    session.add(evaluation)
    session.commit()
    session.refresh(context)

    return context


def join_tournament(
    session: Session, user_id: int, tournament_id: int
) -> UserTournamentEnrollments:
    """
    Enroll a user in a tournament. If the user is already enrolled, do nothing.
    Returns the UserTournamentEnrollments object.
    """

    tournament = session.get(Tournaments, tournament_id)
    if not tournament:
        raise NotFoundError("Tournament not found")
    if tournament.start_date > datetime.now(UTC):
        raise ValueError("Tournament has not started yet")
    if tournament.end_date < datetime.now(UTC):
        raise ValueError("Tournament has already ended")

    existing_enrollment = session.exec(
        select(UserTournamentEnrollments).where(
            and_(
                UserTournamentEnrollments.user_id == user_id,
                UserTournamentEnrollments.tournament_id == tournament_id,
            )
        )
    ).first()

    if existing_enrollment:
        return existing_enrollment

    # Create new enrollment
    enrollment = UserTournamentEnrollments(
        user_id=user_id,
        tournament_id=tournament_id,
        enrolled_at=datetime.now(UTC),
    )

    session.add(enrollment)
    session.commit()
    session.refresh(enrollment)

    return enrollment


def list_tournaments(
    session: Session,
    selection_filter: SelectionFilter = SelectionFilter.ACTIVE_ONLY,
    page_index: int = 0,
    count: int = 10
) -> Iterable[Tournaments]:
    """
    List tournaments based on selection filter, pagination, and count.
    """
    now = datetime.now(UTC)

    # Start with base select statement
    statement = select(Tournaments)

    # Apply filters based on selection_filter
    if selection_filter == SelectionFilter.PAST_ONLY:
        statement = statement.where(Tournaments.end_date < now)
    elif selection_filter == SelectionFilter.ACTIVE_ONLY:
        statement = statement.where(
            Tournaments.start_date <= now, Tournaments.end_date >= now
        )
    elif selection_filter == SelectionFilter.FUTURE_ONLY:
        statement = statement.where(Tournaments.start_date > now)
    elif selection_filter == SelectionFilter.PAST_AND_ACTIVE:
        statement = statement.where(
            or_(
                Tournaments.end_date < now,
                and_(Tournaments.start_date <= now, Tournaments.end_date >= now),
            )
        )
    elif selection_filter == SelectionFilter.ACTIVE_AND_FUTURE:
        statement = statement.where(
            or_(
                and_(Tournaments.start_date <= now, Tournaments.end_date >= now),
                Tournaments.start_date > now,
            )
        )

    # Apply pagination
    statement = statement.offset(page_index * count).limit(count)

    # Execute query
    tournaments = session.exec(statement).all()

    # Return directly - FastAPI will handle conversion
    return tournaments


def list_challenges(
    session: Session,
    tournament_id: int | None = None,
    page_index: int = 0,
    count: int = 10
) -> Iterable[Challenges]:
    """
    List challenges based on tournament ID, pagination, and count.
    """
    statement = select(Challenges)
    if tournament_id:
        statement = statement.where(Challenges.tournament_id == tournament_id)
    statement = statement.offset(page_index * count).limit(count)
    challenges = session.exec(statement).all()
    return challenges



def _instantiate_challenge_context_messages(
        challenge_context_messages: Iterable[UserChallengeContextMessages]
) -> Iterable[ChatEntry]:
    challenge_context_messages = sorted(challenge_context_messages, key=lambda m: m.created_at)
    for message in challenge_context_messages:
        if message.content_type == "ChatRequest":
            yield ChatRequest.model_validate_json(message.content) # type: ignore
        elif message.content_type == "ChatResponseWithTools":
            yield ChatResponseWithTools.model_validate_json(message.content)
        elif message.content_type == "ChatMessageWithTools":
            yield ChatMessageWithTools.model_validate_json(message.content)
        elif message.content_type == "ChatResponse":
            yield ChatResponse.model_validate_json(message.content)
        else:
            raise ValueError(f"Unknown content type: {message.content_type}")



def load_challenge_context_messages(
    session: Session, user_challenge_context_id: int
) -> Iterable[Message]:
    """
    Load all messages for a given user challenge context.
    Returns a list of UserChallengeContextMessages.
    """
    messages: Iterable[UserChallengeContextMessages] = session.exec(
        select(UserChallengeContextMessages).where(
            UserChallengeContextMessages.user_challenge_context_id == user_challenge_context_id
        )
    ).all()
    logger.info(
        f"Loading {len(messages)} messages for user challenge context {user_challenge_context_id}"
    )
    return map_chat_entries_to_messages(list(_instantiate_challenge_context_messages(messages)))


def get_challenge_tools(
    session: Session, challenge_id: int
) -> Optional[list[str]]:
    """
    Get the list of tools available for a given challenge.
    Returns a list of tool names.
    """
    challenge = session.get(Challenges, challenge_id)
    if not challenge:
        raise NotFoundError("Challenge not found")
    
    # Assuming tools are stored in a related model or as a JSON field
    return json.loads(challenge.required_tools) if challenge.required_tools else None