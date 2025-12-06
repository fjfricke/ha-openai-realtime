#pragma once

#include "esphome.h"
#include "esphome/components/microphone/microphone.h"
#include "esphome/components/speaker/speaker.h"
#include "esphome/core/automation.h"
#ifdef USE_ESP_IDF
#include "esp_http_client.h"
// ESP-Peer WebRTC libraries
#include "esp_peer.h"
#include "esp_peer_types.h"
#include "esp_peer_default.h"  // For esp_peer_get_default_impl()
// ESP-AFE for AEC (Acoustic Echo Cancellation)
#include "esp_afe_sr_models.h"
#include "esp_afe_sr_iface.h"
#include "esp_afe_config.h"
#include "cJSON.h"
#include "pipecat_signaling.h"
#endif
#include <string>
#include <vector>
#include <queue>

namespace esphome {
namespace voice_assistant_webrtc {

enum VoiceAssistantWebRTCState {
  VOICE_ASSISTANT_WEBRTC_IDLE = 0,
  VOICE_ASSISTANT_WEBRTC_STARTING,
  VOICE_ASSISTANT_WEBRTC_SIGNALLING,  // HTTP signalling phase
  VOICE_ASSISTANT_WEBRTC_RUNNING,     // WebRTC connection established
  VOICE_ASSISTANT_WEBRTC_STOPPING,
  VOICE_ASSISTANT_WEBRTC_ERROR,
  VOICE_ASSISTANT_WEBRTC_DISCONNECTED
};

class VoiceAssistantWebRTC : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

  void set_server_base_url(const std::string &url) { this->server_base_url_ = url; }
  void set_microphone(microphone::Microphone *mic) { this->microphone_ = mic; }
  void set_speaker(speaker::Speaker *spkr) { this->speaker_ = spkr; }
  
  void start();
  void stop();
  void request_start();
  
  bool is_running() const { return this->state_ == VOICE_ASSISTANT_WEBRTC_RUNNING; }
  bool is_connected() const { 
#ifdef USE_ESP_IDF
    return this->peer_handle_ != nullptr && 
           this->state_ == VOICE_ASSISTANT_WEBRTC_RUNNING;
#else
    return false;
#endif
  }
  
  void set_state_callback(std::function<void(VoiceAssistantWebRTCState)> &&callback) {
    this->state_callback_ = std::move(callback);
  }
  
  // Automation triggers
  Trigger<> *get_connected_trigger() { return &this->connected_trigger_; }
  Trigger<> *get_disconnected_trigger() { return &this->disconnected_trigger_; }
  Trigger<> *get_error_trigger() { return &this->error_trigger_; }
  Trigger<> *get_stopped_trigger() { return &this->stopped_trigger_; }

 protected:
  // WebRTC connection methods
  void connect_peer_();
  
  // Lazy initialization of ESP-AFE (delayed until WiFi is connected)
  void initialize_afe_();
  
  // esp_peer callbacks
  static int on_peer_state_(esp_peer_state_t state, void* ctx);
  static int on_peer_msg_(esp_peer_msg_t* msg, void* ctx);
  static int on_peer_audio_data_(esp_peer_audio_frame_t* frame, void* ctx);
  static int on_peer_audio_info_(esp_peer_audio_stream_info_t* info, void* ctx);
  
  // Callback handlers
  int handle_peer_state_(esp_peer_state_t state);
  int handle_peer_msg_(esp_peer_msg_t* msg);
  void handle_peer_audio_data_(esp_peer_audio_frame_t* frame);

  // Audio processing methods
  void on_microphone_data_(const std::vector<uint8_t> &data);
  void process_received_audio_(const uint8_t *data, size_t len);
  
  std::string server_base_url_;
  microphone::Microphone *microphone_{nullptr};
  speaker::Speaker *speaker_{nullptr};

#ifdef USE_ESP_IDF
  // Custom signaling for Pipecat SmallWebRTC protocol
  PipecatSignaling* pipecat_signaling_{nullptr};
  
  // WebRTC peer connection (using esp_peer API directly)
  esp_peer_handle_t peer_handle_{nullptr};
  
  // ESP-AFE for Acoustic Echo Cancellation (AEC) and other audio processing
  esp_afe_sr_data_t *afe_handle_{nullptr};
  esp_afe_sr_iface_t *afe_iface_{nullptr};
  int16_t *afe_in_buffer_{nullptr};
  int afe_feed_chunksize_{0};
#endif

  VoiceAssistantWebRTCState state_{VOICE_ASSISTANT_WEBRTC_IDLE};
  
