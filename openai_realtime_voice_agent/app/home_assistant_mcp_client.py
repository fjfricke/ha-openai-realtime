"""Home Assistant MCP Client using StreamableHTTP transport."""
import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class HomeAssistantMCPClient:
    """Client for Home Assistant MCP Server using StreamableHTTP transport."""
    
    def __init__(self, url: str, access_token: str):
        """
        Initialize Home Assistant MCP Client.
        
        Args:
            url: Home Assistant MCP Server URL (e.g., https://home.felixfricke.de/api/mcp)
            access_token: Long-lived access token for Home Assistant
        """
        self.url = url
        self.access_token = access_token
        self.session: Optional[ClientSession] = None
        self.tools: List[Any] = []
        self._connected = False
        self._transport_context = None
        self._receive_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """Connect to Home Assistant MCP Server."""
        try:
            logger.info(f"🔗 Connecting to Home Assistant MCP Server at {self.url}")
            
            # Create headers with authentication
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            # Create StreamableHTTP transport context manager
            self._transport_context = streamablehttp_client(
                url=self.url,
                headers=headers,
                timeout=30.0,
                sse_read_timeout=300.0
            )
            
            # Enter the context to get streams
            read_stream, write_stream, get_session_id = await self._transport_context.__aenter__()
            
            # Create session
            self.session = ClientSession(read_stream, write_stream)
            
            # Start _receive_loop() manually in a task
            self._receive_task = asyncio.create_task(self.session._receive_loop())
            
            # Initialize the session
            await self.session.initialize()
            
            # List available tools
            tools_result = await self.session.list_tools()
            self.tools = tools_result.tools if tools_result.tools else []
            
            self._connected = True
            logger.info(f"✅ Connected to Home Assistant MCP Server ({len(self.tools)} tools available)")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Home Assistant MCP Server: {e}", exc_info=True)
            self._connected = False
            if self._receive_task:
                try:
                    self._receive_task.cancel()
                    await self._receive_task
                except Exception:
                    pass
                self._receive_task = None
            if self._transport_context:
                try:
                    await self._transport_context.__aexit__(type(e), e, None)
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Error during cleanup: {cleanup_error}")
                self._transport_context = None
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Home Assistant MCP Server."""
        self._connected = False
        
        if self._receive_task:
            try:
                self._receive_task.cancel()
                await self._receive_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"⚠️ Error cancelling receive task: {e}")
            finally:
                self._receive_task = None
        
        if self._transport_context:
            try:
                await self._transport_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"⚠️ Error closing transport: {e}")
            finally:
                self._transport_context = None
        
        self.session = None
        logger.info("🔌 Disconnected from Home Assistant MCP Server")
    
    def get_tools_for_openai(self) -> List[Dict[str, Any]]:
        """
        Get all tools in OpenAI Realtime API format.
        
        Returns:
            List of tool definitions for OpenAI
        """
        openai_tools = []
        
        for tool in self.tools:
            # Extract tool information
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            tool_description = tool.description if hasattr(tool, 'description') else ""
            tool_input_schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
            
            # Convert input schema to OpenAI format
            openai_parameters = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            if isinstance(tool_input_schema, dict):
                properties = tool_input_schema.get('properties', {})
                required = tool_input_schema.get('required', [])
                
                openai_parameters['properties'] = properties
                openai_parameters['required'] = required
            
            openai_tool = {
                "type": "function",
                "name": tool_name,
                "description": tool_description,
                "parameters": openai_parameters
            }
            
            openai_tools.append(openai_tool)
        
        return openai_tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on Home Assistant MCP Server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        if not self._connected or not self.session:
            raise Exception("Home Assistant MCP Server is not connected")
        
        try:
            logger.info(f"🔧 Calling tool {tool_name} on Home Assistant MCP Server")
            result = await self.session.call_tool(tool_name, arguments)
            
            # Convert result to dict format
            if hasattr(result, 'content'):
                # Extract text content from result
                content_text = []
                for item in result.content:
                    if hasattr(item, 'text'):
                        content_text.append(item.text)
                    elif isinstance(item, str):
                        content_text.append(item)
                    elif isinstance(item, dict) and 'text' in item:
                        content_text.append(item['text'])
                
                return {
                    "success": True,
                    "content": "\n".join(content_text) if content_text else "",
                    "isError": result.isError if hasattr(result, 'isError') else False
                }
            else:
                return {
                    "success": True,
                    "content": str(result),
                    "isError": False
                }
        except Exception as e:
            logger.error(f"❌ Error calling tool {tool_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "isError": True
            }
    
    def is_connected(self) -> bool:
        """Check if server is connected."""
        return self._connected


# Global instance (will be initialized in main.py)
_home_assistant_client: Optional[HomeAssistantMCPClient] = None


async def initialize_home_assistant_client(url: Optional[str] = None, access_token: Optional[str] = None) -> HomeAssistantMCPClient:
    """
    Initialize and connect to Home Assistant MCP Server.
    
    Args:
        url: Home Assistant MCP Server URL (defaults to env var or config)
        access_token: Access token (defaults to env var)
        
    Returns:
        Connected HomeAssistantMCPClient instance
    """
    global _home_assistant_client
    
    if url is None:
        url = os.getenv('HA_MCP_URL', 'https://home.felixfricke.de/api/mcp')
    
    if access_token is None:
        access_token = os.getenv('HA_ACCESS_TOKEN')
        if not access_token:
            raise ValueError("HA_ACCESS_TOKEN environment variable is required")
    
    _home_assistant_client = HomeAssistantMCPClient(url, access_token)
    await _home_assistant_client.connect()
    
    return _home_assistant_client


def get_home_assistant_client() -> Optional[HomeAssistantMCPClient]:
    """Get the global Home Assistant MCP Client instance."""
    return _home_assistant_client
