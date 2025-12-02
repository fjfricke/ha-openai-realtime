# Poetry Setup Guide

Das Projekt nutzt jetzt Poetry für Dependency-Management.

## Installation von Poetry

Falls Poetry noch nicht installiert ist:

```bash
# Linux/macOS
curl -sSL https://install.python-poetry.org | python3 -

# Oder mit pip
pip install poetry
```

## Erste Einrichtung

1. **Dependencies installieren** (inkl. Development-Dependencies):
```bash
poetry install
```

2. **Nur Production-Dependencies** (für Docker):
```bash
poetry install --no-dev
```

## ESPHome für Kompilierung

ESPHome ist als Development-Dependency installiert und kann für die Kompilierung der ESPHome-Komponenten verwendet werden:

```bash
# ESPHome im Poetry-Environment nutzen
poetry run esphome compile esphome_config.yaml

# Oder direkt im Poetry-Shell
poetry shell
esphome compile esphome_config.yaml
```

## Entwicklung

### Poetry Shell aktivieren

```bash
poetry shell
```

Danach sind alle Dependencies verfügbar.

### Dependencies hinzufügen

```bash
# Production-Dependency
poetry add package-name

# Development-Dependency
poetry add --group dev package-name
```

### Dependencies aktualisieren

```bash
poetry update
```

### Lock-File aktualisieren

```bash
poetry lock
```

## Docker Build

Das Dockerfile nutzt Poetry automatisch:

```bash
docker build -t ha-openai-realtime .
```

Das Dockerfile:
- Installiert Poetry
- Kopiert `pyproject.toml` und `poetry.lock`
- Installiert nur Production-Dependencies (`--no-dev`)
- Entfernt Poetry-Dateien nach Installation

## Migration von requirements.txt

Die `requirements.txt` wurde durch `pyproject.toml` ersetzt. Alle Dependencies sind jetzt in Poetry definiert:

- **Production**: `openai`, `websockets`, `numpy`, `python-dotenv`
- **Development**: `esphome`

## Troubleshooting

### Poetry-Lock-File fehlt

Falls `poetry.lock` fehlt (z.B. beim ersten Setup):

```bash
poetry lock
```

### Dependencies neu installieren

```bash
poetry install --sync
```

### Poetry-Cache leeren

```bash
poetry cache clear pypi --all
```

