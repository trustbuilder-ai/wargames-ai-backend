import json
from collections.abc import Iterable
from datetime import UTC, datetime
from functools import cache
from typing import Literal

from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, select

from backend.config import MAX_USER_MESSAGE_COUNT_FOR_CHAT_TEMPLATE
from backend.database.models import (
    Badges,
    ChallengeEvaluations,
    ChatTemplate,
    ChatTemplateContainer,
    UserBadges,
    UserChatTemplateContextMessages,
    UserChatTemplateContext,
    Users,
)
from backend.evaluation import format_eval_result
from backend.exceptions import NotFoundError
from backend.llm.shim import map_chat_entries_to_messages
from backend.models.llm import (
    ChatEntry,
    ChatMessageWithTools,
    ChatRequest,
    ChatResponse,
    ChatResponseWithTools,
)
from backend.models.supplemental import (
    ChatTemplateContextResponse,
    Message,
    MessageContainer,
    SelectionFilter,
    UserInfo,
)


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
    # Get all active chat template containers (no user enrollment filtering since that table is removed)
    active_containers = session.exec(
        select(ChatTemplateContainer)
        .where(
            and_(
                ChatTemplateContainer.start_date <= now,
                ChatTemplateContainer.end_date >= now,
            )
        )
    ).all()

    active_chat_template_contexts = session.exec(
        select(UserChatTemplateContext)
        .join(ChatTemplate)
        .where(
            and_(
                UserChatTemplateContext.user_id == user.id,
                ChatTemplate.chat_template_container_id.in_(
                    [container.id for container in active_containers]
                ),
            )
        )
    ).all()

    badges = session.exec(
        select(Badges).join(UserBadges).where(UserBadges.user_id == user.id)
    ).all()

    evaluations: Iterable[ChallengeEvaluations] = session.exec(
        select(ChallengeEvaluations)
        .join(UserChatTemplateContext)
        .where(UserChatTemplateContext.user_id == user.id)
    ).all()

    assert user.id is not None, "User ID should not be None"
    return UserInfo(
        user_id=user.id,
        email=None,  # Email is not stored in the Users model
        active_chat_template_containers=list(active_containers),
        active_chat_template_contexts=list(active_chat_template_contexts),
        badges=list(badges),
        eval_results=list(
            [format_eval_result(evaluation) for evaluation in evaluations]
        ),
    )


def add_message_to_chat_template(
    session: Session,
    user_id: int,
    chat_template_id: int,
    model: str,
    message: str,
    role: Literal["user", "assistant", "system"] = "user",
) -> int:
    """
    Add a message to the chat template context.
    """
    # Add message if it can be added to the context. It will be followed up by a processed
    # at message.
    user_chat_template_context = session.exec(
        select(UserChatTemplateContext).where(
            and_(
                UserChatTemplateContext.user_id == user_id,
                UserChatTemplateContext.chat_template_id == chat_template_id,
            )
        )
    ).first()

    if not user_chat_template_context:
        raise NotFoundError("User chat template context not found")
    user_chat_template_context_id = user_chat_template_context.id
    if not user_chat_template_context.can_contribute:
        raise ValueError("User cannot contribute to this chat template context")

    assert user_chat_template_context.id is not None, (
        "User chat template context ID should not be None"
    )
    if (
        get_user_message_count_in_chat_template_context(
            session=session,
            user_chat_template_context_id=user_chat_template_context.id,
        )
        >= MAX_USER_MESSAGE_COUNT_FOR_CHAT_TEMPLATE
    ):
        raise ValueError("Maximum message count reached for this chat template.")

    if not user_chat_template_context_id:
        raise NotFoundError("User chat template context not found")

    chat_message: ChatMessageWithTools = ChatMessageWithTools(
        role=role, content=message
    )

    context_message: UserChatTemplateContextMessages = UserChatTemplateContextMessages(
        user_chat_template_context_id=user_chat_template_context_id,
        content=chat_message.model_dump_json(),
        created_at=datetime.now(UTC),
        content_type=chat_message.__class__.__name__,
        model=model,
        role=role,
        is_user_provided=True,
    )
    session.add(context_message)
    session.commit()
    return user_chat_template_context_id


