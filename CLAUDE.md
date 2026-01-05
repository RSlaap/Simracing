# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SimRacing Orchestration System** - A distributed client-server system that synchronizes game launches across multiple racing simulator rigs on a local network. The system uses mDNS for automatic discovery, template-based UI automation, and a web interface for orchestration.

## Architecture

This is a **monorepo** containing two separate Python applications:

### SimRacingController (Orchestrator)
Central web server that discovers and manages multiple client setups. Provides a web dashboard for simultaneous multi-player game launches.

### SimRacingClient (Setup Agent)
Runs on each racing rig, registers via mDNS with a unique name and ID (configured in machine_configuration.json), receives commands from the orchestrator, and automates game launches using computer vision-based template matching.

### Key Architectural Patterns

**Network Discovery**: Zeroconf/mDNS automatic service discovery using `_simracing._tcp.local.` service type

**Communication Protocol**:
1. Client advertises via mDNS on port 5000
2. Orchestrator discovers and auto-registers with client
3. Client sends heartbeat every 5s to orchestrator
4. Orchestrator sends configure → start → stop commands
5. Setup assignment: setups ordered by machine ID (lowest ID first)
6. Role assignment: lowest ID = host, others = client
7. Two-phase startup: Configure all → Wait for confirmations → Start all

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
# 1. Create machine configuration file (required)
# Copy and edit the example:
copy machine_configuration.example.json machine_configuration.json
# Edit to set unique name and ID for this machine

# 2. Start the client service
scripts\launcher.bat
# Or directly:
venv\Scripts\python.exe src\simracing_client.py

# Service runs on port 5000 and auto-advertises via mDNS
```

### Template Capture Workflow

```bash
# 1. Launch the game manually
# 2. Run template capture tool
python SimRacingClient\src\templating\template_capture.py

# 3. Press 'S' to start capture
# 4. Click top-left then bottom-right corners of UI element
# 5. Repeat for each navigation step
# 6. Templates saved to src/templating/unclassified_templates/ with JSON metadata
```

## Project Structure

```
SimRacingController/
├── orchestrator.py          # Main Flask server with discovery and API
├── static/index.html        # Web dashboard UI
├── scripts/launcher.bat     # Portable launcher
└── requirements.txt         # flask, zeroconf, requests, pydantic

