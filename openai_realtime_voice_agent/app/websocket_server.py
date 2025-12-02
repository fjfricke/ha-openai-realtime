"""WebSocket server for real-time audio streaming to OpenAI."""
import asyncio
import json
import logging
from typing import Set, Optional
import websockets
from websockets.exceptions import ConnectionClosed
from openai_client import OpenAIRealtimeClient
from audio_recorder import AudioRecorder

logger = logging.getLogger(__name__)


class WebSocketServer:
    """WebSocket server for real-time audio streaming with OpenAI."""
    
    def __init__(self, port: int, openai_api_key: str, enable_recording: bool = True):
        """
        Initialize WebSocket server.
        
        Args:
            port: Port to run the server on
            openai_api_key: OpenAI API key for creating client sessions
            enable_recording: Enable audio recording for debugging
        """
        self.port = port
        self.openai_api_key = openai_api_key
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self._server = None
        self._audio_sender_tasks: Set[asyncio.Task] = set()
        # Map of client websocket to their OpenAI client instance
        self.client_openai_clients: dict = {}
        # Audio recording for debugging
        self.enable_recording = enable_recording
        self.recorders: dict = {}  # Map of websocket to AudioRecorder
        
    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol):
        """Handle a new WebSocket client connection."""
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        # Get path if available (may not exist in all websockets versions)
        path = getattr(websocket, 'path', 'N/A')
        logger.info(f"✅ New WebSocket client connected: {client_addr} (path: {path})")
        self.clients.add(websocket)
        
        # Create a new OpenAI client session for this client
        openai_client = None
        sender_task = None
        recorder = None
        try:
            # Start audio recording if enabled
            if self.enable_recording:
                recorder = AudioRecorder()
                recorder.start_recording(client_id=client_addr.replace(":", "_"))
                self.recorders[websocket] = recorder
                logger.info(f"🎙️ Started audio recording for client {client_addr}")
            
            logger.info(f"🔗 Creating new OpenAI session for client {client_addr}...")
            
            # Create disconnect callback for the tool
            async def disconnect_client():
                """Disconnect callback for disconnect tool."""
                logger.info(f"🔌 Disconnect tool triggered - sending disconnect message to {client_addr}")
                try:
                    # Send disconnect message to ESP32 so it can go to idle mode
                    await websocket.send(json.dumps({
                        "type": "disconnect",
                        "message": "User requested disconnect",
                        "reason": "user_requested"
                    }))
                    logger.info(f"✅ Sent disconnect message to {client_addr}")
                    # Give ESP32 a moment to process the message
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.warning(f"⚠️ Error sending disconnect message: {e}")
                finally:
                    # Close the WebSocket connection, which will trigger cleanup
                    await websocket.close()
            
            openai_client = OpenAIRealtimeClient(self.openai_api_key, disconnect_callback=disconnect_client)
            await asyncio.wait_for(openai_client.connect(), timeout=30.0)
            self.client_openai_clients[websocket] = openai_client
            logger.info(f"✅ OpenAI session created for client {client_addr}")
            
            # Send welcome message
            await websocket.send(json.dumps({
                "type": "connected",
                "message": "Connected to OpenAI Realtime server",
                "audio_format": {
                    "input": "24kHz, 16-bit, mono PCM",
                    "output": "24kHz, 16-bit, mono PCM"
                }
            }))
            
            # Start task to send audio responses to this client
            sender_task = asyncio.create_task(self._send_audio_responses(websocket, openai_client, recorder))
            self._audio_sender_tasks.add(sender_task)
            
            # Handle incoming messages (audio data)
            async for message in websocket:
                try:
                    # Check if message is JSON (control message) or binary (audio)
                    if isinstance(message, str):
                        # JSON control message
                        data = json.loads(message)
                        await self._handle_control_message(websocket, data, openai_client)
                    else:
                        # Binary audio data
                        await self._handle_audio_data(message, openai_client, recorder)
                        
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Invalid JSON from client {client_addr}: {message}")
                except Exception as e:
                    logger.error(f"❌ Error handling message from {client_addr}: {e}", exc_info=True)
                    # Continue processing even if one message fails
                    continue
                    
        except ConnectionClosed:
            logger.info(f"🔌 Client {client_addr} disconnected")
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout creating OpenAI session for client {client_addr}")
        except Exception as e:
            logger.error(f"❌ Error in client handler for {client_addr}: {e}", exc_info=True)
        finally:
            # Cleanup: disconnect OpenAI session for this client
            if openai_client:
                try:
                    logger.info(f"🔌 Disconnecting OpenAI session for client {client_addr}...")
                    await openai_client.disconnect()
                    logger.info(f"✅ OpenAI session disconnected for client {client_addr}")
                except Exception as e:
                    logger.error(f"⚠️ Error disconnecting OpenAI session: {e}")
                finally:
                    self.client_openai_clients.pop(websocket, None)
            
            # Stop audio recording
            if recorder:
                recorder.stop_recording()
                self.recorders.pop(websocket, None)
            
            # Cleanup WebSocket client
            self.clients.discard(websocket)
            if sender_task:
                sender_task.cancel()
                self._audio_sender_tasks.discard(sender_task)
                try:
                    await sender_task
                except asyncio.CancelledError:
                    pass
            logger.info(f"🧹 Cleaned up client {client_addr}")
    
    async def _handle_control_message(self, websocket: websockets.WebSocketServerProtocol, data: dict, openai_client: OpenAIRealtimeClient):
        """Handle control messages from client."""
        msg_type = data.get("type")
        
        if msg_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))
        elif msg_type == "flush":
            # Client wants to flush audio buffer
            logger.info("🔄 Client requested flush - committing audio buffer")
            await openai_client.flush_audio()
            await websocket.send(json.dumps({"type": "flushed"}))
            logger.info("✅ Audio buffer flushed and committed")
        else:
            logger.info(f"📨 Control message: {msg_type}")
    
    async def _handle_audio_data(self, audio_bytes: bytes, openai_client: OpenAIRealtimeClient, recorder: Optional[AudioRecorder] = None):
        """Handle incoming audio data from client.
        
        Args:
            audio_bytes: PCM audio bytes (16-bit, 24kHz, mono)
            openai_client: OpenAI client instance for this connection
            recorder: Optional audio recorder for debugging
        """
        if not audio_bytes:
            return
        
        # Record audio if recording is enabled
        if recorder:
            recorder.record_input_audio(audio_bytes)
        
        # Send directly to OpenAI client (it handles buffering)
        await openai_client.send_audio(audio_bytes)
        logger.debug(f"📡 Received {len(audio_bytes)} bytes of audio from client, sending to OpenAI")
    
    async def _send_audio_responses(self, websocket: websockets.WebSocketServerProtocol, 
                                    openai_client: OpenAIRealtimeClient, 
                                    recorder: Optional[AudioRecorder] = None):
        """Send audio responses from OpenAI to client with rate limiting.
        
        This runs in a separate task for each client.
        
        Args:
            websocket: WebSocket connection to client
            openai_client: OpenAI client instance for this connection
            recorder: Optional audio recorder for debugging
        """
        import time
        
        # Audio format: 24kHz, 16-bit, mono = 48,000 bytes/sec
        OUTPUT_SAMPLE_RATE = 24000
        BYTES_PER_SAMPLE = 2  # 16-bit
        BYTES_PER_SECOND = OUTPUT_SAMPLE_RATE * BYTES_PER_SAMPLE  # 48,000 bytes/sec
        
        chunk_count = 0
        total_bytes = 0
        last_interrupt_check = 0
        last_send_time = time.time()
        audio_buffer = b""  # Buffer for rate-limited sending
        aec_training_sent = False  # Track if we've sent AEC training signal
        
        try:
            while True:
                try:
                    # Check for interrupts periodically (every 100ms)
                    current_time = time.time()
                    if current_time - last_interrupt_check > 0.1:
                        if openai_client.was_interrupted():
                            # Send interrupt message to client
                            await websocket.send(json.dumps({
                                "type": "interrupt",
                                "message": "User interrupted - clearing audio queue"
                            }))
                            logger.info("🛑 User interrupted - sent interrupt message to client")
                            # Clear buffer on interrupt
                            audio_buffer = b""
                            # Reset AEC training flag on interrupt
                            aec_training_sent = False
                        last_interrupt_check = current_time
                    
                    # Get audio from OpenAI (24kHz, 16-bit, mono PCM)
                    audio_bytes = await asyncio.wait_for(
                        openai_client.get_response_audio(),
                        timeout=0.1  # 100ms timeout
                    )
                    
                    if audio_bytes:
                        # Add to buffer
                        audio_buffer += audio_bytes
                        chunk_count += 1
                        total_bytes += len(audio_bytes)
                        
                        # Record audio if recording is enabled
                        if recorder:
                            recorder.record_output_audio(audio_bytes)
                        
                        # Send AEC training signal before first audio chunk
                        # This helps the XMOS AEC adapt before the actual response
                        if not aec_training_sent and len(audio_buffer) > 0:
                            # Send ~300ms of silence (14400 bytes at 24kHz, 16-bit mono)
                            # This gives the AEC time to adapt to the speaker output
                            training_silence = b'\x00' * 14400  # 300ms of silence
                            await websocket.send(training_silence)
                            logger.info("🔇 Sent AEC training silence (300ms) to help echo cancellation adapt")
                            aec_training_sent = True
                            # Adjust timing to account for training
                            last_send_time = current_time
                    
                    # Send audio from buffer at playback rate
                    if audio_buffer:
                        elapsed = current_time - last_send_time
                        # Calculate how much audio we should have sent in this time
                        bytes_to_send = int(elapsed * BYTES_PER_SECOND)
                        
                        if bytes_to_send > 0:
                            # Send up to bytes_to_send bytes
                            send_bytes = min(bytes_to_send, len(audio_buffer))
                            if send_bytes > 0:
                                chunk_to_send = audio_buffer[:send_bytes]
                                audio_buffer = audio_buffer[send_bytes:]
                                
                                # Send binary audio data to client
                                await websocket.send(chunk_to_send)
                                last_send_time = current_time
                                
                                logger.debug(f"🔊 Sent {send_bytes} bytes at playback rate (buffer: {len(audio_buffer)} bytes, total: {total_bytes} bytes)")
                    else:
                        # Log occasionally when no audio is available
                        if chunk_count == 0 and total_bytes == 0:
                            # Only log once at the start
                            logger.debug("⏳ Waiting for audio from OpenAI...")
                    
                    # Small sleep to prevent busy-waiting
                    await asyncio.sleep(0.01)  # 10ms
                    
                except asyncio.TimeoutError:
                    # No audio available, but still send buffered audio at rate
                    if audio_buffer:
                        current_time = time.time()
                        elapsed = current_time - last_send_time
                        bytes_to_send = int(elapsed * BYTES_PER_SECOND)
                        
                        if bytes_to_send > 0:
                            send_bytes = min(bytes_to_send, len(audio_buffer))
                            if send_bytes > 0:
                                chunk_to_send = audio_buffer[:send_bytes]
                                audio_buffer = audio_buffer[send_bytes:]
                                
                                await websocket.send(chunk_to_send)
                                last_send_time = current_time
                                logger.debug(f"🔊 Sent {send_bytes} bytes from buffer (remaining: {len(audio_buffer)} bytes)")
                    
                    await asyncio.sleep(0.01)  # Small sleep
                    continue
                except ConnectionClosed:
                    # Client disconnected
                    logger.info(f"🔌 Audio sender task ended (sent {chunk_count} chunks, {total_bytes} total bytes)")
                    break
                except Exception as e:
                    logger.error(f"❌ Error sending audio to client: {e}", exc_info=True)
                    await asyncio.sleep(0.1)  # Brief pause before retrying
                    
        except asyncio.CancelledError:
            logger.debug(f"Audio sender task cancelled (sent {chunk_count} chunks, {total_bytes} total bytes)")
        except Exception as e:
            logger.error(f"❌ Error in audio sender task: {e}", exc_info=True)
    
    async def start(self) -> None:
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket server on port {self.port}...")
        
        # Create a wrapper function that matches websockets.serve() signature
        # In websockets 12.0+, handler receives only websocket (path is websocket.path)
        async def handler(websocket: websockets.WebSocketServerProtocol):
            await self._handle_client(websocket)
        
        self._server = await websockets.serve(
            handler,
            "0.0.0.0",
            self.port,
            ping_interval=20,  # Send ping every 20 seconds
            ping_timeout=10,    # Wait 10 seconds for pong
        )
        
        logger.info(f"✅ WebSocket server started on ws://0.0.0.0:{self.port}")
    
    async def stop(self) -> None:
        """Stop the WebSocket server."""
        logger.info("Stopping WebSocket server...")
        
        # Disconnect all OpenAI sessions
        for websocket, openai_client in list(self.client_openai_clients.items()):
            try:
                logger.info("Disconnecting OpenAI session for client...")
                await openai_client.disconnect()
            except Exception as e:
                logger.warning(f"⚠️ Error disconnecting OpenAI session: {e}")
        self.client_openai_clients.clear()
        
        # Cancel all audio sender tasks
        for task in self._audio_sender_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._audio_sender_tasks:
            await asyncio.gather(*self._audio_sender_tasks, return_exceptions=True)
        
        # Close all client connections
        for client in self.clients.copy():
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"⚠️ Error closing client connection: {e}")
        self.clients.clear()
        
        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        logger.info("✅ WebSocket server stopped")

