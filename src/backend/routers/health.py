"""Health and root routes for API status and information.

This module provides API endpoints for:
- Root endpoint with API information
- Health check for monitoring and load balancer checks
"""

from fastapi import APIRouter

# Create router without prefix for root-level endpoints
router = APIRouter(
    tags=["health"],
)


@router.get("/")
async def root():
    """Root endpoint - API information.

    Provides basic information about the API including version,
    documentation links, and available endpoints.

    Returns:
        dict: API information containing:
            - message: API description
            - version: Current API version
            - docs: Link to interactive API documentation
            - health_check: Health check endpoint path

    Example:
        ```python
        GET /
        Response:
        {
            "message": "TrustBuilder Wargames AI Backend API",
            "version": "1.0.0",
            "docs": "/docs",
            "health_check": "/health_check"
        }
        ```

    Note:
        This endpoint is publicly accessible without authentication,
        making it useful for API discovery and initial integration testing.
    """
    return {
        "message": "TrustBuilder Wargames AI Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health_check": "/health_check",
    }


@router.get("/health_check")
async def health_check():
    """Health check endpoint for monitoring and load balancers.

    Simple endpoint that returns a success status to indicate the
    service is running and responsive. Used by:
    - Kubernetes liveness and readiness probes
    - Load balancer health checks
    - Monitoring systems (Datadog, New Relic, etc.)
    - Docker health checks

    Returns:
        dict: Health status with "ok" status

    Example:
        ```python
        GET /health_check
        Response:
        {
            "status": "ok"
        }
        ```

    Note:
        This endpoint is intentionally simple and doesn't check
        dependencies (database, external services) to ensure it
        remains fast and reliable. For comprehensive health checks
        including dependencies, use the /llm/health endpoint for
        LLM services or implement a separate /health/detailed endpoint.
    """
    return {"status": "ok"}
