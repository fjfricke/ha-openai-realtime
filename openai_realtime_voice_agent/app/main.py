"""Main application entry point using Pipecat."""
import os
import sys
import asyncio
import logging
from typing import Optional
import dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, InputAudioRawFrame, OutputAudioRawFrame, StartFrame, EndFrame

from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import IceServer
from pipecat.transports.smallwebrtc.request_handler import ConnectionMode
from app.mcp_service import HomeAssistantMCPService
from app.disconnect_tool import get_disconnect_tool_definition, create_disconnect_tool_handler
from app.audio_recording_service import AudioRecordingService
from app.webrtc_service import WebRTCService
from app.session_manager import SessionManager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce verbosity of noisy loggers
logging.getLogger("aiortc").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("__main__").setLevel(logging.INFO)  # Reduce SessionActivityTracker debug logs

dotenv.load_dotenv()


class SessionActivityTracker(FrameProcessor):
    """Processor that tracks session activity by monitoring audio frames."""
    
    def __init__(self, activity_callback, **kwargs):
        super().__init__(**kwargs)
        self.activity_callback = activity_callback
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Log all frame types for debugging
        if isinstance(frame, StartFrame):
            logger.debug("🎬 SessionActivityTracker: Received StartFrame")
            # Let parent handle StartFrame lifecycle first
            await super().process_frame(frame, direction)
            # Then push the frame through
            await self.push_frame(frame, direction)
            return
        elif isinstance(frame, EndFrame):
            logger.debug("🏁 SessionActivityTracker: Received EndFrame")
            # Push EndFrame through
            await self.push_frame(frame, direction)
            return
        
        # Track activity on any audio frame
        if isinstance(frame, (InputAudioRawFrame, OutputAudioRawFrame)):
            if self.activity_callback:
                self.activity_callback()
            logger.debug(f"🎵 SessionActivityTracker: Processing {type(frame).__name__} ({len(frame.audio)} bytes)")
        
        # Pass frame through to next processor
        await self.push_frame(frame, direction)


