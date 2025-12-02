# Migration zu Poetry - Zusammenfassung

## ✅ Durchgeführte Änderungen

### 1. Poetry-Konfiguration erstellt

**Neue Datei**: `pyproject.toml`
- Production-Dependencies: `openai`, `websockets`, `numpy`, `python-dotenv`
- Development-Dependencies: `esphome` (für Kompilierung)
- Python-Version: `^3.11`

### 2. Dockerfile angepasst

**Geändert**: `Dockerfile`
- Installiert Poetry
- Nutzt `poetry install --no-dev` für Production-Builds
- Kopiert `pyproject.toml` und `poetry.lock`
- Entfernt Poetry-Dateien nach Installation

### 3. .gitignore aktualisiert

**Geändert**: `.gitignore`
- `.venv/` hinzugefügt (Poetry Virtual Environment)
- `poetry.lock` wird **nicht** ignoriert (sollte committed werden für reproduzierbare Builds)

### 4. poetry.lock generiert

**Neue Datei**: `poetry.lock`
- Lock-File für reproduzierbare Builds
- Sollte im Repository committed werden

## 📝 Verwendung

### Lokale Entwicklung

```bash
# Dependencies installieren (inkl. ESPHome)
poetry install

# Poetry Shell aktivieren
poetry shell

# ESPHome für Kompilierung nutzen
esphome compile esphome_config.yaml
```

### Docker Build

Das Dockerfile nutzt Poetry automatisch:

```bash
docker build -t ha-openai-realtime .
```

### Dependencies aktualisieren

```bash
# Alle Dependencies aktualisieren
poetry update

# Nur bestimmte Dependency aktualisieren
poetry update esphome

# Lock-File neu generieren
poetry lock
```

## 🔄 Migration von requirements.txt

Die `requirements.txt` wurde durch `pyproject.toml` ersetzt. Alle Dependencies sind jetzt in Poetry definiert.

**Alte Dependencies** (requirements.txt):
- openai>=1.12.0
- websockets>=12.0
- numpy>=1.26.0
- python-dotenv>=1.0.0

**Neue Dependencies** (pyproject.toml):
- Production: Gleiche wie oben
- Development: esphome (neu hinzugefügt)

## 📚 Weitere Informationen

Siehe `POETRY_SETUP.md` für detaillierte Anleitung zur Poetry-Nutzung.

## ⚠️ Wichtige Hinweise

1. **poetry.lock** sollte im Repository committed werden für reproduzierbare Builds
2. **ESPHome** ist als Development-Dependency installiert und nur für lokale Kompilierung verfügbar
3. **Docker** installiert nur Production-Dependencies (`--no-dev`), daher ist ESPHome im Container nicht verfügbar
4. Für ESPHome-Kompilierung lokal: `poetry run esphome compile <config.yaml>`

