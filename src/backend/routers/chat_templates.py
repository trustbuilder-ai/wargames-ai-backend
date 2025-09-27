"""Chat template routes for managing and interacting with chat templates.

This module provides API endpoints for:
- Listing and retrieving chat template containers
- Managing chat templates
- Starting and interacting with chat template contexts
- Evaluating chat template responses
- Managing message trees
"""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

import backend.db_api as db_api
import backend.evaluation as evaluation
from backend.auth.dependencies import get_current_user
from backend.config import MAX_MESSAGE_LENGTH, MAX_USER_MESSAGE_COUNT_FOR_CHAT_TEMPLATE
from backend.database.connection import get_db
from backend.database.models import (
    ChatTemplate,
    ChatTemplateContainer,
    UserChatTemplateContext,
    Users,
)
from backend.db_api import (
    add_chat_entries_to_chat_template_no_checks,
    ensure_user_exists,
)
from backend.exceptions import NotFoundError
from backend.llm.shim import (
    DEFAULT_CHAT_COMPLETION_MODEL,
    map_chat_entries_to_messages,
    send_shim_request,
    send_shim_request_with_tools,
)
from backend.models.evaluation import EvalResult
from backend.models.llm import ChatEntry
from backend.models.supplemental import (
    ChatTemplateContextLLMResponse,
    ChatTemplateContextResponse,
    ChatTemplatesPublic,
    Message,
    MessageContainer,
    MessageTree,
    SelectionFilter,
)
from backend.util.log import logger

# Create router with prefix and tags
router = APIRouter(
    tags=["chat_templates"],
    responses={404: {"description": "Not found"}},
)


