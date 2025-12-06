# ESP_PEER Examples Reference

This document contains notes from studying the official esp_peer examples to understand the correct usage patterns.

## Examples Location
- **Repository**: `esp-webrtc-solution-examples` (cloned from https://github.com/espressif/esp-webrtc-solution)
- **Peer Demo**: `components/esp_peer/examples/peer_demo/main/peer_demo.c`
- **WebRTC Solution**: `solutions/peer_demo/main/webrtc.c`

## Key Findings

### 1. ICE Server Configuration

**Peer Demo Example** (peer_demo.c:208-210):
```c
esp_peer_cfg_t cfg = {
    //.server_lists = &server_info, // Should set to actual stun/turn servers
    //.server_num = 0,
    ...
};
```
- **Key Insight**: The example shows ICE servers are **optional** (`server_num = 0`)
- For same-network communication, ICE servers may not be required
- Host candidates will be used automatically

**WebRTC Solution Example** (webrtc.c:172-173):
```c
.server_lists = &info->server_info,
.server_num = 1,
```
- Uses ICE servers when provided by signaling server
- Server info comes from signaling protocol

### 2. esp_peer_new_connection() Usage

**Peer Demo Example** (peer_demo.c:247-248):
```c
// Create connection
esp_peer_new_connection(peers[idx].peer);
```
- Called **immediately** after `esp_peer_open()`
- No delay or wait loop before calling
- No error checking (assumes it will succeed)

**WebRTC Solution Example** (webrtc.c:205-210):
```c
static int signaling_connected_handler(void* ctx)
{
    if (peer) {
        return esp_peer_new_connection(peer);
    }
    return 0;
}
```
- Called **after signaling is connected**
- Returns error code but doesn't handle it

### 3. esp_peer_main_loop() Usage

**Peer Demo Example** (peer_demo.c:166-175):
```c
static void pc_task(void *arg)
{
    peer_info_t *peer_info = (peer_info_t *)arg;
    while (peer_info->peer_running) {
        esp_peer_main_loop(peer_info->peer);
        vTaskDelay(pdMS_TO_TICKS(20));  // 20ms delay
    }
    peer_info->peer_stopped = true;
    vTaskDelete(NULL);
}
```
- **Key Insight**: Runs in a **dedicated task** with **20ms delay**
- Called continuously while peer is running
- Not called in main application loop

**WebRTC Solution Example** (webrtc.c:156-163):
```c
static void pc_task(void *arg)
{
    while (peer_running) {
        esp_peer_main_loop(peer);
        media_lib_thread_sleep(20);  // 20ms delay
    }
    media_lib_thread_destroy(NULL);
}
```
- Same pattern: dedicated task with 20ms delay
- Uses `media_lib_thread_sleep()` instead of `vTaskDelay()`

### 4. Peer Configuration

**Common Configuration Pattern**:
```c
esp_peer_cfg_t cfg = {
    .role = ESP_PEER_ROLE_CONTROLLING,  // or ESP_PEER_ROLE_CONTROLLED
    .audio_dir = ESP_PEER_MEDIA_DIR_SEND_RECV,
    .audio_info = {
        .codec = ESP_PEER_AUDIO_CODEC_G711A,  // or OPUS
    },
    .enable_data_channel = true,  // or false
    .on_state = peer_state_handler,
    .on_msg = peer_msg_handler,
    .on_audio_data = peer_audio_data_handler,
    .ctx = context_pointer,
    .extra_cfg = &peer_cfg,  // esp_peer_default_cfg_t
    .extra_size = sizeof(esp_peer_default_cfg_t),
};
```

### 5. Message Handling

**SDP Message Handler** (peer_demo.c:104-113):
```c
static int peer_msg_handler(esp_peer_msg_t *msg, void *ctx)
{
    if (msg->type == ESP_PEER_MSG_TYPE_SDP) {
        peer_info_t *peer_info = (peer_info_t *)ctx;
        // Exchange SDP with peer
        esp_peer_handle_t peer = (peer_info == &peers[0]) ? peers[1].peer : peers[0].peer;
        esp_peer_send_msg(peer, (esp_peer_msg_t *)msg);
    }
    return 0;
}
```
- Handles `ESP_PEER_MSG_TYPE_SDP` messages
- Sends SDP to signaling server or other peer
- Also handles `ESP_PEER_MSG_TYPE_CANDIDATE` (ICE candidates)

### 6. State Handling

**State Handler** (peer_demo.c:77-102):
```c
static int peer_state_handler(esp_peer_state_t state, void *ctx)
{
    peer_info_t *peer_info = (peer_info_t *)ctx;
    if (state == ESP_PEER_STATE_CONNECTED) {
        peer_info->peer_connected = true;
        // Start sending data
    } else if (state == ESP_PEER_STATE_DISCONNECTED) {
        peer_info->peer_connected = false;
        // Stop sending data
    }
    return 0;
}
```
- Handles `ESP_PEER_STATE_CONNECTED` and `ESP_PEER_STATE_DISCONNECTED`
- Other states: `ESP_PEER_STATE_NEW_CONNECTION`, `ESP_PEER_STATE_PAIRING`, etc.

## Differences from Our Implementation

1. **ICE Servers**: Examples show ICE servers are optional, but we're using a STUN server
2. **Main Loop**: Examples use dedicated tasks, we use ESPHome's `loop()` function
3. **Error Handling**: Examples don't check `esp_peer_new_connection()` return value
4. **Timing**: Examples call `esp_peer_new_connection()` immediately, we were waiting

## Recommendations

1. ✅ Keep calling `esp_peer_main_loop()` in `loop()` (ESPHome pattern)
2. ✅ Call `esp_peer_new_connection()` immediately after `esp_peer_open()`
3. ✅ Don't wait/block for SDP generation - let `esp_peer_main_loop()` handle it
4. ✅ Handle `ESP_PEER_STATE_DISCONNECTED` gracefully during signaling
5. ⚠️ Consider making ICE servers optional for same-network communication

## Current Implementation Status

- ✅ `esp_peer_main_loop()` called in `loop()` function
- ✅ `esp_peer_new_connection()` called after `esp_peer_open()`
- ✅ STUN server configured (`stun.l.google.com:19302`)
- ✅ Message handler sends SDP to Pipecat server
- ✅ State handler logs all state changes
- ⚠️ Still seeing "Fail to new connection" error - investigating

