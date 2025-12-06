"""WebRTC service using Pipecat's SmallWebRTCTransport."""
import logging
from typing import Optional, TYPE_CHECKING

from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection, IceServer
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCRequestHandler,
    SmallWebRTCRequest,
    SmallWebRTCPatchRequest,
    ConnectionMode
)
from pipecat.transports.base_transport import TransportParams

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class WebRTCService:
    """Service for managing WebRTC connections using SmallWebRTCTransport."""
    
    def __init__(
        self,
        ice_servers: Optional[list[IceServer]] = None,
        esp32_mode: bool = False,
        host: Optional[str] = None,
        connection_mode: ConnectionMode = ConnectionMode.SINGLE
    ):
        """
        Initialize WebRTC service.
        
        Args:
            ice_servers: Optional list of ICE servers for NAT traversal
            esp32_mode: Enable ESP32-specific SDP munging
            host: Host address for SDP munging in ESP32 mode
            connection_mode: Connection mode (SINGLE or MULTIPLE)
        """
        self.ice_servers = ice_servers
        self.esp32_mode = esp32_mode
        self.host = host
        self.connection_mode = connection_mode
        
        # Create request handler
        self.request_handler = SmallWebRTCRequestHandler(
            ice_servers=ice_servers,
            esp32_mode=esp32_mode,
            host=host,
            connection_mode=connection_mode
        )
        
        # Transport will be created per connection
        self.transport: Optional[SmallWebRTCTransport] = None
        self.transport_params = TransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=24000,
            audio_in_channels=1,
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            audio_out_channels=1
        )
        
        logger.info("✅ WebRTCService initialized")
    
    async def handle_webrtc_request(
        self,
        request: SmallWebRTCRequest,
        connection_callback
    ) -> dict:
        """
        Handle incoming WebRTC request and create transport.
        
        Args:
            request: WebRTC request with SDP offer
            connection_callback: Async callback to handle new connections (receives transport and client_ip)
            
        Returns:
            Response dictionary with SDP answer
        """
        async def webrtc_connection_callback(connection: SmallWebRTCConnection):
            """Create transport for new WebRTC connection."""
            logger.info(f"🔗 New WebRTC connection: pc_id={connection.pc_id}")
            
            # Create transport for this connection
            self.transport = SmallWebRTCTransport(
                webrtc_connection=connection,
                params=self.transport_params
            )
            
            # Call the provided callback with the transport
            # Note: client_ip should be passed from the caller
            await connection_callback(self.transport)
        
        # Handle the WebRTC request - it returns the answer dict
        answer = await self.request_handler.handle_web_request(
            request,
            webrtc_connection_callback
        )
        
        return answer
    
    async def handle_ice_candidates(
        self,
        patch_request: SmallWebRTCPatchRequest
    ) -> None:
        """
        Handle ICE candidate patches.
        
        Args:
            patch_request: ICE candidate patch request
        """
        await self.request_handler.handle_patch_request(patch_request)
    
    def get_transport(self) -> Optional[SmallWebRTCTransport]:
        """Get the current WebRTC transport."""
        return self.transport
    
    def register_fastapi_routes(self, app: "FastAPI", base_path: str = "/webrtc"):
        """
        Register FastAPI routes for WebRTC signaling.
        
        Note: The /offer route should be registered separately with a connection callback.
        This method only registers the /ice route.
        
        Args:
            app: FastAPI application instance
            base_path: Base path for WebRTC endpoints
        """
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse
        
        @app.patch(f"{base_path}/offer")
        async def handle_ice(patch_request: dict):
            """Handle ICE candidate patches (PATCH on same endpoint as offer, matching Pipecat example)."""
            try:
                patch = SmallWebRTCPatchRequest(**patch_request)
                await self.handle_ice_candidates(patch)
                return JSONResponse(content={"status": "success"})
            except Exception as e:
                logger.error(f"❌ Error handling ICE candidates: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        logger.info(f"✅ Registered FastAPI route at PATCH {base_path}/offer (for ICE candidates)")

