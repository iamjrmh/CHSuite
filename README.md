<p align="center">
  <a href="https://github.com/iamjrmh/CHSuite">
    <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/public/assets/images/logo.png" width="140">
  </a>
</p>
<div align="center">
  <h1>CHSuite by JURMR</h1>

An all-in-one toolkit for Clone Hero - swap menu backgrounds, craft colored names and note colors, clean up broken songs, download charts, and manage every install, all in one app.

[![Platform](https://img.shields.io/badge/platform-Windows-green)](https://github.com/iamjrmh/CHSuite)
[![Built with](https://img.shields.io/badge/built%20with-Tauri%202-24C8DB)](https://tauri.app)
[![Frontend](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-61DAFB)](https://react.dev)
[![Sidecar](https://img.shields.io/badge/sidecar-Python%203.11-3776AB)](https://python.org)
[![License](https://img.shields.io/badge/license-Non--Commercial-black)](https://github.com/iamjrmh/CHSuite/blob/main/LICENSE)
</div>

---

## ✨ What's Inside

| Tab | Description |
|--|--|
| **About** | Overview of every tool with a one-click launch into any of them |
| **CHMenuChanger** | Swap Clone Hero's menu background textures directly in the Unity asset files |
| **CHNameGen** | Build gradient or per-letter colored player names and export to `profiles.ini` |
| **CHNoteGen** | Design custom note colors across Guitar, 6-Fret, and Drums with a live highway preview |
| **CHCleaner** | Parse `badsongs.txt` and bulk-delete the ERROR folders cluttering your library |
| **CHPatcher** | Patch or unpatch any registered install so the launcher stops resetting your game files |
| **CHSongManager** | Search the ChorusEncore library and download charts, then manage what's already downloaded |
| **CHManager** | View every install at a glance, rename/launch/patch them, and install any release or PTB build |
| **Settings** | 25 built-in themes, Clone Hero path configuration, and update checking |

---

## ⓘ About

Every tool's description and a quick-launch button, all in one landing page.

<details>
<summary><h3 align="center">About Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/About%20This%20Tool.png">
</p>
</details>

---

## 🎨 CHMenuChanger

Reads and writes Unity `.assets` files directly, no external tools or config edits required.

<details>
<summary><h3 align="center">CHMenuChanger Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHMenuChanger.png">
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
- **Auto scan** - point it at your `Clone Hero_Data` folder and it scans automatically, no extra button to click
- **15 supported backgrounds** - all standard menu backgrounds plus the logo
- **Live preview** - see the current in-game texture right in the grid before replacing it
- **Auto backup** - original files are automatically backed up to `_CH_BG_Backups` on first scan
- **One-click restore** - revert to originals at any time from **Restore originals**
- **Size validation** - enforces minimum resolution per background (1920x1080 standard, 2030x1328 exact for the logo)

### Usage

1. Click **Browse** and select your `Clone Hero_Data` folder
   - Usually at `Documents\Clone Hero\<version>\Clone Hero_Data`
   - If not, look inside your Clone Hero installation folder (the one with the `.exe`)
2. The tool scans automatically and creates backups on first run
3. Click **Replace** on any background and pick your image
4. Click **Apply** to write the changes directly to your game files
5. Open Clone Hero to see the result

### Supported Backgrounds

| Name | Min Size | Source File |
|--|--|--|
| Spray | 1920x1080 | sharedassets1.assets |
| Pastel Burst | 1920x1080 | sharedassets1.assets |
| Groovy | 1920x1080 | sharedassets1.assets |
| Grains | 1920x1080 | sharedassets1.assets |
| Blue Rays | 1920x1080 | sharedassets1.assets |
| Alien | 1920x1080 | sharedassets1.assets |
| Autumn | 1920x1080 | sharedassets1.assets |
| Light | 1920x1080 | sharedassets1.assets |
| Dark | 1920x1080 | sharedassets1.assets |
| Classic | 1920x1080 | sharedassets1.assets |
| Surfer | 1920x1080 | sharedassets1.assets |
| SurferAlt | 1920x1080 | sharedassets1.assets |
| Rainbow | 1920x1080 | sharedassets1.assets |
| Animated | 1920x1080 | sharedassets1.assets |
| Logo_Transparent | 2030x1328 exact | globalgamemanagers.assets |

### Backup System

On the first scan of any folder, CHSuite automatically copies the original asset files into a `_CH_BG_Backups` subfolder inside `Clone Hero_Data`. This happens once - later scans skip files that are already backed up.

- **Restore originals** copies all backed-up files back over the live game files and rescans.
- Applying is blocked if no backups exist, as a safety measure.

---

## ✏️ CHNameGen

<details>
<summary><h3 align="center">CHNameGen Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHNameGen.png">
</p>
</details>

Create unique colored player names using gradient fills or per-letter customization, with a live preview, then export directly to your `profiles.ini`.

### Gradient Mode

Perfect for smooth, flowing color transitions across your entire name.

1. Switch to the **Gradient** tab
2. Enter your name
3. Add color stops - start and end are required, add up to 3 more for complex gradients
4. Apply styling if desired: **Bold**, **Italic**, **Underline**, **Strikethrough**
5. Optionally set **Font size** and **Character spacing**
6. Copy the markup or click **Export** to write straight to `profiles.ini`

### Per-Letter Mode

Perfect for rainbow effects or unique per-character styling.

1. Switch to the **Per-Letter** tab
2. Enter your name
3. Set a color and optional B/I/U/S styling for each individual letter
4. Copy the markup or click **Export**

### Color Tips

Colors use standard hex format: `#RRGGBB`

- Use [coolors.co](https://coolors.co) to find color schemes
- High contrast colors make names more readable
- For gradients: 2-3 colors for smooth transitions, similar hues for subtle, contrasting hues for bold
- For rainbow: Red → Orange → Yellow → Green → Blue → Purple per letter

---

## 🎨 CHNoteGen

<details>
<summary><h3 align="center">CHNoteGen Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHNoteGen.png">
</p>
</details>

Design your own note colors and preview them on a real highway before you export anything.

### Features
- **Live highway preview** - tinted lanes, sustains, and composited note sprites, updating as you edit
- **Guitar, 6-Fret, Drums, and Effects** sections, each with the primary note colors surfaced at the top
- **Custom color picker** - drag around a saturation/value square and hue slider, or type/paste a hex code
- **Profile auto-detection** - finds existing color profiles from Clone Hero's `Custom/Colors` folders automatically
- **Export** to `Default.ini` or a named profile `.ini` in your Clone Hero folder

### Usage

1. Pick a profile from the dropdown, or create a new one
2. Switch between **Guitar**, **6-Fret**, **Drums**, and **Effects**
3. Click a color swatch to open the picker, or type a hex code directly
4. Watch the live preview update on the right
5. Click **Export** when you're happy with it

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

❌ **Does NOT touch** songs under `Warning:` sections (UTF-8 issues, notes after end events, video background warnings, etc.) - this is intentional.

### Usage

1. Click **Browse** and select your `badsongs.txt`
   - Usually at `Documents\Clone Hero\badsongs.txt`
2. Review the list of folders marked for deletion - use **Select all** / **None** as needed
3. Click **Delete**
4. Done - check `Documents\Clone Hero\deletedsongs.log` for a full record

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

- Each install displays its current state: **Manual** (patched) or **Launcher** (unpatched)
- **Patch** stops the launcher from resetting your game files
- **Unpatch** reverses this and restores the install to launcher-managed
- `game_installs.json` is backed up automatically before every write
- **Refresh** button to re-read the file at any time without restarting

---

## 🎵 CHSongManager

<details>
<summary><h3 align="center">Search Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHSongManagerSearch.png">
</p>
</details>
<details>
<summary><h3 align="center">Library Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHSongManagerLibrary.png">
</p>
</details>

A dedicated tool for finding, downloading, and managing songs, built on the public ChorusEncore API.

### Search

- Pre-fills with the latest charts on open, just like the search bar itself
- Filter by instrument and difficulty
- Scroll to load more results automatically, no "Load more" button to click
- Select individual songs or everything at once, then download in bulk with a live progress bar showing what's currently downloading
- Colorful chart names and artist names render properly, not as raw markup

### Library

- Scans your songs folder for both `.sng` files and classic folder-based charts
- Shows album art for both, including art extracted directly from inside `.sng` containers
- Select and bulk-delete downloaded songs straight from the app
- The scan is cached for the session - it only rescans when you hit **Refresh**, change your songs folder, or restart the app

---

## 📦 CHManager

<details>
<summary><h3 align="center">Local Installs Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHManagerLI.png">
</p>
</details>
<details>
<summary><h3 align="center">Releases Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHManagerR.png">
</p>
</details>
<details>
<summary><h3 align="center">PTB Preview</h3></summary>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHSuite/refs/heads/main/Screenshots/CHManagerPTB.png">
</p>
</details>

An all-in-one install manager. View every registered install at a glance, manage them directly, and download any release or PTB build straight from GitHub, all without leaving the tab.

### Local Installs

- Every install registered in `game_installs.json` is listed with its version, path, and patch state
- **Rename** any install with your own label - purely cosmetic, the actual folder is never touched
- The version shown is read directly from that install's own `Clone Hero_Data/version.json`, not guessed from a filename
- **Launch**, **Open folder**, **Set default**, **Patch/Unpatch**, and **Delete** are all one click away
- Deleting an install removes its files from disk too, not just the registry entry
- **Add existing** registers any Clone Hero folder you already have

### Releases & PTB

- Fetches every release directly from the Clone Hero GitHub, split into stable and PTB tabs
- Automatically picks the matching asset for your OS and architecture
- Installing shows live progress through downloading, extracting, and registering
- Automatically carries over `GameData`, `PlayerData`, `Replays`, `profiles.ini`, and `scorestats.json` from whatever was previously your default install
- Also carries over your current menu backgrounds from CHMenuChanger onto the freshly installed version
- If you haven't set a default install location in Settings, it'll ask where to put this one

---

## ⚙️ Settings

- **25 built-in themes** - swap instantly, no restart needed
- **Clone Hero paths** - Clone Hero_Data folder, default install, songs folder, and where new versions get auto-installed
- **Auto-detect** - best-effort discovery of your Documents folder and registered installs
- **Check for updates** - see [Updating](#-updating) below

---

## 🔄 Updating

CHSuite checks the same GitHub release feed on every launch, silently if you're already up to date. You'll also find a check-for-updates icon next to the CHSuite logo in the sidebar, and a dedicated button in **Settings → About**.

If a newer version is found, clicking through opens its GitHub release page so you can grab the new installer - this version doesn't replace itself automatically, you'll install the update the same way you installed CHSuite in the first place.

---

## 📥 Installation

CHSuite is a Windows desktop app (Tauri 2 + React, with a bundled Python sidecar - no Python install required on your machine).

1. Go to the **[Releases](https://github.com/iamjrmh/CHSuite/releases)** page and download either the `.exe` (NSIS installer) or the `.msi` from the [**latest release**](https://github.com/iamjrmh/CHSuite/releases/latest).
2. Run the installer and follow the prompts.
3. Launch **CHSuite** from your Start Menu or Desktop.
4. On first launch, use **Auto-detect** in Settings or point each tool at your Clone Hero folders manually.

---

## 🐛 Troubleshooting

**Backgrounds show "No texture matched"**
Make sure you selected the `Clone Hero_Data` folder, not the game's root folder or a subfolder inside it.

**Changes are reverted after launching Clone Hero**
The launcher patch may not have applied correctly. Head over to **CHPatcher** and check the install's state - if it shows **Launcher** instead of **Manual**, patch it there. Also make sure the install is set as your default in **CHManager**.

**Image rejected as too small**
Your replacement must meet the minimum resolution for that slot. Upscale to at least 1920x1080 (or exactly 2030x1328 for Logo_Transparent).

**"Access is denied" on song deletion**
The folder is in use by Clone Hero or another program. Close Clone Hero and try again.

**Songs not appearing in the CHCleaner list**
They're under `Warning:` sections, not `ERROR:` sections - this is intentional.

**Export to profiles.ini doesn't work**
`profiles.ini` is in use or read-only. Close Clone Hero and check file permissions.

**CHPatcher not patching**
CHPatcher can't overwrite the files while Clone Hero or the Clone Hero Launcher is open. Close both and try again.

**"Unregistered, but could not delete files" when removing an install**
Something still has a file in that install open, most often CHMenuChanger having scanned it. Close CHSuite and reopen it, then try again.

---

## 🔨 Building from Source

**Requirements**
- Windows 10 or 11 (64-bit)
- [Node.js](https://nodejs.org) + npm
- [Rust](https://rustup.rs) (cargo)
- Python 3.11 (64-bit) - from [python.org](https://python.org)

**Steps**

1. Clone this repository
2. Run `build.bat`

The first step lets you set a new version number (`X.X.X`), or press Enter to keep the current one. From there it's fully automatic:

- Builds the Python sidecar into a standalone `.exe` (PyInstaller)
- Builds the React frontend (`tsc` + Vite)
- Compiles the Tauri shell and bundles an NSIS `.exe` and a WiX `.msi` installer
- Collects both installers plus the raw `chsuite.exe` into `Software\`
- Cleans up intermediate build files (PyInstaller's work dir, `__pycache__`, `dist\`) when it's done

Cargo's incremental build cache, `node_modules`, and the Python virtual environment are all left alone between builds, so repeat builds are fast.

**Sidecar dependencies** (installed automatically by `build.bat` into `sidecar\.venv`)

| Package | Purpose |
|--|--|
| Pillow | Image decoding and encoding |
| UnityPy | Unity asset file reading/writing |
| texture2ddecoder | GPU texture format decoding |
| requests | GitHub API calls, downloads, update checks |

---

## 📄 License

[CHSuite Non-Commercial License](LICENSE) - free and open source to use, modify, and distribute, with two conditions:

- **No commercial use.** CHSuite (or any fork of it) can't be sold, paywalled, or otherwise used for profit in any way.
- **Credit stays attached.** Forks and derivative versions must keep JURMR (iamjrmh) credited as the original author.

---

## ⚠️ Disclaimer

**CHMenuChanger, CHCleaner, and CHManager make permanent changes to files.** CHSuite includes safety features (auto-backup, deletion logs, restore functionality) but:

- Always keep your own backups of important files and songs
- CHMenuChanger's auto-backup covers asset files, not your entire Clone Hero install
- Song and install deletions cannot be undone
- By using this tool you assume all responsibility for the results

Use at your own risk.

---

## 🎮 Related Projects

- [Clone Hero](https://clonehero.net/) - The rhythm game this tool supports
- [CHColorGen](https://github.com/iamjrmh/CHColorGen) - Colored name generator for Clone Hero
- [CHCleaner](https://github.com/iamjrmh/CHCleaner) - Clean up problematic songs from your library
- [Chorus](https://chorus.fightthe.pw/) - Song database and downloader
- [Clone Hero Launcher](https://github.com/clonehero-game/releases/releases/download/CloneHeroLauncher/chlauncher-setup.exe) - Direct download of the latest build of the Clone Hero Launcher
- [Murrin' It Central](https://discord.gg/PtVqaCWFHa) - Questions? Join the discord server and ask!

---

Made with 🎸 by JURMR
