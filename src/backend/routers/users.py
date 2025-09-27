"""User routes for managing user profiles and information.

This module provides API endpoints for:
- Retrieving current user information
- Managing user profiles
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.db_api import get_user_info
from backend.models.supplemental import UserInfo

# Create router with prefix and tags
router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={401: {"description": "Unauthorized"}},
)


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user information.

    Retrieves comprehensive information about the currently authenticated user,
    including their profile details, badges earned, and challenge progress.

    Args:
        current_user: Current authenticated user from JWT token
        db: Database session

    Returns:
        UserInfo: Complete user information including:
            - user: Basic user details (id, username, email, created_at)
            - badges: List of badges earned by the user
            - badge_count: Total number of badges earned
            - contexts: List of active chat template contexts
            - context_count: Total number of contexts created

    Example:
        ```python
        GET /users/me
        Response:
        {
            "user": {
                "id": 1,
                "sub_id": "uuid-from-supabase",
                "username": "john_doe",
                "email": "john@example.com",
                "created_at": "2024-01-15T10:00:00Z"
            },
            "badges": [
                {
                    "id": 1,
                    "name": "First Steps",
                    "description": "Completed first challenge",
                    "earned_at": "2024-01-16T14:30:00Z"
                }
            ],
            "badge_count": 1,
            "contexts": [
                {
                    "id": 5,
                    "chat_template_id": 10,
                    "started_at": "2024-01-16T14:00:00Z",
                    "can_contribute": true
                }
            ],
            "context_count": 3
        }
        ```

    Note:
        This endpoint uses the Supabase user ID (sub_id) to fetch the internal
        user record and all associated data. The user is automatically created
        in the internal database if they don't exist yet.
    """
    return get_user_info(db, current_user["id"])