# Multi-Option Navigation Template Guide

## Overview

The screen navigation system now supports:
1. **Multi-option steps** - Multiple templates can be matched at a single navigation step, with different actions executed based on which template matches first
2. **Sequential actions** - A single match can trigger multiple key presses in sequence (e.g., `["down", "down", "down"]`)
3. **Combined** - Multi-option steps where each option can have sequential actions

## Sequential Actions

### When to Use
Use sequential actions when a template match requires multiple key presses in sequence:
- Navigating multiple menu items down (e.g., `["down", "down", "down"]`)
- Complex navigation requiring multiple keys (e.g., `["right", "down", "enter"]`)
- Skipping through multiple screens (e.g., `["space", "space", "enter"]`)

### Basic Example
```json
{
  "template": "menu_screen.png",
  "region": [0.4, 0.3, 0.6, 0.5],
  "key_press": ["down", "down", "down", "enter"]
}
```

This will:
1. Match the template
2. Press "down" three times (with 0.2s delay between each)
3. Press "enter"
4. Move to the next step

### Delay Between Actions
By default, there's a 0.2 second delay between sequential actions. You can adjust this:
```python
load_and_execute_navigation(
    steps=steps,
    template_dir=template_dir,
    action_delay=0.3  # 0.3 seconds between key presses
)
```

## When to Use Multi-Option Steps

### 1. Error Dialog Handling
When error dialogs may or may not appear during navigation:

```json
{
  "options": [
    {
      "template": "multiplayer_navigation/connection_error.png",
      "region": [0.3, 0.4, 0.7, 0.6],
      "key_press": "enter"
    },
    {
      "template": "multiplayer_navigation/lobby.png",
      "region": [0.2, 0.1, 0.8, 0.3],
      "key_press": "down"
    }
  ]
}
```

### 2. Alternative UI States
When the game might show different buttons or prompts:

```json
{
  "options": [
    {
      "template": "multiplayer_navigation/skip_button.png",
      "region": [0.7, 0.8, 0.9, 0.9],
      "key_press": "space"
    },
    {
      "template": "multiplayer_navigation/continue_button.png",
      "region": [0.7, 0.8, 0.9, 0.9],
      "key_press": "enter"
    },
    {
      "template": "multiplayer_navigation/already_passed.png",
      "region": [0.4, 0.3, 0.6, 0.5],
      "key_press": "escape"
    }
  ]
}
```

### 3. Dynamic Content Selection
When any option from a set is acceptable (e.g., track selection):

```json
{
  "options": [
    {
      "template": "track_selection/track_monaco.png",
      "region": [0.1, 0.2, 0.3, 0.3],
      "key_press": "enter"
    },
    {
      "template": "track_selection/track_silverstone.png",
      "region": [0.1, 0.2, 0.3, 0.3],
      "key_press": "enter"
    },
    {
      "template": "track_selection/track_spa.png",
      "region": [0.1, 0.2, 0.3, 0.3],
      "key_press": "enter"
    }
  ]
}
```

### 4. Account/Login Variations
When different account states show different screens:

```json
{
  "options": [
    {
      "template": "multiplayer_navigation/login_required.png",
      "region": [0.3, 0.3, 0.7, 0.7],
      "key_press": "enter"
    },
    {
      "template": "multiplayer_navigation/logged_in.png",
      "region": [0.3, 0.3, 0.7, 0.7],
      "key_press": "down_arrow"
    },
    {
      "template": "multiplayer_navigation/guest_mode.png",
      "region": [0.3, 0.3, 0.7, 0.7],
      "key_press": "escape"
    }
  ]
}
```

### 5. Combining Multi-Option with Sequential Actions
When different UI states require different navigation sequences:

```json
{
  "options": [
    {
      "template": "track_selection/desired_track_at_top.png",
      "region": [0.3, 0.2, 0.7, 0.4],
      "key_press": "enter"
    },
    {
      "template": "track_selection/desired_track_in_middle.png",
      "region": [0.3, 0.2, 0.7, 0.4],
      "key_press": ["down", "down", "enter"]
    },
    {
      "template": "track_selection/desired_track_at_bottom.png",
      "region": [0.3, 0.2, 0.7, 0.4],
      "key_press": ["down", "down", "down", "down", "enter"]
    }
  ]
}
```

This is powerful for:
- Track selection where position varies
- Menu navigation with dynamic item counts
- Situations where you need different navigation depth

## How It Works

### Matching Behavior
1. **Order matters**: Options are checked in the order they appear in the array
2. **First match wins**: As soon as one template matches, its action is executed
3. **Retry on failure**: If no options match, the entire step retries (up to `max_retries`)
4. **Fallback logic**: Failed steps fall back to previous step (same as single-option format)

### Example Flow
```
Step with 3 options: [A, B, C]
Attempt 1: Check A -> no match, Check B -> no match, Check C -> MATCH! Execute action C
Step succeeds, move to next step
```

```
Step with 3 options: [A, B, C]
Attempt 1-10: None match
Step fails, retry previous step
```

