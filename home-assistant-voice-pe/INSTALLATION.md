# Installation Guide - Voice PE Hardware with OpenAI Realtime API

This guide will help you set up the Home Assistant Voice PE hardware to work with the OpenAI Realtime API via WebSocket.

## Prerequisites

1. **ESPHome 2025.11.0 or higher** installed (via Poetry: `poetry install` in the parent directory)
2. **Voice PE Hardware** (Home Assistant Voice Pod Edition)
3. **Home Assistant** with the OpenAI Realtime Addon installed and running
4. **WiFi credentials** and **Home Assistant API Key**
5. **Python 3.7+** with `idf-component-manager` package (installed automatically by the script)

## Step-by-Step Installation

### 1. Install Python Dependencies

First, install the required Python dependencies:

```bash
cd /path/to/ha-openai-realtime
poetry install
```

This will install ESPHome and all required dependencies.

**Note:** The `voice_assistant_websocket` component automatically downloads ESP-IDF WebSocket client dependencies using ESPHome's built-in `add_idf_component()` function. No manual download is required.

### 3. Create Secrets File

Copy `secrets.yaml.example` to `secrets.yaml` and fill in the values:

```bash
cp secrets.yaml.example secrets.yaml
```

Edit `secrets.yaml`:
- `wifi_ssid`: Your WiFi network name
- `wifi_password`: Your WiFi password
- `api_encryption_key`: Home Assistant API encryption key
- `ota_password`: Password for OTA updates
- `server_url`: WebSocket URL for the OpenAI Realtime addon (format: `ws://<IP>:<PORT>` or `wss://<IP>:<PORT>` for secure connections)

**Example:**
```yaml
wifi_ssid: "MyWiFi"
wifi_password: "MyPassword"
api_encryption_key: "YourAPIKey"
ota_password: "MyOTAPassword"
server_url: "ws://192.168.1.10:8080"  # Use ws:// for WebSocket or wss:// for secure WebSocket
```

**Important:** Use `ws://` for unencrypted WebSocket connections or `wss://` for secure WebSocket (TLS) connections.

### 4. Adjust Device Name (Optional)

If desired, change the device name in `voice_pe_config_websocket.yaml`:

```yaml
esphome:
  name: ha-voice-openai  # Change this if desired
```

### 5. Compile

**Note:** The WebSocket component automatically downloads and includes all required ESP-IDF components during compilation.

```bash
# From the project directory
cd /path/to/home-assistant-voice-pe

# Compile
poetry run esphome compile voice_pe_config_websocket.yaml

# Or if ESPHome is globally installed
esphome compile voice_pe_config_websocket.yaml
```

If you encounter compilation errors about missing WebSocket client headers:
1. Ensure ESPHome can download the IDF components (check internet connection)
2. Check that ESPHome can access GitHub to download components
3. Try cleaning and rebuilding: `esphome clean voice_pe_config_websocket.yaml && esphome compile voice_pe_config_websocket.yaml`

```bash
# From the parent directory with Poetry
cd /path/to/ha-openai-realtime
poetry run esphome compile home-assistant-voice-pe/voice_pe_config_websocket.yaml

# Or directly (if ESPHome is globally installed)
esphome compile home-assistant-voice-pe/voice_pe_config_websocket.yaml
```

### 6. Flash to Device

**Option A: USB Connection**
```bash
poetry run esphome upload home-assistant-voice-pe/voice_pe_config_websocket.yaml --device /dev/cu.usbmodem101
```

**Option B: OTA (Over-The-Air)**
- After the first USB upload, you can do future updates over OTA
- The device must be connected to Home Assistant
- Use: `esphome upload home-assistant-voice-pe/voice_pe_config_websocket.yaml` (automatically selects OTA if available)

## Third-Party Components and Licenses

### ESP WebSocket Client

The `voice_assistant_websocket` component automatically downloads the **ESP WebSocket Client** library during compilation using ESPHome's `add_idf_component()` function.

**Source:**
- Repository: https://github.com/espressif/esp-protocols
- Component: `components/esp_websocket_client`
- Version: websocket-v1.6.0
- Automatically downloaded by ESPHome during compilation

**License:**
Apache License 2.0

