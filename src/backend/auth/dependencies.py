"""Authentication dependencies for FastAPI endpoints.

This module provides authentication and authorization utilities using Supabase JWT tokens.
It includes token verification, user extraction, and caching mechanisms for performance.
"""

import os
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from backend.util.log import logger

# Security scheme for JWT bearer tokens
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


class SupabaseAuth:
    """Handle Supabase JWT token verification with caching for performance.

    This class provides JWT token verification using the Supabase client,
    with an in-memory cache to reduce API calls during rapid requests.

    Attributes:
        supabase: The Supabase client instance for token verification
        cache: In-memory token cache mapping tokens to (user_data, expiry_timestamp)
        ttl: Time-to-live in seconds for cached tokens (default: 10 seconds)

    Cache Design Rationale:
        PROS:
        - Reduces API calls to Supabase during rapid requests (e.g., page loads)
        - Simple implementation with no external dependencies
        - Fast lookups with O(1) dictionary access

        CONS:
        - No memory limits (could grow unbounded with many unique tokens)
        - Not shared across worker processes (each process has its own cache)
        - Lost on server restart
        - No automatic cleanup of expired entries (only cleaned on access)

    Note: For production deployments, consider using Redis or memcached for
    distributed caching across multiple workers.
    """

    def __init__(self):
        """Initialize the SupabaseAuth handler with caching."""
        self.supabase = supabase
        self.cache: dict[str, tuple[dict[str, Any], float]] = {}
        self.ttl = 10  # 10 seconds TTL - balance between performance and freshness

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify JWT token from Supabase using the Supabase client.

        Args:
            token: The JWT token string to verify

        Returns:
            dict: User data dictionary containing:
                - sub: User ID (UUID)
                - email: User email address
                - role: User role (e.g., "authenticated")
                - app_metadata: Application-specific metadata
                - user_metadata: User-specific metadata
                - aud: Audience claim
                - created_at: User creation timestamp

        Raises:
            HTTPException: 401 if token is invalid or verification fails
        """
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


# Initialize auth handler as a singleton
auth_handler = SupabaseAuth()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Extract and verify user from JWT token.

    This is the primary dependency for protecting API endpoints. It verifies
    the JWT token and returns user information.

    Args:
        credentials: HTTP Bearer token credentials from the request header

    Returns:
        dict: User information dictionary containing:
            - id: User ID (UUID)
            - email: User email address
            - role: User role
            - app_metadata: Application metadata
            - user_metadata: User metadata
            - aud: Audience claim
            - exp: Token expiration (if available)

    Raises:
        HTTPException: 401 if token is missing or invalid

    Example:
        ```python
        @app.get("/protected")
        async def protected_route(
            current_user: dict[str, Any] = Depends(get_current_user),
        ):
            return {"user_id": current_user["id"]}
        ```
    """
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


async def get_current_user_full(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Get full user data from Supabase.

    Alternative dependency that returns the complete user data from token verification.
    Use this when you need all available user information.

    Args:
        credentials: HTTP Bearer token credentials from the request header

    Returns:
        dict: Complete user data from token verification

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    token = credentials.credentials

    # Verify token and get user data in one call
    user_data = auth_handler.verify_token(token)

    return user_data
