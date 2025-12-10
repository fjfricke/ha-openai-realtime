# OpenAI Realtime Voice Agent

Voice control system for Home Assistant using OpenAI Realtime API with ESP32/ESP32-S3 devices.

## Components

This repository contains two main components:

- **Server** (`openai_realtime_voice_agent/`): Home Assistant addon that provides OpenAI Realtime API integration and WebSocket server for ESP32 devices
- **Client** (`home-assistant-voice-pe/`): ESPHome configuration for ESP32/ESP32-S3 devices with custom WebSocket component

## Documentation

- **Server Installation**: See [`openai_realtime_voice_agent/README.md`](openai_realtime_voice_agent/README.md)
- **Client Installation**: See [`home-assistant-voice-pe/README.md`](home-assistant-voice-pe/README.md)

## Quick Start

1. **Install the Server Addon**: Follow the [server documentation](openai_realtime_voice_agent/README.md)
2. **Configure ESP32 Device**: Follow the [client documentation](home-assistant-voice-pe/README.md)

## Known Issues

The endpoint `http://supervisor/core/api/mcp` is not working. You need to:
- Create a long-lived token in Home Assistant
- Use it in the addon configuration
- Set the Home Assistant MCP URL to `http://localhost:8123/api/mcp` (or your Home Assistant URL). The MCP Server needs to be enabled in Home Assistant.

## License

MIT License - see [LICENSE](LICENSE) file for details.

**Note**: This project uses [Pipecat](https://github.com/pipecat-ai/pipecat) which is licensed under BSD 2-Clause License. See the Pipecat repository for license details.
