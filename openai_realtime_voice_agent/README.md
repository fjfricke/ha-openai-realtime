# OpenAI Realtime Voice Agent - Home Assistant Addon

A Home Assistant addon that provides voice control using OpenAI's Realtime API with WebSocket support for ESP32 devices.

## Features

- **OpenAI Realtime API Integration**: Real-time voice conversations with OpenAI's latest voice model
- **WebSocket Support**: Simple WebSocket protocol for ESP32 devices (no complex WebRTC setup needed)
- **ESP32 Device Support**: Connect ESP32-based voice devices via WebSocket
- **Wake Word Detection**: Support for on-device wake word detection on ESP32-S3
- **Server VAD**: Automatic speech detection and turn-taking handled by OpenAI

## Installation

### Prerequisites

- Home Assistant (Supervisor) installation
- OpenAI API key with access to Realtime API
- ESP32 or ESP32-S3 device with I2S microphone/speaker (for voice device)

### Installation Steps

1. **Add the Addon Repository** (if using a repository):
   - Go to Home Assistant → Settings → Add-ons → Add-on Store
   - Click the three dots (⋮) → Repositories
   - Add the repository URL

2. **Install the Addon**:
   - Find "OpenAI Realtime Voice Agent" in the addon store
   - Click "Install"
   - Wait for installation to complete

3. **Configure the Addon**:
   - Click "Configuration" tab
   - Set your OpenAI API key
   - Adjust WebSocket port if needed (default: 8080)

4. **Start the Addon**:
   - Click "Start"
   - Check logs to ensure it started successfully

## Configuration

### Addon Configuration

The addon can be configured via the Home Assistant addon configuration UI or by editing the addon's `config.json`:

```json
{
  "openai_api_key": "sk-...",
  "websocket_port": 8080,
  "ha_access_token": "",
  "ha_mcp_url": "http://supervisor/core/api/mcp"
}
```

**Configuration Options**:
- `openai_api_key`: Your OpenAI API key (required)
- `websocket_port`: Port for WebSocket connections (default: 8080)
- `ha_access_token`: Home Assistant long-lived access token (optional, enables MCP integration)
- `ha_mcp_url`: Home Assistant MCP Server URL (optional, default: `http://supervisor/core/api/mcp`)

## ESPHome Device Setup

### Hardware Requirements

- ESP32 or ESP32-S3 board
- I2S microphone (e.g., INMP441, SPH0645)
- I2S amplifier/speaker (e.g., MAX98357A)
- Optional: Status LED, button

### ESPHome Configuration

1. Copy `esphome_config.yaml.example` to your ESPHome configuration directory
2. Edit the configuration:
   - Replace `<ADDON_IP>` with your Home Assistant IP address
   - Replace `<WEBSOCKET_PORT>` with the port from addon config (default: 8080)
   - Adjust GPIO pins based on your hardware
   - Configure WiFi credentials in `secrets.yaml`

3. **For ESP32-S3** (with wake word support):
   - Uncomment the `wake_word` section
   - Choose a wake word model
   - Set `use_wake_word: true` in voice_assistant config

4. **For ESP32** (without wake word):
   - Comment out the `wake_word` section
   - Set `use_wake_word: false` in voice_assistant config
   - Use the manual trigger button instead

5. Flash the device:
   ```bash
   esphome run your-config.yaml
   ```

### Example ESPHome Configuration

Example configurations are available in the `home-assistant-voice-pe/` folder:

1. **Home Assistant Voice PE**: `home-assistant-voice-pe/voice_pe_config.yaml` - For the official Home Assistant Voice PE hardware
2. **Generic ESP32/ESP32-S3**: `home-assistant-voice-pe/esphome_config_ha_voice_improved.yaml.example` - For generic ESP32 boards with I2S audio

**Note**: ESPHome's `voice_assistant` component currently supports WebRTC. For WebSocket support, you need to use the custom `voice_assistant_websocket` component provided in this repository. The server is ready to accept WebSocket connections at `ws://<ADDON_IP>:<WEBSOCKET_PORT>`.

#### Using the Custom Component

1. Copy the `voice_assistant_websocket` component to your ESPHome custom components directory:
   ```bash
   cp -r ../home-assistant-voice-pe/esphome/components/voice_assistant_websocket ~/.esphome/custom_components/
   ```
   
   Or if you're working from the repository root:
   ```bash
   cp -r home-assistant-voice-pe/esphome/components/voice_assistant_websocket ~/.esphome/custom_components/
   ```

2. Use one of the example configurations as a starting point
3. Replace `<ADDON_IP>` and `<WEBSOCKET_PORT>` with your server details
4. Adjust GPIO pins if needed for your hardware

## Usage

### Voice Control

Once configured:

1. **With Wake Word** (ESP32-S3):
   - Say the wake word (e.g., "Hi ESP")
   - Wait for confirmation (LED flash)
   - Speak your command
   - The assistant will respond via speaker

2. **Manual Trigger** (ESP32 or testing):
   - Press the trigger button
   - Speak your command
   - The assistant will respond via speaker

### Example Commands

- "What's the weather like?"
- "Tell me a joke"
- "What time is it?"

The assistant uses OpenAI's Realtime API with server-side voice activity detection (VAD) for natural conversation flow.

## Testing

### Browser Testing

1. Open `test/websocket-simple-test.html` in your browser
2. Click "Connect & Start Call"
3. Allow microphone access
4. Speak and hear responses in real-time

## Troubleshooting

### Addon Won't Start

1. Check logs: Home Assistant → Add-ons → OpenAI Realtime Voice Agent → Logs
2. Verify OpenAI API key is correct
3. Ensure port 8080 is not in use by another service

### ESP32 Device Won't Connect

1. Verify device is on the same network as Home Assistant
2. Check that WebSocket port is accessible (firewall rules)
3. Verify the URL in ESPHome config matches addon IP and port
4. Check ESPHome logs for connection errors

### No Audio Response

1. Verify OpenAI API key has Realtime API access
2. Check addon logs for OpenAI connection errors
3. Verify audio hardware is properly configured in ESPHome
4. Test with browser test page first

## Development

### Project Structure

```
.
├── config.yaml          # Addon metadata and options
├── Dockerfile           # Container build instructions
├── pyproject.toml      # Python dependencies (Poetry)
├── poetry.lock         # Locked dependencies
├── root/
│   ├── run.sh         # Startup script
│   └── apparmor.txt   # Security profile
└── app/
    ├── main.py        # Application entry point
    ├── openai_client.py    # OpenAI Realtime API client
    └── websocket_server.py  # WebSocket server for ESP32 devices
```

### Building Locally

1. Clone the repository
2. Build the Docker image:
   ```bash
   docker build -t ha-openai-realtime .
   ```
3. Run locally:
   ```bash
   docker run -e OPENAI_API_KEY=sk-... -e WEBSOCKET_PORT=8080 -p 8080:8080 ha-openai-realtime
   ```

## Security Considerations

- OpenAI API key is stored securely in Home Assistant addon configuration
- AppArmor profile restricts addon permissions
- WebSocket connections are validated

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or pull request.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the logs in Home Assistant
- Review the troubleshooting section above