@router.get("/chat_template_containers", response_model=list[ChatTemplateContainer])
async def list_chat_template_containers(
    selection_filter: SelectionFilter = SelectionFilter.ACTIVE_ONLY,
    container_type: str | None = None,
    page_index: int = 0,
    count: int = 10,
    # current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List chat template containers with filtering by date and container type.

    Args:
        selection_filter: Filter containers by date (ACTIVE_ONLY, ALL, or EXPIRED_ONLY)
        container_type: Optional filter by container type (e.g., 'challenge', 'tutorial')
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page
        db: Database session

    Returns:
        List of ChatTemplateContainer objects matching the criteria
    """
    return db_api.list_chat_template_containers(
        session=db,
        selection_filter=selection_filter,
        container_type=container_type,
        page_index=page_index,
        count=count,
    )


@router.get(
    "/chat_template_containers/{chat_template_container_id}",
    response_model=ChatTemplateContainer,
)
async def get_chat_template_container(
    chat_template_container_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific chat template container by ID.

    Args:
        chat_template_container_id: The ID of the container to retrieve
        current_user: Current authenticated user
        db: Database session

    Returns:
        ChatTemplateContainer object

    Raises:
        HTTPException: 404 if container not found
    """
    container = db.get(ChatTemplateContainer, chat_template_container_id)
    if container:
        return container
    raise HTTPException(status_code=404, detail="Chat template container not found")


@router.get("/chat_templates", response_model=list[ChatTemplatesPublic])
async def list_chat_templates(
    chat_template_container_id: int | None = None,
    container_type: str | None = None,
    page_index: int = 0,
    count: int = 10,
    db: Session = Depends(get_db),
):
    """List chat templates with filtering options.

    Args:
        chat_template_container_id: Optional filter by container ID
        container_type: Optional filter by container type
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page
        db: Database session

    Returns:
        List of ChatTemplatesPublic objects with template and container information
    """
    templates: list[ChatTemplate] = list(
        db_api.list_chat_templates(
            session=db,
            chat_template_container_id=chat_template_container_id,
            container_type=container_type,
            page_index=page_index,
            count=count,
        )
    )
    return [
        ChatTemplatesPublic(
            chat_template=template,
            container_name=template.chat_template_container.name
            if template.chat_template_container
            else "No Container",
        )
        for template in templates
    ]


@router.post(
    "/chat_templates/{chat_template_id}/start", response_model=UserChatTemplateContext
)
async def start_chat_template(
    chat_template_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new chat template context for the current user.

    This creates a new context for the user to interact with the specified
    chat template. Each user can have multiple contexts for the same template.

    Args:
        chat_template_id: The ID of the chat template to start
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserChatTemplateContext object representing the new context

    Raises:
        HTTPException: 404 if template not found, 400 if start fails
    """
    # Get the internal user id from sub_id
    user: Users = ensure_user_exists(db, current_user["id"])

    # Ensure user.id is not None (should always be set after ensure_user_exists)
    if user.id is None:
        raise HTTPException(status_code=500, detail="User ID not found")

    template = db.get(ChatTemplate, chat_template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chat template not found")

    try:
        assert template.id is not None, "Template ID should not be None"
        return db_api.start_chat_template(db, user.id, template.id)
    except ValueError as e:
        logger.error(
            f"Failed to start chat template {chat_template_id} for user {user.id}: {e}"
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/chat_templates/{chat_template_id}/add_message",
    response_model=ChatTemplateContextLLMResponse,
)
async def add_message_to_chat_template(
    chat_template_id: int,
    message: str,
    role: Literal["user", "assistant", "system"] = "user",
    current_user: dict[str, Any] = Depends(get_current_user),
    solicit_llm_response: bool = True,
    parent_id_in_tree: int | None = None,
    db: Session = Depends(get_db),
):
    """Add a message to the chat template context and optionally get LLM response.

    This endpoint allows users to send messages to their chat template context
    and optionally receive an AI-generated response.

    Args:
        chat_template_id: The ID of the chat template
        message: The message content to add
        role: The role of the message sender (user, assistant, or system)
        current_user: Current authenticated user
        solicit_llm_response: Whether to get an LLM response (default: True)
        parent_id_in_tree: Optional parent message ID for branching conversations
        db: Database session

    Returns:
        ChatTemplateContextLLMResponse with remaining message count and LLM response

    Raises:
        HTTPException: 400 if message too long or invalid, 404 if template not found
    """
    try:
        if len(message) > MAX_MESSAGE_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
            )
        user: Users = ensure_user_exists(db, current_user["id"])
        assert user.id is not None, "User ID should not be None"

        user_chat_template_context_id, user_message_tree_id = (
            db_api.add_message_to_chat_template_context(
                session=db,
                user_id=user.id,
                chat_template_id=chat_template_id,
                model=DEFAULT_CHAT_COMPLETION_MODEL,
                message=message,
                role=role,
                parent_id_in_tree=parent_id_in_tree,
            )
        )
        context_messages: list[Message] = list(
            db_api.load_chat_template_context_messages(
                session=db,
                user_chat_template_context_id=user_chat_template_context_id,
            )
        )

        if solicit_llm_response:
            template_tools: list[str] | None = db_api.get_chat_template_tools(
                session=db, chat_template_id=chat_template_id
            )
            chat_entry_list: list[ChatEntry] = []
            if template_tools:
                chat_entry_list.extend(
                    await send_shim_request_with_tools(
                        message=message,
                        tools=template_tools,
                        context=context_messages,
                        role=role,
                    )
                )
            else:
                chat_entry_list.append(
                    await send_shim_request(
                        message=message, role=role, context=context_messages
                    )
                )
            add_chat_entries_to_chat_template_no_checks(
                session=db,
                user_chat_template_context_id=user_chat_template_context_id,
                chat_entries=chat_entry_list,
                parent_id_in_tree=user_message_tree_id,
            )
            return ChatTemplateContextLLMResponse(
                remaining_message_count=MAX_USER_MESSAGE_COUNT_FOR_CHAT_TEMPLATE
                - db_api.get_user_message_count_in_chat_template_context(
                    session=db,
                    user_chat_template_context_id=user_chat_template_context_id,
                ),
                messages=list(map_chat_entries_to_messages(chat_entry_list)),
            )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/chat_templates/{chat_template_id}/evaluate", response_model=EvalResult)
async def evaluate_chat_template_context(
    chat_template_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate the user's chat template context for correctness.

    This endpoint runs evaluation logic on the user's chat template context
    to determine if they've successfully completed the template objectives.

    Args:
        chat_template_id: The ID of the chat template to evaluate
        current_user: Current authenticated user
        db: Database session

    Returns:
        EvalResult with success status and evaluation details

    Raises:
        HTTPException: 404 if template or context not found
    """
    user: Users = ensure_user_exists(db, current_user["id"])
    assert user.id is not None, "User ID should not be None"
    # Get the chat template context for the user
    try:
        return await evaluation.evaluate_chat_template_context(
            session=db,
            chat_template_context_id=db.exec(
                select(UserChatTemplateContext).where(
                    UserChatTemplateContext.user_id == user.id,
                    UserChatTemplateContext.chat_template_id == chat_template_id,
                )
            )
            .first()
            .id,  # type: ignore
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chat template not found")


@router.get(
    "/chat_templates/{chat_template_id}/context",
    response_model=ChatTemplateContextResponse,
)
async def get_chat_template_context(
    chat_template_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's chat template context.

    Retrieves the full context including all messages and metadata for the
    user's interaction with the specified chat template.

    Args:
        chat_template_id: The ID of the chat template
        current_user: Current authenticated user
        db: Database session

    Returns:
        ChatTemplateContextResponse with context details and messages

    Raises:
        HTTPException: 404 if template or context not found
    """
    # Get the internal user id from sub_id
    user = ensure_user_exists(db, current_user["id"])

    # Get the chat template context for the user
    try:
        return db_api.get_chat_template_context_response(
            session=db,
            user_id=user.id,
            chat_template_id=chat_template_id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chat template not found")


@router.get("/message_tree/{user_chat_template_context_id}", response_model=MessageTree)
async def get_message_tree(
    user_chat_template_context_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Get message tree for a user chat template context.

    TEMPORARY ROUTE: This endpoint is intended solely for OpenAPI type generation
    from FastAPI and should be removed once the actual message tree functionality
    is implemented in the appropriate service layer.

    Currently returns dummy data for type generation purposes only.

    Args:
        user_chat_template_context_id: The ID of the user chat template context
        current_user: Current authenticated user from JWT token

    Returns:
        MessageTree: A dummy list of MessageContainer objects for OpenAPI generation
    """
    # Return dummy MessageTree data for OpenAPI type generation
    dummy_tree: MessageTree = [
        MessageContainer(
            id_in_tree=1,
            parent_id_in_tree=None,
            message=Message(
                role="user",
                content="Dummy message for OpenAPI type generation",
                is_tool_call=False,
            ),
        ),
        MessageContainer(
            id_in_tree=2,
            parent_id_in_tree=1,
            message=Message(
                role="assistant",
                content="Dummy response for OpenAPI type generation",
                is_tool_call=False,
            ),
        ),
    ]
    return dummy_tree