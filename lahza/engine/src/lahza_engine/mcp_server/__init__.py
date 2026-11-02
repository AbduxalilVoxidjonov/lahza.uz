"""`lahza mcp` - Claude (Code/Desktop) uchun stdio MCP server.

Server engine ichida ishlamaydi: tirik engine'ni discovery fayli (`engine.json`) orqali topib,
token bilan 127.0.0.1 HTTP API'ga murojaat qiladi. Batafsil: docs/15b-mcp-server.md.
"""

from lahza_engine.mcp_server.protocol import MCPServer, serve, serve_stdio
from lahza_engine.mcp_server.tools import LahzaTools

__all__ = ["LahzaTools", "MCPServer", "serve", "serve_stdio"]