class Application:
    """Main application class using Pipecat."""
    
    def __init__(self):
        """Initialize application."""
        self.pipeline: Optional[Pipeline] = None
        self.runner: Optional[PipelineRunner] = None
        self.webrtc_service: Optional[WebRTCService] = None
        self.webrtc_transport: Optional[SmallWebRTCTransport] = None
        self.openai_service: Optional[OpenAIRealtimeLLMService] = None
        self.mcp_service: Optional[HomeAssistantMCPService] = None
        self.audio_recording_service: Optional[AudioRecordingService] = None
        self.session_manager: Optional[SessionManager] = None
        self.current_task: Optional[PipelineTask] = None
        self._pipeline_lock: Optional[asyncio.Lock] = None
        self.fastapi_app: Optional[FastAPI] = None
        
    async def initialize(self) -> None:
        """Initialize all components."""
        # Get configuration from environment
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        webrtc_port = int(os.environ.get("WEBRTC_PORT", "8080"))
        
        # Get turn detection settings with defaults
        vad_threshold = float(os.environ.get("VAD_THRESHOLD", "0.5"))
        vad_prefix_padding_ms = int(os.environ.get("VAD_PREFIX_PADDING_MS", "300"))
        vad_silence_duration_ms = int(os.environ.get("VAD_SILENCE_DURATION_MS", "500"))
        
        # Get instructions with default
        instructions = os.environ.get("INSTRUCTIONS", "You are the Home Assistant Voice Agent and can control the Smart Home.")
        
        # Get recording setting (optional, defaults to false)
        enable_recording = os.environ.get("ENABLE_RECORDING", "false").lower() == "true"
        
        # Get session reuse timeout and initialize session manager
        session_reuse_timeout = float(os.environ.get("SESSION_REUSE_TIMEOUT_SECONDS", "300"))
        self.session_manager = SessionManager(reuse_timeout=session_reuse_timeout)
        logger.info(f"Session reuse timeout: {session_reuse_timeout} seconds")
        
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Initialize Home Assistant MCP Service
        mcp_client = None
        try:
            supervisor_token = os.environ.get("LONGLIVED_TOKEN") or os.environ.get("SUPERVISOR_TOKEN")
            ha_mcp_url = os.environ.get("HA_MCP_URL", "http://supervisor/core/api/mcp")
            if supervisor_token:
                logger.info("Loading Home Assistant MCP tools...")
                self.mcp_service = HomeAssistantMCPService(url=ha_mcp_url, access_token=supervisor_token)
                mcp_client = await self.mcp_service.initialize()
                logger.info("✅ Home Assistant MCP Client initialized")
            else:
                logger.warning("⚠️ SUPERVISOR_TOKEN not set, skipping Home Assistant MCP integration")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Home Assistant MCP Client: {e}")
        
        # Initialize WebRTC service
        logger.info("Initializing WebRTC transport...")
        
        # Get ICE servers from environment (optional, for NAT traversal)
        ice_servers = None
        stun_server = os.environ.get("STUN_SERVER")
        if stun_server:
            ice_servers = [IceServer(urls=[stun_server])]
            logger.info(f"Using STUN server: {stun_server}")
        
        # Initialize WebRTC service
        self.webrtc_service = WebRTCService(
            ice_servers=ice_servers,
            esp32_mode=True,  # Enable ESP32-specific SDP munging
            host=None,
            connection_mode=ConnectionMode.SINGLE  # Single connection mode
        )
        
        # Create FastAPI app for WebRTC signaling
        self.fastapi_app = FastAPI(title="OpenAI Realtime Voice Agent - WebRTC")
        
        # Add CORS middleware for browser clients
        self.fastapi_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, specify allowed origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register WebRTC routes with connection callback
        async def connection_callback(transport: SmallWebRTCTransport, client_ip: str):
            """Handle new WebRTC connection.
            
            Args:
                transport: The WebRTC transport instance
                client_ip: The IP address of the client (used as client_id)
            """
            logger.info(f"🔗 New WebRTC connection established from IP: {client_ip}")
            # Use IP address as client ID
            client_id = client_ip
            logger.info(f"✅ Using client_id (IP): {client_id}")
            
            # Ensure OpenAI service exists (will create new session)
            await self._ensure_openai_service(client_id=client_id)
            # Build pipeline for this transport
            self._build_pipeline_for_transport(transport, client_id)
        
        # Store callback for use in routes
        self._webrtc_connection_callback = connection_callback
        
        # Register FastAPI routes
        self.webrtc_service.register_fastapi_routes(self.fastapi_app, base_path="/webrtc")
        
        # Override the offer handler to use our connection callback
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse
        from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequest
        
        @self.fastapi_app.post("/webrtc/offer")
        async def handle_offer(request_data: dict, http_request: Request):
            """Handle WebRTC offer request."""
            try:
                # Extract client IP address for client identification
                client_ip = http_request.client.host if http_request.client else None
                if not client_ip:
                    # Fallback: try to get from headers (for proxies)
                    client_ip = http_request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                    if not client_ip:
                        client_ip = http_request.headers.get("X-Real-IP", "")
                
                if not client_ip:
                    import uuid
                    client_ip = f"unknown_{uuid.uuid4().hex[:8]}"
                    logger.warning("⚠️ Could not extract client IP, using generated ID")
                else:
                    logger.info(f"✅ Extracted client IP: {client_ip}")
                
                request = SmallWebRTCRequest.from_dict(request_data)
                
                # Create a callback that passes client_ip to connection_callback
                async def webrtc_callback(transport: SmallWebRTCTransport):
                    await connection_callback(transport, client_ip)
                
                response = await self.webrtc_service.handle_webrtc_request(
                    request,
                    webrtc_callback
                )
                
                return JSONResponse(content=response)
            except Exception as e:
                logger.error(f"❌ Error handling WebRTC offer: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        logger.info(f"✅ WebRTC service initialized on port {webrtc_port}")
        
        # Store configuration for session creation
        self.openai_api_key = openai_api_key
        self.vad_threshold = vad_threshold
        self.vad_prefix_padding_ms = vad_prefix_padding_ms
        self.vad_silence_duration_ms = vad_silence_duration_ms
        self.instructions = instructions
        self.mcp_client = mcp_client
        
        # Create initial OpenAI service
        await self._ensure_openai_service()
        
        # Initialize audio recording service (optional)
        self.audio_recording_service = AudioRecordingService(
            enable_recording=enable_recording,
            sample_rate=24000,
            chunk_duration_seconds=30,
            output_dir="recordings"
        )
        
        logger.info("✅ Application initialized - waiting for WebRTC connection")
    
    def _build_pipeline_for_transport(self, transport: SmallWebRTCTransport, client_id: str):
        """
        Build pipeline for a WebRTC transport connection.
        
        Args:
            transport: The WebRTC transport instance
            client_id: Unique identifier for the client device
        """
        self.webrtc_transport = transport
        logger.info(f"🔗 Building pipeline for client: {client_id}")
        
        # Ensure OpenAI service exists
        if self.openai_service is None:
            raise RuntimeError("OpenAI service must be created before building pipeline")
        
        logger.info(f"🔗 Building pipeline with WebRTC transport and OpenAI service: {type(self.openai_service).__name__}")
        
        # Create activity trackers (one for input, one for output)
        input_activity_tracker = SessionActivityTracker(
            activity_callback=self._update_session_activity
        )
        output_activity_tracker = SessionActivityTracker(
            activity_callback=self._update_session_activity
        )
        
        # Create context aggregator with cached context if available
        context_aggregator = self.session_manager.create_context_aggregator(client_id)
        
        # Create context initializer if we have cached messages
        context_initializer = self.session_manager.create_context_initializer(client_id, context_aggregator)
        
        # Build pipeline components
        pipeline_components = [
            transport.input(),
            input_activity_tracker,
            context_aggregator.user(),
            self.openai_service,
            context_aggregator.assistant(),
            output_activity_tracker,
            transport.output()
        ]
        
        # Add context initializer if we have cached messages
        if context_initializer:
            pipeline_components.append(context_initializer)
        
        # Add audio buffer processor if recording is enabled
        audio_buffer = self.audio_recording_service.get_audio_buffer_processor() if self.audio_recording_service else None
        if audio_buffer:
            pipeline_components.append(audio_buffer)
        
        self.pipeline = Pipeline(pipeline_components)
        logger.info("✅ Pipeline erstellt für WebRTC connection")
        
        # Start audio recording if enabled
        if self.audio_recording_service and audio_buffer:
            asyncio.create_task(audio_buffer.start_recording())
            logger.info("🎙️ Started audio recording for WebRTC connection")
        
        # Create pipeline runner and start it
        self.runner = PipelineRunner()
        self.current_task = PipelineTask(self.pipeline)
        
        # Start pipeline in background
        asyncio.create_task(self.runner.run(self.current_task))
        logger.info("✅ Pipeline started for WebRTC connection")
        
        # Register disconnect handler to cache context when client disconnects
        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(*args, **kwargs):
            """Handle client disconnection - cache context before cleanup."""
            self.session_manager.handle_client_disconnect(client_id, self.openai_service)
        
        logger.info("✅ Application initialized successfully")
    
    def _update_session_activity(self):
        """Update session activity timestamp (called by SessionActivityTracker)."""
        pass  # Placeholder for activity tracking if needed in the future
    
    async def _ensure_openai_service(self, client_id: Optional[str] = None):
        """Create a new OpenAI service instance for a client.
        
        Args:
            client_id: Optional client ID for session management
        """
        if self._pipeline_lock is None:
            self._pipeline_lock = asyncio.Lock()
        
        async with self._pipeline_lock:
            # Client ID should always be provided when called from connection callback
            if client_id is None:
                logger.warning("⚠️ No client_id provided to _ensure_openai_service")
            
            # Create new session (each WebRTC connection gets a new session)
            # Context is cached and reused by SessionManager
            if client_id:
                logger.info(f"🆕 Erstelle neue OpenAI Session für Client {client_id}...")
            else:
                logger.info("🆕 Erstelle neue OpenAI Session...")
            
            # Cache context from old service before creating new one (if we have client_id)
            if client_id and self.openai_service is not None:
                try:
                    self.session_manager.cleanup_before_new_session(client_id)
                    logger.debug(f"Cached context from previous session for client {client_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Error caching context from old service for client {client_id}: {e}")
            
            # Create session properties with audio configuration
            from pipecat.services.openai.realtime.events import (
                SessionProperties,
                AudioConfiguration,
                AudioInput,
                AudioOutput,
                TurnDetection
            )
            
            # Create disconnect tool definition
            disconnect_tool_def = get_disconnect_tool_definition()
            
            # Collect all tool definitions for session properties
            all_tools = [disconnect_tool_def]
            
            # Get MCP tool definitions if available (BEFORE creating session)
            # We need the tool definitions for SessionProperties, so we fetch them first
            mcp_tools_schema = None
            if self.mcp_client:
                try:
                    logger.info("🔧 Fetching MCP tool definitions...")
                    mcp_tools_schema = await self.mcp_client.get_tools_schema()
                    
                    # Convert MCP tool schemas to OpenAI format for SessionProperties
                    for function_schema in mcp_tools_schema.standard_tools:
                        # Convert FunctionSchema to OpenAI Realtime API format
                        openai_tool = {
                            "type": "function",
                            "name": function_schema.name,
                            "description": function_schema.description,
                            "parameters": {
                                "type": "object",
                                "properties": function_schema.properties,
                                "required": function_schema.required
                            }
                        }
                        all_tools.append(openai_tool)
                    
                    logger.info(f"✅ Fetched {len(mcp_tools_schema.standard_tools)} MCP tools")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to fetch MCP tool definitions: {e}")
            
            session_properties = SessionProperties(
                instructions=self.instructions,
                # Configure audio input with VAD
                audio=AudioConfiguration(
                    input=AudioInput(
                        turn_detection=TurnDetection(
                            type="server_vad",
                            threshold=self.vad_threshold,
                            prefix_padding_ms=self.vad_prefix_padding_ms,
                            silence_duration_ms=self.vad_silence_duration_ms
                        )
                    ),
                    output=AudioOutput(voice="marin")
                ),
                # Add all tools (disconnect + MCP tools) to session
                tools=all_tools
            )
            
            logger.info(f"🔧 Creating session with {len(all_tools)} tools: {[tool.get('name', 'unknown') for tool in all_tools]}")
            
            # Create new service instance
            self.openai_service = OpenAIRealtimeLLMService(
                api_key=self.openai_api_key,
                model="gpt-realtime",
                session_properties=session_properties,
                start_audio_paused=False
            )
            logger.info(f"✅ OpenAI Service erstellt: {type(self.openai_service).__name__}")
            
            # Register disconnect tool handler
            disconnect_tool_handler = create_disconnect_tool_handler(self.webrtc_transport)
            self.openai_service.register_function("disconnect_client", disconnect_tool_handler)
            logger.info("✅ Registered disconnect tool handler")
            
            # Register MCP tool handlers if available
            if self.mcp_client and mcp_tools_schema:
                try:
                    await self.mcp_client.register_tools_schema(mcp_tools_schema, self.openai_service)
                    logger.info(f"✅ Registered {len(mcp_tools_schema.standard_tools)} MCP tool handlers")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to register MCP tool handlers: {e}")
            
            # Register service with session manager (if we have client_id)
            if client_id:
                self.session_manager.set_current_service(client_id, self.openai_service)
            
            logger.info("✅ Neue OpenAI Session erstellt")
            return self.openai_service
    
    async def run(self) -> None:
        """Run the application."""
        await self.initialize()
        
        # Get port from environment
        webrtc_port = int(os.environ.get("WEBRTC_PORT", "8080"))
        
        try:
            # Start FastAPI server
            config = uvicorn.Config(
                app=self.fastapi_app,
                host="0.0.0.0",
                port=webrtc_port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            await server.serve()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up application...")
        
        if self.runner:
            try:
                await self.runner.cancel()
            except Exception as e:
                logger.warning(f"⚠️ Error cancelling runner: {e}")
        
        if self.webrtc_transport:
            try:
                # WebRTC transport cleanup is handled by the connection
                pass
            except Exception as e:
                logger.warning(f"⚠️ Error stopping transport: {e}")
        
        if self.audio_recording_service:
            self.audio_recording_service.cleanup()
        
        logger.info("✅ Application cleanup complete")


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
