"""Evaluation routes for managing chat context evaluations.

This module provides API endpoints for:
- Listing evaluation results for chat contexts
- Evaluating chat contexts to specific message leaves
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

import backend.db_api as db_api
import backend.evaluation as evaluation
from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import ChatContext, Users
from backend.exceptions import NotFoundError
from backend.models.evaluation import EvalResult
from backend.models.supplemental import ChatContextResponse, EvaluateRequest

# Create router with prefix and tags
router = APIRouter(
    prefix="/evaluations",
    tags=["evaluations"],
    responses={404: {"description": "Not found"}},
)


@router.get("", response_model=list[ChatContextResponse])
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


@router.post("/chat_contexts/{chat_context_id}/evaluate", response_model=EvalResult)
async def evaluate_chat_context(
    chat_context_id: int,
    request: EvaluateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate a chat context to a specific message leaf.

    Creates or retrieves an evaluation for the given chat context and message leaf.
    If an evaluation already exists for this context+leaf combination, returns the
    existing result. Otherwise, processes the evaluation.

    Args:
        chat_context_id: ID of the chat context to evaluate
        request: Request containing the leaf_id to evaluate to
        current_user: Current authenticated user
        db: Database session

    Returns:
        EvalResult: Evaluation outcome with status and reason

    Raises:
        HTTPException: 404 if context not found, 403 if user doesn't own context
    """
    try:
        # Verify user exists and get internal user ID
        user: Users = db_api.ensure_user_exists(db, current_user["id"])
        if user.id is None:
            raise HTTPException(status_code=500, detail="User ID not found")

        # Get and verify ownership of chat context
        context = db.get(ChatContext, chat_context_id)
        if not context:
            raise HTTPException(status_code=404, detail="Chat context not found")

        if context.user_id != user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to evaluate this context"
            )

        # Call evaluation function with both chat_context_id and leaf_id
        return await evaluation.evaluate_chat_template_context(
            session=db, chat_context_id=chat_context_id, leaf_id=request.leaf_id
        )

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
