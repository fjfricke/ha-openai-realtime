#include "pipecat_signaling.h"
#include "esphome/core/log.h"
#include <cstring>
#include <cstdlib>

#ifdef USE_ESP_IDF
#include "esp_timer.h"
#include "esp_netif.h"
#include "lwip/ip4_addr.h"
#include <ctime>

static const char *TAG = "pipecat_signaling";

namespace esphome {
namespace voice_assistant_webrtc {

PipecatSignaling::PipecatSignaling(const std::string &server_base_url)
    : server_base_url_(server_base_url), http_client_(nullptr) {
  ESP_LOGI(TAG, "PipecatSignaling initialized with server URL: %s", server_base_url_.c_str());
}

PipecatSignaling::~PipecatSignaling() {
  if (http_client_ != nullptr) {
    esp_http_client_cleanup(http_client_);
    http_client_ = nullptr;
  }
}

esp_err_t PipecatSignaling::http_event_handler_(esp_http_client_event_t *evt) {
  PipecatSignaling* instance = static_cast<PipecatSignaling*>(evt->user_data);
  
  switch (evt->event_id) {
    case HTTP_EVENT_ON_DATA:
      if (!esp_http_client_is_chunked_response(evt->client)) {
        if (evt->data != nullptr && evt->data_len > 0) {
          instance->response_buffer_.append((char*)evt->data, evt->data_len);
        }
      }
      break;
    default:
      break;
  }
  return ESP_OK;
}

int PipecatSignaling::handle_sdp_message(esp_peer_handle_t peer, const uint8_t* data, int size) {
  if (data == nullptr || size == 0 || peer == nullptr) {
    return ESP_PEER_ERR_INVALID_ARG;
  }
  
  ESP_LOGI(TAG, "Received SDP message from esp_peer (size=%d)", size);
  
  // This is an SDP offer from esp_peer - send it to the server
  std::string sdp((char*)data, size);
  ESP_LOGD(TAG, "SDP offer: %.200s...", sdp.c_str()); // Log first 200 chars
  
  cJSON *json = cJSON_CreateObject();
  cJSON_AddStringToObject(json, "sdp", sdp.c_str());
  cJSON_AddStringToObject(json, "type", "offer");
  char *json_string = cJSON_Print(json);
  
  this->response_buffer_.clear();
  ESP_LOGI(TAG, "Sending SDP offer to %s/webrtc/offer", this->server_base_url_.c_str());
  int status_code = this->send_http_post_("/webrtc/offer", json_string);
  
  free(json_string);
  cJSON_Delete(json);
  
  // Only parse response if HTTP request was successful
  if (status_code != 200) {
    ESP_LOGE(TAG, "HTTP POST to /webrtc/offer failed with status %d", status_code);
    ESP_LOGE(TAG, "Response body: %s", this->response_buffer_.substr(0, 500).c_str());
    return ESP_PEER_ERR_FAIL;
  }
  
  ESP_LOGI(TAG, "Received response from server (length=%d): %s", 
           this->response_buffer_.length(), 
           this->response_buffer_.substr(0, 200).c_str());
  
  // Parse response to get SDP answer and pc_id
  cJSON *response_json = cJSON_Parse(this->response_buffer_.c_str());
  if (response_json == nullptr) {
    ESP_LOGE(TAG, "Failed to parse JSON response: %s", cJSON_GetErrorPtr());
    return ESP_PEER_ERR_FAIL;
  }
  
  cJSON *answer_sdp = cJSON_GetObjectItem(response_json, "sdp");
  cJSON *pc_id_item = cJSON_GetObjectItem(response_json, "pc_id");
  
  if (answer_sdp == nullptr || !cJSON_IsString(answer_sdp)) {
    ESP_LOGE(TAG, "Response missing 'sdp' field or not a string");
    ESP_LOGE(TAG, "Response keys: %s", cJSON_Print(response_json));
    cJSON_Delete(response_json);
    return ESP_PEER_ERR_FAIL;
  }
  
  // We already checked answer_sdp is valid above, so process it
  std::string answer = cJSON_GetStringValue(answer_sdp);
  
  // Send SDP answer back to esp_peer
  if (this->peer_handle_ != nullptr) {
    // Allocate memory for the answer (esp_peer will use it)
    uint8_t *answer_data = (uint8_t*)malloc(answer.length());
    if (answer_data != nullptr) {
      memcpy(answer_data, answer.c_str(), answer.length());
      
      esp_peer_msg_t answer_msg = {};
      answer_msg.type = ESP_PEER_MSG_TYPE_SDP;
      answer_msg.data = answer_data;
      answer_msg.size = answer.length();
      
      int ret = esp_peer_send_msg(this->peer_handle_, &answer_msg);
      if (ret != ESP_PEER_ERR_NONE) {
        ESP_LOGE(TAG, "Failed to send SDP answer to peer: %d", ret);
        free(answer_data);
      } else {
        ESP_LOGI(TAG, "Successfully sent SDP answer to esp_peer");
      }
      // Note: Memory will be freed by esp_peer when done
    } else {
      ESP_LOGE(TAG, "Failed to allocate memory for SDP answer");
    }
  } else {
    ESP_LOGE(TAG, "Peer handle is null, cannot send SDP answer");
  }
  
  if (pc_id_item != nullptr && cJSON_IsString(pc_id_item)) {
    this->pc_id_ = cJSON_GetStringValue(pc_id_item);
    ESP_LOGI(TAG, "Received pc_id: %s", this->pc_id_.c_str());
  }
  
  cJSON_Delete(response_json);
  
  return ESP_PEER_ERR_NONE;
}

int PipecatSignaling::handle_ice_candidate(esp_peer_handle_t peer, const uint8_t* data, int size) {
  if (data == nullptr || size == 0 || peer == nullptr) {
    return ESP_PEER_ERR_INVALID_ARG;
  }
  
  // Send ICE candidate to /webrtc/offer (PATCH method, matching Pipecat example)
  std::string candidate((char*)data, size);
  
  cJSON *json = cJSON_CreateObject();
  cJSON_AddStringToObject(json, "pc_id", this->pc_id_.c_str());
  
  cJSON *candidates_array = cJSON_CreateArray();
  cJSON *candidate_obj = cJSON_CreateObject();
  cJSON_AddStringToObject(candidate_obj, "candidate", candidate.c_str());
  cJSON_AddStringToObject(candidate_obj, "sdp_mid", "0");
  cJSON_AddNumberToObject(candidate_obj, "sdp_mline_index", 0);
  cJSON_AddItemToArray(candidates_array, candidate_obj);
  cJSON_AddItemToObject(json, "candidates", candidates_array);
  
  char *json_string = cJSON_Print(json);
  this->send_http_patch_("/webrtc/offer", json_string);
  
  free(json_string);
  cJSON_Delete(json);
  
  return ESP_PEER_ERR_NONE;
}

int PipecatSignaling::send_http_post_(const std::string &path, const std::string &json_body) {
  std::string url = server_base_url_ + path;
  
  esp_http_client_config_t config = {};
  config.url = url.c_str();
  config.event_handler = http_event_handler_;
  config.user_data = this;
  config.method = HTTP_METHOD_POST;
  config.timeout_ms = 10000;
  
  http_client_ = esp_http_client_init(&config);
  if (http_client_ == nullptr) {
    ESP_LOGE(TAG, "Failed to initialize HTTP client");
    return 0;
  }
  
  esp_http_client_set_header(http_client_, "Content-Type", "application/json");
  esp_http_client_set_post_field(http_client_, json_body.c_str(), json_body.length());
  
  response_buffer_.clear();
  esp_err_t err = esp_http_client_perform(http_client_);
  
  int status_code = 0;
  if (err == ESP_OK) {
    status_code = esp_http_client_get_status_code(http_client_);
    ESP_LOGI(TAG, "HTTP POST status = %d", status_code);
  } else {
    ESP_LOGE(TAG, "HTTP POST failed: %s", esp_err_to_name(err));
  }
  
  esp_http_client_cleanup(http_client_);
  http_client_ = nullptr;
  
  // Return status code for caller to check
  return status_code;
}

void PipecatSignaling::send_http_patch_(const std::string &path, const std::string &json_body) {
  std::string url = server_base_url_ + path;
  
  esp_http_client_config_t config = {};
  config.url = url.c_str();
  config.event_handler = http_event_handler_;
  config.user_data = this;
  config.method = HTTP_METHOD_PATCH;
  config.timeout_ms = 5000;
  
  http_client_ = esp_http_client_init(&config);
  if (http_client_ == nullptr) {
    ESP_LOGE(TAG, "Failed to initialize HTTP client");
    return;
  }
  
  esp_http_client_set_header(http_client_, "Content-Type", "application/json");
  esp_http_client_set_post_field(http_client_, json_body.c_str(), json_body.length());
  
  esp_err_t err = esp_http_client_perform(http_client_);
  
  if (err == ESP_OK) {
    int status_code = esp_http_client_get_status_code(http_client_);
    ESP_LOGD(TAG, "HTTP PATCH status = %d", status_code);
  } else {
    ESP_LOGE(TAG, "HTTP PATCH failed: %s", esp_err_to_name(err));
  }
  
  esp_http_client_cleanup(http_client_);
  http_client_ = nullptr;
}

}  // namespace voice_assistant_webrtc
}  // namespace esphome

#endif  // USE_ESP_IDF

