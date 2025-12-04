"""Main application entry point using Pipecat."""
import os
import sys
import asyncio
import logging
import time
from typing import Optional
import dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, InputAudioRawFrame, OutputAudioRawFrame, StartFrame, EndFrame

from pipecat.transports.websocket.server import WebsocketServerTransport, WebsocketServerParams
from app.mcp_service import HomeAssistantMCPService
from app.raw_audio_serializer import RawAudioSerializer
from app.disconnect_tool import get_disconnect_tool_definition, create_disconnect_tool_handler
from app.audio_recording_service import AudioRecordingService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        self.websocket_transport: Optional[WebsocketServerTransport] = None
        self.openai_service: Optional[OpenAIRealtimeLLMService] = None
        self.mcp_service: Optional[HomeAssistantMCPService] = None
        self.audio_recording_service: Optional[AudioRecordingService] = None
        self.session_last_activity: Optional[float] = None
        self.session_reuse_timeout: float = 300.0  # Default: 5 Minuten
        self.current_task: Optional[PipelineTask] = None
        self._pipeline_lock: Optional[asyncio.Lock] = None  # Wird beim ersten Aufruf erstellt
        
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
        
        # Get recording setting (optional, defaults to false)
        enable_recording = os.environ.get("ENABLE_RECORDING", "false").lower() == "true"
        
        # Get session reuse timeout
        session_reuse_timeout = float(os.environ.get("SESSION_REUSE_TIMEOUT_SECONDS", "300"))
        self.session_reuse_timeout = session_reuse_timeout
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
        
        # Initialize WebSocket transport using official Pipecat transport
        logger.info("Initializing WebSocket transport...")
        transport_params = WebsocketServerParams(
            add_wav_header=False,  # Raw PCM audio, no WAV headers
            serializer=RawAudioSerializer(),  # Custom serializer for raw binary PCM audio
            # Enable audio input and output with correct format
            audio_in_enabled=True,
            audio_in_sample_rate=24000,  # 24kHz for OpenAI
            audio_in_channels=1,  # Mono
            audio_out_enabled=True,
            audio_out_sample_rate=24000,  # 24kHz for OpenAI
            audio_out_channels=1  # Mono
            # audio_out_destinations defaults to empty list, which uses default destination
        )
        self.websocket_transport = WebsocketServerTransport(
            params=transport_params,
            host="0.0.0.0",
            port=websocket_port
        )
        
        # Store configuration for session creation
        self.openai_api_key = openai_api_key
        self.vad_threshold = vad_threshold
        self.vad_prefix_padding_ms = vad_prefix_padding_ms
        self.vad_silence_duration_ms = vad_silence_duration_ms
        self.instructions = instructions
        self.mcp_client = mcp_client
        
        # Create initial OpenAI service (wird beim ersten Client-Connect erstellt)
        # NICHT beim Initialisieren, damit die Pipeline die richtige Instanz verwendet
        await self._ensure_openai_service()
        
        # Note: Disconnect tool and other custom tools should be registered
        # via the service's tool registration mechanism if needed
        
        # Note: Disconnect tool execution will be handled by OpenAI service
        # We'll need to set up a tool handler to intercept disconnect_client calls
        
        # Initialize audio recording service (optional)
        self.audio_recording_service = AudioRecordingService(
            enable_recording=enable_recording,
            sample_rate=24000,
            chunk_duration_seconds=30,
            output_dir="recordings"
        )
        
        # Create activity trackers (one for input, one for output)
        input_activity_tracker = SessionActivityTracker(
            activity_callback=self._update_session_activity
        )
        output_activity_tracker = SessionActivityTracker(
            activity_callback=self._update_session_activity
        )
        
        # Build pipeline using official Pipecat WebSocket transport
        # Flow: WebSocket Input -> Activity Tracker -> OpenAI -> Activity Tracker -> WebSocket Output -> AudioBuffer
        if self.openai_service is None:
            raise RuntimeError("OpenAI service must be created before building pipeline")
        
        logger.info(f"🔗 Building pipeline with OpenAI service: {type(self.openai_service).__name__}")
        
        # Build pipeline components
        pipeline_components = [
            self.websocket_transport.input(),  # Input: receives audio from clients
            input_activity_tracker,  # Track activity on input
            self.openai_service,
            output_activity_tracker,  # Track activity on output
            self.websocket_transport.output()  # Output: sends audio to clients
        ]
        
        # Add audio buffer processor after transport.output() if recording is enabled
        audio_buffer = self.audio_recording_service.get_audio_buffer_processor() if self.audio_recording_service else None
        if audio_buffer:
            pipeline_components.append(audio_buffer)
        
        self.pipeline = Pipeline(pipeline_components)
        logger.info("✅ Pipeline erstellt")
        
        # Register transport event handlers for audio recording
        if self.audio_recording_service:
            self.audio_recording_service.register_transport_handlers(self.websocket_transport)
        
        # Create pipeline runner
        self.runner = PipelineRunner()
        
        logger.info("✅ Application initialized successfully")
    
    def _should_reuse_session(self) -> bool:
        """Prüft, ob die aktuelle Session wiederverwendet werden kann."""
        if self.session_last_activity is None:
            return False
        
        time_since_activity = time.time() - self.session_last_activity
        can_reuse = time_since_activity < self.session_reuse_timeout
        
        if can_reuse:
            logger.debug(f"♻️ Session kann wiederverwendet werden (letzte Aktivität: {time_since_activity:.1f}s ago, Timeout: {self.session_reuse_timeout}s)")
        else:
            logger.info(f"⏰ Session abgelaufen (letzte Aktivität: {time_since_activity:.1f}s ago, Timeout: {self.session_reuse_timeout}s)")
        
        return can_reuse
    
    def _update_session_activity(self):
        """Aktualisiert den Timestamp der letzten Session-Aktivität."""
        self.session_last_activity = time.time()
    
    async def _ensure_openai_service(self):
        """Erstellt eine neue Service-Instanz oder wiederverwendet die bestehende."""
        # Erstelle Lock beim ersten Aufruf
        if self._pipeline_lock is None:
            self._pipeline_lock = asyncio.Lock()
        
        async with self._pipeline_lock:
            # Prüfe, ob Session wiederverwendet werden kann
            if self._should_reuse_session() and self.openai_service is not None:
                logger.info(f"♻️ Wiederverwende bestehende Session (letzte Aktivität: {time.time() - self.session_last_activity:.1f}s ago)")
                self._update_session_activity()
                return self.openai_service
            
            # Neue Session erstellen
            logger.info("🆕 Erstelle neue OpenAI Session...")
            
            # Alte Service-Instanz cleanup (falls vorhanden)
            if self.openai_service is not None:
                try:
                    # Cleanup der alten Service-Instanz
                    logger.debug("Cleaning up old OpenAI service...")
                except Exception as e:
                    logger.warning(f"⚠️ Error cleaning up old service: {e}")
            
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
                # Add disconnect tool to session
                tools=[disconnect_tool_def]
            )
            
            # Create new service instance
            # Note: start_audio_paused=False is the default, but we set it explicitly for clarity
            self.openai_service = OpenAIRealtimeLLMService(
                api_key=self.openai_api_key,
                model="gpt-realtime",
                session_properties=session_properties,
                start_audio_paused=False  # Start processing audio immediately
            )
            logger.info(f"✅ OpenAI Service erstellt: {type(self.openai_service).__name__}")
            
            # Register disconnect tool handler
            disconnect_tool_handler = create_disconnect_tool_handler(self.websocket_transport)
            self.openai_service.register_function("disconnect_client", disconnect_tool_handler)
            logger.info("✅ Registered disconnect tool handler")
            
            # Register MCP tools if available
            if self.mcp_client:
                try:
                    await self.mcp_client.register_tools(self.openai_service)
                    logger.info("✅ Registered MCP tools with OpenAI service")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to register MCP tools: {e}")
            
            # Update activity timestamp
            self._update_session_activity()
            
            # WICHTIG: Wenn die Pipeline bereits läuft, muss sie neu aufgebaut werden,
            # damit sie die neue Service-Instanz verwendet
            if self.pipeline is not None:
                logger.warning("⚠️ Pipeline existiert bereits - neue Session wird möglicherweise nicht verwendet!")
                logger.warning("⚠️ Die Pipeline muss neu erstellt werden, um die neue Session zu verwenden")
            
            logger.info("✅ Neue OpenAI Session erstellt")
            return self.openai_service
    
    async def run(self) -> None:
        """Run the application."""
        await self.initialize()
        
        try:
            # Create pipeline task and run it
            self.current_task = PipelineTask(self.pipeline)
            await self.runner.run(self.current_task)
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
        
        if self.websocket_transport:
            try:
                # Official transport cleanup is handled by the pipeline
                pass
            except Exception as e:
                logger.warning(f"⚠️ Error stopping transport: {e}")
        
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
