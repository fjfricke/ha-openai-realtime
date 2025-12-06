# Migration to Pipecat - Implementation Notes

This document notes the migration from custom implementations to Pipecat framework.

## Changes Made

### 1. Dependencies
- Updated `pyproject.toml` to use `pipecat-ai[mcp,openai]` instead of individual packages
- Removed direct dependencies on `openai`, `websockets`, `numpy`, and `mcp` packages (now handled by Pipecat)

### 2. WebSocket Transport
- **New file**: `app/websocket_transport.py`
- Created custom `WebSocketTransport` class extending Pipecat's `FrameProcessor`
- Handles ESP32 device connections, control messages (ping/pong, flush, disconnect), and audio streaming
- Preserves 24kHz, 16-bit, mono PCM audio format

### 3. OpenAI Realtime Service
- **Modified**: `app/main.py`
- Replaced custom `OpenAIRealtimeClient` with Pipecat's `OpenAIRealtimeService`
- VAD configuration (threshold, prefix padding, silence duration) preserved
- Tool system integration maintained

### 4. MCP Client
- **New file**: `app/mcp_service.py`
- Replaced custom `HomeAssistantMCPClient` with Pipecat's `MCPClient` using `StreamableHttpParameters`
- Streamable HTTP transport configured with Home Assistant URL and authentication

### 5. Audio Recording
- **New file**: `app/recording_processor.py`
- Created `AudioRecordingProcessor` frame processor for audio recording
- Integrates with existing `AudioRecorder` utility
- Records both input and output audio streams

### 6. Disconnect Tool
- **Modified**: `app/disconnect_tool.py`
- Updated to work with Pipecat's tool system
- Tool definition format maintained for OpenAI compatibility

### 7. Main Application
- **Modified**: `app/main.py`
- Refactored to use Pipecat's `Pipeline` and `PipelineRunner`
- Service initialization and pipeline construction updated
- Environment variable configuration preserved

## Files Removed/Deprecated
- `app/websocket_server.py` - Replaced by `websocket_transport.py`
- `app/openai_client.py` - Replaced by Pipecat's OpenAI Realtime service
- `app/home_assistant_mcp_client.py` - Replaced by `mcp_service.py`

## Potential API Adjustments

The implementation makes assumptions about Pipecat's API structure. When testing with Pipecat installed, you may need to adjust:

1. **Import paths**: The actual module structure may differ. Check Pipecat documentation for correct imports.
2. **Pipeline construction**: Pipeline structure and processor connections may need adjustment.
3. **Service configuration**: OpenAI Realtime service parameters may have different names or structure.
4. **Tool registration**: MCP tool registration and disconnect tool handling may need refinement.
5. **Frame processing**: Frame direction and processing flow may need adjustment based on actual Pipecat behavior.

## Testing Checklist

- [ ] Install Pipecat: `pip install 'pipecat-ai[mcp,openai]'`
- [ ] Verify WebSocket connections from ESP32 devices
- [ ] Test MCP tool execution through Home Assistant
- [ ] Verify audio recording functionality
- [ ] Test disconnect tool functionality
- [ ] Verify VAD settings are properly applied
- [ ] Test control messages (ping/pong, flush)

## Notes

- The WebSocket transport is custom-built as Pipecat may not have a built-in WebSocket server transport
- Audio recording uses a shared recorder instance to handle both input and output streams
- Tool execution (especially disconnect tool) may need additional integration with Pipecat's tool handling system





