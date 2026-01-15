# CAMMUS Pre-Launch Configuration Guide

This guide explains how to set up automatic CAMMUS software configuration before game launches.

## Overview

The pre-launch configuration feature allows you to automatically configure external software (like CAMMUS wheel/pedal/motion sim software) before launching a game. The system uses template matching to find and click buttons in the CAMMUS interface.

## How It Works

1. **Before game launch**: The system can optionally launch CAMMUS software
2. **Find buttons**: Uses OpenCV template matching to locate buttons on screen
3. **Click sequence**: Clicks through a configured sequence of buttons
4. **Launch game**: Only after CAMMUS is configured, the game launches

## Setup Steps

### 1. Capture CAMMUS Button Templates

Run the template capture tool while CAMMUS is open:

```bash
python src\templating\template_capture.py
```

**Capture the following buttons:**
- Settings button
- Wheel configuration tab
- Apply/Save button
- Any other buttons you need to click

**Tips:**
- Press 'S' to start capture mode
- Click top-left then bottom-right corners of each button
- Templates are saved to `src\templating\unclassified_templates\`
- Move captured templates to `templates\CAMMUS\` folder

### 2. Organize Templates

Create a folder structure:
```
templates/
  └── CAMMUS/
      ├── settings_button.png
      ├── wheel_tab.png
      ├── apply_button.png
      └── ... (other buttons)
