"""Chat context routes for managing user chat contexts.

This module provides API endpoints for:
- Ensuring chat contexts exist
- Updating message trees in chat contexts
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

import backend.db_api as db_api
from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import ChatContext, Users
from backend.exceptions import NotFoundError
from backend.models.supplemental import (
    EnsureChatContextRequest,
    EnsureChatContextResponse,
    UpdateMessageTreeRequest,
    UpdateMessageTreeResponse,
)

# Create router with prefix and tags
router = APIRouter(
    prefix="/chat_contexts",
    tags=["chat_contexts"],
    responses={404: {"description": "Not found"}},
)


@router.post("/ensure", response_model=EnsureChatContextResponse)
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
    "/{chat_context_id}/message_tree",
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


@router.delete("/{chat_context_id}", status_code=204)
async def delete_chat_context(
    chat_context_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a chat context.

    Deletes the specified chat context if the current user owns it.
    Related challenge evaluations will be automatically deleted due to cascade.

    Args:
        chat_context_id: ID of the chat context to delete
        current_user: Current authenticated user
        db: Database session

    Returns:
        204 No Content on successful deletion

    Raises:
        HTTPException: 404 if context not found, 403 if user doesn't own the context
    """
    try:
        # Verify user exists and get internal user ID
        user: Users = db_api.ensure_user_exists(db, current_user["id"])
        if user.id is None:
            raise HTTPException(status_code=500, detail="User ID not found")

        # Get the context to verify ownership
        context = db.get(ChatContext, chat_context_id)
        if not context:
            raise HTTPException(status_code=404, detail="Chat context not found")

        # Verify ownership
        if context.user_id != user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this context"
            )

        # Delete the context
        db.delete(context)
        db.commit()

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
