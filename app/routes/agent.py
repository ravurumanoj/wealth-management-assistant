
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from app.schemas.agent import ChatRequest, ChatResponse, SessionInfo
from app.utils.logger import logger
from app.agents.orchestrator import process_chat, stream_agent
from app.services.memory import memory_service
from app.utils.helpers import validate_session_id, sanitize_input
from app.config import settings
from typing import List
import traceback
import json
import os

router = APIRouter(tags=["Agent"], prefix="/agent")

# ── App info endpoint (used by UI for dynamic header/badge values) ─────────────

@router.get("/info", tags=["Agent"], summary="Return app name and model info for the UI.")
async def app_info():
    """Return dynamic configuration values shown in the chat UI header."""
    return {
        "app_name": settings.APP_NAME,
        "model": settings.GEMINI_MODEL,
        "version": settings.VERSION,
    }

# ── Streaming chat endpoint (SSE) ─────────────────────────────────────────────

@router.post(
    "/stream",
    summary="Stream the agent response via Server-Sent Events.",
    response_description="text/event-stream — step, token, done, and error events",
)
async def stream_chat(request: ChatRequest):
    """
    POST /api/v1/agent/stream

    Streams the LangGraph agent pipeline as Server-Sent Events:
      - ``step``  events mark router/agent state transitions (running → done)
      - ``token`` events carry individual LLM output tokens for live rendering
      - ``done``  event carries the complete response and agent_used name
      - ``error`` event signals a pipeline failure

    The client should parse each ``data: <json>`` line and render progressively.
    """
    # Validate inputs eagerly before opening the stream
    if not validate_session_id(request.session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format.",
        )
    sanitized_message = sanitize_input(request.message)
    if not sanitized_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    # Save user message to persistent memory before streaming
    memory_service.save_chat(request.session_id, sanitized_message, "user")

    async def event_generator():
        full_response = ""
        agent_used = "unknown"
        try:
            async for event in stream_agent(
                sanitized_message,
                request.session_id,
                request.metadata,
            ):
                if event.get("type") == "token":
                    full_response += event.get("content", "")
                if event.get("type") == "done":
                    agent_used = event.get("agent_used", "unknown")
                    full_response = event.get("full_response", full_response)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # Persist the assistant turn once streaming completes
            if full_response:
                try:
                    memory_service.save_chat(
                        request.session_id, full_response, "assistant"
                    )
                except Exception as mem_err:
                    logger.warning(f"Could not save assistant turn to memory: {mem_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx proxy buffering
            "Connection": "keep-alive",
        },
    )


# ── Non-streaming chat endpoint (kept for compatibility) ──────────────────────

_CLIENTS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "portfolio", "clients.json"
)

# Default sample clients shown when the JSON file is empty or missing
_DEFAULT_CLIENTS = [
    {"id": "C001", "name": "Arjun Mehta"},
    {"id": "C002", "name": "Priya Sharma"},
    {"id": "C003", "name": "Vikram Nair"},
    {"id": "C004", "name": "Anjali Reddy"},
    {"id": "C005", "name": "Rohit Kapoor"},
]


@router.get("/clients", tags=["Agent"], summary="List available clients for the UI dropdown.")
async def list_clients():
    """Return the client list used by the UI sidebar dropdown."""
    try:
        path = os.path.abspath(_CLIENTS_FILE)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Support both list and dict-of-clients formats
            clients = data if isinstance(data, list) else data.get("clients", [])
            if clients:
                return {"clients": clients}
        # Fall back to defaults when file is empty/missing
        return {"clients": _DEFAULT_CLIENTS}
    except Exception as e:
        logger.error(f"Error loading clients: {e}")
        return {"clients": _DEFAULT_CLIENTS}

# ── Non-streaming chat endpoint (kept for compatibility) ──────────────────────

@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_with_agent(request: ChatRequest):
    """
    Endpoint to interact with the Wealth Management Assistant.
    Routes user queries to the appropriate agent via LangGraph orchestrator.
    
    Args:
        request: ChatRequest with message, session_id, and optional metadata
    
    Returns:
        ChatResponse with agent's response and session information
    
    Raises:
        HTTPException: 400 for invalid input, 500 for server errors
    """
    logger.info(f"Received chat request for session: {request.session_id}")
    
    # Validate session ID
    if not validate_session_id(request.session_id):
        logger.warning(f"Invalid session ID format: {request.session_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format. Use alphanumeric characters, hyphens, or underscores."
        )
    
    # Sanitize user input
    sanitized_message = sanitize_input(request.message)
    if not sanitized_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty"
        )
    
    try:
        # 1. Save user message to memory
        memory_service.save_chat(request.session_id, sanitized_message, "user")

        # 2. Process via LangGraph Orchestrator
        result = await process_chat(
            message=sanitized_message,
            session_id=request.session_id,
            metadata=request.metadata
        )
        
        # 3. Save assistant response to memory
        final_response = result.get("final_output", "No response generated.")
        memory_service.save_chat(request.session_id, final_response, "assistant")

        return ChatResponse(
            session_id=request.session_id,
            response=final_response,
            agent_used=result.get("next_agent", "orchestrator")
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        logger.debug(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your request. Please try again."
        )

@router.get("/sessions", response_model=List[SessionInfo], status_code=status.HTTP_200_OK)
async def get_sessions():
    """
    List all active/stored chat sessions.
    
    Returns:
        List of SessionInfo objects with session metadata
    """
    try:
        sessions = memory_service.list_sessions()
        logger.info(f"Retrieved {len(sessions)} sessions")
        return sessions
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        logger.debug(traceback.format_exc())
        return []

@router.get("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def get_session_history(session_id: str):
    """
    Get complete chat history for a specific session.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        Session history with all messages
    
    Raises:
        HTTPException: 404 if session not found
    """
    if not validate_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    
    try:
        history = memory_service.get_history(session_id)
        if not history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found"
            )
        
        logger.info(f"Retrieved history for session {session_id}: {len(history)} messages")
        return {"session_id": session_id, "history": history}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session history: {e}")
        logger.debug(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving session history"
        )

@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session(session_id: str):
    """
    Delete a specific session and its history.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        Confirmation message
    """
    if not validate_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    
    try:
        result = memory_service.delete_session(session_id)
        if result:
            logger.info(f"Deleted session: {session_id}")
            return {"message": f"Session '{session_id}' deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        logger.debug(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting session"
        )


