from mcp_security import create_access_token

mcp_client_id = str(input("Please enter your MCP Client ID: ")).strip()
mcp_client_secret = str(input("Please enter your MCP Client Secret: ")).strip()

token = create_access_token(username=mcp_client_id, secret=mcp_client_secret)

print(token)