## Backward Compatibility

Old single-option format still works:
```json
{
  "template": "main_menu.png",
  "region": [0.4, 0.3, 0.6, 0.5],
  "key_press": "enter"
}
```

You can mix both formats in the same template file:
```json
[
  {
    "template": "main_menu.png",
    "region": [0.4, 0.3, 0.6, 0.5],
    "key_press": "enter"
  },
  {
    "options": [
      {
        "template": "error.png",
        "region": [0.3, 0.4, 0.7, 0.6],
        "key_press": "enter"
      },
      {
        "template": "no_error.png",
        "region": [0.4, 0.3, 0.6, 0.5],
        "key_press": "down"
      }
    ]
  },
  {
    "template": "lobby.png",
    "region": [0.2, 0.1, 0.8, 0.3],
    "key_press": "space"
  }
]
```

## Best Practices

### 1. Order Options by Likelihood
Place the most likely option first to minimize checking time:
```json
{
  "options": [
    {
      "template": "common_case.png",
      ...
    },
    {
      "template": "rare_error.png",
      ...
    }
  ]
}
```

### 2. Use Distinct Templates
Ensure templates are visually distinct to avoid false matches:
```json
// GOOD - Different UI elements
{
  "options": [
    {"template": "button_ok.png", ...},
    {"template": "button_cancel.png", ...}
  ]
}

// BAD - Similar looking elements
{
  "options": [
    {"template": "button_1.png", ...},  // Might match button_2 by mistake
    {"template": "button_2.png", ...}
  ]
}
```

### 3. Group Related Options
Keep related alternatives in one multi-option step:
```json
// GOOD - All account prompts in one step
{
  "options": [
    {"template": "account_login.png", ...},
    {"template": "account_skip.png", ...},
    {"template": "account_guest.png", ...}
  ]
}

// BAD - Separate steps for related options
// (causes unnecessary failures and retries)
```

### 4. Use Appropriate Thresholds
For similar-looking UI elements, you may need to adjust the matching threshold in code:
```python
load_and_execute_navigation(
    steps=steps,
    template_dir=template_dir,
    threshold=0.85  # Higher = stricter matching
)
```

## Converting Existing Templates

### Adding Multi-Option Support

**Before:**
```json
[
  {"template": "step1.png", "region": [...], "key_press": "enter"},
  {"template": "step2.png", "region": [...], "key_press": "down"},
  {"template": "step3.png", "region": [...], "key_press": "enter"}
]
```

**After (if step2 has alternatives):**
```json
[
  {"template": "step1.png", "region": [...], "key_press": "enter"},
  {
    "options": [
      {"template": "step2_option_a.png", "region": [...], "key_press": "down"},
      {"template": "step2_option_b.png", "region": [...], "key_press": "space"}
    ]
  },
  {"template": "step3.png", "region": [...], "key_press": "enter"}
]
```

### Adding Sequential Actions

**Before (repeating similar steps):**
```json
[
  {"template": "menu.png", "region": [...], "key_press": "down"},
  {"template": "menu.png", "region": [...], "key_press": "down"},
  {"template": "menu.png", "region": [...], "key_press": "down"},
  {"template": "submenu.png", "region": [...], "key_press": "enter"}
]
```

**After (simplified):**
```json
[
  {"template": "menu.png", "region": [...], "key_press": ["down", "down", "down"]},
  {"template": "submenu.png", "region": [...], "key_press": "enter"}
]
```

### Combining Both Features

**Scenario:** Track selection where track position varies
```json
{
  "options": [
    {
      "template": "track_selection/monaco_position_1.png",
      "region": [0.3, 0.2, 0.7, 0.4],
      "key_press": "enter"
    },
    {
      "template": "track_selection/monaco_position_3.png",
      "region": [0.3, 0.2, 0.7, 0.4],
      "key_press": ["down", "down", "enter"]
    },
    {
      "template": "track_selection/monaco_position_5.png",
      "region": [0.3, 0.2, 0.7, 0.4],
      "key_press": ["down", "down", "down", "down", "enter"]
    }
  ]
}
```

## Debugging Tips

### Console Output

**Single action:**
```
Matched path/to/template.png with accuracy 0.87
✓ Step 5 matched - pressed 'enter'
```

**Sequential actions:**
```
Matched path/to/template.png with accuracy 0.87
✓ Step 5 matched - pressed [down, down, enter]
```

**Multi-option with sequential actions:**
```
Step 5: Trying 3 possible matches...
Matched path/to/template_b.png with accuracy 0.87
✓ Step 5 matched option 2/3 - pressed [down, down, enter]
```

### Common Issues

1. **No options matching**: Check template paths and regions are correct
2. **Wrong option matching first**: Reorder options (most specific first)
3. **Too many retries**: Reduce the number of options or adjust threshold
4. **All options too similar**: Use more distinctive template images

## See Also

- `TEMPLATE_FORMAT_EXAMPLES.json` - Complete format examples
- `src/utils/screen_navigator.py` - Implementation details
- Parent `CLAUDE.md` - Architecture overview
