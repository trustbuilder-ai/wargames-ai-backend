"""Streaming utilities for LLM responses.

This module provides utilities for streaming LLM responses using Server-Sent Events (SSE)
format, compatible with OpenAI's streaming API format.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from backend.util.log import logger


async def format_sse_chunk(chunk: Any) -> str:
    """Format a streaming chunk as a Server-Sent Event.

    Args:
        chunk: A chunk from the LLM streaming response

    Returns:
        SSE-formatted string with the chunk data
    """
    try:
        # Convert chunk to dict if it's a litellm object
        if hasattr(chunk, "model_dump"):
            chunk_dict = chunk.model_dump()
        elif hasattr(chunk, "__dict__"):
            chunk_dict = chunk.__dict__
        else:
            chunk_dict = chunk

        # Format as SSE data event
        return f"data: {json.dumps(chunk_dict)}\n\n"
    except Exception as e:
        logger.error(f"Error formatting SSE chunk: {e}")
        error_chunk = {"error": {"message": str(e), "type": "formatting_error"}}
        return f"data: {json.dumps(error_chunk)}\n\n"


async def stream_completion_sse(
    stream_iterator: AsyncIterator[Any],
) -> AsyncIterator[str]:
    """Convert an async iterator of LLM chunks to SSE format.

    Args:
        stream_iterator: Async iterator from LiteLLM streaming response

    Yields:
        SSE-formatted strings for each chunk
    """
    try:
        async for chunk in stream_iterator:
            yield await format_sse_chunk(chunk)

        # Send the final [DONE] message (OpenAI convention)
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error in streaming completion: {e}")
        # Send error in SSE format
        error_chunk = {"error": {"message": str(e), "type": "stream_error"}}
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


def create_sse_headers() -> dict[str, str]:
    """Create headers for SSE streaming response.

    Returns:
        Dictionary of headers optimized for SSE streaming
    """
    return {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "X-Accel-Buffering": "no",  # Disable Nginx buffering
        "Connection": "keep-alive",
    }
