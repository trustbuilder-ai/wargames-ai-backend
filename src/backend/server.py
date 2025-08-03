# Backend: Python/FastAPI implementation

import os
import time
from datetime import UTC, datetime
from typing import Any, Literal, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select
from supabase import Client, create_client

from backend.database.connection import get_db
from backend.database.models import (
    Badges,
    Challenges,
    Tournaments,
    UserBadges,
    UserChallengeContexts,
    Users,
)
from backend.db_api import add_chat_entries_to_challenge_no_checks, ensure_user_exists, get_user_info
import backend.db_api as db_api
from backend.exceptions import NotFoundError
from backend.llm.client import LLMClient
import backend.evaluation as evaluation
from backend.llm.shim import DEFAULT_CHAT_COMPLETION_MODEL, send_shim_request, send_shim_request_with_tools
from backend.models.evaluation import EvalResult
from backend.models.llm import (
    ChatEntry,
    ChatRequest,
    ChatResponse,
    LLMHealthStatus,
    ModelsResponse,
)
from backend.models.supplemental import ChallengeContextResponse, Message, SelectionFilter, UserInfo
from backend.util.log import logger

# Initialize FastAPI
app = FastAPI(title="Backend API with Supabase Auth")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security scheme
security = HTTPBearer()

# Supabase configuration
SUPABASE_URL_DEFAULT_DEVEL = "YOUR_SUPABASE_URL"
SUPABASE_SVCKEY_DEFAULT_DEVEL = "YOUR_SERVICE_KEY"
SUPABASE_URL = os.getenv("SUPABASE_URL", SUPABASE_URL_DEFAULT_DEVEL)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", SUPABASE_SVCKEY_DEFAULT_DEVEL)

# Initialize Supabase client with validation
supabase: Client | None = None
is_development_env = (
    SUPABASE_URL == SUPABASE_URL_DEFAULT_DEVEL
    or SUPABASE_SERVICE_KEY == SUPABASE_SVCKEY_DEFAULT_DEVEL
)

if is_development_env:
    logger.info("Supabase not configured - running in development mode")
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Supabase client: {e}")
        logger.warning("Running in development mode without Supabase authentication")

# uvicorn config
port = int(os.getenv("PORT", 8080))
host = "127.0.0.1" if is_development_env else "0.0.0.0"


class SupabaseAuth:
    """Handle Supabase JWT token verification"""

    def __init__(self):
        self.supabase = supabase
        # Simple in-memory cache: token -> (user_data, expiry_timestamp)
        # PROS:
        #   - Reduces API calls to Supabase during rapid requests
        #     (e.g., page loads with multiple API calls)
        #   - Simple implementation with no external dependencies
        #   - Fast lookups (O(1) dictionary access)
        # CONS:
        #   - No memory limits - could grow unbounded with many unique tokens
        #   - Not shared across worker processes (each process has its own cache)
        #   - Lost on server restart
        #   - No automatic cleanup of expired entries (only cleaned on access)
        # For production, consider Redis or memcached for distributed caching
        self.cache: dict[str, tuple[dict[str, Any], float]] = {}
        self.ttl = 10  # 10 seconds TTL - balance between performance and freshness

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify JWT token from Supabase using the Supabase client"""
        try:
            # Development mode - no Supabase client available
            if self.supabase is None:
                logger.info("Development mode: bypassing token verification")
                return {
                    "id": "dev-user-id",
                    "email": "dev@example.com",
                    "created_at": datetime.now(UTC).isoformat(),
                }

            # Check cache first
            if token in self.cache:
                user_data, expiry = self.cache[token]
                if time.time() < expiry:
                    return user_data
                else:
                    # Clean up expired entry
                    del self.cache[token]

            # Use Supabase client to verify token
            response = self.supabase.auth.get_user(token)

            if not response or not response.user:
                logger.error("Invalid token - no user returned")
                raise HTTPException(status_code=401, detail="Invalid token")

            # Return user data in the expected format
            user_data = {
                "sub": response.user.id,  # User ID
                "email": response.user.email,
                "role": response.user.role or "authenticated",
                "app_metadata": response.user.app_metadata or {},
                "user_metadata": response.user.user_metadata or {},
                "aud": response.user.aud or "authenticated",
                "created_at": response.user.created_at,
            }

            # Store in cache with expiry time
            self.cache[token] = (user_data, time.time() + self.ttl)

            return user_data

        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise HTTPException(
                status_code=401, detail="Could not validate credentials"
            )


# Initialize auth handler
auth_handler = SupabaseAuth()


# Dependency to get current user from JWT token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Extract and verify user from JWT token"""
    token = credentials.credentials

    # Verify the token
    decoded_token = auth_handler.verify_token(token)

    # Extract user information
    user = {
        "id": decoded_token.get("sub"),  # User ID
        "email": decoded_token.get("email"),
        "role": decoded_token.get("role", "authenticated"),
        "app_metadata": decoded_token.get("app_metadata", {}),
        "user_metadata": decoded_token.get("user_metadata", {}),
        "aud": decoded_token.get("aud"),
        "exp": decoded_token.get("exp"),
    }
    return user


