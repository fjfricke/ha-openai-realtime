ARG BUILD_FROM=ghcr.io/hassio-addons/base:latest
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Setup base
RUN \
    apk add --no-cache \
        python3 \
        py3-pip \
        py3-wheel \
        py3-setuptools \
        curl \
        ffmpeg \
        alsa-lib \
        alsa-utils

# Install Poetry
RUN \
    pip3 install --no-cache-dir --break-system-packages poetry \
    && poetry config virtualenvs.create false

# Copy Poetry configuration files and app directory for package installation
# Need to create the directory structure that matches pyproject.toml's "from" path
COPY pyproject.toml poetry.lock* /tmp/
RUN mkdir -p /tmp/openai_realtime_voice_agent
COPY app/ /tmp/openai_realtime_voice_agent/app/

# Install dependencies using Poetry
WORKDIR /tmp
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN \
    rm -f poetry.lock* \
    && poetry install --only=main --no-root --no-interaction --no-ansi \
    && rm -f pyproject.toml \
    && rm -rf openai_realtime_voice_agent/

# Reset working directory
WORKDIR /

# Copy application code
COPY app/ /app/

# Copy root filesystem
COPY root/ /
RUN chmod a+x /run.sh

# Set entrypoint
CMD ["/run.sh"]
