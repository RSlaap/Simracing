# Portable Setup Guide

This guide explains how to set up SimRacingClient for portable deployment across multiple PCs without requiring Python installation on target machines.

## Overview

The portable setup uses:
- **Embedded Python** - A standalone Python distribution that doesn't require installation
- **Portable Virtual Environment** - Created with `--always-copy` flag to ensure all files are self-contained
- **No System Dependencies** - Everything needed is included in the project folder

## One-Time Setup (On Development PC with Internet)

### Step 1: Download Embedded Python

Run the download script:
```batch
download_embedded_python.bat
```

This will:
- Download Python 3.11.9 embedded distribution (amd64)
- Extract it to `python/` directory
- Configure pip and virtualenv support
- Install virtualenv package

**Manual alternative:**
1. Download: https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
2. Extract to `python/` folder in project root
3. Edit `python/python311._pth` - uncomment the line `#import site` (remove the #)
4. Download get-pip.py and run: `python\python.exe get-pip.py`
5. Install virtualenv: `python\python.exe -m pip install virtualenv`

### Step 2: Create Portable Virtual Environment

Run the preparation script:
```batch
prepare_setup.bat
```

This will:
- Verify embedded Python exists
- Create a portable venv using `virtualenv --always-copy`
- Install all dependencies from `requirements.txt`
- Package everything for offline deployment

### Step 3: Configure Machine Settings

Create `machine_configuration.json` (see `machine_configuration.example.json`):
```json
{
    "name": "SimRig-1",
    "id": 1
}
```

**Important:** Each machine needs a unique name and ID.

### Step 4: Test Locally

Run the launcher to verify everything works:
```batch
scripts\launcher.bat
```

The service should start on port 5000 and advertise via mDNS.

## Deployment to Target PC (Offline)

### Option 1: Copy Entire Project
```
Copy the entire SimRacingClient folder to target PC
```

### Option 2: Copy Specific Folders (Minimal)
```
SimRacingClient/
├── python/              ← Embedded Python
├── venv/                ← Virtual environment with all packages
├── src/                 ← Application code
├── scripts/             ← Launcher scripts
├── requirements.txt
└── machine_configuration.json  ← Create/edit on target PC
```

### Running on Target PC

1. Edit `machine_configuration.json` with unique name and ID
2. Run `scripts\launcher.bat`
3. No additional setup required!

## How It Works

### Launcher Priority
The launcher (`scripts\launcher.bat`) checks for Python in this order:
1. **Virtual environment** (`venv\Scripts\python.exe`) - Preferred, has all dependencies
2. **Embedded Python** (`python\python.exe`) - Fallback if venv missing
3. **Error** - If neither found

### Why Embedded Python?

Standard Python virtual environments created with `python -m venv` store only references to the system Python. When copied to another PC:
- ❌ Venv points to Python paths that don't exist
- ❌ Requires Python to be installed in the same location
- ❌ Not truly portable

Embedded Python + `virtualenv --always-copy`:
- ✅ All Python files are physically copied to venv
- ✅ No external dependencies or registry entries
- ✅ Works on any Windows PC (same architecture)
- ✅ Self-contained and portable

### File Structure After Setup

```
SimRacingClient/
├── python/                      ← Embedded Python (not in git)
│   ├── python.exe
│   ├── python311.dll
│   ├── Lib/
│   └── Scripts/
├── venv/                        ← Portable venv (not in git)
│   ├── Scripts/
│   │   ├── python.exe          ← Fully standalone
│   │   └── pip.exe
│   └── Lib/
│       └── site-packages/      ← All dependencies copied here
├── src/
│   └── simracing_client.py
└── scripts/
    └── launcher.bat
```

## Troubleshooting

### "No Python executable found"
- Run `download_embedded_python.bat` on development PC
- Run `prepare_setup.bat` to create venv
- Verify `python/python.exe` and `venv/Scripts/python.exe` exist

### "Module not found" errors on target PC
- Venv may not be truly portable
- Re-run `prepare_setup.bat` - ensures `--always-copy` is used
- Check that entire `venv/` folder was copied

### Venv created with wrong Python
- Delete `venv/` folder
- Verify `python/python.exe` exists (embedded Python)
- Run `prepare_setup.bat` again - it explicitly uses embedded Python

### Need to update dependencies
1. Edit `requirements.txt`
2. Run `prepare_setup.bat` (recreates venv with new packages)
3. Test locally
4. Recopy entire project to target PCs

## Architecture Notes

- **Python Version:** 3.11.9 embedded (amd64)
- **Virtual Environment Tool:** `virtualenv` (not built-in `venv`)
- **Copy Mode:** `--always-copy` ensures true portability
- **Platform:** Windows x64 only (embedded Python is platform-specific)

## Scripts Reference

| Script | Purpose | Internet Required |
|--------|---------|------------------|
| `download_embedded_python.bat` | Download and setup embedded Python | ✅ Yes |
| `prepare_setup.bat` | Create portable venv and install packages | ✅ Yes |
| `scripts\launcher.bat` | Start the SimRacing client service | ❌ No |

## Best Practices

1. **Always test locally** after running `prepare_setup.bat` before deploying
2. **Keep backups** of working portable setups
3. **Document changes** to `requirements.txt` for reproducibility
4. **Use version control** for source code (git), but exclude `python/` and `venv/`
5. **Verify machine_configuration.json** is unique on each target PC
