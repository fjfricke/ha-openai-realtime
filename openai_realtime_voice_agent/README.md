# OpenAI Realtime Voice Agent - Server

Home Assistant addon that provides OpenAI Realtime API integration with WebSocket support for ESP32 devices.

## Installation

### Option 1: Add Repository (Recommended)

1. In Home Assistant, go to **Supervisor** → **Add-on Store**
2. Click the **⋮** menu (top right) → **Repositories**
3. Add this repository: `https://github.com/fjfricke/ha-openai-realtime`
4. Find **OpenAI Realtime Voice Agent** in the addon store and install it

### Option 2: Manual Installation

1. Copy the `openai_realtime_voice_agent/` folder to your Home Assistant `addons/` directory
2. Restart Home Assistant Supervisor
3. Install the addon from **Supervisor** → **Add-on Store** → **Local Add-ons**

## Configuration

Configure the addon in Home Assistant:

1. Go to **Supervisor** → **Add-on Store** → **OpenAI Realtime Voice Agent** → **Configuration**
2. Set the following required options:
   - `openai_api_key`: Your OpenAI API key
   - `websocket_port`: Port for WebSocket connections (default: 8080)
   - `ha_mcp_url`: Home Assistant MCP URL (e.g., `http://localhost:8123/api/mcp`)
   - `longlived_token`: Home Assistant long-lived access token

3. Optional settings:
   - `vad_threshold`: Voice activity detection threshold (0.0-1.0, default: 0.5)
   - `instructions`: Custom instructions for the AI assistant
   - `enable_recording`: Enable audio recording for debugging (default: false)

4. Start the addon

## Features

- OpenAI Realtime API integration
- WebSocket server for ESP32 devices
- Home Assistant MCP (Model Context Protocol) integration
- Voice activity detection
- Session management with automatic reuse
- Optional audio recording for debugging

## Troubleshooting

- **MCP connection issues**: Ensure you're using a long-lived token and the correct MCP URL (`http://homeassistant.local:8123/api/mcp`)
- **WebSocket connection**: Check that the port is accessible and not blocked by firewall
- **Check logs**: View addon logs in Home Assistant Supervisor
