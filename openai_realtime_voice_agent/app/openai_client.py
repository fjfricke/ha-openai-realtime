"""OpenAI Realtime API client with function calling support."""
import json
import asyncio
import logging
import base64
from typing import Dict, Optional, Any, Callable, Awaitable
from openai import OpenAI
from openai.resources.realtime.realtime import RealtimeConnection
from concurrent.futures import ThreadPoolExecutor
from websockets.exceptions import ConnectionClosedOK, ConnectionClosed
from disconnect_tool import get_disconnect_tool_definition, execute_disconnect_tool
from home_assistant_mcp_client import get_home_assistant_client

logger = logging.getLogger(__name__)


class OpenAIRealtimeClient:
    """Client for OpenAI Realtime API with WebSocket connection."""
    
    def __init__(self, api_key: str, disconnect_callback: Optional[Callable[[], Awaitable[None]]] = None):
        """
        Initialize OpenAI Realtime client.
        
        Args:
            api_key: OpenAI API key
            disconnect_callback: Optional async callback function to disconnect the client (for tools)
        """
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)
        self.connection: Optional[RealtimeConnection] = None
        self.connection_manager = None
        self.response_audio_queue: asyncio.Queue = asyncio.Queue()
        self._connected = False
        self._receive_task: Optional[asyncio.Task] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="openai-realtime")
        # Track interruptions (when user starts speaking while assistant is responding)
        self._interrupted = False
        self._last_speech_started_time = 0
        # Track when user stopped speaking (for AEC grace period)
        self._last_speech_stopped_time = 0
        self._aec_grace_period_seconds = 3.0  # 3 seconds for AEC to kick in
        # Track session creation - wait for session.created before sending config
        self._session_created_event = asyncio.Event()
        self._session_created = False
        # Track if we've received the first user message (to trigger response after create_response: False)
        self._first_user_message_received = False
        
        # Audio buffering configuration
        self._sample_rate = 24000  # 24kHz for OpenAI input
        self._bytes_per_sample = 2  # 16-bit = 2 bytes
        self._bytes_per_100ms = (self._sample_rate * self._bytes_per_sample * 100) // 1000  # 4800 bytes
        self._audio_buffer: bytes = b""
        
        # Tool support
        self._disconnect_callback = disconnect_callback
        
    async def connect(self) -> None:
        """Connect to OpenAI Realtime API."""
        try:
            logger.info("Connecting to OpenAI Realtime API...")
            
            # Connect using the Realtime API connect method (still in beta)
            self.connection_manager = self.client.realtime.connect(
                model="gpt-realtime"
            )
            
            # Get the RealtimeConnection from the connection manager
            # enter() is synchronous, returns RealtimeConnection directly
            self.connection = self.connection_manager.enter()
            self._connected = True

            # Start receiving messages (run sync iterator in thread)
            # This must start before we wait for session.created
            self._receive_task = asyncio.create_task(self._receive_messages())
            
            # Wait for session.created event (with timeout)
            try:
                await asyncio.wait_for(self._session_created_event.wait(), timeout=5.0)
                logger.info("✅ Session created, sending configuration...")
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout waiting for session.created event, sending configuration anyway...")
            
            # Send configuration with tools and server_vad (after session is created)
            await self._send_configuration()
            
            # Give the session a moment to fully initialize before accepting audio
            # This ensures the first user input is properly detected
            await asyncio.sleep(0.3)
            
            logger.info("✅ Connected to OpenAI Realtime API with server_vad enabled")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to OpenAI Realtime API: {e}", exc_info=True)
            self._connected = False
            raise
    
    async def _send_configuration(self) -> None:
        """Send configuration with server_vad."""
        # Collect all tools
        tools = [get_disconnect_tool_definition()]
        
        # Add Home Assistant MCP tools
        ha_client = get_home_assistant_client()
        if ha_client and ha_client.is_connected():
            ha_tools = ha_client.get_tools_for_openai()
            tools.extend(ha_tools)
            logger.info(f"✅ Added {len(ha_tools)} Home Assistant tools to OpenAI session")
        
        # Define session configuration as a dictionary
        session_config = {
            "type": "realtime",
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": 24000
                    },
                    "noise_reduction": {
                        "type": "far_field"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.25,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                        "create_response": False,
                        "interrupt_response": True
                    }
                    # "turn_detection": {
                    #     "type": "semantic_vad",
                    #     "eagerness": "medium",
                    #     "create_response": True,
                    #     "interrupt_response": True
                    # }
                },
                "output": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": 24000
                    },
                    "voice": "marin"
                }
            },
            "output_modalities": ["audio"],
            "instructions": "Du bist der Hüter des Hauses und kannst das Smart Home steuern.",
            "tools": tools
        }
        
        # Construct the session.update message
        config = {
            "type": "session.update",
            "session": session_config
        }
        
        try:
            await self._send_message(config)
            logger.info("✅ Session configured with server_vad")
        except Exception as e:
            logger.error(f"❌ Failed to send session configuration: {e}", exc_info=True)
            logger.error(f"Configuration that failed: {json.dumps(config, indent=2)}")
            raise
    
    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send audio data to OpenAI.
        
        Args:
            audio_data: PCM audio bytes (16-bit, 24kHz, mono)
        """
        if not self._connected:
            logger.warning("⚠️ Not connected, ignoring audio")
            return
        
        if not audio_data or len(audio_data) == 0:
            # If empty data but buffer has content, try to flush it
            if len(self._audio_buffer) >= self._bytes_per_100ms:
                # Flush existing buffer
                duration_ms = (len(self._audio_buffer) / self._bytes_per_sample / self._sample_rate) * 1000
                audio_b64 = base64.b64encode(self._audio_buffer).decode('utf-8')
                await self._send_message({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                })
                logger.debug(f"📤 Flushed {len(self._audio_buffer)} bytes ({duration_ms:.1f}ms) of audio")
                self._audio_buffer = b""
            return
        
        # Accumulate audio in buffer
        self._audio_buffer += audio_data
        
        # Only send when we have at least 100ms of audio (4800 bytes at 24kHz, 16-bit mono)
        if len(self._audio_buffer) >= self._bytes_per_100ms:
            # Calculate duration for logging
            duration_ms = (len(self._audio_buffer) / self._bytes_per_sample / self._sample_rate) * 1000
            
            # Convert to base64 for OpenAI format
            audio_b64 = base64.b64encode(self._audio_buffer).decode('utf-8')
            
            message = {
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }
            
            await self._send_message(message)
            logger.debug(f"📤 Sent {len(self._audio_buffer)} bytes ({duration_ms:.1f}ms) of audio to OpenAI")
            
            # Clear buffer
            self._audio_buffer = b""
            
            # With server_vad, OpenAI automatically processes audio when it detects speech
            # We don't need to commit manually - server_vad handles turn detection
            # Commits will only happen when explicitly flushing (e.g., end of audio file)
        else:
            logger.debug(f"📦 Buffering audio: {len(self._audio_buffer)}/{self._bytes_per_100ms} bytes")
    
    async def flush_audio(self) -> None:
        """Flush any remaining audio in buffer and commit."""
        if len(self._audio_buffer) > 0:
            remaining = len(self._audio_buffer)
            logger.info(f"Flushing {remaining} bytes from buffer...")
            
            # Check if we have enough audio (at least 100ms = 3200 bytes)
            if remaining >= self._bytes_per_100ms:
                # Send remaining buffer
                audio_b64 = base64.b64encode(self._audio_buffer).decode('utf-8')
                await self._send_message({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                })
                self._audio_buffer = b""
                logger.info(f"✅ Flushed {remaining} bytes")
                
                # Commit after flushing to ensure OpenAI processes the audio
                await self._send_message({"type": "input_audio_buffer.commit"})
                logger.info("✅ Committed audio buffer after flush")
            else:
                # Not enough audio, just send what we have
                audio_b64 = base64.b64encode(self._audio_buffer).decode('utf-8')
                await self._send_message({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                })
                self._audio_buffer = b""
                logger.info(f"✅ Flushed {remaining} bytes (less than 100ms, no commit)")
        else:
            # Buffer is empty - don't commit (OpenAI will reject empty commits)
            logger.info("⚠️ Flush requested but buffer is empty - skipping commit")
    
    async def get_response_audio(self) -> Optional[bytes]:
        """Get audio response from OpenAI."""
        try:
            audio = await asyncio.wait_for(self.response_audio_queue.get(), timeout=0.01)
            return audio
        except asyncio.TimeoutError:
            return None
    
    async def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to OpenAI Realtime API."""
        if not self.connection:
            raise Exception("Realtime connection not established")
        
        # RealtimeConnection.send() is synchronous (not async), run in thread pool
        def send_sync():
            try:
                self.connection.send(message)
            except Exception as e:
                logger.error(f"❌ Error sending message: {e}")
                raise
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, send_sync)
    
    async def _receive_messages(self) -> None:
        """Receive and handle messages from OpenAI Realtime API."""
        if not self.connection:
            logger.error("❌ No connection available for receiving messages")
            return
            
        try:
            loop = asyncio.get_event_loop()
            
            def receive_next():
                try:
                    return self.connection.recv()
                except (ConnectionClosedOK, ConnectionClosed):
                    # Normal connection closure, re-raise to handle in outer loop
                    raise
                except StopIteration:
                    raise
                except Exception as e:
                    logger.error(f"❌ Error receiving message: {e}", exc_info=True)
                    raise
            
            while self._connected:
                try:
                    event = await loop.run_in_executor(self._executor, receive_next)
                    
                    # Convert RealtimeServerEvent to dict for handling
                    if hasattr(event, 'model_dump'):
                        message = event.model_dump(by_alias=True, exclude_none=True)
                    elif hasattr(event, 'dict'):
                        message = event.dict()
                    elif hasattr(event, '__dict__'):
                        message = event.__dict__
                    else:
                        event_type = type(event).__name__
                        logger.warning(f"⚠️ Unknown event type: {event_type}")
                        message = {"type": event_type, "data": str(event)}
                    
                    await self._handle_message(message)
                except (ConnectionClosedOK, ConnectionClosed):
                    # Normal connection closure when client disconnects
                    logger.debug("Connection closed by client")
                    break
                except StopIteration:
                    logger.info("📥 Message stream ended")
                    break
                except Exception as e:
                    logger.error(f"❌ Error receiving message: {e}", exc_info=True)
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"❌ Error in message receiver: {e}", exc_info=True)
        finally:
            self._connected = False
            logger.info("📥 Message receiver stopped")
    
    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message from OpenAI."""
        msg_type = message.get("type")
        
        # Log important message types
        if msg_type in ["response.created", "response.done", "input_audio_buffer.speech_started", "input_audio_buffer.speech_stopped", "error"]:
            logger.info(f"📥 {msg_type}")
        
        if msg_type == "session.created":
            logger.info("✅ Session created by OpenAI")
            self._session_created = True
            self._session_created_event.set()
        
        elif msg_type == "session.updated":
            logger.debug("✅ Session configuration updated by OpenAI")
        
        elif msg_type == "response.audio.delta":
            # Audio response chunk (beta format)
            audio_b64 = message.get("delta", "")
            if audio_b64:
                try:
                    audio_data = base64.b64decode(audio_b64)
                    await self.response_audio_queue.put(audio_data)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to decode audio: {e}", exc_info=True)
        
        elif msg_type == "response.output_audio.delta":
            # Audio response chunk (non-beta format)
            audio_b64 = message.get("delta", "")
            if audio_b64:
                try:
                    audio_data = base64.b64decode(audio_b64)
                    await self.response_audio_queue.put(audio_data)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to decode audio: {e}", exc_info=True)
        
        elif msg_type == "response.output_item.delta":
            # Audio response chunk (non-beta format)
            audio_b64 = message.get("delta", "")
            if audio_b64:
                try:
                    audio_data = base64.b64decode(audio_b64)
                    if len(audio_data) > 0:
                        await self.response_audio_queue.put(audio_data)
                except Exception as e:
                    logger.error(f"⚠️ Failed to decode audio: {e}", exc_info=True)
        
        elif msg_type == "response.created":
            # Reset interruption flag when new response starts
            self._interrupted = False
        
        elif msg_type == "input_audio_buffer.speech_started":
            # Mark as interrupted if there's an active response
            # BUT: Ignore interrupts within AEC grace period (3 seconds after user stopped speaking)
            import time
            current_time = time.time()
            time_since_speech_stopped = current_time - self._last_speech_stopped_time
            
            if time_since_speech_stopped >= self._aec_grace_period_seconds:
                # Enough time has passed, allow interrupt
                self._interrupted = True
                self._last_speech_started_time = current_time
                logger.debug(f"🛑 User interrupted (AEC grace period passed: {time_since_speech_stopped:.1f}s)")
            else:
                # Still in AEC grace period, ignore interrupt
                remaining_time = self._aec_grace_period_seconds - time_since_speech_stopped
                logger.debug(f"🔇 Ignoring interrupt (AEC grace period: {remaining_time:.1f}s remaining)")
        
        elif msg_type == "input_audio_buffer.speech_stopped":
            # After user speech stops, trigger a response (since create_response: False)
            # Track first message for logging
            import time
            self._last_speech_stopped_time = time.time()  # Track when user stopped speaking
            
            if not self._first_user_message_received:
                self._first_user_message_received = True
                logger.info("🎤 First user speech stopped, triggering response...")
            else:
                logger.debug("🎤 User speech stopped, triggering response...")
            
            # Always trigger response after user stops speaking
            await self._send_message({
                "type": "response.create"
            })
            logger.debug(f"✅ Triggered response after user speech stopped (AEC grace period: {self._aec_grace_period_seconds}s)")
        
        elif msg_type == "conversation.item.input_audio_transcription.completed":
            transcript = message.get("transcript", "")
            logger.debug(f"💬 User said: {transcript}")
            
            # Note: We trigger response on speech_stopped, not here, to avoid double-triggering
            # This event is just for logging the transcript
        
        elif msg_type == "response.audio_transcript.delta":
            text = message.get("delta", "")
            if text:
                logger.debug(f"💬 Assistant: {text}")
        
        elif msg_type == "response.audio_transcript.done":
            logger.debug("💬 Assistant finished speaking")
        
        elif msg_type == "response.function_call_arguments.done":
            # Function call completed - execute the tool
            call_id = message.get("call_id")
            function_name = message.get("name")
            arguments_raw = message.get("arguments", {})
            
            # Arguments might come as a string (JSON) or as a dict
            if isinstance(arguments_raw, str):
                try:
                    arguments = json.loads(arguments_raw)
                except json.JSONDecodeError:
                    logger.error(f"❌ Failed to parse function arguments as JSON: {arguments_raw}")
                    arguments = {}
            else:
                arguments = arguments_raw
            
            logger.info(f"🔧 Function call: {function_name}({json.dumps(arguments)})")
            
            # Execute the function
            result = await self._execute_function(function_name, arguments)
            
            # Send result back to OpenAI
            # Function call outputs are sent via conversation.item.create
            # with an item of type "function_call_output"
            await self._send_message({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result)
                }
            })
            logger.debug(f"✅ Sent function call output for {function_name}")

            # Trigger a response so the assistant confirms the tool usage verbally
            # This ensures the user gets feedback about what was done
            await self._send_message({
                "type": "response.create"
            })
            logger.debug(f"✅ Triggered response after function call {function_name}")
        
        elif msg_type == "error":
            error = message.get("error", {})
            error_msg = error.get("message", str(error))
            error_code = error.get("code", "unknown")
            logger.error(f"❌ OpenAI API error [{error_code}]: {error_msg}")
        
        else:
            # Log unknown message types at debug level
            if msg_type not in ["session.updated", "conversation.item.added", "conversation.item.done", 
                               "response.content_part.added", "response.content_part.done",
                               "response.output_audio_transcript.delta", "response.output_audio_transcript.done",
                               "response.output_audio.done", "rate_limits.updated"]:
                logger.debug(f"Unhandled message type: {msg_type}")
    
    async def _execute_function(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a function call.
        
        Args:
            function_name: Name of the function to execute
            arguments: Function arguments
            
        Returns:
            Result dictionary
        """
        if function_name == "disconnect_client":
            if not self._disconnect_callback:
                return {
                    "success": False,
                    "error": "Disconnect callback not available"
                }
            return await execute_disconnect_tool(arguments, self._disconnect_callback)
        
        # Try Home Assistant MCP tools
        ha_client = get_home_assistant_client()
        if ha_client and ha_client.is_connected():
            try:
                result = await ha_client.call_tool(function_name, arguments)
                
                # Format result for OpenAI
                if result.get("success"):
                    if result.get("isError"):
                        return {
                            "success": False,
                            "error": result.get("content", "Unknown error")
                        }
                    else:
                        return {
                            "success": True,
                            "result": result.get("content", "")
                        }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }
            except Exception as e:
                logger.error(f"❌ Error executing Home Assistant tool {function_name}: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        logger.warning(f"⚠️ Unknown function: {function_name}")
        return {
            "success": False,
            "error": f"Unknown function: {function_name}"
        }
    
    async def disconnect(self) -> None:
        """Disconnect from OpenAI API."""
        logger.info("Disconnecting from OpenAI Realtime API...")
        
        self._connected = False
        self._session_created = False
        self._session_created_event.clear()
        self._first_user_message_received = False
        self._last_speech_stopped_time = 0
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.connection:
            try:
                # Close the connection (synchronous, run in executor)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self._executor, self.connection.close)
            except Exception as e:
                logger.warning(f"⚠️ Error closing connection: {e}")
        
        if self._executor:
            self._executor.shutdown(wait=False)
        
            logger.info("✅ Disconnected from OpenAI Realtime API")
    
    def was_interrupted(self) -> bool:
        """Check if user interrupted the current response."""
        if self._interrupted:
            # Reset flag after checking (one-time check)
            self._interrupted = False
            return True
        return False
