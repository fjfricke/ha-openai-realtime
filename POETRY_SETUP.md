# Poetry Setup Guide

This project uses separate Poetry environments for the client and server components to avoid dependency conflicts.

## Project Structure

- **Client** (`home-assistant-voice-pe/`): ESPHome configuration and compilation tools
- **Server** (`openai_realtime_voice_agent/`): Pipecat-based OpenAI Realtime voice agent server
- **Root**: Minimal workspace configuration

## Installation

### Client (ESPHome)

For ESPHome configuration and compilation:

```bash
cd home-assistant-voice-pe
poetry install
```

This will install ESPHome and its dependencies in a separate virtual environment.

### Server (Pipecat)

For the OpenAI Realtime voice agent server:

```bash
cd openai_realtime_voice_agent
poetry install
```

This will install Pipecat, OpenAI dependencies, and other server requirements in a separate virtual environment.

## Usage

### Client - ESPHome Compilation

```bash
cd home-assistant-voice-pe
poetry shell
esphome compile voice_pe_config.yaml
```

Or directly:
```bash
cd home-assistant-voice-pe
poetry run esphome compile voice_pe_config.yaml
```

### Server - Running the Voice Agent

```bash
cd openai_realtime_voice_agent
poetry shell
python -m app.main
```

Or directly:
```bash
cd openai_realtime_voice_agent
poetry run start
```

## Why Separate Projects?

ESPHome and Pipecat have different dependency requirements that can conflict when installed in the same environment. By using separate Poetry projects:

- Each component has its own virtual environment
- No dependency conflicts
- Cleaner dependency management
- Easier to maintain and update independently

## Development

### Adding Dependencies

**Client:**
```bash
cd home-assistant-voice-pe
poetry add package-name
```

**Server:**
```bash
cd openai_realtime_voice_agent
poetry add package-name
```

### Updating Dependencies

**Client:**
```bash
cd home-assistant-voice-pe
poetry update
```

**Server:**
```bash
cd openai_realtime_voice_agent
poetry update
```

## Docker Build

The Dockerfile in `openai_realtime_voice_agent/` uses Poetry to install server dependencies:

```bash
cd openai_realtime_voice_agent
docker build -t openai-realtime-voice-agent .
```

## Troubleshooting

### Poetry Lock File Issues

If you encounter lock file issues:

```bash
# For client
cd home-assistant-voice-pe
poetry lock

# For server
cd openai_realtime_voice_agent
poetry lock
```

### Virtual Environment Issues

Each project creates its own virtual environment:
- Client: `home-assistant-voice-pe/.venv`
- Server: `openai_realtime_voice_agent/.venv`

To recreate:
```bash
cd <project-directory>
rm -rf .venv
poetry install
```
