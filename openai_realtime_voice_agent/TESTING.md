# Local Testing Guide

This guide explains how to test the OpenAI Realtime Voice Agent addon locally on your Mac.

## Prerequisites

1. **Python 3.11+** installed on your Mac
2. **OpenAI API Key** with access to Realtime API

## Quick Test (Direct Python)

The fastest way to test the addon is to run it directly with Python:

1. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Set your OpenAI API key** in `.env` file:
   ```bash
   echo "OPENAI_API_KEY=sk-your-api-key-here" >> .env
   ```

3. **Run the application**:
   ```bash
   python3 app/main.py
   ```

The addon will start and listen on port 8080 for WebSocket connections from ESP32 devices.

## Browser Testing

1. **Start the server**:
   ```bash
   python3 app/main.py
   ```

2. **Open the test page**:
   - Open `test/websocket-simple-test.html` in your browser
   - Click "Connect & Start Call"
   - Allow microphone access
   - Speak and hear responses in real-time

## Testing WebSocket Connection

To test the WebSocket server:

1. **Check server is running**:
   - Server should log: `✅ WebSocket server started on ws://0.0.0.0:8080`

2. **Test with browser**:
   - Use the test page: `test/websocket-simple-test.html`
   - Check browser console (F12) for connection status
   - Audio should be sent and received

3. **Test with ESP32 device**:
   - Configure your ESP32 device with the addon's IP and port
   - The device should connect via WebSocket
   - Check addon logs for connection messages

## Troubleshooting

### Import Errors
If you get import errors, make sure you're in the project root and have installed dependencies:
```bash
pip3 install -r requirements.txt
```

### OpenAI API Errors
- Verify your API key is correct
- Check that your API key has access to Realtime API
- Check OpenAI API status

### Port Already in Use
If port 8080 is already in use:
```bash
export WEBSOCKET_PORT=8081
python3 app/main.py
```

### No Audio
- Check browser console for errors
- Verify microphone permissions are granted
- Check server logs for audio reception
- Ensure OpenAI API key is valid

### Audio Too Fast
- This should be fixed with the audio queue implementation
- If still happening, check browser console for errors

## Development Tips

- **Logs**: Check console output for detailed logging
- **Hot Reload**: Restart the script after code changes
- **ESP32 Testing**: Use the example config in `esphome_config.yaml.example`
- **Browser Testing**: Use `test/websocket-simple-test.html` for quick testing
