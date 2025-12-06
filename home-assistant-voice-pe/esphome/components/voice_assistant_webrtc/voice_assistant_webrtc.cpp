#include "voice_assistant_webrtc.h"
#include "esphome/core/log.h"
#include "esphome/core/helpers.h"
#include "esphome/components/audio/audio.h"
#include "esphome/core/hal.h"
#include <cstring>
#include <algorithm>
#include <queue>
#include <sstream>

#ifdef USE_ESP_IDF
#include "esp_http_client.h"
#include "esp_afe_sr_iface.h"
#include "esp_afe_sr_models.h"
#include "esp_afe_config.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#endif

static const char *TAG = "voice_assistant_webrtc";

namespace esphome {
namespace voice_assistant_webrtc {

#ifdef USE_ESP_IDF
// Static callback wrappers for esp_peer
int VoiceAssistantWebRTC::on_peer_state_(esp_peer_state_t state, void* ctx) {
  VoiceAssistantWebRTC *instance = static_cast<VoiceAssistantWebRTC*>(ctx);
  return instance->handle_peer_state_(state);
}

int VoiceAssistantWebRTC::on_peer_msg_(esp_peer_msg_t* msg, void* ctx) {
  VoiceAssistantWebRTC *instance = static_cast<VoiceAssistantWebRTC*>(ctx);
  return instance->handle_peer_msg_(msg);
}

int VoiceAssistantWebRTC::on_peer_audio_data_(esp_peer_audio_frame_t* frame, void* ctx) {
  VoiceAssistantWebRTC *instance = static_cast<VoiceAssistantWebRTC*>(ctx);
  instance->handle_peer_audio_data_(frame);
  return ESP_PEER_ERR_NONE;
}

int VoiceAssistantWebRTC::on_peer_audio_info_(esp_peer_audio_stream_info_t* info, void* ctx) {
  VoiceAssistantWebRTC *instance = static_cast<VoiceAssistantWebRTC*>(ctx);
  ESP_LOGI("voice_assistant_webrtc", "Audio stream info: codec=%d, sample_rate=%d, channel=%d",
           info->codec, info->sample_rate, info->channel);
  return ESP_PEER_ERR_NONE;
}
#endif

void VoiceAssistantWebRTC::setup() {
  ESP_LOGCONFIG(TAG, "Setting up Voice Assistant WebRTC...");
  this->input_buffer_.reserve(INPUT_BUFFER_SIZE);
  this->output_buffer_.reserve(4096);
  this->mono_buffer_.reserve(INPUT_BUFFER_SIZE / 2);
  this->resampled_buffer_.reserve(INPUT_BUFFER_SIZE * 3 / 2); // 1.5x upsampling
  this->output_stereo_buffer_.reserve(4096 * 2);
  // Playback reference buffer: only needed for AEC (currently disabled)
  // Reserve minimal space to save memory - will be resized if AEC is re-enabled
  this->playback_reference_buffer_.reserve(0); // Don't allocate until needed
  this->playback_reference_write_pos_ = 0;
  this->state_ = VOICE_ASSISTANT_WEBRTC_IDLE;

#ifdef USE_ESP_IDF
  // Create custom signaling for Pipecat SmallWebRTC protocol
  this->pipecat_signaling_ = new PipecatSignaling(this->server_base_url_);
  
  // Delay ESP-AFE initialization until WiFi is connected to avoid WiFi initialization conflicts
  // AFE will be initialized lazily in initialize_afe_() when start() is called
  ESP_LOGI(TAG, "ESP-AFE initialization deferred until WiFi is connected");
#endif

  if (this->microphone_ != nullptr) {
    this->microphone_->add_data_callback([this](const std::vector<uint8_t> &data) {
      this->on_microphone_data_(data);
    });
  }
}

void VoiceAssistantWebRTC::loop() {
  // Handle pending disconnect
  if (this->pending_disconnect_) {
    this->pending_disconnect_ = false;
#ifdef USE_ESP_IDF
    if (this->peer_handle_ != nullptr) {
      esp_peer_close(this->peer_handle_);
      this->peer_handle_ = nullptr;
    }
#endif
    this->input_buffer_.clear();
    this->output_buffer_.clear();
    this->state_ = VOICE_ASSISTANT_WEBRTC_IDLE;
    this->reconnect_attempts_ = 0;
    this->reconnect_pending_ = false;
    
    if (this->state_callback_) {
      this->state_callback_(this->state_);
    }
    
    this->stopped_trigger_.trigger();
    ESP_LOGI(TAG, "Voice Assistant WebRTC stopped");
    return;
  }
  
  // Process queued audio
  if (this->speaker_ != nullptr && this->speaker_->is_running() && !this->audio_queue_.empty()) {
    const std::vector<uint8_t> &queued_data = this->audio_queue_.front();
    size_t written = this->speaker_->play(queued_data.data(), queued_data.size());
    
    if (written == queued_data.size()) {
      this->audio_queue_.pop();
    } else if (written > 0) {
      // Partial write - remove written portion
      std::vector<uint8_t> remainder(queued_data.begin() + written, queued_data.end());
      this->audio_queue_.pop();
      this->audio_queue_.push(remainder);
    }
  }
  
  // Auto-stop if no audio received for a while
  if (this->state_ == VOICE_ASSISTANT_WEBRTC_RUNNING && 
      this->last_speaker_audio_time_ > 0 &&
      (millis() - this->last_speaker_audio_time_) > AUTO_STOP_INACTIVITY_MS) {
    ESP_LOGI(TAG, "Auto-stopping due to inactivity");
    this->stop();
  }
  
#ifdef USE_ESP_IDF
  // Call esp_peer_main_loop() regularly to process events and generate SDP/ICE
  // According to esp_peer docs: "This loop need to be call repeatedly. It handle peer 
  // connection status change also receive stream data"
  if (this->peer_handle_ != nullptr) {
    esp_peer_main_loop(this->peer_handle_);
    
    // Log periodically if we're in signaling state (every 50 calls ≈ 1 second)
    static int loop_count = 0;
    if (this->state_ == VOICE_ASSISTANT_WEBRTC_SIGNALLING) {
      loop_count++;
      if (loop_count % 50 == 0) {
        ESP_LOGD(TAG, "Still in signaling state, main_loop called %d times, free heap: %d bytes", 
                 loop_count, esp_get_free_heap_size());
      }
    } else {
      loop_count = 0;
    }
  }
#endif
  
  // Handle pending start
  if (this->pending_start_) {
    this->pending_start_ = false;
    this->start();
  }
}

void VoiceAssistantWebRTC::dump_config() {
  ESP_LOGCONFIG(TAG, "Voice Assistant WebRTC:");
  ESP_LOGCONFIG(TAG, "  Server URL: %s", this->server_base_url_.c_str());
  ESP_LOGCONFIG(TAG, "  State: %d", this->state_);
}

void VoiceAssistantWebRTC::start() {
  if (this->state_ != VOICE_ASSISTANT_WEBRTC_IDLE && 
      this->state_ != VOICE_ASSISTANT_WEBRTC_DISCONNECTED &&
      this->state_ != VOICE_ASSISTANT_WEBRTC_ERROR) {
    ESP_LOGD(TAG, "Cannot start: already in state %d (start request ignored)", this->state_);
    return;
  }
  
  ESP_LOGI(TAG, "Starting Voice Assistant WebRTC...");
  this->state_ = VOICE_ASSISTANT_WEBRTC_STARTING;
  this->explicit_disconnect_ = false;
  this->reconnect_attempts_ = 0;
  
  if (this->state_callback_) {
    this->state_callback_(this->state_);
  }
  
#ifdef USE_ESP_IDF
  this->connect_peer_();
#else
  ESP_LOGE(TAG, "WebRTC not supported on this platform");
  this->state_ = VOICE_ASSISTANT_WEBRTC_ERROR;
  this->error_trigger_.trigger();
#endif
}

void VoiceAssistantWebRTC::stop() {
  if (this->state_ == VOICE_ASSISTANT_WEBRTC_IDLE) {
    return;
  }
  
  ESP_LOGI(TAG, "Stopping Voice Assistant WebRTC...");
  this->explicit_disconnect_ = true;
  this->state_ = VOICE_ASSISTANT_WEBRTC_STOPPING;
  this->pending_disconnect_ = true;
}

void VoiceAssistantWebRTC::request_start() {
  this->pending_start_ = true;
}

#ifdef USE_ESP_IDF

int VoiceAssistantWebRTC::handle_peer_msg_(esp_peer_msg_t* msg) {
  if (msg == nullptr || this->pipecat_signaling_ == nullptr) {
    ESP_LOGE(TAG, "handle_peer_msg_ called with null msg or signaling");
    return ESP_PEER_ERR_INVALID_ARG;
  }
  
  ESP_LOGI(TAG, "Received message from esp_peer: type=%d (%s), size=%d", 
           msg->type, 
           msg->type == ESP_PEER_MSG_TYPE_SDP ? "SDP" : 
           msg->type == ESP_PEER_MSG_TYPE_CANDIDATE ? "CANDIDATE" : "UNKNOWN",
           msg->size);
  
  switch (msg->type) {
    case ESP_PEER_MSG_TYPE_SDP:
      // Handle SDP offer/answer from esp_peer
      ESP_LOGI(TAG, "Processing SDP message from esp_peer (size=%d bytes)", msg->size);
      return this->pipecat_signaling_->handle_sdp_message(this->peer_handle_, msg->data, msg->size);
      
    case ESP_PEER_MSG_TYPE_CANDIDATE:
      // Handle ICE candidate
      ESP_LOGI(TAG, "Processing ICE candidate from esp_peer (size=%d bytes)", msg->size);
      return this->pipecat_signaling_->handle_ice_candidate(this->peer_handle_, msg->data, msg->size);
      
    default:
      ESP_LOGW(TAG, "Unknown message type: %d", msg->type);
      return ESP_PEER_ERR_NOT_SUPPORT;
  }
}

int VoiceAssistantWebRTC::handle_peer_state_(esp_peer_state_t state) {
  const char* state_name = "UNKNOWN";
  switch (state) {
    case ESP_PEER_STATE_CLOSED: state_name = "CLOSED"; break;
    case ESP_PEER_STATE_DISCONNECTED: state_name = "DISCONNECTED"; break;
    case ESP_PEER_STATE_NEW_CONNECTION: state_name = "NEW_CONNECTION"; break;
    case ESP_PEER_STATE_PAIRING: state_name = "PAIRING"; break;
    case ESP_PEER_STATE_PAIRED: state_name = "PAIRED"; break;
    case ESP_PEER_STATE_CONNECTING: state_name = "CONNECTING"; break;
    case ESP_PEER_STATE_CONNECTED: state_name = "CONNECTED"; break;
    case ESP_PEER_STATE_CONNECT_FAILED: state_name = "CONNECT_FAILED"; break;
    case ESP_PEER_STATE_DATA_CHANNEL_CONNECTED: state_name = "DATA_CHANNEL_CONNECTED"; break;
    case ESP_PEER_STATE_DATA_CHANNEL_OPENED: state_name = "DATA_CHANNEL_OPENED"; break;
    case ESP_PEER_STATE_DATA_CHANNEL_CLOSED: state_name = "DATA_CHANNEL_CLOSED"; break;
    case ESP_PEER_STATE_DATA_CHANNEL_DISCONNECTED: state_name = "DATA_CHANNEL_DISCONNECTED"; break;
    default: state_name = "UNKNOWN"; break;
  }
  ESP_LOGI(TAG, "Peer state changed: %d (%s)", state, state_name);
  
  // Handle DISCONNECTED state during signaling - this might happen if
  // esp_peer_new_connection() fails internally (e.g., ICE server issues).
  // Continue processing - esp_peer_main_loop() might recover
  if (state == ESP_PEER_STATE_DISCONNECTED && this->state_ == VOICE_ASSISTANT_WEBRTC_SIGNALLING) {
    ESP_LOGW(TAG, "Peer disconnected during signaling - likely esp_peer_new_connection() failed internally");
    ESP_LOGW(TAG, "Continuing - esp_peer_main_loop() may recover or generate SDP automatically");
    // Don't change state or trigger error - let esp_peer_main_loop() handle recovery
    return ESP_PEER_ERR_NONE;
  }
  
  switch (state) {
    case ESP_PEER_STATE_CONNECTED:
      if (this->state_ == VOICE_ASSISTANT_WEBRTC_SIGNALLING) {
        this->state_ = VOICE_ASSISTANT_WEBRTC_RUNNING;
        ESP_LOGI(TAG, "WebRTC connection established");
        
        if (this->state_callback_) {
          this->state_callback_(this->state_);
        }
        
        this->connected_trigger_.trigger();
      }
      break;
      
    case ESP_PEER_STATE_DISCONNECTED:
      if (this->state_ == VOICE_ASSISTANT_WEBRTC_RUNNING || 
          this->state_ == VOICE_ASSISTANT_WEBRTC_SIGNALLING) {
        this->state_ = VOICE_ASSISTANT_WEBRTC_DISCONNECTED;
        ESP_LOGI(TAG, "WebRTC connection closed");
        
        if (this->state_callback_) {
          this->state_callback_(this->state_);
        }
        
        this->disconnected_trigger_.trigger();
        
        // Auto-reconnect if not explicitly disconnected
        if (!this->explicit_disconnect_ && this->reconnect_attempts_ < MAX_RECONNECT_ATTEMPTS) {
          this->reconnect_attempts_++;
          this->reconnect_pending_ = true;
          this->last_reconnect_attempt_ = millis();
          ESP_LOGI(TAG, "Scheduling reconnect attempt %d/%d", 
                   this->reconnect_attempts_, MAX_RECONNECT_ATTEMPTS);
        }
      }
      break;
      
    case ESP_PEER_STATE_CONNECT_FAILED:
      this->state_ = VOICE_ASSISTANT_WEBRTC_ERROR;
      ESP_LOGE(TAG, "WebRTC connection failed");
      
      if (this->state_callback_) {
        this->state_callback_(this->state_);
      }
      
      this->error_trigger_.trigger();
      break;
      
    default:
      break;
  }
  
  return ESP_PEER_ERR_NONE;
}

void VoiceAssistantWebRTC::handle_peer_audio_data_(esp_peer_audio_frame_t* frame) {
  if (frame == nullptr || frame->data == nullptr || frame->size == 0) {
    return;
  }
  
  // Forward to process_received_audio_ for playback and AEC reference
  this->process_received_audio_(frame->data, frame->size);
}

void VoiceAssistantWebRTC::initialize_afe_() {
  if (this->afe_handle_ != nullptr) {
    // Already initialized
    return;
  }
  
#ifdef USE_ESP_IDF
  ESP_LOGI(TAG, "Initializing ESP-AFE for NS, AGC (AEC disabled due to crash, lazy initialization after WiFi connection)...");
  
  // Small delay to ensure ESP-IDF components are fully initialized
  // This helps avoid race conditions with WiFi and other system components
  vTaskDelay(pdMS_TO_TICKS(100));
  
  // Initialize ESP-AFE for NS, AGC (AEC temporarily disabled due to crash)
  // Create AFE config: "M" = microphone channel only (no reference needed without AEC)
  // Use LOW_COST mode to reduce memory usage (HIGH_PERF consumes too much memory)
  afe_config_t *afe_cfg = afe_config_init("M", NULL, AFE_TYPE_VC, AFE_MODE_LOW_COST);
  if (afe_cfg == nullptr) {
    ESP_LOGE(TAG, "Failed to create AFE config!");
    return;
  }
  
  // Configure AFE
  afe_cfg->wakenet_model_name = NULL; // No wake word in AFE, handled by micro_wake_word
  // Temporarily disable AEC due to crash in ESP-AFE initialization
  // TODO: Investigate ESP-AFE v2.0.0 AEC initialization issue
  afe_cfg->aec_init = false; // Disable AEC temporarily - crashes during initialization
  afe_cfg->ns_init = true; // Enable Noise Suppression
  afe_cfg->agc_init = true; // Enable Auto Gain Control
  afe_cfg->vad_init = false; // VAD handled by OpenAI server
  afe_cfg->pcm_config.sample_rate = MICROPHONE_SAMPLE_RATE; // 16kHz input
  afe_cfg->pcm_config.mic_num = 1; // One microphone channel
  afe_cfg->pcm_config.ref_num = 0; // No reference channel needed without AEC
  afe_cfg->pcm_config.total_ch_num = 1; // Total: mic only (no ref needed without AEC)
  
  // Check and validate config
  afe_cfg = afe_config_check(afe_cfg);
  if (afe_cfg == nullptr) {
    ESP_LOGE(TAG, "afe_config_check returned null!");
    return;
  }
  
  // Get AFE interface
  this->afe_iface_ = esp_afe_handle_from_config(afe_cfg);
  if (this->afe_iface_ == nullptr) {
    ESP_LOGE(TAG, "Failed to get AFE interface!");
    afe_config_free(afe_cfg);
    return;
  }
  
  // Verify interface has required methods
  if (this->afe_iface_->create_from_config == nullptr) {
    ESP_LOGE(TAG, "AFE interface missing create_from_config method!");
    afe_config_free(afe_cfg);
    return;
  }
  
  // Create AFE instance with error handling
  ESP_LOGI(TAG, "Creating AFE handle from config...");
  this->afe_handle_ = this->afe_iface_->create_from_config(afe_cfg);
  if (this->afe_handle_ == nullptr) {
    ESP_LOGE(TAG, "Failed to create AFE handle! This may indicate insufficient memory or invalid config.");
    afe_config_free(afe_cfg);
    return;
  }
  
  // Get feed chunk size
  this->afe_feed_chunksize_ = this->afe_iface_->get_feed_chunksize(this->afe_handle_);
  if (this->afe_feed_chunksize_ <= 0) {
    ESP_LOGE(TAG, "Invalid feed chunksize: %d", this->afe_feed_chunksize_);
    // Clean up
    if (this->afe_iface_->destroy != nullptr && this->afe_handle_ != nullptr) {
      this->afe_iface_->destroy(this->afe_handle_);
    }
    this->afe_handle_ = nullptr;
    afe_config_free(afe_cfg);
    return;
  }
  
  // Allocate AFE input buffer (mono: mic only, no ref needed without AEC)
  this->afe_in_buffer_ = (int16_t *) calloc(this->afe_feed_chunksize_, sizeof(int16_t));
  if (this->afe_in_buffer_ == nullptr) {
    ESP_LOGE(TAG, "Failed to allocate AFE input buffer!");
    // Clean up
    if (this->afe_iface_->destroy != nullptr && this->afe_handle_ != nullptr) {
      this->afe_iface_->destroy(this->afe_handle_);
    }
    this->afe_handle_ = nullptr;
    afe_config_free(afe_cfg);
    return;
  }
  
  afe_config_free(afe_cfg);
  
  // Log memory status after initialization
  size_t free_heap = esp_get_free_heap_size();
  ESP_LOGI(TAG, "ESP-AFE initialized successfully for NS, AGC (AEC disabled, feed_chunksize=%d, free_heap=%d bytes)", 
           this->afe_feed_chunksize_, free_heap);
#endif
}

void VoiceAssistantWebRTC::connect_peer_() {
  ESP_LOGI(TAG, "Initializing WebRTC peer connection with Pipecat signaling...");
  this->state_ = VOICE_ASSISTANT_WEBRTC_SIGNALLING;
  
  // Initialize AFE lazily (after WiFi is connected)
  this->initialize_afe_();
  
  if (this->pipecat_signaling_ == nullptr) {
    ESP_LOGE(TAG, "Pipecat signaling not initialized");
    this->state_ = VOICE_ASSISTANT_WEBRTC_ERROR;
    this->error_trigger_.trigger();
    return;
  }
  
  if (this->afe_handle_ == nullptr || this->afe_iface_ == nullptr) {
    ESP_LOGE(TAG, "AFE not initialized - cannot proceed");
    this->state_ = VOICE_ASSISTANT_WEBRTC_ERROR;
    this->error_trigger_.trigger();
    return;
  }
  
  // Configure esp_peer default config - match peer_demo.c example exactly
  // Note: struct field order must match declaration: cache_timeout, send_cache_size, recv_cache_size
  esp_peer_default_cfg_t default_cfg = {
    .agent_recv_timeout = 100,   // Enlarge this value if network is poor
    .data_ch_cfg = {
      .send_cache_size = 1536, // Should be bigger than one MTU size
      .recv_cache_size = 1536, // Should be bigger than one MTU size
    },
    .rtp_cfg = {
      .audio_recv_jitter = {
        .cache_size = 1024,
      },
      .send_pool_size = 1024,
      .send_queue_num = 10,
    },
  };
  
  // Configure esp_peer - match peer_demo.c example exactly
  esp_peer_cfg_t peer_cfg = {};
  
  // Set role to CONTROLLING since we're initiating the connection
  peer_cfg.role = ESP_PEER_ROLE_CONTROLLING;
  
  // Audio configuration - match peer_demo.c example structure
  // Note: peer_demo.c only sets codec, but OPUS may require sample_rate/channel
  peer_cfg.audio_dir = ESP_PEER_MEDIA_DIR_SEND_RECV;
  peer_cfg.audio_info.codec = ESP_PEER_AUDIO_CODEC_OPUS;
  // For OPUS, sample_rate and channel should be set (G711A doesn't need them)
  peer_cfg.audio_info.sample_rate = INPUT_SAMPLE_RATE; // 24kHz
  peer_cfg.audio_info.channel = 1; // Mono
  
  // Note: peer_demo.c doesn't explicitly set video_dir, so it defaults
  // We'll set it explicitly to NONE to be clear
  peer_cfg.video_dir = ESP_PEER_MEDIA_DIR_NONE;
  
  // ICE transport policy - not set in peer_demo.c, defaults to ALL
  peer_cfg.ice_trans_policy = ESP_PEER_ICE_TRANS_POLICY_ALL;
  
  // Configure ICE servers - match peer_demo.c example (commented out, defaults to 0)
  peer_cfg.server_lists = nullptr;
  peer_cfg.server_num = 0;
  
  ESP_LOGI(TAG, "Peer configuration:");
  ESP_LOGI(TAG, "  role: CONTROLLING");
  ESP_LOGI(TAG, "  audio_dir: SEND_RECV");
  ESP_LOGI(TAG, "  audio_codec: OPUS, sample_rate: %d, channels: %d", 
           peer_cfg.audio_info.sample_rate, peer_cfg.audio_info.channel);
  ESP_LOGI(TAG, "  video_dir: NONE");
  ESP_LOGI(TAG, "  ice_trans_policy: ALL");
  ESP_LOGI(TAG, "  server_num: 0 (no ICE servers)");
  
  // Enable data channel - peer_demo.c sets this to true, but we don't need it
  peer_cfg.enable_data_channel = false;
  
  // Set callbacks
  peer_cfg.on_state = on_peer_state_;
  peer_cfg.on_msg = on_peer_msg_;  // Handle SDP and ICE candidate messages
  peer_cfg.on_audio_data = on_peer_audio_data_;
  peer_cfg.on_audio_info = on_peer_audio_info_;
  peer_cfg.ctx = this;
  
  // Set extra config (required according to peer_demo example)
  peer_cfg.extra_cfg = &default_cfg;
  peer_cfg.extra_size = sizeof(esp_peer_default_cfg_t);
  
  // Get default peer implementation
  const esp_peer_ops_t* peer_impl = esp_peer_get_default_impl();
  if (peer_impl == nullptr) {
    ESP_LOGE(TAG, "Failed to get default peer implementation");
    this->state_ = VOICE_ASSISTANT_WEBRTC_ERROR;
    this->error_trigger_.trigger();
    return;
  }
  
  // Open peer connection
  ESP_LOGI(TAG, "Opening esp_peer connection...");
  int ret = esp_peer_open(&peer_cfg, peer_impl, &this->peer_handle_);
  if (ret != ESP_PEER_ERR_NONE) {
    ESP_LOGE(TAG, "Failed to open peer connection: %d", ret);
    this->state_ = VOICE_ASSISTANT_WEBRTC_ERROR;
    this->error_trigger_.trigger();
    return;
  }
  
  ESP_LOGI(TAG, "Peer connection opened successfully, handle=%p", this->peer_handle_);
  
  // Update peer handle in signaling (needed for sending messages back)
  this->pipecat_signaling_->set_peer_handle(this->peer_handle_);
  
  ESP_LOGI(TAG, "Peer connection initialized - callbacks registered:");
  ESP_LOGI(TAG, "  on_state: %p", peer_cfg.on_state);
  ESP_LOGI(TAG, "  on_msg: %p", peer_cfg.on_msg);
  ESP_LOGI(TAG, "  on_audio_data: %p", peer_cfg.on_audio_data);
  ESP_LOGI(TAG, "  ctx: %p", peer_cfg.ctx);
  
  // According to examples: esp_peer_main_loop() must be running before esp_peer_new_connection()
  // Call main_loop a few times to ensure esp_peer is ready
  ESP_LOGI(TAG, "Initializing esp_peer (calling main_loop to ensure it's ready)...");
  for (int i = 0; i < 5; i++) {
    esp_peer_main_loop(this->peer_handle_);
    vTaskDelay(pdMS_TO_TICKS(20));
  }
  
  // Now call esp_peer_new_connection() - examples show this happens after main_loop is running
  ESP_LOGI(TAG, "Calling esp_peer_new_connection() to trigger SDP offer generation...");
  ESP_LOGI(TAG, "  peer_handle: %p", this->peer_handle_);
  ESP_LOGI(TAG, "  audio_dir: SEND_RECV");
  ESP_LOGI(TAG, "  audio_codec: OPUS, sample_rate: %d, channels: %d", 
           peer_cfg.audio_info.sample_rate, peer_cfg.audio_info.channel);
  ESP_LOGI(TAG, "  video_dir: NONE");
  ESP_LOGI(TAG, "  enable_data_channel: %s", peer_cfg.enable_data_channel ? "true" : "false");
  ESP_LOGI(TAG, "  role: CONTROLLING");
  ESP_LOGI(TAG, "  server_num: %d", peer_cfg.server_num);
  
  // Log free heap before calling
  ESP_LOGI(TAG, "Free heap before esp_peer_new_connection(): %d bytes", esp_get_free_heap_size());
  
  ret = esp_peer_new_connection(this->peer_handle_);
  ESP_LOGI(TAG, "esp_peer_new_connection() returned: %d", ret);
  
  if (ret != ESP_PEER_ERR_NONE) {
    ESP_LOGE(TAG, "Failed to create new connection: %d", ret);
    ESP_LOGE(TAG, "  ESP_PEER_ERR_NONE = 0");
    ESP_LOGE(TAG, "  ESP_PEER_ERR_INVALID_ARG = -1");
    ESP_LOGE(TAG, "  ESP_PEER_ERR_NOT_SUPPORT = -2");
    ESP_LOGE(TAG, "  ESP_PEER_ERR_FAIL = -3");
    ESP_LOGE(TAG, "Free heap after error: %d bytes", esp_get_free_heap_size());
    this->state_ = VOICE_ASSISTANT_WEBRTC_ERROR;
    this->error_trigger_.trigger();
    return;
  }
  
  ESP_LOGI(TAG, "esp_peer_new_connection() called successfully (returned ESP_PEER_ERR_NONE)");
  ESP_LOGI(TAG, "Free heap after esp_peer_new_connection(): %d bytes", esp_get_free_heap_size());
  ESP_LOGI(TAG, "esp_peer will gather ICE candidates and generate SDP offer");
  ESP_LOGI(TAG, "SDP offer will be sent to server automatically via on_msg callback when generated");
  ESP_LOGI(TAG, "esp_peer_main_loop() is called regularly in loop() to process events");
  
  // Continue calling main_loop a few more times to let it process the new connection
  ESP_LOGI(TAG, "Calling esp_peer_main_loop() a few more times to process new connection...");
  for (int i = 0; i < 10; i++) {
    ESP_LOGD(TAG, "Calling esp_peer_main_loop() iteration %d/10", i + 1);
    esp_peer_main_loop(this->peer_handle_);
    
    // Check if we received any messages (SDP or ICE candidates)
    // This will be logged in handle_peer_msg_ if messages arrive
    
    vTaskDelay(pdMS_TO_TICKS(20));
    
    // Log heap every few iterations
    if ((i + 1) % 5 == 0) {
      ESP_LOGI(TAG, "After %d main_loop iterations, free heap: %d bytes", 
               i + 1, esp_get_free_heap_size());
    }
  }
  ESP_LOGI(TAG, "Finished initial main_loop calls - will continue in regular loop()");
  ESP_LOGI(TAG, "Final free heap: %d bytes", esp_get_free_heap_size());
}

// HTTP methods removed - now handled by PipecatSignaling

void VoiceAssistantWebRTC::on_microphone_data_(const std::vector<uint8_t> &data) {
  if (!this->is_connected() || this->state_ != VOICE_ASSISTANT_WEBRTC_RUNNING || 
      this->afe_handle_ == nullptr || this->afe_iface_ == nullptr) {
    return;
  }

  // Convert 32-bit stereo to 16-bit mono (16kHz) for AFE input
  size_t stereo_32bit_samples = data.size() / (4 * 2);
  size_t mono_16khz_samples = stereo_32bit_samples;

  if (this->mono_buffer_.size() < mono_16khz_samples) {
    this->mono_buffer_.resize(mono_16khz_samples);
  }

  const int32_t *stereo_32bit = reinterpret_cast<const int32_t *>(data.data());
  int16_t *mono_16bit = this->mono_buffer_.data();

  for (size_t i = 0; i < stereo_32bit_samples; i++) {
    mono_16bit[i] = static_cast<int16_t>((stereo_32bit[i * 2] >> 16)); // Left channel
  }

  // Prepare buffer for AFE: mic only (no reference channel needed without AEC)
  size_t samples_to_process = std::min(mono_16khz_samples, (size_t)this->afe_feed_chunksize_);
  
  // Copy microphone data directly (no reference channel)
  for (size_t i = 0; i < samples_to_process; i++) {
    this->afe_in_buffer_[i] = mono_16bit[i];
  }
  
  // Feed to AFE (mono mic only)
  this->afe_iface_->feed(this->afe_handle_, this->afe_in_buffer_);
  
  // Fetch processed audio
  afe_fetch_result_t *result = this->afe_iface_->fetch(this->afe_handle_);
  
  if (result != nullptr && result->data != nullptr && result->data_size > 0) {
    int audio_chunk_size = result->data_size / sizeof(int16_t);
    // Resample from 16kHz (AFE output) to 24kHz (OpenAI input)
    size_t resampled_24khz_samples = (audio_chunk_size * INPUT_SAMPLE_RATE) / MICROPHONE_SAMPLE_RATE;
    if (this->resampled_buffer_.size() < resampled_24khz_samples) {
      this->resampled_buffer_.resize(resampled_24khz_samples);
    }

    int16_t *resampled_24khz = this->resampled_buffer_.data();

    // Linear interpolation resampling: 16kHz -> 24kHz
    for (size_t i = 0; i < resampled_24khz_samples; i++) {
      float source_pos = (float)i * (float)MICROPHONE_SAMPLE_RATE / (float)INPUT_SAMPLE_RATE;
      size_t source_idx = (size_t)source_pos;
      float fraction = source_pos - source_idx;

      if (source_idx + 1 < audio_chunk_size) {
        int16_t sample0 = result->data[source_idx];
        int16_t sample1 = result->data[source_idx + 1];
        resampled_24khz[i] = static_cast<int16_t>(sample0 + (sample1 - sample0) * fraction);
      } else if (source_idx < audio_chunk_size) {
        resampled_24khz[i] = result->data[source_idx];
      } else {
        resampled_24khz[i] = result->data[audio_chunk_size - 1];
      }
    }

    // Send audio directly via esp_peer
    if (this->peer_handle_ != nullptr) {
      esp_peer_audio_frame_t audio_frame = {};
      audio_frame.data = reinterpret_cast<uint8_t*>(resampled_24khz);
      audio_frame.size = resampled_24khz_samples * BYTES_PER_SAMPLE;
      
      int ret = esp_peer_send_audio(this->peer_handle_, &audio_frame);
      if (ret != ESP_PEER_ERR_NONE) {
        ESP_LOGW(TAG, "Failed to send audio: %d", ret);
      }
    }
  }
}

void VoiceAssistantWebRTC::process_received_audio_(const uint8_t *data, size_t len) {
  if (this->speaker_ == nullptr || !this->speaker_->is_running()) {
    return;
  }
  
  this->last_speaker_audio_time_ = millis();
  
  // Playback reference buffer disabled - AEC is not enabled
  // (This code would store playback reference for AEC, but AEC is disabled due to crash)
  
  // Convert 24kHz mono to 48kHz stereo for speaker
  size_t mono_samples = len / BYTES_PER_SAMPLE;
  size_t stereo_samples = mono_samples * 2; // 48kHz = 2x 24kHz
  
  if (this->output_stereo_buffer_.size() < stereo_samples * BYTES_PER_SAMPLE) {
    this->output_stereo_buffer_.resize(stereo_samples * BYTES_PER_SAMPLE);
  }
  
  const int16_t *mono_audio = reinterpret_cast<const int16_t *>(data);
  int32_t *stereo_audio = reinterpret_cast<int32_t *>(this->output_stereo_buffer_.data());
  
  // Upsample 24kHz -> 48kHz and convert to stereo
  for (size_t i = 0; i < mono_samples; i++) {
    int16_t sample = mono_audio[i];
    int32_t sample_32 = (int32_t)sample << 16;
    stereo_audio[i * 2] = sample_32;     // Left
    stereo_audio[i * 2 + 1] = sample_32; // Right
  }
  
  // Try to play audio
  size_t written = this->speaker_->play(this->output_stereo_buffer_.data(), stereo_samples * BYTES_PER_SAMPLE * 2);
  
  if (written < stereo_samples * BYTES_PER_SAMPLE * 2) {
    // Buffer full, queue remainder
    if (this->audio_queue_.size() < MAX_QUEUE_SIZE) {
      std::vector<uint8_t> remainder(
        this->output_stereo_buffer_.begin() + written,
        this->output_stereo_buffer_.end()
      );
      this->audio_queue_.push(remainder);
    }
  }
}

#else
// Stub implementations for non-ESP-IDF builds
void VoiceAssistantWebRTC::connect_peer_() {}
int VoiceAssistantWebRTC::on_peer_state_(esp_peer_state_t, void*) { return 0; }
int VoiceAssistantWebRTC::on_peer_msg_(esp_peer_msg_t*, void*) { return 0; }
int VoiceAssistantWebRTC::on_peer_audio_data_(esp_peer_audio_frame_t*, void*) { return 0; }
int VoiceAssistantWebRTC::on_peer_audio_info_(esp_peer_audio_stream_info_t*, void*) { return 0; }
int VoiceAssistantWebRTC::handle_peer_msg_(esp_peer_msg_t*) { return 0; }
int VoiceAssistantWebRTC::handle_peer_state_(esp_peer_state_t) { return 0; }
void VoiceAssistantWebRTC::handle_peer_audio_data_(esp_peer_audio_frame_t*) {}
void VoiceAssistantWebRTC::on_microphone_data_(const std::vector<uint8_t> &) {}
void VoiceAssistantWebRTC::process_received_audio_(const uint8_t *, size_t) {}
#endif

}  // namespace voice_assistant_webrtc
}  // namespace esphome