def add_chat_entries_to_chat_template_no_checks(
    session: Session,
    user_chat_template_context_id: int,
    chat_entries: list[ChatEntry],
):
    """
    Bulk add messages to a chat template context without checks.
    This assumes that the caller has already called add_message_to_challenge
    or similar to ensure the context exists and is valid.
    """
    for chat_entry in chat_entries:
        if not isinstance(
            chat_entry, (ChatResponseWithTools, ChatMessageWithTools, ChatResponse)
        ):  # type: ignore[reportUnnecessaryIsInstance]
            raise ValueError(
                "Messages must be ChatResponseWithTools or ChatMessageWithTools"
            )
        if isinstance(chat_entry, (ChatResponse, ChatResponseWithTools)):
            role: str = "assistant"
        elif isinstance(chat_entry, ChatMessageWithTools):  # type: ignore[reportUnnecessaryIsInstance]
            role = chat_entry.role
        else:
            raise ValueError(f"Invalid chat entry type: {type(chat_entry)}")
        context_message: UserChatTemplateContextMessages = UserChatTemplateContextMessages(
            user_chat_template_context_id=user_chat_template_context_id,
            content=chat_entry.model_dump_json(),
            created_at=datetime.now(UTC),
            content_type=chat_entry.__class__.__name__,
            role=role,
            is_user_provided=True,
        )
        session.add(context_message)
    session.commit()


def get_chat_template_context_response(
    session: Session, user_id: int, chat_template_id: int
) -> ChatTemplateContextResponse:
    """
    Get the chat template context response for a user and chat template.
    Returns the ChatTemplateContextResponse object.
    """
    context = session.exec(
        select(UserChatTemplateContext).where(
            and_(
                UserChatTemplateContext.user_id == user_id,
                UserChatTemplateContext.chat_template_id == chat_template_id,
            )
        )
    ).first()

    if not context:
        raise NotFoundError("User chat template context not found")

    default_messages: list[Message] = []
    assert context.chat_template is not None, "Chat template should not be None"
    # Extract initial messages from message_tree using Pydantic models
    if context.chat_template.message_tree:
        for node_data in context.chat_template.message_tree:
            container = MessageContainer.model_validate(node_data)
            default_messages.append(container.message)

    messages = session.exec(
        select(UserChatTemplateContextMessages).where(
            UserChatTemplateContextMessages.user_chat_template_context_id == context.id
        )
    ).all()
    assert context.id is not None, "User chat template context ID should not be None"
    return ChatTemplateContextResponse(
        user_chat_template_context=context,
        # XXX: This should not be so inefficient.
        messages=default_messages
        + list(
            map_chat_entries_to_messages(
                list(_instantiate_chat_template_context_messages(messages))
            )
        ),
        remaining_message_count=MAX_USER_MESSAGE_COUNT_FOR_CHAT_TEMPLATE
        - get_user_message_count_in_chat_template_context(session, context.id),
        eval_result=format_eval_result(context.challenge_evaluations[0])
        if context.challenge_evaluations
        else None,
    )


def start_chat_template(
    session: Session, user_id: int, chat_template_id: int
) -> UserChatTemplateContext:
    """
    Start a chat template for the user.  Returns the UserChatTemplateContext object.
    """
    # Check if chat template exists
    # Check if user already has a context for this chat template
    existing_context = session.exec(
        select(UserChatTemplateContext).where(
            and_(
                UserChatTemplateContext.user_id == user_id,
                UserChatTemplateContext.chat_template_id == chat_template_id,
            )
        )
    ).first()

    if existing_context:
        return existing_context

    # Verify the chat template exists and is part of a container
    template = session.get(ChatTemplate, chat_template_id)
    if not template:
        raise NotFoundError("Chat template not found")
    if not template.chat_template_container:
        raise ValueError("Chat template is not part of a container")
    assert template.chat_template_container.id is not None, "Container ID should not be None"

    # Create new chat template context
    context = UserChatTemplateContext(
        user_id=user_id,
        chat_template_id=chat_template_id,
        started_at=datetime.now(UTC),
        can_contribute=True,
        last_message_version=0,
    )
    session.add(context)
    session.flush()
    assert context.id is not None, "User chat template context ID should not be None"
    evaluation: ChallengeEvaluations = ChallengeEvaluations(
        user_chat_template_context_id=context.id,
        created_at=datetime.now(UTC),
    )

    session.add(evaluation)
    session.commit()
    session.refresh(context)

    return context


def list_chat_template_containers(
    session: Session,
    selection_filter: SelectionFilter = SelectionFilter.ACTIVE_ONLY,
    page_index: int = 0,
    count: int = 10,
) -> Iterable[ChatTemplateContainer]:
    """
    List chat template containers based on selection filter, pagination, and count.
    """
    now = datetime.now(UTC)

    # Start with base select statement
    statement = select(ChatTemplateContainer)

    # Apply filters based on selection_filter
    if selection_filter == SelectionFilter.PAST_ONLY:
        statement = statement.where(ChatTemplateContainer.end_date < now)
    elif selection_filter == SelectionFilter.ACTIVE_ONLY:
        statement = statement.where(
            ChatTemplateContainer.start_date <= now, ChatTemplateContainer.end_date >= now
        )
    elif selection_filter == SelectionFilter.FUTURE_ONLY:
        statement = statement.where(ChatTemplateContainer.start_date > now)
    elif selection_filter == SelectionFilter.PAST_AND_ACTIVE:
        statement = statement.where(
            or_(
                ChatTemplateContainer.end_date < now,
                and_(ChatTemplateContainer.start_date <= now, ChatTemplateContainer.end_date >= now),
            )
        )
    elif selection_filter == SelectionFilter.ACTIVE_AND_FUTURE:
        statement = statement.where(
            or_(
                and_(ChatTemplateContainer.start_date <= now, ChatTemplateContainer.end_date >= now),
                ChatTemplateContainer.start_date > now,
            )
        )

    # Apply pagination
    statement = statement.offset(page_index * count).limit(count)

    # Execute query
    tournaments = session.exec(statement).all()

    # Return directly - FastAPI will handle conversion
    return tournaments