  std::function<void(VoiceAssistantWebRTCState)> state_callback_;
  
  // Automation triggers
  Trigger<> connected_trigger_{};
  Trigger<> disconnected_trigger_{};
  Trigger<> error_trigger_{};
  Trigger<> stopped_trigger_{};
  
  // Audio buffers
  std::vector<uint8_t> input_buffer_;
  std::vector<uint8_t> output_buffer_;
  
  // Queue for audio data when speaker buffer is full
  std::queue<std::vector<uint8_t>> audio_queue_;
  static const size_t MAX_QUEUE_DURATION_SECONDS = 5;
  static const size_t BYTES_PER_SECOND = 48000;  // 24kHz * 2 bytes/sample (16-bit mono)
  static const size_t MAX_QUEUE_BYTES = MAX_QUEUE_DURATION_SECONDS * BYTES_PER_SECOND;
  static const size_t ESTIMATED_CHUNK_SIZE = 4096;
  static const size_t MAX_QUEUE_SIZE = (MAX_QUEUE_BYTES / ESTIMATED_CHUNK_SIZE) + 10;
  
  // Timing
  uint32_t last_audio_send_{0};
  uint32_t last_audio_receive_{0};
  static const uint32_t AUDIO_SEND_INTERVAL_MS = 100;
  static const uint32_t MICROPHONE_SAMPLE_RATE = 16000;  // 16kHz from microphone
  static const uint32_t INPUT_SAMPLE_RATE = 24000;       // 24kHz for OpenAI input
  static const uint32_t OUTPUT_SAMPLE_RATE = 24000;      // 24kHz for OpenAI output
  static const uint32_t BYTES_PER_SAMPLE = 2;
  static const uint32_t INPUT_BUFFER_SIZE = (INPUT_SAMPLE_RATE * BYTES_PER_SAMPLE * AUDIO_SEND_INTERVAL_MS) / 1000;
  
  // Auto-stop tracking
  uint32_t last_speaker_audio_time_{0};
  static const uint32_t AUTO_STOP_INACTIVITY_MS = 20000;
  
  // Audio conversion buffers
  std::vector<int16_t> mono_buffer_;
  std::vector<int16_t> resampled_buffer_;
  std::vector<uint8_t> output_stereo_buffer_;
  
  // Playback reference buffer for AEC (stores recent playback audio at 16kHz)
  std::vector<int16_t> playback_reference_buffer_;
  size_t playback_reference_write_pos_{0};
  
  bool pending_start_{false};
  bool pending_disconnect_{false};
  bool reconnect_pending_{false};
  bool explicit_disconnect_{false};
  uint32_t reconnect_attempts_{0};
  static const uint32_t MAX_RECONNECT_ATTEMPTS = 5;
  static const uint32_t RECONNECT_DELAY_MS = 5000;
  uint32_t last_reconnect_attempt_{0};
  
};

// Action classes for automations
template<typename... Ts> class VoiceAssistantWebRTCStartAction : public Action<Ts...> {
 public:
  VoiceAssistantWebRTCStartAction(VoiceAssistantWebRTC *parent) : parent_(parent) {}
  void play(const Ts &...x) override { this->parent_->start(); }
 protected:
  VoiceAssistantWebRTC *parent_;
};

template<typename... Ts> class VoiceAssistantWebRTCStopAction : public Action<Ts...> {
 public:
  VoiceAssistantWebRTCStopAction(VoiceAssistantWebRTC *parent) : parent_(parent) {}
  void play(const Ts &...x) override { this->parent_->stop(); }
 protected:
  VoiceAssistantWebRTC *parent_;
};

// Condition classes for automations
template<typename... Ts> class VoiceAssistantWebRTCIsRunningCondition : public Condition<Ts...> {
 public:
  VoiceAssistantWebRTCIsRunningCondition(VoiceAssistantWebRTC *parent) : parent_(parent) {}
  bool check(const Ts &...x) override { return this->parent_->is_running(); }
 protected:
  VoiceAssistantWebRTC *parent_;
};

template<typename... Ts> class VoiceAssistantWebRTCIsConnectedCondition : public Condition<Ts...> {
 public:
  VoiceAssistantWebRTCIsConnectedCondition(VoiceAssistantWebRTC *parent) : parent_(parent) {}
  bool check(const Ts &...x) override { return this->parent_->is_connected(); }
 protected:
  VoiceAssistantWebRTC *parent_;
};

}  // namespace voice_assistant_webrtc
}  // namespace esphome
