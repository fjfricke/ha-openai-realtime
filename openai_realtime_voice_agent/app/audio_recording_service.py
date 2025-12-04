"""Audio recording service using Pipecat's AudioBufferProcessor."""
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from app.audio_recorder import AudioRecorder

if TYPE_CHECKING:
    from pipecat.transports.websocket.server import WebsocketServerTransport

logger = logging.getLogger(__name__)


class AudioRecordingService:
    """Service for recording audio using Pipecat's AudioBufferProcessor."""
    
    def __init__(
        self,
        enable_recording: bool = False,
        sample_rate: int = 24000,
        chunk_duration_seconds: int = 30,
        output_dir: str = "recordings"
    ):
        """
        Initialize audio recording service.
        
        Args:
            enable_recording: Whether to enable audio recording
            sample_rate: Audio sample rate in Hz (default: 24000)
            chunk_duration_seconds: Duration of audio chunks in seconds (default: 30)
            output_dir: Directory to save recordings
        """
        self.enable_recording = enable_recording
        self.sample_rate = sample_rate
        self.chunk_duration_seconds = chunk_duration_seconds
        self.output_dir = output_dir
        
        self.audio_buffer: Optional[AudioBufferProcessor] = None
        self.audio_recorder: Optional[AudioRecorder] = None
        
        if self.enable_recording:
            self._initialize_recording()
    
    def _initialize_recording(self):
        """Initialize audio recording components."""
        # Create audio recorder
        self.audio_recorder = AudioRecorder(output_dir=self.output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audio_recorder.start_recording(client_id=f"session_{timestamp}")
        
        # Create AudioBufferProcessor for track-level recording (separate user and bot tracks)
        # Use chunked recording for regular saves (recommended for most use cases)
        buffer_size = self.sample_rate * 2 * self.chunk_duration_seconds  # 2 bytes per sample (16-bit)
        
        self.audio_buffer = AudioBufferProcessor(
            sample_rate=self.sample_rate,
            num_channels=1,  # Mono
            buffer_size=buffer_size,
            enable_turn_audio=False  # We want continuous recording, not turn-based
        )
        
        # Register event handler for track audio data (separate user and bot tracks)
        @self.audio_buffer.event_handler("on_track_audio_data")
        async def on_track_audio_data(buffer, user_audio, bot_audio, sample_rate, num_channels):
            """Handle track audio data events from AudioBufferProcessor."""
            if user_audio and len(user_audio) > 0:
                self.audio_recorder.record_input_audio(user_audio)
            if bot_audio and len(bot_audio) > 0:
                self.audio_recorder.record_output_audio(bot_audio)
        
        logger.info("✅ AudioRecordingService initialized")
    
    def get_audio_buffer_processor(self) -> Optional[AudioBufferProcessor]:
        """Get the audio buffer processor for pipeline integration."""
        return self.audio_buffer if self.enable_recording else None
    
    def register_transport_handlers(self, transport: "WebsocketServerTransport"):
        """
        Register event handlers for the WebSocket transport.
        
        Args:
            transport: The WebSocket transport instance
        """
        if not self.enable_recording or not self.audio_buffer:
            return
        
        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, websocket):
            """Start recording when client connects."""
            logger.info("🎙️ Client connected - starting audio recording")
            await self.audio_buffer.start_recording()
        
        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, websocket):
            """Stop recording when client disconnects."""
            logger.info("🎙️ Client disconnected - stopping audio recording")
            # Stop recording - this will trigger final audio data handlers
            await self.audio_buffer.stop_recording()
            if self.audio_recorder:
                self.audio_recorder.stop_recording()
                # Create new recorder for next session
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.audio_recorder = AudioRecorder(output_dir=self.output_dir)
                self.audio_recorder.start_recording(client_id=f"session_{timestamp}")
        
        logger.info("✅ Registered transport event handlers for audio recording")
    
    def cleanup(self):
        """Cleanup resources."""
        if self.audio_recorder:
            self.audio_recorder.stop_recording()
            self.audio_recorder = None

