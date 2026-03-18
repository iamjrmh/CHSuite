# 🎸 CHSuite by JURMR

An all-in-one utility suite for Clone Hero — swap menu backgrounds, generate custom colored player names, and clean up bad songs from your library. All three tools in a single unified application.

[![Platform](https://img.shields.io/badge/platform-Windows-blue)](https://github.com/iamjrmh/CHSuite)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/iamjrmh/CHSuite)
[![Python Version](https://img.shields.io/badge/python-3.11-blue)](https://python.org)

---

## ⚠️ Important — Clone Hero Launcher

The Clone Hero launcher **resets your game files back to default after every launch**, which will undo any background changes made with the BG Changer.

To prevent this, set up your install manually:

1. Install Clone Hero through the launcher as normal.
2. Move that install folder to a different location on your PC.
3. In the launcher settings, remove the old install path.
4. Add your new manual path instead.

Once set up this way, the launcher will no longer overwrite your files.

> **A simple video + written walkthrough tutorial for this setup is in progress.**

---

## 🔴 Run as Administrator

**CHSuite must be run as Administrator or the BG Changer will fail to save changes.**

Clone Hero's game files require elevated permissions to write to. Without admin rights the tool will open and scan normally, but Apply & Save will fail silently or with an error.

**To run as admin:**
- Right-click **CHSuite.exe** → **Run as administrator**

To avoid doing this every time: right-click the exe → **Properties** → **Compatibility** tab → check **Run this program as an administrator** → **OK**.

---

## ✨ What's Inside

| Tool | Description |
|---|---|
| **BG Changer** | Swap Clone Hero's menu background textures directly via UnityPy asset editing |
| **Name Generator** | Create gradient or per-letter colored player names with styling and export to `profiles.ini` |
| **Bad Songs Cleaner** | Parse `badsongs.txt` and bulk-delete ERROR folders from your song library |

---

## 📁 Direct Install (Recommended)

1. Go to the **[Releases](https://github.com/iamjrmh/CHSuite/releases)** page and download **CHSuite_Setup.exe** from the latest release.
2. Double-click **CHSuite_Setup.exe** to run the installer.
3. By default it installs to `C:\CHSuite`. Change it if you prefer.
4. Complete the installer, then launch **CHSuite** from your Start Menu or Desktop.
5. On first launch, select your Clone Hero installation folder — CHSuite will derive the `Clone Hero_Data` path automatically.

## 🚀 Portable Install

1. Download **CHSuite_Portable.zip** from the **[Releases](https://github.com/iamjrmh/CHSuite/releases)** page.
2. Extract the ZIP anywhere on your PC.
3. Double-click **CHSuite.exe** — no install, no Python, nothing else needed.
4. On first launch, select your Clone Hero installation folder when prompted.

---

## 🎨 BG Changer

Reads and writes Unity `.assets` files directly using UnityPy. No external tools or config file edits required.

<h3 align="center">Menu Preview</h3>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHMenuChanger/main/Screenshots/Menu.gif">
</p>

<h3 align="center">Clone Hero Preview</h3>
<p align="center">
  <img src="https://raw.githubusercontent.com/iamjrmh/CHMenuChanger/main/Screenshots/CHMenu.gif">
</p>

### Features
- **Direct asset editing** — reads and writes Unity `.assets` files, no external tools needed
- **16 supported backgrounds** — all standard menu backgrounds plus the logo
- **Live preview** — see the current in-game texture and your replacement side by side before applying
- **Auto backup** — original files are automatically backed up to `_CH_BG_Backups` on first scan
- **One-click restore** — revert to originals at any time from the Restore Backups button
- **Profile system** — save multiple background sets and switch between them freely
- **Default profile** — read-only, always reflects the original unmodified textures
- **Size validation** — enforces minimum resolution per background (1920×1080 standard, 2030×1328 exact for the logo)

### Usage

1. Click **Browse** and select your `Clone Hero_Data` folder
   - Usually at `Documents\Clone Hero\Clone Hero_Data`
   - If not, look inside your Clone Hero installation folder (the one with the `.exe`)
2. Click **Load & Scan** — the tool scans all asset files and creates backups automatically
3. Select a background from the left panel
4. Click **Choose Replacement** and pick your image
5. Click **Apply & Save** to write the changes directly to your game files
6. Open Clone Hero to see the result

### Supported Backgrounds

| Name | Min Size | Source File |
|---|---|---|
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

- **Default (Original)** — locked, read-only. Always reflects the unmodified originals. Cannot be renamed or deleted.
- **New** — create a named profile and assign replacement images to any backgrounds.
- **Duplicate** — copy any profile as a starting point for a new one.
- **Rename / Delete** — available on any non-Default profile.

Profiles and the last-used folder path are saved automatically to `chsuite_config.json` and `ch_bg_profiles.json` alongside the exe.

### Backup System

On the first **Load & Scan** of any folder, CHSuite automatically copies the original asset files into a `_CH_BG_Backups` subfolder inside `Clone Hero_Data`. This happens once — subsequent scans skip files that are already backed up.

- The **Restore Backups** button copies all backed-up files back over the live game files and triggers a fresh scan.
- **Apply & Save is blocked** if no backups exist, as a safety measure.

---

## ✏️ Name Generator

Create unique colored player names for Clone Hero using gradient fills or per-letter customization, then export directly to your `profiles.ini`.

### Gradient Mode

Perfect for smooth, flowing color transitions across your entire name.

1. Switch to the **Gradient** tab
2. Enter your name in the Name field
3. Choose a **Start Color** and **End Color** — optionally add up to 3 intermediate colors for complex gradients
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
- For gradient: 2–3 colors for smooth transitions — similar hues = subtle, contrasting hues = bold
- For rainbow: Red → Orange → Yellow → Green → Blue → Purple per letter

---

## 🗑️ Bad Songs Cleaner

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
2. Review the list of folders marked for deletion — all are checked by default
3. Uncheck any songs you want to keep
4. Click **Delete Selected Songs** and confirm
5. Done — check `Documents\Clone Hero\deletedsongs.log` for a full record

### Log Format

```
--- Deletion started at 2026-01-04 21:25:02 ---
✓ Deleted Folder: C:\Users\Owner\Documents\Clone Hero\songs\bad_song_1
✓ Deleted Folder: C:\Users\Owner\Documents\Clone Hero\songs\bad_song_2
⚠ Not found: C:\Users\Owner\Documents\Clone Hero\songs\already_gone
✗ Failed: C:\Users\Owner\Documents\Clone Hero\songs\protected
  Error: [WinError 5] Access is denied
============================================================
```

### File Locations

| File | Default Location |
|---|---|
| `badsongs.txt` | `Documents\Clone Hero\badsongs.txt` |
| Deletion log | `Documents\Clone Hero\deletedsongs.log` |

---

## 🐛 Troubleshooting

**Backgrounds show "No texture matched"**  
Make sure you selected the `Clone Hero_Data` folder, not the game's root folder or a subfolder inside it.

**Changes are reverted after launching Clone Hero**  
The Clone Hero launcher is resetting your files. See the important note at the top of this README.

**Apply & Save fails or does nothing**  
CHSuite is not running as Administrator. Right-click the exe and select Run as administrator.

**Image rejected as too small**  
Your replacement must meet the minimum resolution for that slot. Upscale to at least 1920×1080 (or exactly 2030×1328 for Logo_Transparent).

**"Access Denied" on song deletion**  
The folder is in use by Clone Hero or another program. Close Clone Hero and try again.

**Songs not appearing in the Cleaner list**  
They're under `Warning:` sections, not `ERROR:` sections — this is intentional.

**Export to profiles.ini doesn't work**  
`profiles.ini` is in use or read-only. Close Clone Hero and check file permissions.

---

## 🔨 Building from Source

**Requirements**
- Windows 10 or 11 (64-bit)
- Python 3.11 (64-bit) — from [python.org](https://python.org), check "Add Python to PATH" during install
- NSIS 3.x (optional, for building the installer) — from [nsis.sourceforge.io](https://nsis.sourceforge.io/Download)

**Steps**

1. Clone or download this repository into a single folder (e.g. `E:\Downloads\JURMR CHSuite`)
2. Ensure the following files are all present in that folder:
   - `CHSuite.py`
   - `build.bat`
   - `write_spec.py`
   - `rthook_texture2d.py`
   - `CHSuite_Installer.nsi` *(optional, for installer)*
   - `JURMRWEED.ico` *(optional, for icon)*
3. Double-click **`build.bat`**

The script will automatically create a virtual environment, install all dependencies, generate the spec, and produce the finished build at `dist\CHSuite\`. Zip that entire folder to distribute as portable — do not ship the `.exe` alone.

If NSIS is installed, `CHSuite_Setup.exe` will also be compiled automatically.

**Dependencies installed by build.bat**

| Package | Purpose |
|---|---|
| Pillow | Image decoding and encoding |
| UnityPy | Unity asset file reading/writing |
| texture2ddecoder | GPU texture format decoding |
| brotli / brotlicffi / lz4 | Compression support |
| requests | Name Generator update checks |
| PyInstaller | Executable bundling |

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## ⚠️ Disclaimer

**The BG Changer and Bad Songs Cleaner make permanent changes to files.** CHSuite includes safety features (auto-backup, confirmation dialogs, restore functionality) but:

- Always keep your own backups of important files and songs
- The BG Changer's auto-backup covers asset files, not your entire Clone Hero install
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
- [Discord Server](https://discord.gg/PtVqaCWFHa) - Questions? Join the discord server and ask! 

---

Made with 🎸 by JURMR
