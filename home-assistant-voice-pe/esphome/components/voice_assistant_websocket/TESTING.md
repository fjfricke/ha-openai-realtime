# Testing the Voice Assistant WebSocket Component

## Prerequisites

1. ESP32 or ESP32-S3 development board
2. I2S microphone (e.g., INMP441, SPH0645)
3. I2S amplifier/speaker (e.g., MAX98357A)
4. OpenAI Realtime API server running (this addon)
5. ESPHome installed and configured

## Setup Steps

### 1. Install the Component

Copy the component to your ESPHome custom components directory:
```bash
cp -r esphome/components/voice_assistant_websocket ~/.esphome/custom_components/
```

### 2. Configure ESPHome

1. Use the `voice_pe_config.yaml` in the parent directory as a reference
2. Update the configuration:
   - Replace `<ADDON_IP>` with your Home Assistant IP
   - Replace `<WEBSOCKET_PORT>` with the port (default: 8080)
   - Adjust GPIO pins for your hardware
   - Configure WiFi credentials in `secrets.yaml`

### 3. Compile and Flash

```bash
esphome compile your-config.yaml
esphome upload your-config.yaml
```

### 4. Test Connection

1. Check ESPHome logs for WebSocket connection status
2. Verify the device connects to the server
3. Test wake word detection (ESP32-S3) or manual trigger button

## Testing Checklist

- [ ] Component compiles without errors
- [ ] WebSocket connection established
- [ ] Microphone audio is sent to server
- [ ] Server audio is received and played
- [ ] Wake word detection works (ESP32-S3)
- [ ] Manual trigger button works
- [ ] Reconnection works after disconnect
- [ ] Interrupt handling works (server sends interrupt message)

## Debugging

### Enable Debug Logging

In your ESPHome config:
```yaml
logger:
  level: DEBUG
  logs:
    voice_assistant_websocket: DEBUG
```

### Common Issues

1. **WebSocket connection fails**
   - Check server URL format: `ws://IP:PORT`
   - Verify network connectivity
   - Check firewall rules

2. **No audio input**
   - Verify I2S pins are correct
   - Check microphone is powered
   - Verify I2S audio component configuration

3. **No audio output**
   - Verify speaker is connected
   - Check I2S output pins
   - Verify sample rate matches (24kHz)

4. **Wake word not detected**
   - Ensure ESP32-S3 is used (not regular ESP32)
   - Check `micro_wake_word` configuration
   - Verify wake word model is available

## Performance Testing

- Measure latency from wake word to response
- Test with different network conditions
- Verify audio quality at different volumes
- Test concurrent connections (if multiple devices)

## Integration Testing

1. Test with real OpenAI Realtime API server
2. Verify end-to-end voice interaction
3. Test error handling and recovery
4. Verify interrupt handling works correctly

