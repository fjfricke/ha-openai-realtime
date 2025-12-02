"""Tool for disconnecting the client when user says goodbye or stop."""
import logging
from typing import Dict, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


def get_disconnect_tool_definition() -> Dict[str, Any]:
    """Get the tool definition for OpenAI Realtime API."""
    return {
        "type": "function",
        "name": "disconnect_client",
        "description": "Disconnect the voice assistant session when the user says goodbye, farewell, stop, or only thank you without additional questions and wants to end the conversation. Use this when the user explicitly wants to end the conversation or says phrases like 'Auf Wiedersehen', 'Tschüss', 'Stop', 'Beenden', 'Ende', etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "The reason for disconnecting (e.g., 'user_said_goodbye', 'user_requested_stop')",
                    "enum": ["user_requested_stop", "conversation_ended"]
                }
            },
            "required": ["reason"]
        }
    }


async def execute_disconnect_tool(
    arguments: Dict[str, Any],
    disconnect_callback: Callable[[], Awaitable[None]]
) -> Dict[str, Any]:
    """
    Execute the disconnect tool.
    
    Args:
        arguments: Tool arguments containing the reason
        disconnect_callback: Async callback function to disconnect the client
        
    Returns:
        Result dictionary with success status
    """
    reason = arguments.get("reason", "unknown")
    logger.info(f"🔌 Disconnect tool called with reason: {reason}")
    
    try:
        # Call the disconnect callback
        await disconnect_callback()
        
        return {
            "success": True,
            "message": "Client disconnected successfully",
            "reason": reason
        }
    except Exception as e:
        logger.error(f"❌ Error executing disconnect tool: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "reason": reason
        }

