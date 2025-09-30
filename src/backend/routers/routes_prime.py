"""Enhanced chat template routes with improved patterns.

This module provides improved API endpoints for:
- Ensuring chat contexts exist
- Updating message trees
- Listing evaluations
- Managing chat templates
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

import backend.db_api as db_api
from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import (
    ChatContext,
    ChatTemplate,
    ChatTemplateContainer,
    Users,
)
from backend.exceptions import NotFoundError
from backend.models.supplemental import (
    ChatContextResponse,
    ChatTemplatesPublic,
    MessageTree,
    SelectionFilter,
)

# Create router with tags
router = APIRouter(
    tags=["chat_templates_prime"],
    responses={404: {"description": "Not found"}},
)


class EnsureChatContextRequest(BaseModel):
    """Request body for ensuring chat context exists."""

    chat_template_id: int


class EnsureChatContextResponse(BaseModel):
    """Response for ensure chat context endpoint."""

    chat_context: ChatContext

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


class UpdateMessageTreeRequest(BaseModel):
    """Request body for updating message tree."""

    message_tree: MessageTree


class UpdateMessageTreeResponse(BaseModel):
    """Response for update message tree endpoint."""

    chat_context: ChatContext

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True


@router.post("/chat_contexts/ensure", response_model=EnsureChatContextResponse)
async def ensure_chat_context(
    request: EnsureChatContextRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ensure a chat context exists for the current user and template.

    If the user has no chat context for the template, create one.
    If one already exists, return it.
    If more than one exists, return the chat context with the highest id.

    Args:
        request: Request containing chat_template_id
        current_user: Current authenticated user
        db: Database session

    Returns:
        EnsureChatContextResponse with the chat context

    Raises:
        HTTPException: 404 if template not found
    """
    try:
        # Get the internal user id from sub_id
        user: Users = db_api.ensure_user_exists(db, current_user["id"])
        if user.id is None:
            raise HTTPException(status_code=500, detail="User ID not found")

        # Ensure chat context exists
        context = db_api.ensure_chat_context(
            session=db,
            user_id=user.id,
            chat_template_id=request.chat_template_id,
        )

        return EnsureChatContextResponse(chat_context=context)

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/chat_contexts/{chat_context_id}/message_tree",
    response_model=UpdateMessageTreeResponse,
)
async def update_chat_context_message_tree(
    chat_context_id: int,
    request: UpdateMessageTreeRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the message tree of a chat context.

    If the database row exists and has can_contribute set to true,
    update the message tree with the user provided message_tree.

    Args:
        chat_context_id: ID of the chat context to update
        request: Request containing the new message tree
        current_user: Current authenticated user
        db: Database session

    Returns:
        UpdateMessageTreeResponse with the updated chat context

    Raises:
        HTTPException: 404 if context not found, 403 if can_contribute is False
    """
    try:
        # Verify user owns this context
        user: Users = db_api.ensure_user_exists(db, current_user["id"])
        if user.id is None:
            raise HTTPException(status_code=500, detail="User ID not found")

        # Get the context to verify ownership
        context = db.get(ChatContext, chat_context_id)
        if not context:
            raise HTTPException(status_code=404, detail="Chat context not found")

        if context.user_id != user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this context"
            )

        # Update the message tree
        updated_context = db_api.update_chat_context_message_tree(
            session=db,
            chat_context_id=chat_context_id,
            message_tree=request.message_tree,
        )

        return UpdateMessageTreeResponse(chat_context=updated_context)

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluations", response_model=list[ChatContextResponse])
async def list_evaluations(
    chat_template_id: int | None = None,
    page_index: int = 0,
    count: int = 10,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List evaluation results for chat contexts.

    Returns a list of ChatContextResponse objects for the given chat_template_id,
    if they exist. If no filter is provided, returns all evaluations.

    Args:
        chat_template_id: Optional filter by chat template ID
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of ChatContextResponse objects with evaluation results
    """
    try:
        # Get the internal user id from sub_id
        user: Users = db_api.ensure_user_exists(db, current_user["id"])
        if user.id is None:
            raise HTTPException(status_code=500, detail="User ID not found")

        # Get evaluations for the user
        evaluations = db_api.list_evaluations(
            session=db,
            user_id=user.id,
            chat_template_id_filter=chat_template_id,
            page_index=page_index,
            count=count,
        )

        return evaluations

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat_templates", response_model=list[ChatTemplatesPublic])
async def list_chat_templates(
    chat_template_container_id: int | None = None,
    container_type: str | None = None,
    page_index: int = 0,
    count: int = 10,
    db: Session = Depends(get_db),
):
    """List chat templates with filtering options.

    This is identical to the existing list_chat_templates endpoint.

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


@router.get("/chat_templates/{chat_template_id}", response_model=ChatTemplatesPublic)
async def get_chat_template(
    chat_template_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific chat template.

    Retrieves complete information about a chat template including its
    name, description, requirements, and associated container.
    This endpoint does not require authentication.

    Args:
        chat_template_id: The unique identifier of the template to retrieve
        db: Database session

    Returns:
        ChatTemplatesPublic: Complete template information including:
            - chat_template: Full ChatTemplate object with all fields
            - container_name: Name of the parent container

    Raises:
        HTTPException: 404 if template with the specified ID is not found

    Example:
        GET /chat_templates/1
        Response:
        {
            "chat_template": {
                "id": 1,
                "name": "Introduction Challenge",
                "description": "Learn the basics",
                "chat_template_container_id": 5,
                "required_tools": "[\"calculator\", \"search\"]",
                "evaluation_prompt": "User must complete intro",
                "message_tree": [...]
            },
            "container_name": "Tutorial Container"
        }
    """
    template = db_api.get_chat_template_by_id(db, chat_template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Chat template not found")

    return ChatTemplatesPublic(
        chat_template=template,
        container_name=template.chat_template_container.name
        if template.chat_template_container
        else "No Container",
    )


@router.get("/chat_template_containers", response_model=list[ChatTemplateContainer])
async def list_chat_template_containers(
    selection_filter: SelectionFilter = SelectionFilter.ACTIVE_ONLY,
    container_type: str | None = None,
    page_index: int = 0,
    count: int = 10,
    db: Session = Depends(get_db),
):
    """List chat template containers with filtering by date and container type.

    Retrieves a paginated list of chat template containers based on date filters
    and optional container type. This endpoint does not require authentication.

    Args:
        selection_filter: Filter containers by date. Options include:
            - ACTIVE_ONLY: Currently active containers (default)
            - PAST_ONLY: Ended containers
            - FUTURE_ONLY: Not yet started containers
            - PAST_AND_ACTIVE: Past and current containers
            - ACTIVE_AND_FUTURE: Current and upcoming containers
        container_type: Optional filter by container type (e.g., 'challenge', 'tutorial')
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page
        db: Database session

    Returns:
        List of ChatTemplateContainer objects matching the criteria

    Example:
        GET /chat_template_containers?selection_filter=ACTIVE_ONLY&container_type=challenge&page_index=0&count=10
        Response:
        [
            {
                "id": 1,
                "name": "Beginner Challenges",
                "type": "challenge",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-12-31T23:59:59Z",
                "description": "A collection of beginner-level challenges"
            }
        ]
    """
    return list(
        db_api.list_chat_template_containers(
            session=db,
            selection_filter=selection_filter,
            container_type=container_type,
            page_index=page_index,
            count=count,
        )
    )