**Copyright:**
Copyright (c) Espressif Systems (Shanghai) CO LTD

**How It's Included:**
The component is automatically downloaded and registered by ESPHome using the `add_idf_component()` function in the component's `__init__.py`. This is the recommended approach for ESP-IDF components in ESPHome (see [ESPHome PR #4000](https://github.com/esphome/esphome/pull/4000)).

## Features

### 🎤 Voice Assistant with OpenAI Realtime API

The device connects to your OpenAI Realtime API server via **WebSocket** for real-time voice interactions. The WebSocket connection provides:
- Real-time bidirectional audio streaming
- Low latency communication
- Reliable connection handling with automatic reconnection

The assistant can:
- Listen to your voice commands
- Process them with OpenAI's advanced language models
- Respond with natural speech
- Integrate with Home Assistant via MCP (Model Context Protocol)

### 🔇 Wake Word Detection

The device supports multiple wake words:
- **"Okay Nabu"** (default, high accuracy)
- **"Hey Jarvis"**
- **"Hey Mycroft"**

Wake word detection runs continuously and can start the voice assistant automatically.

### 🔊 Wake Sound Feedback

When a wake word is detected, the device can play a customizable sound file (`wake_sound.flac`) to provide audio feedback. This can be enabled/disabled via the "Wake sound" switch in Home Assistant.

### 🎚️ Auto Gain Control (AGC)

The XMOS XU316 chip includes hardware-based Auto Gain Control that automatically adjusts microphone sensitivity to maintain consistent audio levels, regardless of distance or speaking volume.

### 🔁 Acoustic Echo Cancellation (AEC)

Hardware-based echo cancellation prevents the microphone from picking up audio from the speaker, ensuring clean voice input even when the assistant is speaking.

### 🎨 LED Ring Feedback

The 12-LED ring provides visual feedback for various states:
- **Blue twinkle**: Initialization/Improv BLE mode
- **Red twinkle**: No connection to Home Assistant
- **Blue pulse**: Voice assistant active and connected
- **Green/Blue rotation**: Voice assistant listening/thinking
- **Red pulse**: Error state
- **Custom colors**: Adjustable via Home Assistant

### 🎛️ Center Button Controls

- **Single click**: Start/stop voice assistant
- **Double click**: Event for automations
- **Triple click**: Event for automations
- **Long press**: Event for automations

### 🔇 Hardware Mute Switch

The physical mute switch on the side of the device disables the microphone for privacy.

### 🔊 Audio Jack Detection

The device automatically detects when headphones are plugged in and adjusts audio routing accordingly.

### 📊 Automatic Stop

The voice assistant automatically stops after 20 seconds of inactivity (no speaker output and no user speech), helping to conserve resources.

### 🎵 Audio Ducking

When the voice assistant is active, media playback volume is automatically reduced by 20dB to ensure clear voice responses.

### 🔊 Volume Control

Volume can be adjusted via the rotary encoder (dial) on the device or through Home Assistant.

## Usage

### Starting the Voice Assistant

**Method 1: Wake Word**
- Say one of the configured wake words ("Okay Nabu", "Hey Jarvis", or "Hey Mycroft")
- The device will play the wake sound (if enabled) and start listening

**Method 2: Center Button**
- Press the center button once to start/stop the voice assistant

### During a Conversation

- Speak naturally - the assistant listens continuously
- The LED ring shows the current state (listening, thinking, responding)
- You can interrupt the assistant by speaking while it's responding
- The assistant automatically stops after 20 seconds of inactivity

### Stopping the Voice Assistant

- Press the center button again
- Wait for automatic timeout (20 seconds of inactivity)
- Use the hardware mute switch to disable the microphone

## Troubleshooting

### Compilation Errors

**Error: "voice_assistant_websocket component not found"**
- Ensure the `esphome/components` directory is in the correct location
- The `external_components` configuration should find the local component
- Check that `voice_assistant_websocket` directory exists in `esphome/components/`

