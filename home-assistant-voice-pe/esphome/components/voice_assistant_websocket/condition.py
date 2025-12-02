import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.automation import maybe_simple_id

# Import after __init__ is fully loaded to avoid circular import
def get_voice_assistant_websocket_class():
    from esphome.components.voice_assistant_websocket import VoiceAssistantWebSocket
    return VoiceAssistantWebSocket

CONF_VOICE_ASSISTANT_WEBSOCKET_ID = "voice_assistant_websocket_id"

VOICE_ASSISTANT_WEBSOCKET_CONDITION_SCHEMA = maybe_simple_id(
    {
        cv.Required(CONF_ID): cv.use_id(VoiceAssistantWebSocket),
    }
)


@automation.register_condition(
    "voice_assistant_websocket.is_running",
    lambda: get_voice_assistant_websocket_class().IsRunningCondition,
    VOICE_ASSISTANT_WEBSOCKET_CONDITION_SCHEMA,
)
async def voice_assistant_websocket_is_running_to_code(config, condition_id, template_arg, args):
    VoiceAssistantWebSocket = get_voice_assistant_websocket_class()
    paren = await cg.get_variable(config[CONF_ID])
    return cg.new_Pvariable(condition_id, template_arg, paren)

