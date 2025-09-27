# Backend: Python/FastAPI implementation

"""Main FastAPI application server.

This module initializes the FastAPI application, configures middleware,
and includes all route modules. It serves as the entry point for the
TrustBuilder Wargames AI Backend API.

The application is structured using modular routers for better organization:
- chat_templates: Chat template and context management
- llm: Language model interactions
- badges: User achievements and rewards
- users: User profile management
- health: Health checks and API information
"""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth.dependencies import is_development_env
from backend.routers import badges, chat_templates, health, llm, users
from backend.util.log import logger

# Initialize FastAPI application
app = FastAPI(
    title="TrustBuilder Wargames AI Backend",
    description="Backend API for TrustBuilder Wargames platform with AI agent integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local frontend development
        "https://trustbuilder-ai.github.io",  # GitHub Pages Frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers from different modules
# Order matters: more specific routes should come before generic ones

# Health and root endpoints (no prefix)
app.include_router(health.router)

# Feature-specific routers with their prefixes
app.include_router(chat_templates.router)  # Handles /chat_templates/* and related
app.include_router(llm.router)  # Handles /llm/*
app.include_router(badges.router)  # Handles /badges/*
app.include_router(users.router)  # Handles /users/*

# Server configuration
port = int(os.getenv("PORT", 8080))
host = "127.0.0.1" if is_development_env else "0.0.0.0"


@app.on_event("startup")
async def startup_event():
    """Execute startup tasks.

    This function runs when the FastAPI application starts up.
    It logs the server configuration and performs any necessary
    initialization tasks.
    """
    mode = "development" if is_development_env else "production"
    logger.info(f"Starting TrustBuilder Wargames AI Backend in {mode} mode")
    logger.info(f"Server configured for {host}:{port}")
    logger.info(f"API documentation available at http://{host}:{port}/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Execute shutdown tasks.

    This function runs when the FastAPI application shuts down.
    It performs cleanup tasks and logs the shutdown event.
    """
    logger.info("Shutting down TrustBuilder Wargames AI Backend")


# Run the application with uvicorn
if __name__ == "__main__":
    logger.info(
        f"Starting server on {host}:{port} "
        f"({'development' if is_development_env else 'production'} mode)"
    )
    uvicorn.run(app, host=host, port=port)