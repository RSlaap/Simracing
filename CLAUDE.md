# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SimRacing Orchestration System** - A distributed client-server system that synchronizes game launches across multiple racing simulator rigs on a local network. The system uses mDNS for automatic discovery, template-based UI automation, and a web interface for orchestration.

## Architecture

This is a **monorepo** containing two separate Python applications:

### SimRacingController (Orchestrator)
Central web server that discovers and manages multiple client setups. Provides a web dashboard for simultaneous multi-player game launches.

### SimRacingClient (Setup Agent)
Runs on each racing rig, registers via mDNS, receives commands from the orchestrator, and automates game launches using computer vision-based template matching.

### Key Architectural Patterns

**Network Discovery**: Zeroconf/mDNS automatic service discovery using `_simracing._tcp.local.` service type

**Communication Protocol**:
1. Client advertises via mDNS on port 5000
2. Orchestrator discovers and auto-registers with client
3. Client sends heartbeat every 5s to orchestrator
4. Orchestrator sends configure → start → stop commands
5. Setup assignment: first N online setups (ordered by setup ID) become players 1-N

**Template-Based Automation**: Uses OpenCV template matching to navigate game menus
- Templates captured with `templating/template_capture.py` (interactive crosshair tool)
- Navigation sequences defined in JSON with region coordinates and key presses
- Screen navigation in `utils/screen_navigator.py` handles retry logic and fallback

**Portable Deployment**: Both projects designed for offline deployment with embedded Python and virtual environments

## Development Commands

### SimRacingController (Orchestrator)

```bash
# Start the orchestrator web interface
scripts\launcher.bat
# Or directly:
venv\Scripts\python.exe orchestrator.py

# Access web interface at http://<local-ip>:8000

# Prepare portable environment (requires internet)
setup\prepare_setup.bat
```

### SimRacingClient (Setup Agent)

```bash
# Start the client service
scripts\launcher.bat
# Or directly:
venv\Scripts\python.exe simracing_client.py

# Service runs on port 5000 and auto-advertises via mDNS
```

### Template Capture Workflow

```bash
# 1. Launch the game manually
# 2. Run template capture tool
python SimRacingClient\templating\template_capture.py

# 3. Press 'S' to start capture
# 4. Click top-left then bottom-right corners of UI element
# 5. Repeat for each navigation step
# 6. Templates saved to unclassified_templates/ with JSON metadata
```

## Project Structure

```
SimRacingController/
├── orchestrator.py          # Main Flask server with discovery and API
├── static/index.html        # Web dashboard UI
├── scripts/launcher.bat     # Portable launcher
└── requirements.txt         # flask, zeroconf, requests, pydantic

SimRacingClient/
├── simracing_client.py      # Main Flask service with mDNS registration
├── client/
│   └── game_handler.py      # Game-specific launch orchestration
├── utils/
│   ├── game_launcher.py     # Subprocess-based game launching
│   ├── game_closer.py       # Process termination
│   ├── screen_navigator.py  # Template matching navigation engine
│   ├── focus_window.py      # Win32 window focus management
│   ├── input_blocker.py     # Keyboard/mouse input blocking
│   └── get_local_ip.py      # Network utility
└── templating/
    ├── template_capture.py  # Interactive template creation tool
    └── crosshair_overlay.py # Visual crosshair for capturing
```

## API Endpoints

### Orchestrator (port 8000)
- `POST /api/start_all` - Start game on N setups (body: `{game, num_players}`)
- `POST /api/stop_all` - Stop games on all online setups
- `GET /api/setups` - Get all discovered setups with status
- `POST /api/heartbeat` - Receive heartbeat from client (internal)
- `POST /api/register_setup` - Manually register a setup

### Client (port 5000)
- `POST /api/register_orchestrator` - Register orchestrator for heartbeats (body: `{orchestrator_url}`)
- `POST /api/configure` - Receive game configuration (body: `{game, session_id, player_id}`)
- `POST /api/start` - Start the configured game
- `POST /api/stop` - Stop the running game

## Dependencies

### Controller
- **flask** - Web server and API
- **zeroconf** - mDNS service discovery
- **requests** - HTTP client for setup communication
- **pydantic** - Data validation

### Client
- **flask** - REST API server
- **zeroconf** - mDNS service advertising
- **requests** - HTTP client for heartbeat
- **opencv-python** - Template matching
- **pyautogui** - Screen capture and mouse control
- **pydirectinput** - DirectInput keyboard simulation (games require this)
- **pynput** - Input capture for template tool
- **psutil** - Process management
- **pywin32** - Win32 API for window focus

## Navigation Template Format

Templates are stored as JSON with relative screen coordinates:

```json
[
  {
    "template": "main_menu.png",
    "region": [0.4, 0.3, 0.6, 0.5],
    "key_press": "enter"
  },
  {
    "template": "multiplayer.png",
    "region": [0.3, 0.4, 0.7, 0.6],
    "key_press": "down_arrow"
  }
]
```

The screen_navigator executes sequences with retry logic, fallback to previous step on failure, and abort after 2 consecutive failures.

## State Management

**Orchestrator State**:
- `REGISTERED_SETUPS`: Dict mapping `{ip}:{port}` to SetupRegistration
- Each setup tracks heartbeat (status, last_seen timestamp, current_game)
- Online = heartbeat received within 15 seconds

**Client State**:
- `SETUP_STATE`: Current status ('idle', 'configured', 'running'), game, session_id
- Heartbeat sent every 5 seconds to registered orchestrator

## Important Implementation Notes

- Both client and controller use port numbers that are **hardcoded** (8000 for orchestrator, 5000 for client)
- Game assignment uses **first N online setups** ordered by setup_id (lexicographic)
- Template matching uses **relative coordinates** (0.0-1.0) to support different screen resolutions
- The `skip_intro_until_screen` function repeatedly presses escape until first template appears
- Input blocking (Windows only) prevents user interference during automated navigation
- Session IDs use Unix timestamp: `session-{int(time.time())}`
- All game paths are configured in `client/config.json` (not version controlled)

## Portable Deployment Workflow

1. **Development machine** (with internet): Run `setup\prepare_setup.bat` to create venv with all dependencies
2. **Copy entire folder** to target offline PC (via USB/SSD)
3. **Launch** using `scripts\launcher.bat` - no additional setup required
4. Optionally install as Windows startup service with `scripts\install_startup.bat`

## Current Limitations / TODO

Based on `SimRacingClient/TODO.txt`:
- Game start/stop handlers in client are not fully implemented (stub endpoints)
- F1 22 specific: needs host vs joiner navigation templates
- PC naming/identification for consistent setup ordering
- Configuration settings for different game modes