# Alternative: Get full user data from Supabase
async def get_current_user_full(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Get full user data from Supabase"""
    token = credentials.credentials

    # Verify token and get user data in one call
    user_data = auth_handler.verify_token(token)

    return user_data


@app.get("/tournaments", response_model=list[Tournaments])
async def list_tournaments(
    selection_filter: SelectionFilter = SelectionFilter.ACTIVE_ONLY,
    page_index: int = 0,
    count: int = 10,
    # current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List tournaments with filtering"""
    return db_api.list_tournaments(
        session=db,
        selection_filter=selection_filter,
        page_index=page_index,
        count=count
    )


@app.get("/tournaments/{tournament_id}", response_model=Tournaments)
async def get_tournament(
    tournament_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific tournament"""
    # Example: tournament = db.query(Tournaments)
    #   .filter(Tournaments.id == tournament_id).first()
    tournament = db.get(Tournaments, tournament_id)
    if tournament:
        return tournament
    raise HTTPException(status_code=404, detail="Tournament not found")


@app.get("/badges", response_model=list[Badges])
async def list_badges(
    user_badges_only: bool = False,
    page_index: int = 0,
    count: int = 10,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List badges, optionally filtered to user's badges only"""
    statement = select(Badges)

    if user_badges_only:
        # First get the user by sub_id to get the internal user id
        user = ensure_user_exists(db, current_user["id"])
        # Now join with UserBadges using the correct internal user id
        statement = statement.join(UserBadges).where(UserBadges.user_id == user.id)

    statement = statement.offset(page_index * count).limit(count)
    badges = db.exec(statement).all()
    return badges


@app.get("/badges/{badge_id}", response_model=Badges)
async def get_badge(
    badge_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific badge"""
    badge = db.get(Badges, badge_id)
    if badge:
        return badge
    raise HTTPException(status_code=404, detail="Badge not found")


@app.get("/challenges", response_model=list[Challenges])
async def list_challenges(
    tournament_id: int | None = None,
    page_index: int = 0,
    count: int = 10,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List challenges with filtering"""
    return db_api.list_challenges(
        session=db,
        tournament_id=tournament_id,
        page_index=page_index,
        count=count
    )

# start challenge route
@app.post("/challenges/{challenge_id}/start", response_model=UserChallengeContexts)
async def start_challenge(
    challenge_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a challenge for the current user"""
    # Get the internal user id from sub_id
    user: Users = ensure_user_exists(db, current_user["id"])

    # Ensure user.id is not None (should always be set after ensure_user_exists)
    if user.id is None:
        raise HTTPException(status_code=500, detail="User ID not found")

    challenge = db.get(Challenges, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    try:
        assert challenge.id is not None, "Challenge ID should not be None"
        db_api.start_challenge(db, user.id, challenge.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Route for submitting a message to a challenge agent
@app.post(
    "/challenges/{challenge_id}/add_message",
    response_model=ChallengeContextResponse,
)
async def add_message_to_challenge(
    challenge_id: int,
    message: str,
    role: Literal["user", "assistant", "system"] = "user",
    current_user: dict[str, Any] = Depends(get_current_user),
    solicit_llm_response: bool = True,
    db: Session = Depends(get_db),
):
    """Submit a message to the challenge agent"""
    try:
        user: Users = ensure_user_exists(db, current_user["id"])

        user_challenge_context_id: int = db_api.add_message_to_challenge(
            session=db,
            user_id=user.id,
            challenge_id=challenge_id,
            model=DEFAULT_CHAT_COMPLETION_MODEL,
            message=message,
            role=role,
        )
        context_messages: list[Message] = list(db_api.load_challenge_context_messages(
            session=db,
            user_challenge_context_id=user_challenge_context_id,
        ))
        logger.info(f"Number of context messages loaded: {len(context_messages)}")

        if solicit_llm_response:
            # XXXXXX TODO: add LLM contexts.
            # Optionally trigger LLM response generation
            # This could be an async task or direct call depending on your architecture
            challenge_tools: Optional[list[str]] = db_api.get_challenge_tools(
                session=db, challenge_id=challenge_id
            )
            chat_entry_list: list[ChatEntry] = []
            if challenge_tools:
                chat_entry_list.extend(await send_shim_request_with_tools(
                    message=message,
                    tools=challenge_tools,
                    context=context_messages,
                    role=role,
                ))
            else:
                chat_entry_list.append(
                    await send_shim_request(
                        message=message, role=role,
                        context=context_messages
                    )
                )
            add_chat_entries_to_challenge_no_checks(
                session=db,
                user_challenge_context_id=user_challenge_context_id,
                chat_entries=chat_entry_list,
            )
            return db_api.get_challenge_context_response(
                session=db,
                user_id=user.id,
                challenge_id=challenge_id,
            )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/challenges/{challenge_id}/evaluate", response_model=EvalResult)
async def evaluate_challenge_context(
    challenge_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate the challenge context"""
    user: Users = ensure_user_exists(db, current_user["id"])
    assert user.id is not None, "User ID should not be None"
    # Get the challenge context for the user
    try:
        return evaluation.evaluate_challenge_context(
            session=db,
            challenge_context_id=challenge_id,)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Challenge not found")


@app.post("/tournaments/{tournament_id}/join")
async def join_tournament(
    tournament_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Join a tournament"""

    user: Users = ensure_user_exists(db, current_user["id"])
    assert user.id is not None, "User ID should not be None"
    # Check if tournament exists and is active.
    try:
        db_api.join_tournament(
            db, user.id, tournament_id
        )
        return {"message": "Successfully joined tournament"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e.message))


# Route for getting user info
@app.get("/users/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user information"""
    return get_user_info(db, current_user["id"])


@app.get("/challenges/{challenge_id}/context", response_model=ChallengeContextResponse)
async def get_challenge_context(
    challenge_id: int,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get challenge context for current user"""
    # Get the internal user id from sub_id
    user = ensure_user_exists(db, current_user["id"])

    # Get the challenge context for the user
    try:
        return db_api.get_challenge_context_response(
            session=db,
            user_id=user.id,
            challenge_id=challenge_id,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Challenge not found")


# LLM endpoints
@app.post("/llm/chat/completions", response_model=ChatResponse)
async def create_chat_completion(
    request: ChatRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Create a chat completion using direct LiteLLM integration.

    This endpoint uses LiteLLM library to make direct calls to LLM providers
    without requiring a separate proxy server.
    """
    try:
        # Add user tracking for monitoring and billing
        if request.user is None:
            request.user = current_user["id"]

        client = LLMClient()
        response = await client.chat_completion(request)

        logger.info(f"Chat completion for user {current_user['id']}: {request.model}")
        return response

    except Exception as e:
        logger.error(f"Chat completion failed for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


@app.get("/llm/models", response_model=ModelsResponse)
async def list_available_models(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List available LLM models.

    Returns a list of all models that have their API keys configured
    and are ready to use.
    """
    try:
        client = LLMClient()
        response = await client.list_models()

        logger.info(f"Models list requested by user {current_user['id']}")
        return response

    except Exception as e:
        logger.error(f"Failed to list models for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@app.get("/llm/health", response_model=LLMHealthStatus)
async def check_llm_health(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Check the health status of the LLM service.

    Returns health information including available models and missing API keys.
    """
    try:
        client = LLMClient()
        health_status = await client.health_check()

        logger.info(f"LLM health check requested by user {current_user['id']}")
        return health_status

    except Exception as e:
        logger.error(f"LLM health check failed for user {current_user['id']}: {e}")
        raise HTTPException(
            status_code=500, detail=f"LLM health check failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "TrustBuilder Wargames AI Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health_check": "/health_check",
    }


@app.get("/health_check")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    logger.info(
        f"Starting server on {host}:{port} "
        f"({'development' if is_development_env else 'production'} mode)"
    )
    uvicorn.run(app, host=host, port=port)
