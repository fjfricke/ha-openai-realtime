import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.automation import maybe_simple_id

# Import after __init__ is fully loaded to avoid circular import
def get_voice_assistant_websocket_class():
from esphome.components.voice_assistant_websocket import VoiceAssistantWebSocket
    return VoiceAssistantWebSocket

CONF_VOICE_ASSISTANT_WEBSOCKET_ID = "voice_assistant_websocket_id"

VOICE_ASSISTANT_WEBSOCKET_ACTION_SCHEMA = maybe_simple_id(
    {
        cv.Required(CONF_ID): cv.use_id(VoiceAssistantWebSocket),
    }
)


@automation.register_action(
    "voice_assistant_websocket.start",
    lambda: get_voice_assistant_websocket_class().StartAction,
    VOICE_ASSISTANT_WEBSOCKET_ACTION_SCHEMA,
)
async def voice_assistant_websocket_start_to_code(config, action_id, template_arg, args):
    VoiceAssistantWebSocket = get_voice_assistant_websocket_class()
    paren = await cg.get_variable(config[CONF_ID])
    return cg.new_Pvariable(action_id, template_arg, paren)


@automation.register_action(
    "voice_assistant_websocket.stop",
    lambda: get_voice_assistant_websocket_class().StopAction,
    VOICE_ASSISTANT_WEBSOCKET_ACTION_SCHEMA,
)
async def voice_assistant_websocket_stop_to_code(config, action_id, template_arg, args):
    VoiceAssistantWebSocket = get_voice_assistant_websocket_class()
    paren = await cg.get_variable(config[CONF_ID])
    return cg.new_Pvariable(action_id, template_arg, paren)

