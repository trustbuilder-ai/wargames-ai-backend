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
from datetime import datetime
import logging
from enum import StrEnum

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

from backend.models.models import (
    Tournaments, Users, Challenges, UserTournamentEnrollments,
    Badges, UserChallengeContexts, UserBadges
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
async def create_user(request: CreateUserRequest):
    """Create a new user"""
    # NEEDS SQLALCHEMY GLUE
    return {"message": "User creation pending implementation"}


@app.get("/tournaments", response_model=List[TournamentResponse])
async def list_tournaments(
    selection_filter: SelectionFilter,
    page_index: int = 0,
    count: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List tournaments with filtering"""
    # NEEDS SQLALCHEMY GLUE
    return []


@app.get("/tournaments/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(
    tournament_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific tournament"""
    # NEEDS SQLALCHEMY GLUE
    raise HTTPException(status_code=404, detail="Tournament not found")


@app.get("/badges", response_model=List[BadgeResponse])
async def list_badges(
    user_badges_only: bool = False,
    page_index: int = 0,
    count: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List badges, optionally filtered to user's badges only"""
    # NEEDS SQLALCHEMY GLUE
    return []


@app.get("/badges/{badge_id}", response_model=BadgeResponse)
async def get_badge(
    badge_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get a specific badge"""
    # NEEDS SQLALCHEMY GLUE
    raise HTTPException(status_code=404, detail="Badge not found")


@app.get("/challenges", response_model=List[ChallengeResponse])
async def list_challenges(
    selection_filter: SelectionFilter,
    tournament_id: Optional[int] = None,
    page_index: int = 0,
    count: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List challenges with filtering"""
    # NEEDS SQLALCHEMY GLUE
    return []


@app.get("/users/me/badges", response_model=List[UserBadgeResponse])
async def list_user_badges(
    page_index: int = 0,
    count: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List current user's badges"""
    # NEEDS SQLALCHEMY GLUE
    return []


@app.post("/tournaments/{tournament_id}/join")
async def join_tournament(
    tournament_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Join a tournament"""
    # NEEDS SQLALCHEMY GLUE
    return {"message": "Tournament join pending implementation"}


@app.get("/challenges/{challenge_id}/context", response_model=ChallengeContextResponse)
async def get_challenge_context(
    challenge_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get challenge context for current user"""
    # NEEDS SQLALCHEMY GLUE
    raise HTTPException(status_code=404, detail="Challenge context not found")

#### END STUBBED CODE


@app.get("/health_check")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
