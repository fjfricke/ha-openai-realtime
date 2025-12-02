#!/usr/bin/with-contenv bashio
set -e

# Get configuration
OPENAI_API_KEY=$(bashio::config 'openai_api_key')
WEBSOCKET_PORT=$(bashio::config 'websocket_port')
HA_ACCESS_TOKEN=$(bashio::config 'ha_access_token')
HA_MCP_URL=$(bashio::config 'ha_mcp_url')

# Validate required configuration
if [ -z "$OPENAI_API_KEY" ]; then
    bashio::log.error "OPENAI_API_KEY is required but not set"
    exit 1
fi

# Export environment variables
export OPENAI_API_KEY
export WEBSOCKET_PORT

# Export optional Home Assistant MCP configuration
if [ -n "$HA_ACCESS_TOKEN" ]; then
    export HA_ACCESS_TOKEN
    bashio::log.info "Home Assistant MCP integration enabled"
fi

if [ -n "$HA_MCP_URL" ]; then
    export HA_MCP_URL
fi

# Start the application
exec poetry run python3 -m app.main