```

### 3. Configure config.json

Edit `config.json` for each game that needs CAMMUS configuration:

```json
{
  "f1_22": {
    "name": "F1 22",
    "executable_path": "Games/F1 22 Champions Edition/F1_22.exe",
    "process_name": "F1_22.exe",
    "window_title": "F1 22",

    "pre_launch_config": {
      "enabled": true,                                    // Set to true to enable
      "executable_path": "C:/Program Files/CAMMUS/CAMMUS.exe",  // Path to CAMMUS
      "process_name": "CAMMUS.exe",                      // Process name to check
      "window_title": "CAMMUS",                          // Window title to focus
      "template_dir": "CAMMUS",                          // Folder in templates/
      "template_threshold": 0.85,                        // Matching threshold (0.0-1.0)
      "max_retries": 10,                                 // Retries per button
      "retry_delay": 1.0,                                // Seconds between retries
      "click_delay": 0.5,                                // Seconds after each click
      "click_steps": [
        {
          "template": "settings_button.png",             // First button to click
          "double_click": false                          // Single click
        },
        {
          "template": "wheel_tab.png",                   // Second button
          "double_click": false
        },
        {
          "template": "apply_button.png",                // Third button
          "double_click": false
        }
      ]
    },

    "navigation_config": {
      // ... existing game navigation
    }
  }
}
```

## Configuration Options

### Required Fields

- `enabled`: Whether pre-launch config is active for this game
- `template_dir`: Folder containing template images (relative to `templates/`)
- `click_steps`: List of buttons to click in sequence

### Optional Fields

- `executable_path`: Path to CAMMUS executable (if needs launching)
- `process_name`: Process name to check if already running
- `window_title`: Window title to focus before clicking
- `template_threshold`: Matching confidence (default: 0.85)
  - Higher = more strict matching (0.9-0.95 for exact matches)
  - Lower = more lenient (0.7-0.8 if buttons change slightly)
- `max_retries`: How many times to retry finding each button (default: 10)
- `retry_delay`: Seconds to wait between retries (default: 1.0)
- `click_delay`: Seconds to wait after clicking (default: 0.5)

### Click Step Options

Each step in `click_steps`:
- `template`: Template image filename (required)
- `double_click`: Use double-click instead of single-click (optional, default: false)

## How the System Works

### Execution Flow

When you start a game with pre-launch config enabled:

1. **Check if CAMMUS is running**
   - If not running and `executable_path` is set → Launch CAMMUS
   - If already running → Focus the window

2. **Execute click sequence**
   - For each step:
     - Search entire screen for template
     - Click on it when found
     - Wait `click_delay` seconds
     - If not found, retry up to `max_retries` times

3. **Launch game**
   - Only after all clicks succeed
   - If any click fails → Abort game launch

### Template Matching

The system uses **full-screen template matching**:
- Searches the entire screen for the button
- No need to specify coordinates
- Clicks the center of the matched region
- Works across different screen resolutions

## Troubleshooting

### Button Not Found

**Problem**: Template matching fails, button not clicked

**Solutions**:
1. Lower `template_threshold` (try 0.75-0.80)
2. Recapture template at exact screen position
3. Check template file path is correct
4. Increase `max_retries` and `retry_delay`

### CAMMUS Not Launching

**Problem**: CAMMUS doesn't start automatically

**Solutions**:
1. Check `executable_path` is correct
2. Check `process_name` matches actual process
3. Manually start CAMMUS before game launch (system will detect it)

### Wrong Button Clicked

**Problem**: System clicks wrong button

**Solutions**:
1. Increase `template_threshold` (try 0.90-0.95)
2. Recapture template more precisely
3. Check for duplicate buttons on screen

### Clicks Too Fast

**Problem**: UI doesn't update before next click

**Solutions**:
1. Increase `click_delay` (try 1.0-2.0 seconds)
2. Increase `retry_delay` for slower UI transitions

## Example Workflows

### Simple Configuration (CAMMUS Already Running)

If CAMMUS is always running in background:

```json
"pre_launch_config": {
  "enabled": true,
  "template_dir": "CAMMUS",
  "click_steps": [
    {"template": "profile_button.png"},
    {"template": "f1_profile.png"}
  ]
}
```

### Full Configuration (Launch CAMMUS)

If CAMMUS needs to be started:

```json
"pre_launch_config": {
  "enabled": true,
  "executable_path": "C:/CAMMUS/CAMMUS.exe",
  "process_name": "CAMMUS.exe",
  "window_title": "CAMMUS Control",
  "template_dir": "CAMMUS",
  "template_threshold": 0.85,
  "max_retries": 15,
  "retry_delay": 1.5,
  "click_delay": 1.0,
  "click_steps": [
    {"template": "settings.png"},
    {"template": "wheel_config.png"},
    {"template": "load_preset.png"},
    {"template": "f1_preset.png", "double_click": true},
    {"template": "apply.png"}
  ]
}
```

### Disable Pre-Launch Config

To disable for a specific game:

```json
"pre_launch_config": {
  "enabled": false
}
```

## Tips

1. **Test templates first**: Use `template_capture.py` to verify button positions
2. **Use high thresholds**: Start with 0.85-0.90 for reliable matching
3. **Add delays**: Give UI time to respond between clicks
4. **Keep it simple**: Only configure what's necessary
5. **One game at a time**: Test with one game before copying to others

## Advanced Usage

### Using with Different Games

Each game can have different CAMMUS configurations:

```json
{
  "f1_22": {
    "pre_launch_config": {
      "enabled": true,
      "click_steps": [
        {"template": "f1_profile.png"}
      ]
    }
  },
  "acc": {
    "pre_launch_config": {
      "enabled": true,
      "click_steps": [
        {"template": "gt3_profile.png"}
      ]
    }
  }
}
```

### Skipping CAMMUS Launch

If CAMMUS should always be running manually:

```json
"pre_launch_config": {
  "enabled": true,
  "window_title": "CAMMUS",  // Just focus, don't launch
  "template_dir": "CAMMUS",
  "click_steps": [...]
}
```

## File Structure

After setup, your directory should look like:

```
SimRacingClient/
├── config.json                              # Game + CAMMUS config
├── templates/
│   ├── CAMMUS/
│   │   ├── settings_button.png
│   │   ├── wheel_tab.png
│   │   └── apply_button.png
│   └── F1_22/
│       └── ... (game navigation templates)
├── src/
│   ├── utils/
│   │   └── click_navigator.py               # Click-based navigation
│   └── templating/
│       └── template_capture.py              # Template capture tool
└── scripts/
    └── launcher.bat
```

## Need Help?

- Check logs in `scripts/simracing_client.log` for detailed error messages
- Template matching reports confidence scores for debugging
- Test CAMMUS clicks independently before full game launch
