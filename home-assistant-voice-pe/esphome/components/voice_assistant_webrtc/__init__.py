import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.components import microphone, speaker
from esphome.const import CONF_ID, CONF_MICROPHONE, CONF_SPEAKER
from esphome.core import CORE
from esphome.components.esp32 import add_idf_component

CODEOWNERS = ["@openai-realtime-voice-agent"]
DEPENDENCIES = ["microphone", "speaker", "wifi"]  # Add wifi dependency to ensure WiFi initializes first

voice_assistant_webrtc_ns = cg.esphome_ns.namespace("voice_assistant_webrtc")
VoiceAssistantWebRTC = voice_assistant_webrtc_ns.class_(
    "VoiceAssistantWebRTC", cg.Component
)

CONF_SERVER_BASE_URL = "server_base_url"
CONF_VOICE_ASSISTANT_WEBRTC = "voice_assistant_webrtc"
CONF_ON_CONNECTED = "on_connected"
CONF_ON_DISCONNECTED = "on_disconnected"
CONF_ON_ERROR = "on_error"
CONF_ON_STOPPED = "on_stopped"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(VoiceAssistantWebRTC),
        cv.Required(CONF_SERVER_BASE_URL): cv.string,
        cv.Optional(CONF_MICROPHONE): cv.use_id(microphone.Microphone),
        cv.Optional(CONF_SPEAKER): cv.use_id(speaker.Speaker),
        cv.Optional(CONF_ON_CONNECTED): automation.validate_automation(single=True),
        cv.Optional(CONF_ON_DISCONNECTED): automation.validate_automation(single=True),
        cv.Optional(CONF_ON_ERROR): automation.validate_automation(single=True),
        cv.Optional(CONF_ON_STOPPED): automation.validate_automation(single=True),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    # Add ESP-IDF components for WebRTC support
    if CORE.using_esp_idf:
        # esp_peer component - use v1.2.7 from registry
        # Note: This version requires mbedtls with SRTP support
        add_idf_component(
            name="espressif/esp_peer",
            ref="1.2.7"
        )
        
        # esp_libsrtp is a dependency of esp_peer and provides SRTP support
        # It should be automatically added, but we add it explicitly to ensure compatibility
        add_idf_component(
            name="espressif/esp_libsrtp",
            ref="^1.0.0"
        )
        
        # esp_afe_sr for audio processing (AEC, NS, AGC)
        add_idf_component(
            name="esp_afe_sr",
            repo="https://github.com/espressif/esp-sr.git",
            ref="v2.0.0"
        )

    cg.add(var.set_server_base_url(config[CONF_SERVER_BASE_URL]))

    if CONF_MICROPHONE in config:
        mic = await cg.get_variable(config[CONF_MICROPHONE])
        cg.add(var.set_microphone(mic))

    if CONF_SPEAKER in config:
        spkr = await cg.get_variable(config[CONF_SPEAKER])
        cg.add(var.set_speaker(spkr))

    # Register automation triggers
    if CONF_ON_CONNECTED in config:
        await automation.build_automation(
            var.get_connected_trigger(), [], config[CONF_ON_CONNECTED]
        )

    if CONF_ON_DISCONNECTED in config:
        await automation.build_automation(
            var.get_disconnected_trigger(), [], config[CONF_ON_DISCONNECTED]
        )

    if CONF_ON_ERROR in config:
        await automation.build_automation(
            var.get_error_trigger(), [], config[CONF_ON_ERROR]
        )

    if CONF_ON_STOPPED in config:
        await automation.build_automation(
            var.get_stopped_trigger(), [], config[CONF_ON_STOPPED]
        )


# Register actions and conditions
from esphome.automation import maybe_simple_id

CONF_VOICE_ASSISTANT_WEBRTC_ID = "voice_assistant_webrtc_id"

VOICE_ASSISTANT_WEBRTC_ACTION_SCHEMA = maybe_simple_id(
    {
        cv.Required(CONF_ID): cv.use_id(VoiceAssistantWebRTC),
    }
)

VOICE_ASSISTANT_WEBRTC_CONDITION_SCHEMA = maybe_simple_id(
    {
        cv.Required(CONF_ID): cv.use_id(VoiceAssistantWebRTC),
    }
)


@automation.register_action(
    "voice_assistant_webrtc.start",
    voice_assistant_webrtc_ns.class_("VoiceAssistantWebRTCStartAction"),
    VOICE_ASSISTANT_WEBRTC_ACTION_SCHEMA,
)
async def voice_assistant_webrtc_start_to_code(config, action_id, template_arg, args):
    paren = await cg.get_variable(config[CONF_ID])
    return cg.new_Pvariable(action_id, template_arg, paren)


@automation.register_action(
    "voice_assistant_webrtc.stop",
    voice_assistant_webrtc_ns.class_("VoiceAssistantWebRTCStopAction"),
    VOICE_ASSISTANT_WEBRTC_ACTION_SCHEMA,
)
async def voice_assistant_webrtc_stop_to_code(config, action_id, template_arg, args):
    paren = await cg.get_variable(config[CONF_ID])
    return cg.new_Pvariable(action_id, template_arg, paren)


@automation.register_condition(
    "voice_assistant_webrtc.is_running",
    voice_assistant_webrtc_ns.class_("VoiceAssistantWebRTCIsRunningCondition"),
    VOICE_ASSISTANT_WEBRTC_CONDITION_SCHEMA,
)
async def voice_assistant_webrtc_is_running_to_code(config, condition_id, template_arg, args):
    paren = await cg.get_variable(config[CONF_ID])
    return cg.new_Pvariable(condition_id, template_arg, paren)


@automation.register_condition(
    "voice_assistant_webrtc.is_connected",
    voice_assistant_webrtc_ns.class_("VoiceAssistantWebRTCIsConnectedCondition"),
    VOICE_ASSISTANT_WEBRTC_CONDITION_SCHEMA,
)
async def voice_assistant_webrtc_is_connected_to_code(config, condition_id, template_arg, args):
    paren = await cg.get_variable(config[CONF_ID])
    return cg.new_Pvariable(condition_id, template_arg, paren)
