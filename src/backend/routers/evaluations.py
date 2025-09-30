"""Evaluation routes for managing chat context evaluations.

This module provides API endpoints for:
- Listing evaluation results for chat contexts
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

import backend.db_api as db_api
from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import Users
from backend.models.supplemental import ChatContextResponse

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
