# Installation Guide - Home Assistant Addon

This guide explains how to install and test the OpenAI Realtime Voice Agent addon in Home Assistant.

## Prerequisites

- Home Assistant OS, Supervised, or Container (with addon support)
- OpenAI API key
- (Optional) Home Assistant Long-Lived Access Token for MCP integration

## Installation Steps

### 1. Locate Your Home Assistant Config Directory

The location depends on your Home Assistant installation type:

- **Home Assistant OS**: `/config/addons/`
- **Home Assistant Supervised**: `/config/addons/` or `/usr/share/hassio/addons/`
- **Home Assistant Container**: Usually not directly supported, but you can use an addon repository

### 2. Copy the Addon Directory

Copy the entire `openai_realtime_voice_agent` directory to your Home Assistant addons directory:

```bash
# Example for Home Assistant OS (SSH addon or direct access)
cp -r /path/to/ha-openai-realtime/openai_realtime_voice_agent /config/addons/
```

**Important**: The directory name must match the slug in `config.yaml` (`openai_realtime_voice_agent`).

### 3. Verify Required Files

Make sure the following files are present in `/config/addons/openai_realtime_voice_agent/`:

```
openai_realtime_voice_agent/
├── config.yaml          # Addon configuration
├── Dockerfile           # Container build instructions
├── pyproject.toml       # Python dependencies
├── poetry.lock          # Dependency lock file (if exists)
├── app/                 # Application code
│   ├── __init__.py
│   ├── main.py
│   ├── openai_client.py
│   ├── websocket_server.py
│   ├── audio_recorder.py
│   ├── disconnect_tool.py
│   └── home_assistant_mcp_client.py
└── root/                # Runtime files
    ├── run.sh
    └── apparmor.txt
```

### 4. Restart Home Assistant

After copying the addon, restart Home Assistant to make it available:

- **Home Assistant OS**: Go to Settings → System → Restart
- **Home Assistant Supervised**: `sudo systemctl restart hassio-supervisor.service`
- Or restart via the UI

### 5. Install the Addon

1. Go to **Settings** → **Add-ons** → **Add-on Store**
2. Click the three dots (⋮) in the top right
3. Select **Repositories** (if you're using a repository) OR
4. The addon should appear in **Local add-ons** section
5. Click on **OpenAI Realtime Voice Agent**
6. Click **Install**

### 6. Configure the Addon

Before starting, configure the addon:

1. Click on the addon
2. Go to the **Configuration** tab
3. Fill in the required settings:

```yaml
openai_api_key: "sk-your-openai-api-key-here"
websocket_port: 8080
supervisor_token: "your-supervisor-token"  # Optional, for MCP integration
ha_mcp_url: "http://supervisor/core/api/mcp"      # Optional, default value
```

**Getting the Supervisor Token:**
- In Home Assistant addons, the supervisor token is typically available automatically via the `SUPERVISOR_TOKEN` environment variable
- If you need to use a custom token, you can create a Long-Lived Access Token:
  1. Go to your Home Assistant profile (click your user icon)
  2. Scroll down to **Long-lived access tokens**
  3. Click **Create Token**
  4. Give it a name (e.g., "OpenAI Realtime Addon")
  5. Copy the token and paste it in the `supervisor_token` field

### 7. Start the Addon

1. Go to the **Info** tab
2. Click **Start**
3. Check the **Log** tab for any errors

### 8. Verify It's Running

1. Check the **Log** tab - you should see:
   ```
   ✅ WebSocket server started on ws://0.0.0.0:8080
   ✅ Connected to OpenAI Realtime API
   ```

2. Test the WebSocket connection using the test HTML file:
   - Copy `test/websocket-simple-test.html` to a web server
   - Or open it directly in a browser (may have CORS issues)
   - Update the `WS_URL` in the HTML file to match your Home Assistant IP:
     ```javascript
     const WS_URL = 'ws://YOUR_HA_IP:8080';
     ```

## Testing

### Option 1: Using the Test HTML File

1. Open `test/websocket-simple-test.html` in a browser
2. Update the WebSocket URL to your Home Assistant IP
3. Click "Connect & Start Call"
4. Grant microphone permissions
5. Speak into your microphone
6. You should hear the assistant respond

### Option 2: Using ESP32 Device

1. Configure your ESP32 device with the WebSocket URL:
   ```yaml
   server_url: "ws://YOUR_HA_IP:8080"
   ```
2. Flash the device
3. The device should connect automatically
4. Use wake word or button to start voice assistant

## Troubleshooting

### Addon Not Appearing

- Verify the directory is in the correct location
- Check that `config.yaml` exists and is valid YAML
- Restart Home Assistant
- Check Supervisor logs: `ha supervisor logs`

### Addon Won't Start

- Check the **Log** tab for errors
- Verify `OPENAI_API_KEY` is set correctly
- Check that port 8080 is not in use by another addon
- Verify all files are present (especially `app/` directory)

### WebSocket Connection Fails

- Verify the addon is running (check **Info** tab)
- Check firewall rules (port 8080 should be accessible)
- Verify the WebSocket URL format: `ws://IP:PORT` (not `http://`)
- Check addon logs for connection errors

### No Audio

- Check microphone permissions (for browser test)
- Verify audio format settings
- Check addon logs for audio processing errors
- Verify OpenAI API key is valid and has credits

## Configuration Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `openai_api_key` | Yes | - | Your OpenAI API key |
| `websocket_port` | No | 8080 | Port for WebSocket server |
| `supervisor_token` | No | - | Supervisor token for MCP integration |
| `ha_mcp_url` | No | `http://supervisor/core/api/mcp` | Home Assistant MCP endpoint |

## Next Steps

After the addon is running:

1. Configure your ESP32 device (see `home-assistant-voice-pe/INSTALLATION.md`)
2. Test voice interactions
3. Set up Home Assistant automations if needed
4. Monitor recordings in the `recordings/` directory (if enabled)

## Uninstallation

1. Go to **Settings** → **Add-ons**
2. Find **OpenAI Realtime Voice Agent**
3. Click **Uninstall**
4. Optionally remove the directory: `rm -r /config/addons/openai_realtime_voice_agent`

