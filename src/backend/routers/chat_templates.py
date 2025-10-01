"""Chat template routes for managing chat templates and containers.

This module provides API endpoints for:
- Listing chat templates with filtering options
- Getting specific chat template details
- Listing chat template containers with date-based filtering
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

import backend.db_api as db_api
from backend.database.connection import get_db
from backend.database.models import ChatTemplate, ChatTemplateContainer
from backend.models.supplemental import ChatTemplatesPublic, SelectionFilter

# Create router with tags (no prefix for root-level endpoints)
router = APIRouter(
    tags=["chat_templates"],
    responses={404: {"description": "Not found"}},
)


@router.get("/chat_templates", response_model=list[ChatTemplatesPublic])
async def list_chat_templates(
    chat_template_container_id: int | None = None,
    container_type: str | None = None,
    page_index: int = 0,
    count: int = 10,
    db: Session = Depends(get_db),
):
    """List chat templates with filtering options.

    This endpoint is publicly accessible without authentication and provides
    filtering by container ID and container type with pagination support.

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
        container_type: Optional filter by container type
            (e.g., 'challenge', 'tutorial')
        page_index: Page number for pagination (0-indexed)
        count: Number of items per page
        db: Database session

    Returns:
        List of ChatTemplateContainer objects matching the criteria

    Example:
        GET /chat_template_containers?selection_filter=ACTIVE_ONLY
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
