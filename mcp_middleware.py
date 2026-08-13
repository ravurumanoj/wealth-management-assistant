from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from mcp_security import verify_mcp_token

# import logging

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# logger = logging.getLogger(__name__)

class MCPAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail":"Missing Authorization Header"}
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail":"Invalid Authorization Format"}
            )

        token = auth_header.replace("Bearer ", "")

        verify_mcp_token(token)

        response = await call_next(request)

        return response