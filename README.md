# Daily Scheduler

A lightweight daily task manager & note-taking app with a glass-morphism dark UI.

Built with Python + Tkinter. No external dependencies required at runtime.

---

## Features

- **Task Management** - Add, complete, and delete daily tasks
- **Auto Carry-over** - Incomplete tasks automatically move to the next day
- **Notes** - Write meeting notes or memos per day with auto-save
- **Markdown Export** - Export tasks + notes as `.md` file
- **History** - Browse past dates with recorded tasks or notes
- **Adjustable Opacity** - Slider control (30%–100%), setting persists between sessions
- **i18n** - Korean (default) / English, switchable in the top bar
- **Dark Theme** - Glass-morphism design inspired by TPM-OS

---

## Download

Go to [Releases](https://github.com/jinholim-tpm/daily-scheduler/releases) and download the latest version for your OS:

| OS | File | Notes |
|---|---|---|
| macOS | `DailyScheduler.app.zip` | Unzip and move to `/Applications` |
| Windows | `DailyScheduler.exe` | Run directly, no install needed |

### macOS - First launch

macOS may block the app because it's unsigned. To allow it:

1. Right-click `DailyScheduler.app` > **Open**
2. Click **Open** in the dialog
3. Or go to **System Settings > Privacy & Security** and click **Open Anyway**

---

## Run from Source

Requires Python 3.12+ with Tkinter support.

```bash
# Clone
git clone https://github.com/jinholim-tpm/daily-scheduler.git
cd daily-scheduler

# Run
python3 daily_scheduler.py
```

> On macOS, the system Python (3.9) may not work due to an outdated Tcl/Tk.
> Use Homebrew Python instead: `/opt/homebrew/bin/python3 daily_scheduler.py`

---

## Build from Source

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install PyInstaller
pip install pyinstaller

# macOS (.app)
pyinstaller --windowed --onefile --name DailyScheduler --icon AppIcon.icns daily_scheduler.py

# Windows (.exe)
pyinstaller --windowed --onefile --name DailyScheduler --icon AppIcon.ico daily_scheduler.py
```

The output will be in the `dist/` folder.

---

## Data Storage

All data is stored locally in `~/daily_scheduler.db` (SQLite). No cloud, no account needed.

---

## License

MIT
