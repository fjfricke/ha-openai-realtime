"""Tool for disconnecting the client when user says goodbye or stop."""
import asyncio
import json
import logging
from typing import Dict, Any, Callable, Awaitable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pipecat.services.llm_service import FunctionCallParams
    from pipecat.transports.websocket.server import WebsocketServerTransport
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

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
    disconnect_callback: Optional[Callable[[], Awaitable[None]]]
) -> Dict[str, Any]:
    """
    Execute the disconnect tool.
    
    Args:
        arguments: Tool arguments containing the reason
        disconnect_callback: Optional async callback function to disconnect the client
        
    Returns:
        Result dictionary with success status
    """
    reason = arguments.get("reason", "unknown")
    logger.info(f"🔌 Disconnect tool called with reason: {reason}")
    
    if not disconnect_callback:
        return {
            "success": False,
            "error": "Disconnect callback not available",
            "reason": reason
        }
    
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


def create_disconnect_callback(
    transport: Optional["WebsocketServerTransport"] | Optional["SmallWebRTCTransport"],
    reason: str = "user_requested"
) -> Callable[[], Awaitable[None]]:
    """
    Create a disconnect callback that closes the connection.
    
    Args:
        transport: The transport instance (WebSocket or WebRTC)
        reason: The reason for disconnecting
        
    Returns:
        Async callback function that closes the connection
    """
    async def disconnect_callback() -> None:
        """Disconnect callback that closes the connection."""
        logger.info("🔌 Disconnect tool triggered - closing connection")
        try:
            if transport is None:
                logger.warning("⚠️ No transport available for disconnect")
                return
            
            # Handle WebRTC transport
            if hasattr(transport, 'webrtc_connection') or hasattr(transport, '_client'):
                # WebRTC transport - disconnect the peer connection
                if hasattr(transport, '_client') and hasattr(transport._client, '_connection'):
                    connection = transport._client._connection
                    if connection:
                        await connection.disconnect()
                        logger.info("✅ Closed WebRTC connection")
                else:
                    logger.warning("⚠️ Could not find WebRTC connection to close")
            # Handle WebSocket transport (legacy)
            elif hasattr(transport, 'input'):
                input_transport = transport.input()
                if hasattr(input_transport, '_websocket') and input_transport._websocket:
                    # Send disconnect message to client before closing
                    try:
                        await input_transport._websocket.send(json.dumps({
                            "type": "disconnect",
                            "message": "User requested disconnect",
                            "reason": reason
                        }))
                        logger.info("✅ Sent disconnect message to client")
                        await asyncio.sleep(0.1)  # Give client time to process
                    except Exception as e:
                        logger.warning(f"⚠️ Error sending disconnect message: {e}")
                    
                    # Close the WebSocket connection
                    await input_transport._websocket.close()
                    logger.info("✅ Closed WebSocket connection")
        except Exception as e:
            logger.error(f"❌ Error closing connection: {e}", exc_info=True)
    
    return disconnect_callback


def create_disconnect_tool_handler(
    transport: Optional["WebsocketServerTransport"] | Optional["SmallWebRTCTransport"]
) -> Callable[["FunctionCallParams"], Awaitable[None]]:
    """
    Create a disconnect tool handler for Pipecat's OpenAI Realtime Service.
    
    Args:
        transport: The transport instance (WebSocket or WebRTC)
        
    Returns:
        Async function handler that can be registered with OpenAIRealtimeLLMService
    """
    async def disconnect_tool_handler(params: "FunctionCallParams") -> None:
        """Handle disconnect tool calls."""
        logger.info(f"🔌 Disconnect tool called: {params.function_name} with arguments: {params.arguments}")
        
        # Get reason from arguments
        reason = params.arguments.get("reason", "user_requested")
        
        # Create disconnect callback that closes the connection
        disconnect_callback = create_disconnect_callback(transport, reason=reason)
        
        # Execute the disconnect tool
        result = await execute_disconnect_tool(params.arguments, disconnect_callback)
        
        # Send result back to OpenAI
        if result.get("success"):
            await params.result_callback(f"Disconnected successfully: {result.get('message', '')}")
        else:
            await params.result_callback(f"Error: {result.get('error', 'Unknown error')}")
    
    return disconnect_tool_handler
