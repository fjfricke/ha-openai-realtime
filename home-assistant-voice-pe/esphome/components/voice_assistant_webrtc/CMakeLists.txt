# Register this component
# Note: esp_peer and esp_afe_sr are added via add_idf_component in __init__.py
# ESPHome will automatically download and register them

idf_component_register(
    SRCS
        "voice_assistant_webrtc.cpp"
        "pipecat_signaling.cpp"
    INCLUDE_DIRS
        "."
    REQUIRES
        esphome
        microphone
        speaker
        http_client
        espressif__esp_peer  # WebRTC peer connection library (must match directory name from component registry)
        esp_afe_sr  # Audio Front-End for AEC, NS, AGC
)
