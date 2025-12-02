# Voice Assistant WebSocket Component

ESPHome custom component for connecting ESP32 devices to OpenAI Realtime API via WebSocket.

## Features

- WebSocket-based audio streaming (no WebRTC complexity)
- 24kHz input (microphone) and 24kHz output (speaker) - non-beta API requirement
- Integration with ESPHome's `micro_wake_word` component
- Automatic reconnection on disconnect
- Support for interrupt handling

## Requirements

- ESP32 or ESP32-S3 board
- I2S microphone and speaker
- ESPHome with I2S audio support
- OpenAI Realtime API server running (this addon)

## Installation

### Step 1: Download ESP WebSocket Client Files

The component requires ESP WebSocket Client files from the Espressif esp-protocols repository. These files are not included in the repository (see `.gitignore`) and must be downloaded first.

```bash
cd esphome/components/voice_assistant_websocket
python3 download_websocket_client.py
```

This will download the required files:
- `esp_websocket_client.c`
- `esp_websocket_client.h`
- `esp_websocket_client/CMakeLists.txt`
- `esp_websocket_client/LICENSE`

### Step 2: Install the Component

1. Copy the `voice_assistant_websocket` component directory to your ESPHome `custom_components` directory:
   ```
   ~/.esphome/custom_components/voice_assistant_websocket/
   ```

2. Or use it as an external component by adding to your ESPHome config:
   ```yaml
   external_components:
     - source: github://yourusername/ha-openai-realtime
       components: [voice_assistant_websocket]
   ```

**Note:** If using as an external component, you'll need to ensure the ESP WebSocket Client files are downloaded in your ESPHome configuration directory.

## Configuration

See `voice_pe_config.yaml` in the parent directory for a complete example configuration for the Home Assistant Voice PE hardware.

### Basic Configuration

```yaml
voice_assistant_websocket:
  id: voice_assistant_ws
  server_url: "ws://192.168.1.10:8080"
  microphone: !lambda return id(i2s_audio_in);
  speaker: !lambda return id(i2s_audio_out);
```

### With Wake Word

```yaml
micro_wake_word:
  models:
    - model: okay_nabu

automation:
  - alias: "Wake Word to Voice Assistant"
    trigger:
      - platform: micro_wake_word
        wake_word: okay_nabu
    action:
      - voice_assistant_websocket.start:
          id: voice_assistant_ws
```

## API

### Actions

- `voice_assistant_websocket.start` - Start the voice assistant
- `voice_assistant_websocket.stop` - Stop the voice assistant

### Methods (C++)

- `start()` - Start voice assistant
- `stop()` - Stop voice assistant
- `is_running()` - Check if running
- `is_connected()` - Check WebSocket connection status

## Audio Formats

- **Input (Microphone)**: 16kHz, 32-bit stereo (hardware) → resampled to 24kHz, 16-bit mono for OpenAI API
- **Output (Speaker)**: 24kHz, 16-bit mono (from OpenAI) → resampled to 48kHz, 32-bit stereo (hardware)

## Limitations

- I2S audio integration needs to be completed based on ESPHome's actual I2S audio API
- Audio resampling may be needed if hardware sample rates differ
- Memory constraints on ESP32 may limit buffer sizes

## Troubleshooting

1. **Connection fails**: Check server URL and network connectivity
2. **No audio**: Verify I2S pins and audio component configuration
3. **Wake word not working**: Ensure `micro_wake_word` is properly configured for ESP32-S3

## Development Notes

This component uses ESP-IDF's native `esp_websocket_client` API for WebSocket connections. The `esp_websocket_client` library files are downloaded manually using the provided Python script (see Installation section) because ESPHome/PlatformIO does not reliably use the ESP-IDF component manager.

The component integrates with ESPHome's `microphone::Microphone` and `speaker::Speaker` APIs for audio I/O, with automatic resampling to match OpenAI's 24kHz requirement.

## Third-Party Components and Licenses

### ESP WebSocket Client

This component includes files from the **ESP WebSocket Client** library, which is part of the ESP-IDF protocols repository maintained by Espressif Systems.

**Source:**
- Repository: https://github.com/espressif/esp-protocols
- Component: `components/esp_websocket_client`
- Version: 1.6.0 (or latest from master branch)

**Included Files:**
- `esp_websocket_client.c` - WebSocket client implementation (C source)
- `esp_websocket_client.h` - WebSocket client header file
- `esp_websocket_client/CMakeLists.txt` - Build configuration
- `esp_websocket_client/LICENSE` - License file (Apache 2.0)

**License:**
The ESP WebSocket Client is licensed under the **Apache License 2.0**. A copy of the license is included in `esp_websocket_client/LICENSE`.

**Copyright:**
Copyright (c) 2015-2025 Espressif Systems (Shanghai) CO LTD

**How to Download/Update:**
To download or update the ESP WebSocket Client files, use the provided Python script:

```bash
cd esphome/components/voice_assistant_websocket
python3 download_websocket_client.py
```

The script will automatically:
1. Download the latest version from the esp-protocols repository
2. Extract and copy the required files to the correct locations
3. Clean up temporary files

**Manual Update (Alternative):**
If you prefer to update manually, you can use the same commands as shown in the script source code.

**Note:** The ESP WebSocket Client files are included directly in this component because ESPHome/PlatformIO does not reliably use the ESP-IDF component manager. This is a pragmatic solution to ensure the component compiles correctly.

