"""Main application entry point."""
import os
import sys
import asyncio
import logging
from typing import Optional
from app.websocket_server import WebSocketServer
from app.home_assistant_mcp_client import initialize_home_assistant_client
import dotenv
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

dotenv.load_dotenv()


class Application:
    """Main application class."""
    
    def __init__(self):
        """Initialize application."""
        self.websocket_server: Optional[WebSocketServer] = None
        
    async def initialize(self) -> None:
        """Initialize all components."""
        # Get configuration from environment
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        websocket_port = int(os.environ.get("WEBSOCKET_PORT", "8080"))
        
        # Get turn detection settings with defaults
        vad_threshold = float(os.environ.get("VAD_THRESHOLD", "0.5"))
        vad_prefix_padding_ms = int(os.environ.get("VAD_PREFIX_PADDING_MS", "300"))
        vad_silence_duration_ms = int(os.environ.get("VAD_SILENCE_DURATION_MS", "500"))
        
        # Get instructions with default
        instructions = os.environ.get("INSTRUCTIONS", "You are the Home Assistant Voice Agent and can control the Smart Home.")
        
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Initialize Home Assistant MCP Client
        try:
            supervisor_token = os.environ.get("LONGLIVED_TOKEN") or os.environ.get("SUPERVISOR_TOKEN")
            logger.info(f"Supervisor token: {supervisor_token}")
            ha_mcp_url = os.environ.get("HA_MCP_URL", "http://supervisor/core/api/mcp")
            if supervisor_token:
                logger.info("Loading Home Assistant MCP tools...")
                await initialize_home_assistant_client(url=ha_mcp_url, access_token=supervisor_token)
                logger.info("✅ Home Assistant MCP Client initialized")
            else:
                logger.warning("⚠️ SUPERVISOR_TOKEN not set, skipping Home Assistant MCP integration")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Home Assistant MCP Client: {e}")
        
        # Start WebSocket Server (it will create OpenAI sessions per client)
        logger.info("Starting WebSocket Server...")
        self.websocket_server = WebSocketServer(
            websocket_port, 
            openai_api_key, 
            enable_recording=False,
            vad_threshold=vad_threshold,
            vad_prefix_padding_ms=vad_prefix_padding_ms,
            vad_silence_duration_ms=vad_silence_duration_ms,
            instructions=instructions
        )
        await self.websocket_server.start()
        
        logger.info("Application initialized successfully")
    
    async def run(self) -> None:
        """Run the application."""
        await self.initialize()
        
        # Keep the server running - wait for the server to be closed
        if self.websocket_server and self.websocket_server._server:
            await self.websocket_server._server.wait_closed()


async def main() -> None:
    """Main entry point."""
    app = Application()
    
    try:
        await app.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

