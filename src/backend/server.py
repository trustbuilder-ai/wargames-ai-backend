# Backend: Python/FastAPI implementation
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
from enum import StrEnum
import time

from sqlmodel import select, or_, and_
from sqlmodel import Session

from backend.db_api import get_user_info, ensure_user_exists
from backend.database.models import (
    Tournaments, Users, Challenges, UserTournamentEnrollments,
    Badges, UserChallengeContexts, UserBadges
)
from backend.database.connection import get_db
from backend.models.supplemental import LLMRole, Message, UserInfo, ChallengeContextResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
SUPABASE_URL = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "YOUR_SERVICE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

class SupabaseAuth:
    """Handle Supabase JWT token verification"""
    
    def __init__(self):
        self.supabase = supabase
        # Simple in-memory cache: token -> (user_data, expiry_timestamp)
        # PROS: 
        #   - Reduces API calls to Supabase during rapid requests (e.g., page loads with multiple API calls)
        #   - Simple implementation with no external dependencies
        #   - Fast lookups (O(1) dictionary access)
        # CONS:
        #   - No memory limits - could grow unbounded with many unique tokens
        #   - Not shared across worker processes (each process has its own cache)
        #   - Lost on server restart
        #   - No automatic cleanup of expired entries (only cleaned on access)
        # For production, consider Redis or memcached for distributed caching
        self.cache = {}
        self.ttl = 10  # 10 seconds TTL - balance between performance and freshness
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token from Supabase using the Supabase client"""
        try:
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
                "created_at": response.user.created_at
            }
            
            # Store in cache with expiry time
            self.cache[token] = (user_data, time.time() + self.ttl)
            
            return user_data
            
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise HTTPException(status_code=401, detail="Could not validate credentials")

# Initialize auth handler
auth_handler = SupabaseAuth()

# Dependency to get current user from JWT token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
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
        "exp": decoded_token.get("exp")
    }
    
    return user

# Alternative: Get full user data from Supabase
async def get_current_user_full(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get full user data from Supabase"""
    token = credentials.credentials
    
    # Verify token and get user data in one call
    user_data = auth_handler.verify_token(token)
    
    return user_data


#### START STUBBED CODE

class SelectionFilter(StrEnum):
    PAST_ONLY = "PAST"
    ACTIVE_ONLY = "ACTIVE"
    FUTURE_ONLY = "FUTURE"
    PAST_AND_ACTIVE = "PAST_AND_ACTIVE"
    ACTIVE_AND_FUTURE = "ACTIVE_AND_FUTURE"