SimRacingClient/
├── src/
│   ├── simracing_client.py      # Main Flask service with mDNS registration
│   ├── game_handler/
│   │   ├── game_handler.py      # Game-specific launch orchestration
│   │   └── config.json          # Game paths and process names
│   ├── utils/
│   │   ├── game_launcher.py     # Subprocess-based game launching
│   │   ├── game_closer.py       # Process termination
│   │   ├── screen_navigator.py  # Template matching navigation engine
│   │   ├── focus_window.py      # Win32 window focus management
│   │   ├── input_blocker.py     # Keyboard/mouse input blocking
│   │   └── get_local_ip.py      # Network utility
│   └── templating/
│       ├── template_capture.py  # Interactive template creation tool
│       └── crosshair_overlay.py # Visual crosshair for capturing
├── scripts/launcher.bat         # Portable launcher
└── requirements.txt             # Dependencies
```

## API Endpoints

### Orchestrator (port 8000)
- `POST /api/start_all` - Start game on N setups (body: `{game, num_players}`)
  - Phase 1: Configures all setups with roles (host/client) and waits for confirmation
  - Phase 2: Only if all configured, starts games on all setups
- `POST /api/stop_all` - Stop games on all online setups
- `GET /api/setups` - Get all discovered setups with status
- `POST /api/heartbeat` - Receive heartbeat from client (internal)
- `POST /api/register_setup` - Manually register a setup

### Client (port 5000)
- `POST /api/register_orchestrator` - Register orchestrator for heartbeats (body: `{orchestrator_url}`)
- `POST /api/configure` - Receive game configuration (body: `{game, session_id, player_id, role}`)
  - Returns confirmation when successfully configured
- `POST /api/start` - Start the configured game (called after all setups are configured)
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

Templates are stored per-game in JSON with relative screen coordinates. Two formats are supported:

**Single-Option Format (backward compatible):**
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

**Multi-Option Format (new):**
```json
[
  {
    "options": [
      {
        "template": "error_dialog.png",
        "region": [0.4, 0.5, 0.6, 0.6],
        "key_press": "enter"
      },
      {
        "template": "no_error_menu.png",
        "region": [0.4, 0.3, 0.6, 0.5],
        "key_press": "enter"
      }
    ]
  }
]
```

**Multi-Option Behavior:**
- At each step, tries all options in order
- Executes the action for the first matching template
- If no options match, retries the entire step
- Useful for: error handling, alternative UI states, dynamic content, track selection

**Sequential Actions:**
- `key_press` can be a string (`"enter"`) or array (`["down", "down", "enter"]`)
- Array actions execute in sequence with configurable delay (default 0.2s)
- Works with both single-option and multi-option formats
- Useful for: menu navigation, multi-step selections, complex input sequences

**Mixed Format:** You can combine both formats in the same template file. The navigator automatically detects which format each step uses.

Each game has its own folder under `src/templating/templates/{game_name}/` containing:
- `game_host_template.json` - Navigation sequence definition for host role
- `game_client_template.json` - Navigation sequence for client role (future)
- Image subfolders (e.g., `multiplayer_navigation/`, `lan_host/`, `track_selection/`)
- `TEMPLATE_FORMAT_EXAMPLES.json` - Examples and documentation of template formats

The screen_navigator executes sequences with retry logic, fallback to previous step on failure, and abort after 2 consecutive failures.

## Machine Configuration

Each client requires a `machine_configuration.json` file in the SimRacingClient directory:

```json
{
    "name": "SimRig-1",
    "id": 1
}
```

- **name**: Human-readable identifier for the machine (used in UI and logs)
- **id**: Unique integer ID (used for setup ordering - lower IDs become host)

The client will not start without this file. Use `machine_configuration.example.json` as a template.

## State Management

**Orchestrator State**:
- `REGISTERED_SETUPS`: Dict mapping `{ip}:{port}` to SetupRegistration
- Each setup tracks heartbeat (name, id, status, last_seen timestamp, current_game)
- Online = heartbeat received within 15 seconds

**Client State**:
- `MACHINE_CONFIG`: Machine name and ID loaded from machine_configuration.json
- `SETUP_STATE`: Current status ('idle', 'configured', 'running'), game, session_id, role
- Heartbeat sent every 5 seconds to registered orchestrator with name and ID
- Role ('host' or 'client') assigned during configuration phase

## Important Implementation Notes

- Both client and controller use port numbers that are **hardcoded** (8000 for orchestrator, 5000 for client)
- Each client MUST have `machine_configuration.json` with unique name and ID before starting
- Game assignment uses **first N online setups** ordered by machine ID (lowest ID = player 1 = host)
- Template matching uses **relative coordinates** (0.0-1.0) to support different screen resolutions
- The `skip_intro_until_screen` function repeatedly presses escape until first template appears
- Input blocking (Windows only) prevents user interference during automated navigation
- Session IDs use Unix timestamp: `session-{int(time.time())}`
- All game paths are configured in `src/game_handler/config.json` (not version controlled)
- Machine names appear in web UI and logs; machine IDs determine role assignment

## Portable Deployment Workflow

1. **Development machine** (with internet): Run `setup\prepare_setup.bat` to create venv with all dependencies
2. **Copy entire folder** to target offline PC (via USB/SSD)
3. **Launch** using `scripts\launcher.bat` - no additional setup required
4. Optionally install as Windows startup service with `scripts\install_startup.bat`

## Game Launch Flow

When a game is started from the orchestrator:

1. **Discovery & Sorting**: Online setups are retrieved and sorted by machine ID (ascending)
2. **Role Assignment**:
   - Lowest ID (position 0) = "host"
   - All others = "client"
3. **Phase 1 - Configuration**:
   - Orchestrator sends `/api/configure` to each setup with game, session_id, player_id, and role
   - Each client stores configuration and responds with confirmation
   - If any configuration fails, the entire operation is aborted
4. **Phase 2 - Game Start**:
   - Only after ALL configurations are confirmed
   - Orchestrator sends `/api/start` to each configured setup
   - Clients launch game with appropriate navigation template (host vs client - to be implemented)

## Current Limitations / TODO

Based on `SimRacingClient/TODO.txt`:
- Game start/stop handlers in client need to use role to select correct template
- F1 22 specific: needs host vs joiner navigation templates
- Template selection based on role not yet implemented in start_game endpoint
