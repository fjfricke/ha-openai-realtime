#pragma once

#ifdef USE_ESP_IDF
#include "esp_peer.h"
#include "esp_peer_types.h"
#include "esp_http_client.h"
#include "cJSON.h"
#include <string>

namespace esphome {
namespace voice_assistant_webrtc {

/**
 * @brief Custom signaling implementation for Pipecat SmallWebRTC protocol
 * 
 * This class handles HTTP-based signaling with the Pipecat server.
 * It processes SDP offers/answers and ICE candidates via esp_peer's on_msg callback.
 */
class PipecatSignaling {
 public:
  PipecatSignaling(const std::string &server_base_url);
  ~PipecatSignaling();
  
  // Handle SDP message from esp_peer (offer or answer)
  int handle_sdp_message(esp_peer_handle_t peer, const uint8_t* data, int size);
  
  // Handle ICE candidate message from esp_peer
  int handle_ice_candidate(esp_peer_handle_t peer, const uint8_t* data, int size);
  
  // Set peer handle for sending messages back
  void set_peer_handle(esp_peer_handle_t peer) { peer_handle_ = peer; }
  
 private:
  // Server base URL
  std::string server_base_url_;
  
  // Peer handle for sending messages back
  esp_peer_handle_t peer_handle_{nullptr};
  
  // HTTP client handle
  esp_http_client_handle_t http_client_;
  
  // Response buffer
  std::string response_buffer_;
  
  // PC ID from server
  std::string pc_id_;
  
  // HTTP event handler
  static esp_err_t http_event_handler_(esp_http_client_event_t *evt);
  
  // HTTP helpers
  int send_http_post_(const std::string &path, const std::string &json_body);
  void send_http_patch_(const std::string &path, const std::string &json_body);
};

}  // namespace voice_assistant_webrtc
}  // namespace esphome

#endif  // USE_ESP_IDF