@app.get("/tournaments", response_model=List[Tournaments])
async def list_tournaments(
    selection_filter: SelectionFilter = SelectionFilter.ACTIVE_ONLY,
    page_index: int = 0,
    count: int = 10,
    #current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List tournaments with filtering"""

    now = datetime.now(timezone.utc)
    
    # Start with base select statement
    statement = select(Tournaments)
    
    # Apply filters based on selection_filter
    if selection_filter == SelectionFilter.PAST_ONLY:
        statement = statement.where(Tournaments.end_date < now)
    elif selection_filter == SelectionFilter.ACTIVE_ONLY:
        statement = statement.where(
            Tournaments.start_date <= now,
            Tournaments.end_date >= now
        )
    elif selection_filter == SelectionFilter.FUTURE_ONLY:
        statement = statement.where(Tournaments.start_date > now)
    elif selection_filter == SelectionFilter.PAST_AND_ACTIVE:
        statement = statement.where(
            or_(
                Tournaments.end_date < now,
                and_(Tournaments.start_date <= now, Tournaments.end_date >= now)
            )
        )
    elif selection_filter == SelectionFilter.ACTIVE_AND_FUTURE:
        statement = statement.where(
            or_(
                and_(Tournaments.start_date <= now, Tournaments.end_date >= now),
                Tournaments.start_date > now
            )
        )
    
    # Apply pagination
    statement = statement.offset(page_index * count).limit(count)
    
    # Execute query
    tournaments = db.exec(statement).all()
    
    # Return directly - FastAPI will handle conversion
    return tournaments


@app.get("/tournaments/{tournament_id}", response_model=Tournaments)
async def get_tournament(
    tournament_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific tournament"""
    # Example: tournament = db.query(Tournaments).filter(Tournaments.id == tournament_id).first()
    tournament = db.get(Tournaments, tournament_id)
    if tournament:
        return tournament
    raise HTTPException(status_code=404, detail="Tournament not found")


@app.get("/badges", response_model=List[Badges])
async def list_badges(
    user_badges_only: bool = False,
    page_index: int = 0,
    count: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List badges, optionally filtered to user's badges only"""
    statement = select(Badges)
    
    if user_badges_only:
        # First get the user by sub_id to get the internal user id
        user = ensure_user_exists(db, current_user['id'])
        # Now join with UserBadges using the correct internal user id
        statement = statement.join(UserBadges).where(UserBadges.user_id == user.id)
    
    statement = statement.offset(page_index * count).limit(count)
    badges = db.exec(statement).all()
    return badges


@app.get("/badges/{badge_id}", response_model=Badges)
async def get_badge(
    badge_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific badge"""
    badge = db.get(Badges, badge_id)
    if badge:
        return badge
    raise HTTPException(status_code=404, detail="Badge not found")


@app.get("/challenges", response_model=List[Challenges])
async def list_challenges(
    tournament_id: Optional[int] = None,
    page_index: int = 0,
    count: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List challenges with filtering"""
    # Example: query = db.query(Challenges)
    # if tournament_id: query = query.filter(Challenges.tournament_id == tournament_id)
    statement = select(Challenges)
    if tournament_id:
        statement = statement.where(Challenges.tournament_id == tournament_id)
    statement = statement.offset(page_index * count).limit(count)
    challenges = db.exec(statement).all()
    return challenges



# start challenge route
@app.post("/challenges/{challenge_id}/start", response_model=UserChallengeContexts)
async def start_challenge(
    challenge_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a challenge for the current user"""
    # Get the internal user id from sub_id
    user = ensure_user_exists(db, current_user['id'])
    
    # Check if challenge exists
    challenge = db.get(Challenges, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # Check if user already has a context for this challenge
    existing_context = db.exec(
        select(UserChallengeContexts).where(
            and_(
                UserChallengeContexts.user_id == user.id,
                UserChallengeContexts.challenge_id == challenge_id
            )
        )
    ).first()
    
    if existing_context:
        raise HTTPException(status_code=400, detail="Challenge already started")
    
    # Create new challenge context
    context = UserChallengeContexts(
        user_id=user.id,
        challenge_id=challenge_id,
        started_at=datetime.now(timezone.utc),
        can_contribute=True
    )
    
    db.add(context)
    db.commit()
    db.refresh(context)
    
    return context


# Route for submitting a message to a challenge agent
@app.post("/challenges/{challenge_id}/submit_message", response_model=Optional[UserChallengeContexts])
async def submit_message_to_challenge(
    challenge_id: int,
    message: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a message to the challenge agent"""
    # Example: context = db.query(UserChallengeContexts).filter_by(user_id=current_user['id'], challenge_id=challenge_id).first()
    # if not context:
    #     raise HTTPException(status_code=404, detail="Challenge context not found")
    
    # Here you would integrate with the Letta agent to send the message
    # response = send_message_and_check_tools(context.letta_agent_id, message)

    return None


@app.post("/tournaments/{tournament_id}/join")
async def join_tournament(
    tournament_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Join a tournament"""

    enrollment: UserTournamentEnrollments = UserTournamentEnrollments(
        user_id=current_user['id'],
        tournament_id=tournament_id,
        enrolled_at=datetime.now(timezone.utc)
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return {"message": "Successfully joined tournament", "enrollment_id": enrollment.id}


# Route for getting user info
@app.get("/users/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    return get_user_info(db, current_user['id'])


# agent name: user_id_tournament_id_challenge_id

@app.get("/challenges/{challenge_id}/context", response_model=ChallengeContextResponse)
async def get_challenge_context(
    challenge_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get challenge context for current user"""
    # Get the internal user id from sub_id
    user = ensure_user_exists(db, current_user['id'])
    
    # Look up the user's challenge context
    context = db.exec(
        select(UserChallengeContexts).where(
            and_(
                UserChallengeContexts.user_id == user.id,
                UserChallengeContexts.challenge_id == challenge_id
            )
        )
    ).first()
    
    if not context:
        raise HTTPException(status_code=404, detail="Challenge not started yet")
    
    # Return the context with an empty messages list for now
    return ChallengeContextResponse(
        user_challenge_context=context,
        messages=[]
    )

# Get sample messages endpoint
@app.get("/sample_messages", response_model=List[Message])
def get_sample_messages(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get sample messages for testing purposes."""
    return [
        Message(role=LLMRole.SYSTEM, content="Sample system message"),
        Message(role=LLMRole.USER, content="Sample user message"),
        Message(role=LLMRole.ASSISTANT, content="Sample assistant response"),
        Message(role=LLMRole.ERROR, content="Sample error message"),
        Message(role=LLMRole.TOOL_CALL, content="Sample tool call message", tool_name="SampleTool"),
        Message(role=LLMRole.TOOL_RESULT, content="Sample tool result message", tool_name="SampleTool"),
        Message(role=LLMRole.MODEL, content="Sample model message"),
    ]


@app.get("/health_check")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
