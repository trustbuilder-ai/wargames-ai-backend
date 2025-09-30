"""Badge routes for managing user achievements and rewards.

This module provides API endpoints for:
- Listing all available badges
- Filtering badges by user ownership
- Retrieving specific badge details
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import Badges, UserBadges
from backend.db_api import ensure_user_exists

# Create router with prefix and tags
router = APIRouter(
    prefix="/badges",
    tags=["badges"],
    responses={404: {"description": "Not found"}},
)


@router.get("", response_model=list[Badges])
async def list_badges(
    user_badges_only: bool = False,
    page_index: int = 0,
    count: int = 10,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List badges with optional filtering for user's badges only.

    This endpoint returns a paginated list of badges. When `user_badges_only`
    is set to true, it returns only the badges that the current user has earned.

    Args:
        user_badges_only: If true, filter to only badges earned by the current user
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page (default: 10, max: 100)
        current_user: Current authenticated user from JWT token
        db: Database session

    Returns:
        List of Badges objects, optionally filtered by user ownership

    Example:
        ```python
        # Get all available badges
        GET /badges?page_index=0&count=10

        # Get only the current user's earned badges
        GET /badges?user_badges_only=true&page_index=0&count=10
        ```
    """
    statement = select(Badges)

    if user_badges_only:
        # First get the user by sub_id to get the internal user id
        user = ensure_user_exists(db, current_user["id"])
        # Now join with UserBadges using the correct internal user id
        statement = statement.join(UserBadges).where(UserBadges.user_id == user.id)

    statement = statement.offset(page_index * count).limit(count)
    badges = db.exec(statement).all()
    return badges


@router.get("/{badge_id}", response_model=Badges)
async def get_badge(
    badge_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific badge.

    Retrieves complete information about a badge including its name,
    description, requirements, and associated chat template.

    Args:
        badge_id: The unique identifier of the badge to retrieve
        current_user: Current authenticated user from JWT token
        db: Database session

    Returns:
        Badges: Complete badge information including:
            - id: Unique badge identifier
            - name: Badge name
            - description: Badge description
            - icon: Badge icon URL or identifier
            - chat_template_id: Associated chat template ID
            - evaluation_prompt: Criteria for earning the badge

    Raises:
        HTTPException: 404 if badge with the specified ID is not found

    Example:
        ```python
        GET /badges/1
        Response:
        {
            "id": 1,
            "name": "First Steps",
            "description": "Complete your first chat template",
            "icon": "trophy-gold",
            "chat_template_id": 5,
            "evaluation_prompt": "User must complete the introduction template"
        }
        ```
    """
    badge = db.get(Badges, badge_id)
    if badge:
        return badge
    raise HTTPException(status_code=404, detail="Badge not found")
