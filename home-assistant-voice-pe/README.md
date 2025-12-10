# OpenAI Realtime Voice Agent - Client

ESPHome configuration for ESP32/ESP32-S3 devices to connect to the OpenAI Realtime Voice Agent server.
It is mainly based on https://github.com/esphome/home-assistant-voice-pe.

## Prerequisites

- ESPHome 2025.11.0 or higher
- Voice PE Hardware (Home Assistant Voice Pod Edition) or compatible ESP32-S3 device
- Home Assistant with the OpenAI Realtime Addon installed and running
- Python 3.11+ with Poetry

## Installation

### 1. Install Dependencies

```bash
cd home-assistant-voice-pe
poetry install
```

### 2. Configure Secrets

Copy `secrets.yaml.example` to `secrets.yaml` and fill in your values:

```bash
cp secrets.yaml.example secrets.yaml
```

Edit `secrets.yaml`:
- `wifi_ssid`: Your WiFi network name
- `wifi_password`: Your WiFi password
- `api_encryption_key`: Home Assistant API encryption key
- `ota_password`: Password for OTA updates
- `server_url`: WebSocket URL for the OpenAI Realtime addon (e.g., `ws://homeassistant.local:8080`)

### 3. Compile and Flash

```bash
# Compile
poetry run esphome compile voice_pe_config.yaml

# Flash via USB
poetry run esphome upload voice_pe_config.yaml --device /dev/cu.usbmodem101 (or the correct device name for your device. See `ls /dev/cu.*` for the correct device name.)

# Or flash via OTA (after first USB upload)
poetry run esphome upload voice_pe_config.yaml
```

## Configuration

The main configuration file is `voice_pe_config.yaml`. Key settings:

- Device name: Change `esphome.name` if desired
- Wake words: Configured wake words ("Okay Nabu", "Hey Jarvis", "Hey Mycroft")
- Audio settings: Microphone and speaker configuration
- LED ring: Visual feedback for device states

## Features

- **Voice Assistant**: Real-time voice interaction with OpenAI Realtime API
- **Wake Word Detection**: Multiple wake words supported
- **LED Feedback**: Visual status indicators
- **Hardware Controls**: Button controls and mute switch
- **Auto Gain Control**: Hardware-based AGC for consistent audio levels
- **Echo Cancellation**: Hardware-based AEC prevents feedback

## Troubleshooting

### Connection Issues

- **Device doesn't connect**: Check `server_url` in `secrets.yaml` matches your addon configuration
- **No audio**: Check hardware mute switch and verify microphone initialization in logs
- **View logs**: `poetry run esphome logs voice_pe_config.yaml`

