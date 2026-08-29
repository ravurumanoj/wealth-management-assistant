
from fastapi import APIRouter, HTTPException, status, Path
from fastapi.responses import StreamingResponse
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    SessionHistoryResponse,
    SessionInfo,
)
from app.schemas.client import (
    AddClientRequest,
    AddClientResponse,
    Client,
    ClientListResponse,
)
from app.schemas.common import AppInfoResponse, DeletedResponse, MessageResponse
from app.utils.logger import logger
from app.agents.orchestrator import process_chat, stream_agent
from app.services.memory import memory_service
from app.config import settings
from app.constants import (
    CLIENTS_DATA_FILE,
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENTS,
    DEMO_CLIENT_ID_PREFIX,
    DEMO_CLIENT_RM,
    DEMO_CLIENT_RISK_PROFILE,
    DEMO_CLIENT_SEGMENT,
    SSE_RESPONSE_HEADERS,
)
from typing import Annotated, List
from pathlib import Path as FilePath
import traceback
import json
import os

router = APIRouter(tags=["Agent"], prefix="/agent")

# Path-param session IDs are validated declaratively with the same rules as ChatRequest.
SessionIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique session identifier",
    ),
]

# ── App info endpoint (used by UI for dynamic header/badge values) ─────────────

@router.get(
    "/info",
    tags=["Agent"],
    summary="Return app name and model info for the UI.",
    response_model=AppInfoResponse,
)
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
    Streams the LangGraph agent pipeline as Server-Sent Events:
      - ``step``  events mark router/agent state transitions (running → done)
      - ``token`` events carry individual LLM output tokens for live rendering
      - ``done``  event carries the complete response and agent_used name
      - ``error`` event signals a pipeline failure

    The client should parse each ``data: <json>`` line and render progressively.
    """

    # Save user message to persistent memory before streaming
    client_id = (request.metadata or {}).get("client_id") or "unknown"
    memory_service.save_chat(request.session_id, request.message, "user", client_id=client_id)

    async def event_generator():
        full_response = ""
        agent_used = "unknown"
        try:
            async for event in stream_agent(
                request.message,
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
                        request.session_id, full_response, "assistant", client_id=client_id
                    )
                except Exception as mem_err:
                    logger.warning(f"Could not save assistant turn to memory: {mem_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=SSE_RESPONSE_HEADERS,
    )


# ── Non-streaming chat endpoint (kept for compatibility) ──────────────────────

_CLIENTS_FILE = str(FilePath(__file__).resolve().parent.parent.parent / CLIENTS_DATA_FILE)

# Default fallback — matches the 6 customers in data/crm.json and data/portfolio.json
_DEFAULT_CLIENTS = DEFAULT_CLIENTS


@router.get(
    "/clients",
    tags=["Agent"],
    summary="List available clients for the UI dropdown.",
    response_model=ClientListResponse,
)
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


@router.post(
    "/clients",
    tags=["Agent"],
    summary="Add a demo client to the client list.",
    response_model=AddClientResponse,
)
async def add_demo_client(req: AddClientRequest):
    """Append a custom demo client to clients.json and return the new entry."""
    try:
        path = os.path.abspath(_CLIENTS_FILE)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                clients = json.load(f)
            if not isinstance(clients, list):
                clients = []
        else:
            clients = list(_DEFAULT_CLIENTS)

        # Generate next DEMO-XXX id
        existing_demo = [c.get("id", "") for c in clients if str(c.get("id", "")).startswith(DEMO_CLIENT_ID_PREFIX)]
        nums = [int(x.split("-")[1]) for x in existing_demo if x.split("-")[1].isdigit()]
        next_num = max(nums, default=0) + 1
        new_id = f"{DEMO_CLIENT_ID_PREFIX}{next_num:03d}"

        new_client = {
            "id": new_id,
            "name": req.name.strip(),
            "segment": DEMO_CLIENT_SEGMENT,
            "risk_profile": DEMO_CLIENT_RISK_PROFILE,
            "relationship_manager": DEMO_CLIENT_RM,
            "is_custom": True,
            "portfolio_ids": [p.strip() for p in req.portfolio_ids if p.strip()],
        }
        clients.append(new_client)

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clients, f, indent=2)

        logger.info(f"Demo client added: {new_id} — {req.name}")
        return {"client": new_client}
    except Exception as e:
        logger.error(f"Error adding demo client: {e}")
        raise HTTPException(status_code=500, detail="Failed to add client.")


@router.delete(
    "/clients/{client_id}",
    tags=["Agent"],
    summary="Delete a demo client.",
    response_model=DeletedResponse,
)
async def delete_demo_client(client_id: str):
    """Remove a custom demo client from clients.json. Only is_custom clients can be deleted."""
    try:
        path = os.path.abspath(_CLIENTS_FILE)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Client not found.")
        with open(path, "r", encoding="utf-8") as f:
            clients = json.load(f)
        target = next((c for c in clients if c.get("id") == client_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found.")
        if not target.get("is_custom"):
            raise HTTPException(status_code=403, detail="Only custom clients can be deleted.")
        clients = [c for c in clients if c.get("id") != client_id]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clients, f, indent=2)
        logger.info(f"Demo client deleted: {client_id}")
        return {"deleted": client_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting client {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete client.")

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
    
    # Input validation (session ID format, message sanitization/non-empty) is
    # enforced by the ChatRequest model before this handler runs.
    try:
        # 1. Save user message to memory
        client_id = (request.metadata or {}).get("client_id") or "unknown"
        memory_service.save_chat(request.session_id, request.message, "user", client_id=client_id)

        # 2. Process via LangGraph Orchestrator
        result = await process_chat(
            message=request.message,
            session_id=request.session_id,
            metadata=request.metadata
        )
        
        # 3. Save assistant response to memory
        final_response = result.get("final_output", "No response generated.")
        memory_service.save_chat(
            request.session_id, final_response, "assistant", client_id=client_id
        )

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

@router.get(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=SessionHistoryResponse,
)
async def get_session_history(session_id: SessionIdPath):
    """
    Get complete chat history for a specific session.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        Session history with all messages
    
    Raises:
        HTTPException: 404 if session not found
    """
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

@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
)
async def delete_session(session_id: SessionIdPath):
    """
    Delete a specific session and its history.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        Confirmation message
    """
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


