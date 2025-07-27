# Backend: Python/FastAPI implementation
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
from jwt import PyJWKClient
import os
from typing import Optional, Dict, Any, List
import httpx
from datetime import datetime, timezone
import logging
from enum import StrEnum

from sqlmodel import select, or_, and_
from sqlmodel import Session

from backend.db_api import get_user_info
from backend.database.models import (
    Tournaments, Users, Challenges, UserTournamentEnrollments,
    Badges, UserChallengeContexts, UserBadges
)
from backend.database.connection import get_db
from backend.models.supplemental import UserInfo

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
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "YOUR_JWT_SECRET")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "YOUR_SERVICE_KEY")

# JWT verification options
JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "authenticated"

class SupabaseAuth:
    """Handle Supabase JWT token verification"""
    
    def __init__(self):
        self.jwt_secret = SUPABASE_JWT_SECRET
        # For RS256 tokens (if using Supabase's default), use JWKS
        self.jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        self.jwks_client = PyJWKClient(self.jwks_url)
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token from Supabase"""
        try:
            # For HS256 tokens (if configured in Supabase)
            # decoded = jwt.decode(
            #     token,
            #     self.jwt_secret,
            #     algorithms=[JWT_ALGORITHM],
            #     audience=JWT_AUDIENCE
            # )
            
            # For RS256 tokens (Supabase default)
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=JWT_AUDIENCE,
                options={"verify_exp": True}
            )
            
            return decoded
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    async def get_user_from_token(self, token: str) -> Dict[str, Any]:
        """Get user data from Supabase using the token"""
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_SERVICE_KEY
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Could not fetch user data")
            
            return response.json()

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
    
    # Verify token first
    decoded_token = auth_handler.verify_token(token)
    
    # Fetch full user data from Supabase
    user_data = await auth_handler.get_user_from_token(token)
    
    return user_data


#### START STUBBED CODE

class SelectionFilter(StrEnum):
    PAST_ONLY = "PAST"
    ACTIVE_ONLY = "ACTIVE"
    FUTURE_ONLY = "FUTURE"
    PAST_AND_ACTIVE = "PAST_AND_ACTIVE"
    ACTIVE_AND_FUTURE = "ACTIVE_AND_FUTURE"


# Request/Response models
class CreateUserRequest(BaseModel):
    email: str
    password: Optional[str] = None


class TournamentResponse(BaseModel):
    id: int
    name: str
    start_date: datetime
    end_date: datetime
    description: Optional[str] = None


class BadgeResponse(BaseModel):
    id: int
    challenge_id: int


class ChallengeResponse(BaseModel):
    id: int
    name: str
    tournament_id: int
    description: Optional[str] = None


class UserBadgeResponse(BaseModel):
    id: int
    user_id: int
    badge_id: int
    awarded_at: datetime


class ChallengeContextResponse(BaseModel):
    id: int
    can_contribute: bool
    challenge_id: int
    started_at: datetime
    user_id: int
    letta_agent_id: Optional[int] = None
    succeeded_at: Optional[datetime] = None


@app.post("/users")
async def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db)
):
    """Create a new user"""
    # Implementation with session
    # Example: user = Users(sub_id=request.sub_id)
    # db.add(user)
    # db.commit()
    # db.refresh(user)
    return {"message": "User creation pending implementation"}


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
        statement = statement.join(UserBadges).where(UserBadges.user_id == current_user['id'])
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
@app.post("/challenges/{challenge_id}/start")
async def start_challenge(
    challenge_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a challenge for the current user"""
    # Example: context = UserChallengeContexts(user_id=current_user['id'], challenge_id=challenge_id, started_at=datetime.now(timezone.utc))
    # db.add(context)
    # db.commit()
    
    return {"message": "Challenge start pending implementation"}


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
    # Example: Check if user is already enrolled
    # existing_enrollment = db.query(UserTournamentEnrollments).filter_by(user_id=current_user['id'], tournament_id=tournament_id).first()
    # if existing_enrollment:
    #     return {"message": "User is already enrolled in this tournament"}
    enrollment: UserTournamentEnrollments = UserTournamentEnrollments(
        user_id=current_user['id'],
        tournament_id=tournament_id,
        enrolled_at=datetime.now(timezone.utc)
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return {"message": "Successfully joined tournament", "enrollment_id": enrollment.id}
    # Example: enrollment = UserTournamentEnrollments(user_id=current_user['id'], tournament_id=tournament_id)
    # db.add(enrollment)
    # db.commit()

    return {"message": "Tournament join pending implementation"}


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
    # Example: context = db.query(UserChallengeContexts).filter_by(user_id=current_user['id'], challenge_id=challenge_id).first()
    raise HTTPException(status_code=404, detail="Challenge context not found")


@app.get("/health_check")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