**Error: "esp_websocket_client.h: No such file or directory"**
- Ensure ESPHome can automatically download IDF components (they're downloaded during compilation)
- Verify that the component's `__init__.py` is calling `add_idf_component()` correctly
- Check your internet connection - ESPHome needs to download components from GitHub
- Try cleaning and rebuilding: `esphome clean voice_pe_config_websocket.yaml && esphome compile voice_pe_config_websocket.yaml`

**Error: "voice_kit component not found"**
- This is normal on first compilation - ESPHome downloads the component automatically
- Ensure you have an internet connection

**Error: "Could not find file 'wake_sound.flac'"**
- Ensure `wake_sound.flac` is in the same directory as `voice_pe_config_websocket.yaml`
- Or update the `wake_word_triggered_sound_file` substitution to point to the correct path

### Connection Issues

**Device doesn't connect to WebSocket server:**
1. Check that `server_url` in `secrets.yaml` is correct (use `ws://` or `wss://` for secure connections)
2. Verify the OpenAI Realtime addon is running and supports WebSocket connections
3. Check logs: `esphome logs home-assistant-voice-pe/voice_pe_config_websocket.yaml`
4. Verify network connectivity between device and server
5. Ensure the server URL includes the correct WebSocket endpoint path (e.g., `/ws` or `/websocket`)

**No audio:**
- Check that the microphone isn't muted (hardware mute switch)
- Check logs for audio errors
- Ensure Voice Kit was correctly initialized
- Verify AGC and AEC settings in the configuration

**Low microphone volume:**
- AGC (Auto Gain Control) is enabled by default and should adjust automatically
- If volume is still too low, check the microphone gain settings in the configuration

### LED Issues

**LED ring not responding:**
- Check that the LED ring is properly connected
- Verify GPIO21 is correctly configured
- Check logs for LED-related errors

**LED shows wrong state:**
- The LED state is managed by the `control_leds` script
- Check that `voice_assistant_phase` global variable is being set correctly

## Advanced Configuration

### Wake Word Sensitivity

Wake word sensitivity can be adjusted via Home Assistant if the entity is available. The configuration supports three levels:
- Slightly sensitive (lowest false positives)
- Moderately sensitive (balanced)
- Very sensitive (catches more wake words, but may have more false positives)

### Audio Format

The device is configured for:
- **Microphone input**: 16kHz, 32-bit stereo (resampled to 24kHz mono for OpenAI)
- **Speaker output**: 48kHz, 32-bit stereo
- **OpenAI API**: 24kHz, 16-bit mono

All conversions are handled automatically by the firmware.

### Server-Side Features

The OpenAI Realtime API server includes:
- **AEC Training**: Sends 300ms of silence before the first audio response to help hardware AEC adapt
- **Rate Limiting**: Sends audio at the correct playback rate to prevent buffer overflow
- **Audio Recording**: Records input/output audio for debugging (saved to `recordings/` directory)

## Support

For issues:
1. Check ESPHome logs: `esphome logs home-assistant-voice-pe/voice_pe_config_websocket.yaml`
2. Check Home Assistant logs (OpenAI Realtime Addon)
3. Check network connectivity between device and server
4. Verify all secrets are correctly configured

## Technical Details

### Hardware Components
- **ESP32-S3** with PSRAM (8MB)
- **XMOS XU316** for audio processing (AEC, AGC)
- **AIC3204** audio codec
- **WS2812** LED ring (12 LEDs)
- **I2S** audio interface for microphone and speaker

### Software Components
- **ESPHome 2025.11.0+** framework
- **ESP-IDF** framework
- **Custom `voice_assistant_websocket` component** for WebSocket communication
- **esp_websocket_client** (ESP-Protocols) for WebSocket client functionality
- **microWakeWord** for wake word detection
- **ESPHome audio pipeline** for audio processing

### Audio Pipeline
1. Microphone → I2S (16kHz, 32-bit stereo)
2. Voice Kit (hardware AEC, AGC processing)
3. microWakeWord (wake word detection)
4. voice_assistant_websocket (resample to 24kHz mono, send via WebSocket)
5. Receive audio from WebSocket (24kHz, 16-bit mono)
6. Resampler (24kHz → 48kHz)
7. I2S Speaker (48kHz, 32-bit stereo)

**Note:** The component uses hardware AEC (Voice Kit) for echo cancellation. The XMOS XU316 chip provides hardware-based Acoustic Echo Cancellation and Auto Gain Control.
