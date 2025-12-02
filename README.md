# OpenAI Realtime Voice Agent

This repository contains both the Home Assistant addon and the ESPHome client configuration for the OpenAI Realtime Voice Agent system.

## Repository Structure

```
.
├── openai_realtime_voice_agent/    # Home Assistant Addon
│   ├── config.yaml                # Addon configuration
│   ├── Dockerfile                 # Container build instructions
│   ├── pyproject.toml             # Python dependencies
│   ├── app/                       # Application code
│   ├── root/                      # Addon runtime files
│   └── README.md                  # Addon documentation
│
└── home-assistant-voice-pe/       # ESPHome Client Configuration
    ├── voice_pe_config.yaml       # Main ESPHome config for Voice PE hardware
    ├── esphome_config_ha_voice_improved.yaml.example  # Example config
    ├── esphome/                   # Custom ESPHome components
    ├── secrets.yaml.example       # Secrets template
    └── INSTALLATION.md            # Client installation guide
```

## Components

### Home Assistant Addon (`openai_realtime_voice_agent/`)

The server-side addon that runs in Home Assistant and provides:
- OpenAI Realtime API integration
- WebSocket server for ESP32 devices
- Home Assistant MCP integration for device control

See [`openai_realtime_voice_agent/README.md`](openai_realtime_voice_agent/README.md) for installation and configuration.

### ESPHome Client (`home-assistant-voice-pe/`)

The client-side configuration for ESP32/ESP32-S3 devices, including:
- Custom `voice_assistant_websocket` component
- Configuration for Home Assistant Voice PE hardware
- Example configurations for other ESP32 devices

See [`home-assistant-voice-pe/INSTALLATION.md`](home-assistant-voice-pe/INSTALLATION.md) for client setup.

## Quick Start

1. **Install the Addon**:
   - Copy `openai_realtime_voice_agent/` to your Home Assistant `addons/` directory
   - Or add this repository as an addon repository
   - Configure and start the addon

2. **Configure ESP32 Device**:
   - Copy the custom component from `home-assistant-voice-pe/esphome/components/` to your ESPHome custom components
   - Use `voice_pe_config.yaml` or the example config as a starting point
   - Flash to your ESP32 device

## Documentation

- **Addon Documentation**: [`openai_realtime_voice_agent/README.md`](openai_realtime_voice_agent/README.md)
- **Client Installation**: [`home-assistant-voice-pe/INSTALLATION.md`](home-assistant-voice-pe/INSTALLATION.md)
- **Poetry Setup**: [`POETRY_SETUP.md`](POETRY_SETUP.md)
- **Migration Guide**: [`MIGRATION_TO_POETRY.md`](MIGRATION_TO_POETRY.md)

## License

MIT

## Third-Party Components and Licenses

This project includes third-party components with their own licenses:

### ESP WebSocket Client

The ESPHome client component includes files from the **ESP WebSocket Client** library:

- **Source**: https://github.com/espressif/esp-protocols
- **Component**: `components/esp_websocket_client`
- **License**: Apache License 2.0
- **Copyright**: Copyright (c) 2015-2025 Espressif Systems (Shanghai) CO LTD
- **Location**: `home-assistant-voice-pe/esphome/components/voice_assistant_websocket/esp_websocket_client.*` and `esp_websocket_client/` directory

A copy of the Apache License 2.0 is included in `home-assistant-voice-pe/esphome/components/voice_assistant_websocket/esp_websocket_client/LICENSE`.

For more details, see:
- [`home-assistant-voice-pe/esphome/components/voice_assistant_websocket/README.md`](home-assistant-voice-pe/esphome/components/voice_assistant_websocket/README.md#third-party-components-and-licenses)
- [`home-assistant-voice-pe/INSTALLATION.md`](home-assistant-voice-pe/INSTALLATION.md#third-party-components-and-licenses)
