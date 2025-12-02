"""Main application entry point."""
import os
import sys
import asyncio
import logging
import signal
from typing import Optional
from websocket_server import WebSocketServer
from home_assistant_mcp_client import initialize_home_assistant_client, get_home_assistant_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Application:
    """Main application class."""
    
    def __init__(self):
        """Initialize application."""
        self.websocket_server: Optional[WebSocketServer] = None
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self) -> None:
        """Initialize all components."""
        # Get configuration from environment
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        websocket_port = int(os.environ.get("WEBSOCKET_PORT", "8080"))
        
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Initialize Home Assistant MCP Client
        try:
            ha_access_token = os.environ.get("HA_ACCESS_TOKEN")
            ha_url = os.environ.get("HA_MCP_URL", "http://supervisor/core/api/mcp")
            
            if ha_access_token:
                logger.info("Loading Home Assistant MCP tools...")
                await initialize_home_assistant_client(url=ha_url, access_token=ha_access_token)
                logger.info("✅ Home Assistant MCP Client initialized")
            else:
                logger.warning("⚠️ HA_ACCESS_TOKEN not set, skipping Home Assistant MCP integration")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Home Assistant MCP Client: {e}")
        
        # Start WebSocket Server (it will create OpenAI sessions per client)
        logger.info("Starting WebSocket Server...")
        self.websocket_server = WebSocketServer(websocket_port, openai_api_key, True)
        await self.websocket_server.start()
        
        logger.info("Application initialized successfully")
    
    async def shutdown(self) -> None:
        """Shutdown all components."""
        logger.info("Shutting down application...")
        
        if self.websocket_server:
            try:
                await self.websocket_server.stop()
            except Exception as e:
                logger.error(f"Error stopping WebSocket server: {e}")
        
        # Disconnect from Home Assistant MCP Server
        ha_client = get_home_assistant_client()
        if ha_client:
            try:
                logger.info("Disconnecting from Home Assistant MCP Server...")
                await ha_client.disconnect()
                logger.info("✅ Disconnected from Home Assistant MCP Server")
            except Exception as e:
                logger.error(f"Error disconnecting Home Assistant MCP Client: {e}")
        
        logger.info("Application shutdown complete")
    
    async def run(self) -> None:
        """Run the application."""
        try:
            await self.initialize()
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
        finally:
            await self.shutdown()


def setup_signal_handlers(app: Application) -> None:
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        app._shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main() -> None:
    """Main entry point."""
    app = Application()
    setup_signal_handlers(app)
    
    try:
        await app.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

