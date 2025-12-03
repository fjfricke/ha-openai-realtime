#!/usr/bin/with-contenv bashio
set -e

# Get configuration
OPENAI_API_KEY=$(bashio::config 'openai_api_key')
WEBSOCKET_PORT=$(bashio::config 'websocket_port')
HA_MCP_URL=$(bashio::config 'ha_mcp_url')
LONGLIVED_TOKEN=$(bashio::config 'longlived_token')

# Validate required configuration
if [ -z "$OPENAI_API_KEY" ]; then
    bashio::log.error "OPENAI_API_KEY is required but not set"
    exit 1
fi

# Export environment variables
export OPENAI_API_KEY
export WEBSOCKET_PORT
export LONGLIVED_TOKEN

# Export HA_MCP_URL if set (empty string means use default in main.py)
if [ -n "$HA_MCP_URL" ]; then
    export HA_MCP_URL
fi

# SUPERVISOR_TOKEN is automatically provided by Home Assistant when homeassistant_api: true

# Start the application
export PYTHONUNBUFFERED=1
exec python3 -m app.main