def list_chat_templates(
    session: Session,
    chat_template_container_id: int | None = None,
    page_index: int = 0,
    count: int = 10,
) -> Iterable[ChatTemplate]:
    """
    List chat templates based on container ID, pagination, and count.
    """
    statement = select(ChatTemplate).options(selectinload(ChatTemplate.chat_template_container))
    if chat_template_container_id:
        statement = statement.where(ChatTemplate.chat_template_container_id == chat_template_container_id)
    statement = statement.offset(page_index * count).limit(count)
    challenges = session.exec(statement).all()
    return challenges


def _instantiate_chat_template_context_messages(
    chat_template_context_messages: Iterable[UserChatTemplateContextMessages],
) -> Iterable[ChatEntry]:
    """Instantiate chat entries from user chat template context messages.

    Args:
        chat_template_context_messages (Iterable[UserChatTemplateContextMessages]): The user chat template context messages to instantiate.

    Raises:
        ValueError: If the content type of the message is unknown.

    Returns:
        Iterable[ChatEntry]: Yields chat entries based on the content type of the messages.

    Yields:
        Iterator[Iterable[ChatEntry]]: An iterator that yields chat entries based on the content type of the messages.
    """
    chat_template_context_messages = sorted(
        chat_template_context_messages, key=lambda m: m.created_at
    )
    for message in chat_template_context_messages:
        if message.content_type == "ChatRequest":
            yield ChatRequest.model_validate_json(message.content)  # type: ignore
        elif message.content_type == "ChatResponseWithTools":
            yield ChatResponseWithTools.model_validate_json(message.content)
        elif message.content_type == "ChatMessageWithTools":
            yield ChatMessageWithTools.model_validate_json(message.content)
        elif message.content_type == "ChatResponse":
            yield ChatResponse.model_validate_json(message.content)
        else:
            raise ValueError(f"Unknown content type: {message.content_type}")


def load_chat_template_context_messages(
    session: Session, user_chat_template_context_id: int
) -> Iterable[Message]:
    """
    Load all messages for a given user chat template context.
    Returns a list of UserChatTemplateContextMessages.
    """
    user_chat_template_context: UserChatTemplateContext | None = session.exec(
        select(UserChatTemplateContext).where(
            UserChatTemplateContext.id == user_chat_template_context_id
        )
    ).first()
    if not user_chat_template_context:
        raise NotFoundError("User chat template context not found")

    default_messages: list[Message] = []
    assert user_chat_template_context.chat_template is not None, "Chat template should not be None"
    # Extract initial messages from message_tree using Pydantic models
    if user_chat_template_context.chat_template.message_tree:
        for node_data in user_chat_template_context.chat_template.message_tree:
            container = MessageContainer.model_validate(node_data)
            default_messages.append(container.message)

    context_messages: Iterable[UserChatTemplateContextMessages] = session.exec(
        select(UserChatTemplateContextMessages).where(
            UserChatTemplateContextMessages.user_chat_template_context_id
            == user_chat_template_context_id
        )
    ).all()
    return default_messages + list(
        map_chat_entries_to_messages(
            list(_instantiate_chat_template_context_messages(context_messages))
        )
    )


def get_user_message_count_in_chat_template_context(
    session: Session, user_chat_template_context_id: int
) -> int:
    """
    Get the count of user messages in a given chat template context.
    Returns the count of messages.
    """
    count: int = session.exec(
        select(func.count())
        .select_from(UserChatTemplateContextMessages)
        .where(
            and_(
                UserChatTemplateContextMessages.user_chat_template_context_id
                == user_chat_template_context_id,
                UserChatTemplateContextMessages.role == "user",
            )
        )
    ).one()
    return count


def get_chat_template_tools(session: Session, chat_template_id: int) -> list[str] | None:
    """
    Get the list of tools available for a given chat template.
    Returns a list of tool names.
    """
    template = session.get(ChatTemplate, chat_template_id)
    if not template:
        raise NotFoundError("Chat template not found")

    # Assuming tools are stored in a related model or as a JSON field
    return json.loads(template.required_tools) if template.required_tools else None
