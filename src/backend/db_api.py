"""Database API functions for chat template management.

This module provides database operations for chat templates and contexts,
using the new ChatContext model instead of the legacy UserChatTemplateContext.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from functools import cache

from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, or_, select

from backend.database.models import (
    Badges,
    ChallengeEvaluations,
    ChatContext,
    ChatTemplate,
    ChatTemplateContainer,
    UserBadges,
    Users,
)
from backend.exceptions import NotFoundError
from backend.models.evaluation import EvalResult, EvalStatus
from backend.models.supplemental import (
    ChatContextResponse,
    Message,
    MessageContainer,
    MessageTree,
    SelectionFilter,
    UserInfo,
)


def format_eval_result(evaluation: ChallengeEvaluations) -> EvalResult:
    """Format a ChallengeEvaluations object into an EvalResult.

    Args:
        evaluation: ChallengeEvaluations object to format

    Returns:
        EvalResult: Formatted evaluation result
    """
    # Determine status from timestamp fields
    if evaluation.succeeded_at:
        status = EvalStatus.SUCCEEDED
    elif evaluation.failed_at:
        status = EvalStatus.FAILED
    elif evaluation.errored_at:
        status = EvalStatus.ERRORED
    else:
        status = EvalStatus.NOT_EVALUATED

    # Get chat_template_id from the related chat_context if available
    chat_template_id = (
        evaluation.chat_context.chat_template_id if evaluation.chat_context else None
    )

    return EvalResult(
        reason=evaluation.result_text or "No result text",
        status=status,
        chat_template_id=chat_template_id,
        chat_context_id=evaluation.chat_context_id,
        context_message_leaf_id=evaluation.context_message_leaf_id,
    )


# Bind between sub and local user id should be persistent enough to justify caching
@cache
def ensure_user_exists(session: Session, user_sub: str) -> Users:
    """Ensure the user exists in the database.

    If not, create a new user. Returns the user object.

    Args:
        session: Database session
        user_sub: User's Supabase ID (sub)

    Returns:
        Users: The existing or newly created user
    """
    user = session.exec(select(Users).where(Users.sub_id == user_sub)).first()
    if not user:
        user = Users(sub_id=user_sub)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def ensure_chat_context(
    session: Session, user_id: int, chat_template_id: int
) -> ChatContext:
    """Ensure a chat context exists for the user and template.

    If the user has no chat context for the template, create one.
    If one already exists, return it.
    If more than one exists (shouldn't happen due to unique constraint),
    return the chat context with the highest id.

    Args:
        session: Database session
        user_id: Internal user ID
        chat_template_id: Chat template ID

    Returns:
        ChatContext: The existing or newly created chat context

    Raises:
        NotFoundError: If the chat template doesn't exist
    """
    # Verify the chat template exists
    template = session.get(ChatTemplate, chat_template_id)
    if not template:
        raise NotFoundError("Chat template not found")

    # Query for existing contexts (should be at most one due to unique constraint)
    existing_contexts = session.exec(
        select(ChatContext)
        .where(
            and_(
                ChatContext.user_id == user_id,
                ChatContext.chat_template_id == chat_template_id,
            )
        )
        .order_by(ChatContext.id.desc())  # Order by ID descending to get highest first
    ).all()

    if existing_contexts:
        # Return the context with highest ID (first in list due to ordering)
        return existing_contexts[0]

    # Create new chat context with template's message tree
    context = ChatContext(
        user_id=user_id,
        chat_template_id=chat_template_id,
        started_at=datetime.now(UTC),
        can_contribute=True,
        message_tree=template.message_tree,  # Copy template's message tree
    )
    session.add(context)
    session.commit()
    session.refresh(context)

    return context


def update_chat_context_message_tree(
    session: Session, chat_context_id: int, message_tree: MessageTree
) -> ChatContext:
    """Update the message tree of a chat context.

    If the database row exists and has can_contribute set to true,
    update the message tree with the user provided message_tree.

    Args:
        session: Database session
        chat_context_id: Chat context ID
        message_tree: New message tree structure to set

    Returns:
        ChatContext: The updated chat context

    Raises:
        NotFoundError: If the chat context doesn't exist
        ValueError: If can_contribute is False
    """
    # Get the chat context
    context = session.get(ChatContext, chat_context_id)
    if not context:
        raise NotFoundError("Chat context not found")

    # Check if contribution is allowed
    if not context.can_contribute:
        raise ValueError("User cannot contribute to this chat context")

    # Convert MessageTree (list of MessageContainer) to dict for JSONB storage
    # Each MessageContainer has model_dump() method to convert to dict
    message_tree_dict = [container.model_dump() for container in message_tree]

    # Update the message tree
    context.message_tree = message_tree_dict
    session.add(context)
    session.commit()
    session.refresh(context)

    return context


def list_evaluations(
    session: Session,
    user_id: int,
    chat_template_id_filter: int | None = None,
    page_index: int = 0,
    count: int = 10,
) -> list[ChatContextResponse]:
    """List chat context evaluations for a specific user.

    Returns a list of ChatContextResponse objects for the given user and
    optionally filtered by chat_template_id.

    Args:
        session: Database session
        user_id: Internal user ID to filter by
        chat_template_id_filter: Optional filter by chat template ID
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page

    Returns:
        List of ChatContextResponse objects with evaluation results
    """
    # Build the query - always filter by user
    statement = (
        select(ChatContext)
        .options(
            selectinload(ChatContext.challenge_evaluations),
            selectinload(ChatContext.chat_template),
        )
        .where(ChatContext.user_id == user_id)
    )

    # Apply template filter if provided
    if chat_template_id_filter is not None:
        statement = statement.where(
            ChatContext.chat_template_id == chat_template_id_filter
        )

    # Apply pagination
    statement = statement.offset(page_index * count).limit(count)

    # Execute query
    contexts = session.exec(statement).all()

    # Convert to response objects
    responses = []
    for context in contexts:
        # Get the most recent evaluation if any exist
        eval_result = None
        if context.challenge_evaluations:
            # Sort by created_at to get most recent
            sorted_evals = sorted(
                context.challenge_evaluations,
                key=lambda e: e.created_at,
                reverse=True,
            )
            eval_result = format_eval_result(sorted_evals[0])

        response = ChatContextResponse(
            user_chat_template_context=context,
            eval_result=eval_result,
            remaining_message_count=0,  # Set to 0 as we don't track this in the new pattern
        )
        responses.append(response)

    return responses


def list_evaluations_by_context_id(
    session: Session,
    chat_context_id: int,
    page_index: int = 0,
    count: int = 10,
) -> list[EvalResult]:
    """List all evaluation results for a specific chat context.

    Returns a list of EvalResult objects for the given chat context,
    ordered by creation date (most recent first).

    Args:
        session: Database session
        chat_context_id: Chat context ID to filter by
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page

    Returns:
        List of EvalResult objects with evaluation results
    """
    # Build query for evaluations of this context
    statement = (
        select(ChallengeEvaluations)
        .where(ChallengeEvaluations.chat_context_id == chat_context_id)
        .order_by(ChallengeEvaluations.created_at.desc())
        .offset(page_index * count)
        .limit(count)
    )

    # Execute query
    evaluations = session.exec(statement).all()

    # Convert to EvalResult objects
    return [format_eval_result(evaluation) for evaluation in evaluations]


def list_chat_template_containers(
    session: Session,
    selection_filter: SelectionFilter = SelectionFilter.ACTIVE_ONLY,
    container_type: str | None = None,
    page_index: int = 0,
    count: int = 10,
) -> Iterable[ChatTemplateContainer]:
    """List chat template containers based on selection filter, container type, and pagination.

    Args:
        session: Database session
        selection_filter: Filter containers by date (ACTIVE_ONLY, PAST_ONLY, etc.)
        container_type: Optional filter by container type
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page

    Returns:
        Iterable of ChatTemplateContainer objects matching the criteria
    """
    now = datetime.now(UTC)

    # Start with base select statement
    statement = select(ChatTemplateContainer)

    # Apply filters based on selection_filter
    if selection_filter == SelectionFilter.PAST_ONLY:
        # Container is past only if it HAS an end_date AND it's in the past
        statement = statement.where(
            and_(
                ChatTemplateContainer.end_date.isnot(None),
                ChatTemplateContainer.end_date < now,
            )
        )
    elif selection_filter == SelectionFilter.ACTIVE_ONLY:
        # Active if (no start OR started) AND (no end OR not ended)
        statement = statement.where(
            and_(
                or_(
                    ChatTemplateContainer.start_date.is_(None),
                    ChatTemplateContainer.start_date <= now,
                ),
                or_(
                    ChatTemplateContainer.end_date.is_(None),
                    ChatTemplateContainer.end_date >= now,
                ),
            )
        )
    elif selection_filter == SelectionFilter.FUTURE_ONLY:
        # Container is future only if it HAS a start_date AND it's in the future
        statement = statement.where(
            and_(
                ChatTemplateContainer.start_date.isnot(None),
                ChatTemplateContainer.start_date > now,
            )
        )
    elif selection_filter == SelectionFilter.PAST_AND_ACTIVE:
        # Past OR Active
        statement = statement.where(
            or_(
                # Past: has end_date and it's past
                and_(
                    ChatTemplateContainer.end_date.isnot(None),
                    ChatTemplateContainer.end_date < now,
                ),
                # Active: (no start OR started) AND (no end OR not ended)
                and_(
                    or_(
                        ChatTemplateContainer.start_date.is_(None),
                        ChatTemplateContainer.start_date <= now,
                    ),
                    or_(
                        ChatTemplateContainer.end_date.is_(None),
                        ChatTemplateContainer.end_date >= now,
                    ),
                ),
            )
        )
    elif selection_filter == SelectionFilter.ACTIVE_AND_FUTURE:
        # Active OR Future
        statement = statement.where(
            or_(
                # Active: (no start OR started) AND (no end OR not ended)
                and_(
                    or_(
                        ChatTemplateContainer.start_date.is_(None),
                        ChatTemplateContainer.start_date <= now,
                    ),
                    or_(
                        ChatTemplateContainer.end_date.is_(None),
                        ChatTemplateContainer.end_date >= now,
                    ),
                ),
                # Future: has start_date and it's in future
                and_(
                    ChatTemplateContainer.start_date.isnot(None),
                    ChatTemplateContainer.start_date > now,
                ),
            )
        )

    # Apply container type filter if provided
    if container_type:
        statement = statement.where(ChatTemplateContainer.type == container_type)

    # Apply pagination
    statement = statement.offset(page_index * count).limit(count)

    # Execute query
    containers = session.exec(statement).all()

    # Return directly - FastAPI will handle conversion
    return containers


def list_chat_templates(
    session: Session,
    chat_template_container_id: int | None = None,
    container_type: str | None = None,
    page_index: int = 0,
    count: int = 10,
) -> Iterable[ChatTemplate]:
    """List chat templates based on container ID, container type, pagination, and count.

    Args:
        session: Database session
        chat_template_container_id: Optional filter by container ID
        container_type: Optional filter by container type
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page

    Returns:
        Iterable of ChatTemplate objects
    """
    statement = select(ChatTemplate).options(
        selectinload(ChatTemplate.chat_template_container)
    )

    # Filter by specific container ID if provided
    if chat_template_container_id:
        statement = statement.where(
            ChatTemplate.chat_template_container_id == chat_template_container_id
        )

    # Filter by container type if provided
    if container_type:
        statement = statement.join(ChatTemplateContainer).where(
            ChatTemplateContainer.type == container_type
        )

    statement = statement.offset(page_index * count).limit(count)
    templates = session.exec(statement).all()
    return templates


def get_user_info(session: Session, user_sub: str) -> UserInfo | None:
    """Get user active tournaments, badges, and active challenges.

    If the user isn't in the postgres db for joining, add the user,
    and return the user data. Updated to work with ChatContext instead
    of the old UserChatTemplateContext.

    Args:
        session: Database session
        user_sub: User's Supabase ID (sub)

    Returns:
        UserInfo object with user details, badges, and contexts
    """
    now = datetime.now(UTC)
    user: Users = ensure_user_exists(session, user_sub)

    # Get all active chat template containers
    active_containers = session.exec(
        select(ChatTemplateContainer).where(
            and_(
                or_(
                    ChatTemplateContainer.start_date.is_(None),
                    ChatTemplateContainer.start_date <= now,
                ),
                or_(
                    ChatTemplateContainer.end_date.is_(None),
                    ChatTemplateContainer.end_date >= now,
                ),
            )
        )
    ).all()

    # Get user's chat contexts for active containers
    active_chat_contexts = session.exec(
        select(ChatContext)
        .join(ChatTemplate)
        .where(
            and_(
                ChatContext.user_id == user.id,
                ChatTemplate.chat_template_container_id.in_(
                    [container.id for container in active_containers]
                    if active_containers
                    else []
                ),
            )
        )
    ).all()

    # Get user's badges
    badges = session.exec(
        select(Badges).join(UserBadges).where(UserBadges.user_id == user.id)
    ).all()

    # Get user's evaluations
    evaluations: Iterable[ChallengeEvaluations] = session.exec(
        select(ChallengeEvaluations)
        .join(ChatContext)
        .where(ChatContext.user_id == user.id)
    ).all()

    assert user.id is not None, "User ID should not be None"
    return UserInfo(
        user_id=user.id,
        email=None,  # Email is not stored in the Users model
        active_chat_template_containers=list(active_containers),
        active_chat_template_contexts=list(active_chat_contexts),
        badges=list(badges),
        eval_results=list(
            [format_eval_result(evaluation) for evaluation in evaluations]
        ),
    )


def get_chat_template_by_id(
    session: Session, chat_template_id: int
) -> ChatTemplate | None:
    """Get a chat template by ID with container eagerly loaded.

    Args:
        session: Database session
        chat_template_id: ID of the chat template to retrieve

    Returns:
        ChatTemplate object with container loaded, or None if not found
    """
    statement = (
        select(ChatTemplate)
        .options(selectinload(ChatTemplate.chat_template_container))
        .where(ChatTemplate.id == chat_template_id)
    )
    return session.exec(statement).first()


def get_chat_template_tools(
    session: Session, chat_template_id: int
) -> list[str] | None:
    """Get the list of tools available for a given chat template.

    Args:
        session: Database session
        chat_template_id: ID of the chat template

    Returns:
        List of tool names or None if no tools are defined

    Raises:
        NotFoundError: If chat template not found
    """
    import json

    template = session.get(ChatTemplate, chat_template_id)
    if not template:
        raise NotFoundError("Chat template not found")

    # Assuming tools are stored as JSON string in required_tools field
    return json.loads(template.required_tools) if template.required_tools else None


def load_chat_context_messages_to_leaf(
    session: Session, chat_context_id: int, leaf_id: int | None = None
) -> list[Message]:
    """Load messages from chat context, optionally to a specific leaf.

    Uses message_tree_utils to extract conversation path from the JSONB
    message_tree field.

    Args:
        session: Database session
        chat_context_id: ID of the chat context
        leaf_id: Optional ID of leaf message to extract path to

    Returns:
        List of Message objects in conversation order

    Raises:
        NotFoundError: If chat context not found
    """
    from backend.message_tree_utils import (
        extract_messages_to_leaf,
        flatten_message_tree,
    )

    # Get the chat context
    context = session.get(ChatContext, chat_context_id)
    if not context:
        raise NotFoundError("Chat context not found")

    # Get messages from context message_tree (includes template messages)
    messages: list[Message] = []
    if context.message_tree:
        # Convert JSONB to MessageTree
        message_tree = [
            MessageContainer.model_validate(node) for node in context.message_tree
        ]

        if leaf_id is not None:
            # Extract path to specific leaf
            messages = extract_messages_to_leaf(message_tree, leaf_id)
        else:
            # Get all messages in tree order
            messages = flatten_message_tree(message_tree)

    return messages
