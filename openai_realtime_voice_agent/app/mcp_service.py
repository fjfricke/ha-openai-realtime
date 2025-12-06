"""MCP service integration using Pipecat's MCPClient with StreamableHTTP."""
import logging
from typing import Optional
from pipecat.services.mcp_service import MCPClient, StreamableHttpParameters

logger = logging.getLogger(__name__)


class HomeAssistantMCPService:
    """Home Assistant MCP service using Pipecat's MCPClient."""
    
    def __init__(self, url: str, access_token: str):
        """
        Initialize Home Assistant MCP service.
        
        Args:
            url: Home Assistant MCP Server URL (e.g., http://supervisor/core/api/mcp)
            access_token: Long-lived access token for Home Assistant
        """
        self.url = url
        self.access_token = access_token
        self.mcp_client: Optional[MCPClient] = None
        
    async def initialize(self) -> MCPClient:
        """Initialize and return the MCP client."""
        try:
            logger.info(f"🔗 Initializing Home Assistant MCP Client at {self.url}")
            
            # Create StreamableHTTP parameters with authentication
            server_params = StreamableHttpParameters(
                url=self.url,
                headers={
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            # Create MCP client
            self.mcp_client = MCPClient(server_params=server_params)
            
            logger.info("✅ Home Assistant MCP Client initialized")
            return self.mcp_client
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Home Assistant MCP Client: {e}", exc_info=True)
            raise
    
    def get_client(self) -> Optional[MCPClient]:
        """Get the MCP client instance."""
        return self.mcp_client





