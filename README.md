# 🎸 CHSuite by JURMR

An all-in-one utility suite for Clone Hero - swap menu backgrounds, generate custom colored player names, and clean up bad songs from your library. All three tools in a single unified application.

[![Platform](https://img.shields.io/badge/platform-Windows-green)](https://github.com/iamjrmh/CHSuite)
[![Platform](https://img.shields.io/badge/platform-Linux-green)](https://github.com/iamjrmh/CHSuite)
[![Platform](https://img.shields.io/badge/platform-MacOS-red)](https://github.com/iamjrmh/CHSuite)
[![Python Version](https://img.shields.io/badge/python-3.11-pink)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-black)](https://github.com/iamjrmh/CHSuite)

---

## ✨ What's Inside

| Tab | Description |
|--|--|
| **About This Tool** | Read each tools description and quickly launch that tool |
| **CHMenuChanger** | Swap Clone Hero's menu background textures directly via UnityPy asset editing |
| **CHNameGen** | Create gradient or per-letter colored player names with styling and export to `profiles.ini` |
| **CHNoteGen** | Create gradient or per-note colors and export to `(ProfileName).ini` |
| **CHCleaner** | Parse `badsongs.txt` and bulk-delete ERROR folders from your song library |
| **CHPatcher** | Patch or unpatch any registered Clone Hero install on the fly - prevents the launcher from resetting game files |
| **CHSongManager** | Easily download songs using CHSuite via the ChorusEncore API
| **CHManager** | Install or uninstall any version of Clone Hero directly from the CHSuite |

---
## ⓘ CHSuiteLite Now Available 
Don't want to download/only need 1 tool? Check out the live version of the CHSuite, CHSuiteLite!
- [CHSuite Lite](https://iamjrmh.github.io/CHSuite/) - A web-based version of CHSuite with stripped down features to be accessible to everyone, everywhere!

---

## ⓘ About This Tool
Read each tools description and quickly launch each tool from here
<details>
<summary><h3 align="center">About This Tool Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/About%20This%20Tool.png">
</p>
</details>

---

## 🎨 CHMenuChanger
Reads and writes Unity `.assets` files directly using UnityPy. No external tools or config file edits required.

<details>
<summary><h3 align="center">CHMenuChanger Preview (Before)</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHMenuChanger1.png">
</p>
</details>
<details>
<summary><h3 align="center">CHMenuChanger Preview (After)</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHMenuChanger2.png">
</p>
</details>
<details>
<summary><h3 align="center">Clone Hero Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHMenuChanger/main/Screenshots/CHMenu.gif">
</p>
</details>

### Features
- **Direct asset editing** - reads and writes Unity `.assets` files, no external tools needed
- **16 supported backgrounds** - all standard menu backgrounds plus the logo
- **Live preview** - see the current in-game texture and your replacement side by side before applying
- **Auto backup** - original files are automatically backed up to `_CH_BG_Backups` on first scan
- **One-click restore** - revert to originals at any time from the Restore Backups button
- **Profile system** - save multiple background sets and switch between them freely
- **Default profile** - read-only, always reflects the original unmodified textures
- **Size validation** - enforces minimum resolution per background (1920×1080 standard, 2030×1328 exact for the logo)

### Usage

1. Click **Browse** and select your `Clone Hero_Data` folder
   - Usually at `Documents\Clone Hero\Clone Hero_Data`
   - If not, look inside your Clone Hero installation folder (the one with the `.exe`)
2. Click **Load & Scan** - the tool scans all asset files and creates backups automatically
3. Select a background from the left panel
4. Click **Choose Replacement** and pick your image
5. Click **Apply & Save** to write the changes directly to your game files
6. Open Clone Hero to see the result

### Supported Backgrounds

| Name | Min Size | Source File |
|--|--|--|
| Black | 1920×1080 (Uneditable) | sharedassets1.assets |
| Spray | 1920×1080 | sharedassets1.assets |
| Pastel Burst | 1920×1080 | sharedassets1.assets |
| Groovy | 1920×1080 | sharedassets1.assets |
| Grains | 1920×1080 | sharedassets1.assets |
| Blue Rays | 1920×1080 | sharedassets1.assets |
| Alien | 1920×1080 | sharedassets1.assets |
| Autumn | 1920×1080 | sharedassets1.assets |
| Light | 1920×1080 | sharedassets1.assets |
| Dark | 1920×1080 | sharedassets1.assets |
| Classic | 1920×1080 | sharedassets1.assets |
| Surfer | 1920×1080 | sharedassets1.assets |
| SurferAlt | 1920×1080 | sharedassets1.assets |
| Rainbow | 1920×1080 | sharedassets1.assets |
| Animated | 1920×1080 | sharedassets1.assets |
| Logo_Transparent | 2030×1328 exact | globalgamemanagers.assets |

### Profile System

Profiles let you maintain multiple background sets and switch between them without re-importing images each time.

- **Default (Original)** - locked, read-only. Always reflects the unmodified originals. Cannot be renamed or deleted.
- **New** - create a named profile and assign replacement images to any backgrounds.
- **Duplicate** - copy any profile as a starting point for a new one.
- **Rename / Delete** - available on any non-Default profile.

Profiles and the last-used folder path are saved automatically to `chsuite_config.json` and `ch_bg_profiles.json` alongside the exe.

### Backup System

On the first **Load & Scan** of any folder, CHSuite automatically copies the original asset files into a `_CH_BG_Backups` subfolder inside `Clone Hero_Data`. This happens once - subsequent scans skip files that are already backed up.

- The **Restore Backups** button copies all backed-up files back over the live game files and triggers a fresh scan.
- **Apply & Save is blocked** if no backups exist, as a safety measure.

---
  
## ✏️ CHNameGen

<details>
<summary><h3 align="center">CHNameGen Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHNameGen.png">
</p>
</details>

Create unique colored player names for Clone Hero using gradient fills or per-letter customization, then export directly to your `profiles.ini`.

### Gradient Mode

Perfect for smooth, flowing color transitions across your entire name.

1. Switch to the **Gradient** tab
2. Enter your name in the Name field
3. Choose a **Start Color** and **End Color** - optionally add up to 3 intermediate colors for complex gradients
4. Apply styling if desired: **Bold**, **Italic**, **Underline**, **Strikethrough**
5. Optionally set **Font Size** and **Character Spacing**
6. Click **Generate**
7. Copy the output or use **Export to profiles.ini**

### Per-Letter Mode

Perfect for rainbow effects or unique per-character styling.

1. Switch to the **Per-Letter** tab
2. Enter your name and click **Update Letters**
3. Set a color and optional B/I/U/S styling for each individual letter
4. Optionally set global **Font Size** and **Character Spacing**
5. Click **Generate**
6. Copy the output or use **Export to profiles.ini**

### Color Tips

Colors use standard hex format: `#RRGGBB`

- Use [coolors.co](https://coolors.co) to find color schemes
- High contrast colors make names more readable
- For gradient: 2–3 colors for smooth transitions - similar hues = subtle, contrasting hues = bold
- For rainbow: Red → Orange → Yellow → Green → Blue → Purple per letter

---

## 🗑️ CHCleaner

<details>
<summary><h3 align="center">CHCleaner Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHCleaner.png">
</p>
</details>

Parses Clone Hero's `badsongs.txt` error log and lets you bulk-delete the problematic song folders.

### What Gets Deleted?

The cleaner **only** targets songs listed under `ERROR:` sections:

✅ Songs with no valid metadata (`song.ini` missing or corrupt)  
✅ Duplicate chart folders  
✅ Songs with no supported instruments charted

❌ **Does NOT touch** songs under `Warning:` sections (UTF-8 issues, notes after end events, video background warnings, etc.)

### Usage

1. Click **Select badsongs.txt** and navigate to your Clone Hero folder
   - Usually at `Documents\Clone Hero\badsongs.txt`
2. Review the list of folders marked for deletion - all are checked by default
3. Uncheck any songs you want to keep
4. Click **Delete Selected Songs** and confirm
5. Done - check `Documents\Clone Hero\deletedsongs.log` for a full record

### Log Format
```
-- Deletion started at 2026-01-04 21:25:02 --
✓ Deleted Folder: C:\Users\Owner\Documents\Clone Hero\songs\bad_song_1
✓ Deleted Folder: C:\Users\Owner\Documents\Clone Hero\songs\bad_song_2
⚠ Not found: C:\Users\Owner\Documents\Clone Hero\songs\already_gone
✗ Failed: C:\Users\Owner\Documents\Clone Hero\songs\protected
  Error: [WinError 5] Access is denied
============================================================
```

### File Locations

| File | Default Location |
|--|--|
| `badsongs.txt` | `Documents\Clone Hero\badsongs.txt` |
| Deletion log | `Documents\Clone Hero\deletedsongs.log` |

---

## ⚙️ CHPatcher

<details>
<summary><h3 align="center">CHPatcher Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHPatcher.png">
</p>
</details>

Lists every install registered in `game_installs.json` and lets you patch or unpatch them on the fly.

- Each install displays its current state: `✓ Manual` (patched) or `⚙ Launcher` (unpatched)
- **Patch** sets `isFromLauncher=false` so the launcher stops resetting your game files
- **Unpatch** reverses this and restores the install to launcher-managed
- CHSuite auto-kills the launcher process before writing if it detects it running, then waits for it to fully exit
- `game_installs.json` is backed up to `.bak` automatically before every write
- **Refresh** button to re-read the file at any time without restarting


---

## 🎵 CHSongManager

<details>
<summary><h3 align="center">CHSongManager Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHSongManager.png">
</p>
</details>

* CHSongManager - a dedicated tool for discovering and downloading songs for Clone Hero
* Integrated with the public ChorusEncore API for fast, reliable song lookup
* Streamlined search functionality with improved filtering and query handling
* Direct download support built into the workflow, reducing manual steps
* Designed for scalability with large song libraries
* Bulk download songs
* Quickly see the progress of the current song download by hovering over the "Active Downloads" button

---

## 🔎 Improved Song Discovery

* **Enhanced** song browsing experience with faster query responses
* Better metadata handling for more accurate search results
* Simplified access to community-maintained charts

---

## ⚙️ Integration & Workflow

* Reduced friction between searching, downloading, and managing songs
* Improved internal handling of song assets and storage paths


---

## 📦 CHManager

<details>
<summary><h3 align="center">CHManager Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHManager.png">
</p>
</details>

An all-in-one install manager for Clone Hero. View every registered install at a glance, manage them directly, and download any release or PTB build straight from GitHub — all without leaving the tab.

### Local Installs

- Every install registered in `game_installs.json` is listed with its version, path, patch state, and whether it was added manually or by the launcher
- **★ Default** — set any install as the default used by CHSuite
- **▶ Launch** — launch Clone Hero directly from CHManager
- **📂 Folder** — open the install folder in Explorer
- **⚙ Patch / ↺ Unpatch** — patch or unpatch any install inline without switching to the CHPatcher tab
- **🗑 Delete** — removes the entire install folder from disk and unregisters it from `game_installs.json`
- **Auto-remove** — installs whose `Clone Hero.exe` is missing are silently cleaned from `game_installs.json` on every refresh
- **+ Add Existing Install** — register any existing Clone Hero folder manually

### Download

- Fetches all releases directly from the Clone Hero GitHub
- **Release tab** — full stable releases only, sorted by version number newest to oldest
- **PTB tab** — pre-release builds only, sorted by version number newest to oldest
- **Architecture detection** — automatically detects whether your system is x64 or x32 and shows only matching builds
- Clicking **⬇ Download & Install** prompts you to choose a destination folder, then downloads and installs silently with no dialogs or prompts


---

## Windows Installation
  
## 📁 Direct Install (Recommended)

1. Go to the **[Releases](https://github.com/iamjrmh/CHSuite/releases)** page and download **CHSuiteWindows.exe** from the [latest release](https://github.com/iamjrmh/CHSuite/releases/latest/download/CHSuiteWindows.exe).
2. Double-click **CHSuiteWindows.exe** to run the installer.
3. By default it installs to `C:\CHSuite`. Change it if you prefer.
4. Complete the installer, then launch **CHSuite** from your Start Menu or Desktop.
5. On first launch, select your Clone Hero installation folder - CHSuite will derive the `Clone Hero_Data` path automatically and patch your install in the background.

## 🚀 Portable Install

1. Download **[CHSuiteWindows.zip](https://github.com/iamjrmh/CHSuite/releases/latest/download/CHSuiteWindows.zip)** from the [latest release](https://github.com/iamjrmh/CHSuite/releases/latest/download/CHSuiteWindows.zip).
2. Extract the ZIP anywhere on your PC.
3. Double-click **CHSuite.exe** - no install, no Python, nothing else needed.
4. On first launch, select your Clone Hero installation folder when prompted.

## 🔄 Updating (Direct)

1. Click on "Check for Update".
2. If an update is found, press update.
3. It will automatically install - once done, CHSuite should restart.

## 🔄 Updating (Portable)

1. Click on "Check for Update".
2. If an update is found, press update.
3. It will automatically download and extract the latest zip and replace your current install - once done, CHSuite should restart.

## Linux Installation
  
## 📁 Direct Install (Recommended)

1. Go to the **[Releases](https://github.com/iamjrmh/CHSuite/releases)** page and download **CHSuiteLinux.AppImage** from the [latest release](https://github.com/iamjrmh/CHSuite/releases/latest/download/CHSuiteLinux.AppImage).
2. Double-click **CHSuiteLinux.AppImage** to run CHSuite.
3. On first launch, select your Clone Hero installation folder - CHSuite will derive the `clonehero_Data` path automatically and patch your install in the background (Clone Hero Launcher users).

## 🚀 Portable Install

1. Download **[CHSuiteLinux.zip](https://github.com/iamjrmh/CHSuite/releases/latest/download/CHSuiteLinux.zip)** from the [latest release](https://github.com/iamjrmh/CHSuite/releases/latest/download/CHSuiteLinux.zip).
2. Extract the ZIP anywhere on your PC.
3. Double-click **CHSuite** - no install, no Python, nothing else needed.
4. On first launch, select your Clone Hero installation folder when prompted - CHSuite will derive the `clonehero_Data` path automatically and patch your install in the background (Clone Hero Launcher users).

## 🔄 Updating (Direct)

1. Click on "Check for Update".
2. If an update is found, press update.
3. It will automatically install - once done, CHSuite should restart.

## 🔄 Updating (Portable)

1. Click on "Check for Update".
2. If an update is found, press update.
3. It will automatically download and extract the latest zip and replace your current install - once done, CHSuite should restart.

## macOS Installation
  
being worked on :^)

---

## 🐛 Troubleshooting

**Backgrounds show "No texture matched"**  
Make sure you selected the `Clone Hero_Data` (windows) or `clonehero_Data` (linux) folder, not the game's root folder or a subfolder inside it.

**Changes are reverted after launching Clone Hero**  
The launcher patch may not have applied correctly. Check the welcome screen badge - if it showed `✗ Not Patched`, your install may not be registered in `game_installs.json` yet. Open the Launcher, add the install, then head to the **Launcher Patcher** page and patch it manually. Also make sure the install is set as your default in Launcher → Settings.

**Image rejected as too small**  
Your replacement must meet the minimum resolution for that slot. Upscale to at least 1920×1080 (or exactly 2030×1328 for Logo_Transparent).

**"Access Denied" on song deletion**  
The folder is in use by Clone Hero or another program. Close Clone Hero and try again.

**Songs not appearing in the Cleaner list**  
They're under `Warning:` sections, not `ERROR:` sections - this is intentional.

**Export to profiles.ini doesn't work**  
`profiles.ini` is in use or read-only. Close Clone Hero and check file permissions.

---

## 🔨 Building from Source
<details>
  <summary>Windows</summary>

  **Requirements**
- Windows 10 or 11 (64-bit)
- Python 3.11 (64-bit) - from [python.org](https://python.org), check "Add Python to PATH" during install
- NSIS 3.x (optional, for building the installer) - from [nsis.sourceforge.io](https://nsis.sourceforge.io/Download)

**Steps**

1. Clone or download this repository into a single folder (e.g. `C:\Downloads\CHSuite`)
2. Ensure the following files are all present in that folder:
   - `CHSuite.py`
   - `build.bat`
   - `write_spec.py`
   - `rthook_texture2d.py`
   - `CHSuite_Installer.nsi` *(optional, for installer)*
   - `JURMRWEED.ico` *(optional, for icon)*
   - `ThemeGen.py`
   - `/themes`
   - `/Images`
3. Double-click **`build.bat`**

The script will automatically create a virtual environment, install all dependencies, generate the spec, and produce the finished build at `dist\CHSuite\`. Zip that entire folder to distribute as portable - do not ship the `.exe` alone.

If [NSIS](https://nsis.sourceforge.io/Download) is installed, `CHSuite_Setup.exe` will also be compiled automatically.

**Dependencies installed by build.bat**

| Package | Purpose |
|--|--|
| Pillow | Image decoding and encoding |
| UnityPy | Unity asset file reading/writing |
| texture2ddecoder | GPU texture format decoding |
| brotli / brotlicffi / lz4 | Compression support |
| requests | Name Generator update checks |
| PyInstaller | Executable bundling |
</details>

<details>
  <summary>Linux</summary>

  **Requirements**
- Linux (64-bit)
- Python 3.11 (`python3.11`) with venv support
  - Ubuntu/Debian: `sudo apt install python3.11 python3.11-venv`
- Standard tools: `wget` or `curl`, `zip`, `chmod`, `cp`
- `appimagetool` *(optional — auto-downloaded if missing)*

**Steps**

1. Clone or download this repository into a single folder (e.g. `~/CHSuite`)
2. Ensure the following files are present:
   - `CHSuite.py`
   - `build.sh`
   - `write_spec.py`
   - `rthook_texture2d.py`
   - `ThemeGen.py`
   - `/themes`
   - `/Images`
   - `JURMRWEED.png` *(optional, for AppImage icon)*
3. Open a terminal in that folder
4. Run:
   ```bash
   ./build.sh

## The script will automatically:

- Locate Python 3.11
- Create and activate a .venv
- Install all dependencies
- Patch astc_encoder to prevent enum shadowing crashes
- Generate CHSuite.spec
- Build using PyInstaller
- Stage assets (themes, Images)

## Create:
  
- dist/CHSuite/ (portable build)
- CHSuiteLinux.zip (recommended for distribution)
- CHSuiteLinux.AppImage (fully self-contained, if AppImage build succeeds)

## Output

| File                    | Purpose                             |
| ----------------------- | ----------------------------------- |
| `dist/CHSuite/CHSuite`  | Raw PyInstaller binary (portable)   |
| `CHSuiteLinux.zip`      | Portable distribution (recommended) |
| `CHSuiteLinux.AppImage` | Fully self-contained executable     |


Do not distribute the binary alone — it depends on bundled assets.

Dependencies installed by build.sh

| Package                   | Purpose                          |
| ------------------------- | -------------------------------- |
| Pillow                    | Image decoding and encoding      |
| UnityPy                   | Unity asset file reading/writing |
| texture2ddecoder          | GPU texture decoding             |
| brotli / brotlicffi / lz4 | Compression support              |
| requests                  | Update checks                    |
| pypresence                | Discord Rich Presence            |
| PyInstaller               | Executable bundling              |

</details>

---

## 📄 License

MIT License - free to use, modify, and distribute.

---

## ⚠️ Disclaimer

**The CHMenuChanger and CHCleaner make permanent changes to files.** CHSuite includes safety features (auto-backup, confirmation dialogs, restore functionality) but:

- Always keep your own backups of important files and songs
- **CHMenuChangers**'s auto-backup covers asset files, not your entire Clone Hero install
- Song deletions cannot be undone
- By using this tool you assume all responsibility for the results

Use at your own risk.

---

## 🎮 Related Projects

- [Clone Hero](https://clonehero.net/) - The rhythm game this tool supports
- [CHColorGen](https://github.com/iamjrmh/CHColorGen) - Colored name generator for Clone Hero
- [CHCleaner](https://github.com/iamjrmh/CHCleaner) - Clean up problematic songs from your library
- [Chorus](https://chorus.fightthe.pw/) - Song database and downloader
- [Clone Hero Launcher](https://github.com/clonehero-game/releases/releases/download/CloneHeroLauncher/chlauncher-setup.exe) - Direct Download of the latest build of the Clone Hero Launcher.
- [Murrin' It Central](https://discord.gg/PtVqaCWFHa) - Questions? Join the discord server and ask!

---

Made with 🎸 by JURMR
