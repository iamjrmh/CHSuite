"""
CHNoteGen.py — Clone Hero note/colour profile editor (CHNoteGen)
================================================================
Split out of CHSuite.py.  Imports shared names from the main CHSuite module.
"""

# All shared module-level names live in CHSuite.py.  Wildcard import keeps
# every reference in the moved code resolving exactly the same way it did
# when the file was monolithic.  The import succeeds because CHSuite.py
# defines every shared name BEFORE importing this file (mixins are imported
# at the bottom of CHSuite.py just before the class definition).
import sys as _sys
if "CHSuite" not in _sys.modules:
    _sys.modules["CHSuite"] = _sys.modules.get("__main__")

from CHSuite import *               # noqa: F401, F403
from CHSuite import (               # explicit re-imports for the names this
    C, FT, FTB, FTS, FTH, FTT, FTM, FT_LABEL,
    _IS_WINDOWS, _IS_LINUX, _IS_MAC, _CH_DATA_DIR,
    _CH_EXE_CANDIDATES_WIN, _CH_EXE_CANDIDATES_LIN, _CH_EXE_CANDIDATES_MAC,
    _MAC_CH_APP, _MAC_CH_DATA_PATH,
    _PIL_OK, _UNITYPY_OK, _REQUESTS_OK, _PYPRESENCE_OK,
    _app_dir, _resources_dir, _log,
    _load_json, _save_json,
    CONFIG_FILE, PROFILES_FILE, SCAN_LOG_FILE, THEMES_DIR, IPC_PORT,
    _silent_patch_as_manual, _unpatch_as_launcher,
    _read_installs, _INSTALLS_FILE,
    _launcher_is_running, _kill_launcher, _norm_path,
    StyledDropdown, RoundedButton, _RoundedNavBtn, _RoundedAboutCard,
    HoverTooltip, _card, _label, _sep,
)                                   # static-analysers happier
import os, sys, re, json, copy, math, colorsys, shutil, threading
import subprocess, tempfile, platform, configparser, datetime
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

try:
    import UnityPy
except ImportError:
    UnityPy = None

try:
    import requests
except ImportError:
    requests = None

# ── Module-level helpers/classes ─────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
#  SECTION 3 — NOTEGEN  (ported from CHNoteGen by JURMR)
# ──────────────────────────────────────────────────────────────────────────────

# Storage paths for NoteGen (alongside the exe / script)
_NG_PROFILES_FILE = _app_dir() / "ch_notegen_profiles.json"
_NG_CONFIG_FILE   = _app_dir() / "ch_notegen_config.json"
_NG_DEFAULT_INI   = _app_dir() / "DefaultColors.ini"
_NG_IMAGES_DIR    = _resources_dir() / "Images"
_NG_DEFAULT_PROFILE_NAME = "Default (Read-Only)"

_NOTE_FILE_MAP = [
    ("green",  "note_green",  "Green.png"),
    ("red",    "note_red",    "Red.png"),
    ("yellow", "note_yellow", "Yellow.png"),
    ("blue",   "note_blue",   "Blue.png"),
    ("orange", "note_orange", "Orange.png"),
]
_TEMPLATE_NAMES = ["grayscale metallic.png", "MonoNote.png", "monenote.png"]
_SECTION_ORDER  = ["sixfret", "drums", "other", "guitar"]

# ── Default colours ───────────────────────────────────────────────────────────

_NG_DEFAULT_COLORS: dict = {
    "guitar": {
        "striker_base_orange":"#FFFFFF","striker_base_blue":"#FFFFFF",
        "striker_base_yellow":"#FFFFFF","striker_base_red":"#FFFFFF",
        "striker_base_green":"#FFFFFF",
        "striker_head_light_open":"#FFCE86","striker_head_light_orange":"#FFB300",
        "striker_head_light_blue":"#0089FF","striker_head_light_yellow":"#FFFF00",
        "striker_head_light_red":"#FF0000","striker_head_light_green":"#00FF00",
        "striker_head_cover_orange":"#FFB300","striker_head_cover_blue":"#0089FF",
        "striker_head_cover_yellow":"#FFFF00","striker_head_cover_red":"#FF0000",
        "striker_head_cover_green":"#00FF00",
        "striker_cover_orange":"#FFB300","striker_cover_blue":"#0089FF",
        "striker_cover_yellow":"#FFFF00","striker_cover_red":"#FF0000",
        "striker_cover_green":"#00FF00",
        "sustain_sp_active":"#00FFFF","sustain_sp_phrase_active":"#00FFFF",
        "sustain_sp_phrase":"#00FFFF","sustain_open":"#DB33F9",
        "sustain_orange":"#FFD23B","sustain_blue":"#00C5FF",
        "sustain_yellow":"#FFFF00","sustain_red":"#FF0000","sustain_green":"#00FF00",
        "note_anim_sp_active":"#51FFFF","note_anim_sp_phrase_active":"#FFFFFF",
        "note_anim_sp_phrase":"#51FFFF","note_anim_open":"#FFFFFF",
        "note_anim_orange":"#FFBE28","note_anim_blue":"#77D1FF",
        "note_anim_yellow":"#FFFF57","note_anim_red":"#FF8B8B","note_anim_green":"#00FF00",
        "note_sp_active":"#00FFFF","note_sp_phrase_active":"#00FFFF",
        "note_sp_phrase":"#00FFFF","note_open":"#BA00FF",
        "note_orange":"#FFB300","note_blue":"#0089FF",
        "note_yellow":"#FFFF00","note_red":"#FF0000","note_green":"#00FF00",
    },
    "drums": {
        "striker_base_green":"#FFFFFF","striker_base_blue":"#FFFFFF",
        "striker_base_yellow":"#FFFFFF","striker_base_red":"#FFFFFF",
        "striker_head_light_kick":"#FFCE86","striker_head_light_green":"#00FF00",
        "striker_head_light_blue":"#0089FF","striker_head_light_yellow":"#FFFF00",
        "striker_head_light_red":"#FF0000",
        "striker_head_cover_green":"#00FF00","striker_head_cover_blue":"#0089FF",
        "striker_head_cover_yellow":"#FFFF00","striker_head_cover_red":"#FF0000",
        "striker_cover_green":"#00FF00","striker_cover_blue":"#0089FF",
        "striker_cover_yellow":"#FFFF00","striker_cover_red":"#FF0000",
        "drums_striker_base_green":"#FFFFFF","drums_striker_base_blue":"#FFFFFF",
        "drums_striker_base_yellow":"#FFFFFF","drums_striker_base_red":"#FFFFFF",
        "drums_striker_head_light_kick":"#FFCE86","drums_striker_head_light_green":"#00FF00",
        "drums_striker_head_light_blue":"#0089FF","drums_striker_head_light_yellow":"#FFFF00",
        "drums_striker_head_light_red":"#FF0000",
        "drums_striker_head_cover_green":"#00FF00","drums_striker_head_cover_blue":"#0089FF",
        "drums_striker_head_cover_yellow":"#FFFF00","drums_striker_head_cover_red":"#FF0000",
        "drums_striker_cover_green":"#00FF00","drums_striker_cover_blue":"#0089FF",
        "drums_striker_cover_yellow":"#FFFF00","drums_striker_cover_red":"#FF0000",
        "note_anim_kick_sp_active":"#00FFFF","note_overlay_kick_sp_phrase":"#00D7D7",
        "note_overlay_kick_sp_active":"#00D8D8",
        "note_anim_kick_sp_phrase_active":"#FFFFFF","note_anim_kick_sp_phrase":"#FFFF00",
        "note_kick_sp_active":"#009178","note_kick_sp_phrase_active":"#FFFFFF",
        "note_kick_sp_phrase":"#FF4600","note_anim_kick":"#FFFF00","note_kick":"#FF4600",
        "cym_anim_sp_active":"#7CFFD6","cym_anim_sp_phrase_active":"#FFFFFF",
        "cym_anim_sp_phrase":"#7CFFD6","cym_anim_blue":"#609EFF","cym_anim_yellow":"#FFEF5B",
        "cym_anim_red":"#FF8B8B","cym_anim_green":"#A5FF7B",
        "cym_sp_active":"#7CFFD6","cym_sp_phrase_active":"#7CFFD6","cym_sp_phrase":"#7CFFD6",
        "cym_blue":"#1D63FF","cym_yellow":"#FFE531","cym_red":"#FF4663","cym_green":"#0CFF0C",
        "tom_anim_sp_active":"#51FFFF","tom_anim_sp_phrase_active":"#FFFFFF",
        "tom_anim_sp_phrase":"#51FFFF","tom_anim_blue":"#2685FF","tom_anim_yellow":"#FFFF26",
        "tom_anim_red":"#FF2F2F","tom_anim_green":"#19FF19",
        "tom_sp_active":"#00FFFF","tom_sp_phrase_active":"#00FFFF","tom_sp_phrase":"#00FFFF",
        "tom_blue":"#0089FF","tom_yellow":"#FFFF00","tom_red":"#FF0000","tom_green":"#00FF00",
    },
    "sixfret": {
        "sf_note_hopo":"#00FFFF",
        "sf_striker_base_white_right":"#FFFFFF","sf_striker_base_white_mid":"#FFFFFF",
        "sf_striker_base_white_left":"#FFFFFF","sf_striker_base_black_right":"#3F3F3F",
        "sf_striker_base_black_mid":"#3F3F3F","sf_striker_base_black_left":"#3F3F3F",
        "sf_sustain_sp_active":"#00FFFF","sf_sustain_sp_phrase_active":"#00FFFF",
        "sf_sustain_sp_phrase":"#00FFFF","sf_sustain_open":"#FFFFFF",
        "sf_sustain_right":"#FFFFFF","sf_sustain_mid":"#FFFFFF","sf_sustain_left":"#FFFFFF",
        "sf_note_tap_open":"#BA00FF","sf_note_tap_white_right":"#BA00FF",
        "sf_note_tap_white_mid":"#BA00FF","sf_note_tap_white_left":"#BA00FF",
        "sf_note_tap_black_right":"#BA00FF","sf_note_tap_black_mid":"#BA00FF",
        "sf_note_tap_black_left":"#BA00FF",
        "sf_note_sp_active":"#00FFFF","sf_note_sp_phrase_active":"#00FFFF",
        "sf_note_sp_phrase":"#00FFFF","sf_note_open":"#FFFFFF",
        "sf_note_white_right":"#FFFFFF","sf_note_white_mid":"#FFFFFF","sf_note_white_left":"#FFFFFF",
        "sf_note_black_right":"#3F3F3F","sf_note_black_mid":"#3F3F3F","sf_note_black_left":"#3F3F3F",
        "sf_striker_background_right":"#FFFFFF","sf_striker_background_mid":"#FFFFFF",
        "sf_striker_background_left":"#FFFFFF",
    },
    "other": {
        "combo_sp_active_glow":"#FFFFFF","combo_four_glow":"#E8B1FF",
        "combo_three_glow":"#F0FFF0","combo_two_glow":"#FFFF00",
        "combo_sp_active":"#00CCCC","combo_four":"#874E9E","combo_three":"#00FF00",
        "combo_two":"#D55800","combo_one":"#FFDD00",
        "striker_hold_spark_sp_active":"#FF1200","striker_hold_spark":"#FF1200",
        "striker_hit_particles_sp_active":"#00FFFF","striker_hit_particles":"#FF5000",
        "striker_hit_flame_sp_active":"#00FFFF","striker_hit_flame":"#FFB76D",
        "striker_hit_flame_kick":"#FFB300","striker_hit_flame_open":"#BA00FF",
        "sp_bar_arrow":"#7FFFFF","sp_bar_elec":"#B2B2B2","sp_bar_color":"#004848",
        "sp_act_animation":"#00C1E5","sp_act_flash":"#0029BF",
        "general_sp_active":"#FFFFFF","general_sp":"#00FFFF",
        "leaderboard_first":"#DABA37","leaderboard_second":"#C5C5C5","leaderboard_third":"#75551D",
        "sp_gain_lightning":"#2FCCCC","sp_gain_lightning_secondary":"#BFE5BF",
    },
}

_NG_FRIENDLY: dict = {
    "note_green":"Note · Green","note_red":"Note · Red","note_yellow":"Note · Yellow",
    "note_blue":"Note · Blue","note_orange":"Note · Orange","note_open":"Note · Open",
    "note_sp_active":"Note · SP Active","note_sp_phrase":"Note · SP Phrase",
    "note_sp_phrase_active":"Note · SP Phrase Active",
    "note_anim_green":"Note Anim · Green","note_anim_red":"Note Anim · Red",
    "note_anim_yellow":"Note Anim · Yellow","note_anim_blue":"Note Anim · Blue",
    "note_anim_orange":"Note Anim · Orange","note_anim_open":"Note Anim · Open",
    "note_anim_sp_active":"Note Anim · SP Active","note_anim_sp_phrase":"Note Anim · SP Phrase",
    "note_anim_sp_phrase_active":"Note Anim · SP Phrase Active",
    "sustain_green":"Sustain · Green","sustain_red":"Sustain · Red",
    "sustain_yellow":"Sustain · Yellow","sustain_blue":"Sustain · Blue",
    "sustain_orange":"Sustain · Orange","sustain_open":"Sustain · Open",
    "sustain_sp_active":"Sustain · SP Active","sustain_sp_phrase":"Sustain · SP Phrase",
    "sustain_sp_phrase_active":"Sustain · SP Phrase Active",
    "striker_base_green":"Strikeline Base · Green","striker_base_red":"Strikeline Base · Red",
    "striker_base_yellow":"Strikeline Base · Yellow","striker_base_blue":"Strikeline Base · Blue",
    "striker_base_orange":"Strikeline Base · Orange",
    "striker_head_light_green":"Strikeline Head Light · Green",
    "striker_head_light_red":"Strikeline Head Light · Red",
    "striker_head_light_yellow":"Strikeline Head Light · Yellow",
    "striker_head_light_blue":"Strikeline Head Light · Blue",
    "striker_head_light_orange":"Strikeline Head Light · Orange",
    "striker_head_light_open":"Strikeline Head Light · Open",
    "striker_head_cover_green":"Strikeline Head Cover · Green",
    "striker_head_cover_red":"Strikeline Head Cover · Red",
    "striker_head_cover_yellow":"Strikeline Head Cover · Yellow",
    "striker_head_cover_blue":"Strikeline Head Cover · Blue",
    "striker_head_cover_orange":"Strikeline Head Cover · Orange",
    "striker_cover_green":"Strikeline Cover · Green","striker_cover_red":"Strikeline Cover · Red",
    "striker_cover_yellow":"Strikeline Cover · Yellow","striker_cover_blue":"Strikeline Cover · Blue",
    "striker_cover_orange":"Strikeline Cover · Orange",
    "note_kick":"Kick Note","note_anim_kick":"Kick Note Anim",
    "note_kick_sp_active":"Kick · SP Active","note_kick_sp_phrase":"Kick · SP Phrase",
    "note_kick_sp_phrase_active":"Kick · SP Phrase Active",
    "note_anim_kick_sp_active":"Kick Anim · SP Active","note_anim_kick_sp_phrase":"Kick Anim · SP Phrase",
    "note_anim_kick_sp_phrase_active":"Kick Anim · SP Phrase Active",
    "note_overlay_kick_sp_phrase":"Kick Overlay · SP Phrase",
    "cym_green":"Cymbal · Green","cym_red":"Cymbal · Red","cym_yellow":"Cymbal · Yellow","cym_blue":"Cymbal · Blue",
    "cym_anim_green":"Cymbal Anim · Green","cym_anim_red":"Cymbal Anim · Red",
    "cym_anim_yellow":"Cymbal Anim · Yellow","cym_anim_blue":"Cymbal Anim · Blue",
    "cym_sp_active":"Cymbal · SP Active","cym_sp_phrase":"Cymbal · SP Phrase","cym_sp_phrase_active":"Cymbal · SP Phrase Active",
    "cym_anim_sp_active":"Cymbal Anim · SP Active","cym_anim_sp_phrase":"Cymbal Anim · SP Phrase",
    "cym_anim_sp_phrase_active":"Cymbal Anim · SP Phrase Active",
    "tom_green":"Tom · Green","tom_red":"Tom · Red","tom_yellow":"Tom · Yellow","tom_blue":"Tom · Blue",
    "tom_anim_green":"Tom Anim · Green","tom_anim_red":"Tom Anim · Red",
    "tom_anim_yellow":"Tom Anim · Yellow","tom_anim_blue":"Tom Anim · Blue",
    "tom_sp_active":"Tom · SP Active","tom_sp_phrase":"Tom · SP Phrase","tom_sp_phrase_active":"Tom · SP Phrase Active",
    "tom_anim_sp_active":"Tom Anim · SP Active","tom_anim_sp_phrase":"Tom Anim · SP Phrase",
    "tom_anim_sp_phrase_active":"Tom Anim · SP Phrase Active",
    "drums_striker_base_green":"Drum Strikeline Base · Green","drums_striker_base_red":"Drum Strikeline Base · Red",
    "drums_striker_base_yellow":"Drum Strikeline Base · Yellow","drums_striker_base_blue":"Drum Strikeline Base · Blue",
    "drums_striker_head_light_kick":"Drum Strikeline Head Light · Kick",
    "drums_striker_head_light_green":"Drum Strikeline Head Light · Green",
    "drums_striker_head_light_red":"Drum Strikeline Head Light · Red",
    "drums_striker_head_light_yellow":"Drum Strikeline Head Light · Yellow",
    "drums_striker_head_light_blue":"Drum Strikeline Head Light · Blue",
    "drums_striker_head_cover_green":"Drum Strikeline Head Cover · Green",
    "drums_striker_head_cover_red":"Drum Strikeline Head Cover · Red",
    "drums_striker_head_cover_yellow":"Drum Strikeline Head Cover · Yellow",
    "drums_striker_head_cover_blue":"Drum Strikeline Head Cover · Blue",
    "drums_striker_cover_green":"Drum Strikeline Cover · Green",
    "drums_striker_cover_red":"Drum Strikeline Cover · Red",
    "drums_striker_cover_yellow":"Drum Strikeline Cover · Yellow",
    "drums_striker_cover_blue":"Drum Strikeline Cover · Blue",
    "sf_note_hopo":"Six-Fret Note · HOPO","sf_note_open":"Six-Fret Note · Open",
    "sf_note_white_left":"Six-Fret Note · White Left","sf_note_white_mid":"Six-Fret Note · White Mid",
    "sf_note_white_right":"Six-Fret Note · White Right","sf_note_black_left":"Six-Fret Note · Black Left",
    "sf_note_black_mid":"Six-Fret Note · Black Mid","sf_note_black_right":"Six-Fret Note · Black Right",
    "sf_note_sp_active":"Six-Fret Note · SP Active","sf_note_sp_phrase":"Six-Fret Note · SP Phrase",
    "sf_note_sp_phrase_active":"Six-Fret Note · SP Phrase Active",
    "sf_note_tap_open":"Six-Fret Tap · Open","sf_note_tap_white_left":"Six-Fret Tap · White Left",
    "sf_note_tap_white_mid":"Six-Fret Tap · White Mid","sf_note_tap_white_right":"Six-Fret Tap · White Right",
    "sf_note_tap_black_left":"Six-Fret Tap · Black Left","sf_note_tap_black_mid":"Six-Fret Tap · Black Mid",
    "sf_note_tap_black_right":"Six-Fret Tap · Black Right",
    "sf_sustain_open":"Six-Fret Sustain · Open","sf_sustain_left":"Six-Fret Sustain · Left",
    "sf_sustain_mid":"Six-Fret Sustain · Mid","sf_sustain_right":"Six-Fret Sustain · Right",
    "sf_sustain_sp_active":"Six-Fret Sustain · SP Active","sf_sustain_sp_phrase":"Six-Fret Sustain · SP Phrase",
    "sf_sustain_sp_phrase_active":"Six-Fret Sustain · SP Phrase Active",
    "sf_striker_base_white_left":"Six-Fret Strikeline Base · White Left",
    "sf_striker_base_white_mid":"Six-Fret Strikeline Base · White Mid",
    "sf_striker_base_white_right":"Six-Fret Strikeline Base · White Right",
    "sf_striker_base_black_left":"Six-Fret Strikeline Base · Black Left",
    "sf_striker_base_black_mid":"Six-Fret Strikeline Base · Black Mid",
    "sf_striker_base_black_right":"Six-Fret Strikeline Base · Black Right",
    "combo_one":"Multiplier · x1","combo_two":"Multiplier · x2","combo_three":"Multiplier · x3",
    "combo_four":"Multiplier · x4","combo_sp_active":"Multiplier · SP Active",
    "combo_two_glow":"Multiplier Glow · x2","combo_three_glow":"Multiplier Glow · x3",
    "combo_four_glow":"Multiplier Glow · x4","combo_sp_active_glow":"Multiplier Glow · SP Active",
    "striker_hit_flame":"Hit Flame","striker_hit_flame_sp_active":"Hit Flame · SP Active",
    "striker_hit_flame_kick":"Hit Flame · Kick","striker_hit_flame_open":"Hit Flame · Open",
    "striker_hit_particles":"Hit Particles","striker_hit_particles_sp_active":"Hit Particles · SP Active",
    "striker_hold_spark":"Hold Spark","striker_hold_spark_sp_active":"Hold Spark · SP Active",
    "sp_bar_color":"SP Bar · Color","sp_bar_arrow":"SP Bar · Arrow","sp_bar_elec":"SP Bar · Electric",
    "sp_act_animation":"SP Activation · Animation","sp_act_flash":"SP Activation · Flash",
    "general_sp":"General SP Color","general_sp_active":"General SP Active Color",
}

_NG_GROUPS: dict = {
    "guitar": [
        ("Notes", ["note_green","note_red","note_yellow","note_blue","note_orange","note_open",
                   "note_sp_phrase","note_sp_active","note_sp_phrase_active"]),
        ("Note Animations", ["note_anim_green","note_anim_red","note_anim_yellow","note_anim_blue",
                             "note_anim_orange","note_anim_open",
                             "note_anim_sp_phrase","note_anim_sp_active","note_anim_sp_phrase_active"]),
        ("Sustains", ["sustain_green","sustain_red","sustain_yellow","sustain_blue",
                      "sustain_orange","sustain_open",
                      "sustain_sp_phrase","sustain_sp_active","sustain_sp_phrase_active"]),
        ("Strikeline Head Light", ["striker_head_light_green","striker_head_light_red",
                                   "striker_head_light_yellow","striker_head_light_blue",
                                   "striker_head_light_orange","striker_head_light_open"]),
        ("Strikeline Head Cover", ["striker_head_cover_green","striker_head_cover_red",
                                   "striker_head_cover_yellow","striker_head_cover_blue",
                                   "striker_head_cover_orange"]),
        ("Strikeline Cover", ["striker_cover_green","striker_cover_red","striker_cover_yellow",
                              "striker_cover_blue","striker_cover_orange"]),
    ],
    "drums": [
        ("Cymbals", ["cym_green","cym_red","cym_yellow","cym_blue"]),
        ("Cymbal Animations", ["cym_anim_green","cym_anim_red","cym_anim_yellow","cym_anim_blue",
                               "cym_anim_sp_active","cym_anim_sp_phrase","cym_anim_sp_phrase_active",
                               "cym_sp_active","cym_sp_phrase","cym_sp_phrase_active"]),
        ("Toms", ["tom_green","tom_red","tom_yellow","tom_blue"]),
        ("Tom Animations", ["tom_anim_green","tom_anim_red","tom_anim_yellow","tom_anim_blue",
                            "tom_anim_sp_active","tom_anim_sp_phrase","tom_anim_sp_phrase_active",
                            "tom_sp_active","tom_sp_phrase","tom_sp_phrase_active"]),
        ("Kick", ["note_kick","note_anim_kick",
                  "note_kick_sp_active","note_kick_sp_phrase","note_kick_sp_phrase_active",
                  "note_anim_kick_sp_active","note_anim_kick_sp_phrase","note_anim_kick_sp_phrase_active",
                  "note_overlay_kick_sp_phrase","note_overlay_kick_sp_active"]),
        ("Drum Strikeline", ["drums_striker_base_green","drums_striker_base_red",
                             "drums_striker_base_yellow","drums_striker_base_blue",
                             "drums_striker_head_light_kick","drums_striker_head_light_green",
                             "drums_striker_head_light_red","drums_striker_head_light_yellow",
                             "drums_striker_head_light_blue",
                             "drums_striker_head_cover_green","drums_striker_head_cover_red",
                             "drums_striker_head_cover_yellow","drums_striker_head_cover_blue",
                             "drums_striker_cover_green","drums_striker_cover_red",
                             "drums_striker_cover_yellow","drums_striker_cover_blue"]),
    ],
    "sixfret": [
        ("Notes", ["sf_note_white_left","sf_note_white_mid","sf_note_white_right",
                   "sf_note_black_left","sf_note_black_mid","sf_note_black_right",
                   "sf_note_open","sf_note_hopo",
                   "sf_note_sp_active","sf_note_sp_phrase","sf_note_sp_phrase_active"]),
        ("Taps", ["sf_note_tap_white_left","sf_note_tap_white_mid","sf_note_tap_white_right",
                  "sf_note_tap_black_left","sf_note_tap_black_mid","sf_note_tap_black_right",
                  "sf_note_tap_open"]),
        ("Sustains", ["sf_sustain_left","sf_sustain_mid","sf_sustain_right",
                      "sf_sustain_open","sf_sustain_sp_active","sf_sustain_sp_phrase",
                      "sf_sustain_sp_phrase_active"]),
        ("Strikeline", ["sf_striker_base_white_left","sf_striker_base_white_mid","sf_striker_base_white_right",
                        "sf_striker_base_black_left","sf_striker_base_black_mid","sf_striker_base_black_right",
                        "sf_striker_background_left","sf_striker_background_mid","sf_striker_background_right"]),
    ],
}

_NG_GUITAR_LANES = ["green","red","yellow","blue","orange"]
_NG_DRUM_LANES   = ["red","yellow","blue","green"]
_NG_SF_LANES     = [("black","left"),("white","left"),("black","mid"),
                    ("white","mid"),("black","right"),("white","right")]


def _ng_friendly(key: str) -> str:
    return _NG_FRIENDLY.get(key, key.replace("_"," ").title())

def _ng_valid_hex(s: str) -> bool:
    return bool(re.match(r'^#[0-9A-Fa-f]{6}$', s.strip()))

def _ng_hex_to_rgb(h: str):
    """int-based hex→(r,g,b) for NoteGen colorization."""
    h = h.lstrip("#")
    return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

def _ng_rgb_to_hex(r:int, g:int, b:int) -> str:
    return "#{:02X}{:02X}{:02X}".format(max(0,min(255,r)),max(0,min(255,g)),max(0,min(255,b)))

def _ng_darken(h:str, f:float=0.4) -> str:
    r,g,b = _ng_hex_to_rgb(h); return _ng_rgb_to_hex(int(r*f),int(g*f),int(b*f))

def _ng_lighten(h:str, f:float=1.6) -> str:
    r,g,b = _ng_hex_to_rgb(h); return _ng_rgb_to_hex(int(r*f),int(g*f),int(b*f))

def _ng_lerp_hex(a:str, b:str, t:float) -> str:
    ar,ag,ab_ = _ng_hex_to_rgb(a); br,bg_,bb = _ng_hex_to_rgb(b)
    return _ng_rgb_to_hex(int(ar+(br-ar)*t),int(ag+(bg_-ag)*t),int(ab_+(bb-ab_)*t))

def _ng_alpha_blend(h:str, bg:str, alpha:float) -> str:
    r1,g1,b1 = _ng_hex_to_rgb(h); r2,g2,b2 = _ng_hex_to_rgb(bg)
    return _ng_rgb_to_hex(int(r1*alpha+r2*(1-alpha)),int(g1*alpha+g2*(1-alpha)),int(b1*alpha+b2*(1-alpha)))

def _ng_load_profiles() -> dict:
    try:
        if _NG_PROFILES_FILE.is_file():
            return json.loads(_NG_PROFILES_FILE.read_text(encoding="utf-8"))
    except Exception: pass
    return {}

def _ng_save_profiles(profiles: dict):
    try: _NG_PROFILES_FILE.write_text(json.dumps(profiles,indent=2),encoding="utf-8")
    except Exception as e: print(f"[ng_save_profiles] {e}")

def _ng_fresh_colors() -> dict:
    return copy.deepcopy(_NG_DEFAULT_COLORS)

def _ng_parse_ini(path:str) -> dict:
    cfg = configparser.ConfigParser(allow_no_value=True); cfg.optionxform = str
    cfg.read(path, encoding="utf-8"); result = {}
    for section in cfg.sections():
        result[section.lower()] = {}
        for key, val in cfg.items(section):
            if val and val.strip():
                result[section.lower()][key.lower()] = val.strip().upper()
    return result

def _ng_generate_ini(colors:dict) -> str:
    lines = []
    for section in _SECTION_ORDER:
        if section not in colors: continue
        lines.append(f"[{section}]")
        for key, val in colors[section].items(): lines.append(f"{key} = {val}")
        lines.append("")
    return "\n".join(lines)

def _ng_find_template():
    for name in _TEMPLATE_NAMES:
        p = _NG_IMAGES_DIR / name
        if p.is_file(): return p
        p2 = _app_dir() / name
        if p2.is_file(): return p2
    return None

def _ng_find_mask():
    for d in (_NG_IMAGES_DIR, _app_dir()):
        p = d / "mask.png"
        if p.is_file(): return p
    return None

def _ng_rgb_to_hsl(r,g,b):
    r,g,b = r/255.,g/255.,b/255.; cmax,cmin=max(r,g,b),min(r,g,b); delta=cmax-cmin
    l=(cmax+cmin)/2.; s=0. if delta==0 else delta/(1-abs(2*l-1))
    if delta==0: h=0.
    elif cmax==r: h=60.*(((g-b)/delta)%6)
    elif cmax==g: h=60.*(((b-r)/delta)+2)
    else: h=60.*(((r-g)/delta)+4)
    return h,s,l

def _ng_hsl_to_rgb(h,s,l):
    c=(1-abs(2*l-1))*s; x=c*(1-abs((h/60)%2-1)); m=l-c/2
    if h<60:   r1,g1,b1=c,x,0.
    elif h<120:r1,g1,b1=x,c,0.
    elif h<180:r1,g1,b1=0.,c,x
    elif h<240:r1,g1,b1=0.,x,c
    elif h<300:r1,g1,b1=x,0.,c
    else:      r1,g1,b1=c,0.,x
    return int((r1+m)*255),int((g1+m)*255),int((b1+m)*255)

def _ng_composite_note_pil(body_spr, base_spr, light_spr,
                            body_hex: str, light_hex: str, size: tuple):
    """Composite note sprites using pure PIL — no numpy required.
    body  : multiply-tinted (channel-wise multiply preserving alpha)
    light : source-in tinted (colour fill masked by sprite alpha)
    Layers: body → base → light, result is fully RGBA (transparent bg).
    """
    from PIL import Image as _PI

    def _load_or_blank(spr):
        if spr is None:
            return _PI.new("RGBA", size, (0, 0, 0, 0))
        if spr.size != size:
            spr = spr.resize(size, _PI.LANCZOS)
        return spr.convert("RGBA")

    body  = _load_or_blank(body_spr)
    base  = _load_or_blank(base_spr)
    light = _load_or_blank(light_spr)

    def h2rgb(h):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    # Body: multiply tint — split into channels, scale each by tint colour
    r, g, b = h2rgb(body_hex)
    br, bg_, bb, ba = body.split()
    br  = br.point(lambda x: x * r // 255)
    bg_ = bg_.point(lambda x: x * g // 255)
    bb  = bb.point(lambda x: x * b // 255)
    body_img = _PI.merge("RGBA", (br, bg_, bb, ba))

    # Light: source-in tint — solid colour masked by sprite alpha
    lr, lg_, lb = h2rgb(light_hex)
    _, _, _, la = light.split()
    light_img = _PI.new("RGBA", size, (lr, lg_, lb, 0))
    light_img.putalpha(la)

    # Composite: body(z=1) → base(z=2) → light(z=3)
    out = _PI.new("RGBA", size, (0, 0, 0, 0))
    out = _PI.alpha_composite(out, body_img)
    out = _PI.alpha_composite(out, base)
    out = _PI.alpha_composite(out, light_img)
    return out

def _ng_colorize_pil(img, hex_color:str):
    try:
        import numpy as np
        _NP = True
    except ImportError:
        _NP = False
    rgba = img.convert("RGBA")
    if not _NP:
        hue,sat,_ = _ng_rgb_to_hsl(*_ng_hex_to_rgb(hex_color))
        r_lut,g_lut,b_lut=[],[],[]
        for L in range(256):
            if L<=40: w=0.
            elif L<=85: w=(L-40)/45.
            elif L<=210: w=1.
            elif L<=240: w=1.-(L-210)/30.
            else: w=0.
            w=w*w*(3-2*w)
            rc,gc,bc=_ng_hsl_to_rgb(hue,sat,L/255.)
            r_lut.append(max(0,min(255,int(L*(1-w)+rc*w))))
            g_lut.append(max(0,min(255,int(L*(1-w)+gc*w))))
            b_lut.append(max(0,min(255,int(L*(1-w)+bc*w))))
        r_ch,g_ch,b_ch,a_ch=rgba.split(); gray=r_ch
        from PIL import Image as _PI
        colored=_PI.merge("RGBA",(gray.point(r_lut),gray.point(g_lut),gray.point(b_lut),a_ch))
        mask_path=_ng_find_mask()
        if mask_path:
            mi=_PI.open(str(mask_path)).convert("L").resize(rgba.size,_PI.LANCZOS)
            return _PI.composite(colored,rgba,mi)
        return colored
    import numpy as np
    arr=np.array(rgba,dtype=np.float32); H,W=arr.shape[:2]
    R,G,B,A=arr[:,:,0],arr[:,:,1],arr[:,:,2],arr[:,:,3]
    lum=0.299*R+0.587*G+0.114*B
    mask_path=_ng_find_mask()
    if mask_path:
        from PIL import Image as _PI
        mi=_PI.open(str(mask_path)).convert("L").resize((W,H),_PI.LANCZOS)
        weight=np.array(mi,dtype=np.float32)/255.*(A/255.)
    else:
        weight=A/255.
    tr,tg,tb=_ng_hex_to_rgb(hex_color)
    scale=lum/128.
    r_col=np.clip(scale*tr,0.,255.); g_col=np.clip(scale*tg,0.,255.); b_col=np.clip(scale*tb,0.,255.)
    orig=arr[:,:,:3]
    r_o=np.clip(orig[:,:,0]*(1.-weight)+r_col*weight,0,255).astype(np.uint8)
    g_o=np.clip(orig[:,:,1]*(1.-weight)+g_col*weight,0,255).astype(np.uint8)
    b_o=np.clip(orig[:,:,2]*(1.-weight)+b_col*weight,0,255).astype(np.uint8)
    a_o=arr[:,:,3].astype(np.uint8)
    from PIL import Image as _PI
    return _PI.fromarray(np.stack([r_o,g_o,b_o,a_o],axis=2),"RGBA")

def _ng_generate_note_images(guitar_colors:dict):
    if not _PIL_OK: return [],["Pillow is not installed."]
    tpl=_ng_find_template()
    if tpl is None: return [],[f"Template not found. Place one of {_TEMPLATE_NAMES} in {_NG_IMAGES_DIR}"]
    try:
        from PIL import Image as _PI
        base=_PI.open(str(tpl))
    except Exception as e: return [],[f"Could not open template: {e}"]
    _NG_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    saved,errors=[],[]
    for lane,ini_key,filename in _NOTE_FILE_MAP:
        hex_color=guitar_colors.get(ini_key,"#FFFFFF")
        try:
            colored=_ng_colorize_pil(base,hex_color)
            out=_NG_IMAGES_DIR/filename; colored.save(str(out)); saved.append(filename)
        except Exception as e: errors.append(f"{filename}: {e}")
    return saved,errors


# ── NoteGen custom HSV colour picker ─────────────────────────────────────────

class _ColorPickerDialog(tk.Toplevel):
    """Full HSV square + hue bar colour picker — replaces tkinter's colorchooser."""
    _SQ = 220
    _HH = 20

    def __init__(self, parent, initial_hex:str, title:str="Pick Color"):
        super().__init__(parent)
        self.title(title); self.resizable(False,False)
        self.configure(bg=C["bg"]); self.transient(parent); self.grab_set()
        self.result = None
        try: ri,gi,bi = _ng_hex_to_rgb(initial_hex)
        except Exception: ri,gi,bi = 255,255,255
        h,s,v = colorsys.rgb_to_hsv(ri/255,gi/255,bi/255)
        self._h,self._s,self._v = h,s,v
        self._orig = _ng_rgb_to_hex(ri,gi,bi).upper()
        self._r=tk.IntVar(value=ri); self._g=tk.IntVar(value=gi); self._b=tk.IntVar(value=bi)
        self._hex_var=tk.StringVar(value=self._orig)
        self._busy=False; self._sq_cur_ids=[]; self._hue_cur_ids=[]
        self._sq_photo=None
        self._build_ui(); self._render_sq(); self._render_hue()
        self._refresh_cursors(); self._update_preview()
        self.update_idletasks()
        pw,ph=parent.winfo_width(),parent.winfo_height()
        px,py=parent.winfo_rootx(),parent.winfo_rooty()
        ww,wh=self.winfo_reqwidth(),self.winfo_reqheight()
        self.geometry(f"+{px+(pw-ww)//2}+{py+(ph-wh)//2}")
        self.wait_window()

    def _build_ui(self):
        SQ=self._SQ
        outer=tk.Frame(self,bg=C["bg"],padx=18,pady=16); outer.pack()
        left=tk.Frame(outer,bg=C["bg"]); left.pack(side="left",padx=(0,20))
        sq_wrap=tk.Frame(left,bg="#252845",padx=1,pady=1); sq_wrap.pack()
        self._sq_cv=tk.Canvas(sq_wrap,width=SQ,height=SQ,highlightthickness=0,cursor="crosshair")
        self._sq_cv.pack()
        self._sq_cv.bind("<Button-1>",self._sq_drag)
        self._sq_cv.bind("<B1-Motion>",self._sq_drag)
        tk.Frame(left,bg=C["border"],height=1).pack(fill="x",pady=(10,0))
        hue_wrap=tk.Frame(left,bg="#252845",padx=1,pady=1); hue_wrap.pack(pady=(8,0))
        self._hue_cv=tk.Canvas(hue_wrap,width=SQ,height=self._HH,highlightthickness=0,cursor="sb_h_double_arrow")
        self._hue_cv.pack()
        self._hue_cv.bind("<Button-1>",self._hue_drag)
        self._hue_cv.bind("<B1-Motion>",self._hue_drag)
        right=tk.Frame(outer,bg=C["bg"]); right.pack(side="left",fill="both")
        pv=tk.Frame(right,bg=C["bg"]); pv.pack(fill="x",pady=(0,14))
        tk.Label(pv,text="BEFORE",bg=C["bg"],fg=C["text_dim"],font=("Lato", 7, "bold")).pack(side="left")
        self._sw_old=tk.Frame(pv,bg=self._orig,width=54,height=36); self._sw_old.pack(side="left",padx=(5,2)); self._sw_old.pack_propagate(False)
        self._sw_new=tk.Frame(pv,bg=self._orig,width=54,height=36); self._sw_new.pack(side="left",padx=(2,5)); self._sw_new.pack_propagate(False)
        tk.Label(pv,text="AFTER",bg=C["bg"],fg=C["text_dim"],font=("Lato", 7, "bold")).pack(side="left")
        for label,var,trough in [("R",self._r,"#5c1212"),("G",self._g,"#124a22"),("B",self._b,"#12265c")]:
            row=tk.Frame(right,bg=C["bg"]); row.pack(fill="x",pady=3)
            tk.Label(row,text=label,bg=C["bg"],fg=C["text"],font=FTB,width=2).pack(side="left")
            tk.Scale(row,variable=var,from_=0,to=255,orient="horizontal",length=200,showvalue=True,
                     bg=C["bg"],fg=C["text_mid"],troughcolor=trough,highlightthickness=0,bd=0,
                     sliderrelief="flat",font=("Lato", 8),command=lambda _v: self._on_rgb()).pack(side="left",padx=(4,0))
        tk.Frame(right,bg=C["border"],height=1).pack(fill="x",pady=(10,8))
        hx=tk.Frame(right,bg=C["bg"]); hx.pack(fill="x",pady=(0,4))
        tk.Label(hx,text="HEX",bg=C["bg"],fg=C["text_dim"],font=("Lato", 7, "bold")).pack(side="left",padx=(0,8))
        self._hex_entry=tk.Entry(hx,textvariable=self._hex_var,font=("Lato", 10),width=9,
                                  bg=C["card2"],fg=C["accent"],insertbackground=C["accent"],
                                  relief="flat",bd=0,highlightthickness=1,
                                  highlightbackground=C["border"],highlightcolor=C["accent"])
        self._hex_entry.pack(side="left",ipady=4,padx=4)
        self._hex_entry.bind("<Return>",self._on_hex); self._hex_entry.bind("<FocusOut>",self._on_hex)
        hsv_row=tk.Frame(right,bg=C["bg"]); hsv_row.pack(fill="x",pady=(8,0))
        self._lh=tk.Label(hsv_row,text="H: 0°",bg=C["bg"],fg=C["text_dim"],font=FTS)
        self._ls=tk.Label(hsv_row,text="S: 0%",bg=C["bg"],fg=C["text_dim"],font=FTS)
        self._lv=tk.Label(hsv_row,text="V: 100%",bg=C["bg"],fg=C["text_dim"],font=FTS)
        for lbl in (self._lh,self._ls,self._lv): lbl.pack(side="left",padx=(0,10))
        btn_row=tk.Frame(right,bg=C["bg"]); btn_row.pack(fill="x",pady=(18,0))
        RoundedButton(btn_row, "Cancel", self.destroy,
                      bg_color=C["card2"], hover_color=C["border"],
                      text_color=C["text_mid"], height=42, radius=16,
                      text_font=FT, canvas_bg=C["bg"],
                      width=108).pack(side="right", padx=(4, 0))
        RoundedButton(btn_row, "✓  Apply", self._ok,
                      bg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#fff", height=42, radius=16,
                      text_font=FTB, canvas_bg=C["bg"],
                      width=130).pack(side="right")

    def _render_sq(self):
        SQ=self._SQ
        try:
            import numpy as np
            from PIL import Image as _PI
            from PIL import ImageTk as _ITk
            xs=np.linspace(0,1,SQ); ys=np.linspace(1,0,SQ)
            S,V=np.meshgrid(xs,ys); h=self._h
            hi=np.floor(h*6).astype(int)%6; f=h*6-np.floor(h*6)
            p=V*(1-S); q=V*(1-f*S); t_=V*(1-(1-f)*S)
            cR=np.select([hi==0,hi==1,hi==2,hi==3,hi==4],[V,q,p,p,t_],V)
            cG=np.select([hi==0,hi==1,hi==2,hi==3,hi==4],[t_,V,V,q,p],p)
            cB=np.select([hi==0,hi==1,hi==2,hi==3,hi==4],[p,p,t_,V,V],q)
            rgb=(np.stack([cR,cG,cB],axis=2)*255).astype(np.uint8)
            photo=_ITk.PhotoImage(_PI.fromarray(rgb,"RGB"))
        except Exception:
            photo=tk.PhotoImage(width=SQ,height=SQ)
            rows=[]
            for y in range(SQ):
                v=1.-y/max(SQ-1,1)
                cols=[_ng_rgb_to_hex(*[int(c*255) for c in colorsys.hsv_to_rgb(self._h,x/max(SQ-1,1),v)]) for x in range(SQ)]
                rows.append("{"+' '.join(cols)+"}")
            photo.put(' '.join(rows))
        self._sq_photo=photo
        self._sq_cv.delete("all")
        self._sq_cv.create_image(0,0,anchor="nw",image=photo)

    def _render_hue(self):
        SQ=self._SQ; HH=self._HH
        try:
            import numpy as np
            from PIL import Image as _PI
            from PIL import ImageTk as _ITk
            xs=np.linspace(0,1,SQ)
            r,g,b=np.vectorize(lambda h: colorsys.hsv_to_rgb(h,1,1))(xs)
            row=(np.stack([r,g,b],axis=1)*255).astype(np.uint8)
            arr=np.tile(row[np.newaxis,:,:],(HH,1,1))
            photo=_ITk.PhotoImage(_PI.fromarray(arr,"RGB"))
        except Exception:
            photo=tk.PhotoImage(width=SQ,height=HH)
            rows=[]
            for _ in range(HH):
                cols=[_ng_rgb_to_hex(*[int(c*255) for c in colorsys.hsv_to_rgb(x/max(SQ-1,1),1,1)]) for x in range(SQ)]
                rows.append("{"+' '.join(cols)+"}")
            photo.put(' '.join(rows))
        self._hue_photo=photo
        self._hue_cv.delete("all")
        self._hue_cv.create_image(0,0,anchor="nw",image=photo)

    def _refresh_cursors(self):
        for iid in self._sq_cur_ids: self._sq_cv.delete(iid)
        for iid in self._hue_cur_ids: self._hue_cv.delete(iid)
        self._sq_cur_ids=[]; self._hue_cur_ids=[]
        SQ=self._SQ; cx=int(self._s*(SQ-1)); cy=int((1.-self._v)*(SQ-1)); cr=8
        self._sq_cur_ids=[self._sq_cv.create_oval(cx-cr,cy-cr,cx+cr,cy+cr,outline="#ffffff",width=2),
                          self._sq_cv.create_oval(cx-cr+2,cy-cr+2,cx+cr-2,cy+cr-2,outline="#000000",width=1)]
        hx=int(self._h*(SQ-1))
        self._hue_cur_ids=[self._hue_cv.create_line(hx,0,hx,self._HH,fill="#ffffff",width=2),
                           self._hue_cv.create_line(hx,0,hx,self._HH,fill="#000000",width=1,dash=(3,3))]

    def _update_preview(self):
        hx=_ng_rgb_to_hex(self._r.get(),self._g.get(),self._b.get())
        self._sw_new.config(bg=hx); self._hex_var.set(hx.upper())
        self._lh.config(text=f"H: {int(self._h*360)}°")
        self._ls.config(text=f"S: {int(self._s*100)}%")
        self._lv.config(text=f"V: {int(self._v*100)}%")

    def _sq_drag(self,ev):
        SQ=self._SQ; self._s=max(0.,min(1.,ev.x/(SQ-1))); self._v=max(0.,min(1.,1.-ev.y/(SQ-1)))
        self._sq_cv.delete("all"); self._sq_cv.create_image(0,0,anchor="nw",image=self._sq_photo)
        cx=int(self._s*(SQ-1)); cy=int((1.-self._v)*(SQ-1)); cr=8
        self._sq_cv.create_oval(cx-cr,cy-cr,cx+cr,cy+cr,outline="#ffffff",width=2)
        self._sq_cv.create_oval(cx-cr+2,cy-cr+2,cx+cr-2,cy+cr-2,outline="#000000",width=1)
        r,g,b=colorsys.hsv_to_rgb(self._h,self._s,self._v)
        self._busy=True; self._r.set(int(r*255+.5)); self._g.set(int(g*255+.5)); self._b.set(int(b*255+.5))
        self._busy=False; self._update_preview()

    def _hue_drag(self,ev):
        self._h=max(0.,min(1.,ev.x/(self._SQ-1)))
        self._render_sq(); self._refresh_cursors()
        r,g,b=colorsys.hsv_to_rgb(self._h,self._s,self._v)
        self._busy=True; self._r.set(int(r*255+.5)); self._g.set(int(g*255+.5)); self._b.set(int(b*255+.5))
        self._busy=False; self._update_preview()

    def _on_rgb(self):
        if self._busy: return
        self._busy=True
        self._h,self._s,self._v=colorsys.rgb_to_hsv(self._r.get()/255,self._g.get()/255,self._b.get()/255)
        self._render_sq(); self._render_hue(); self._refresh_cursors(); self._update_preview()
        self._busy=False

    def _on_hex(self,_=None):
        val=self._hex_var.get().strip().lstrip("#")
        if len(val)==6:
            try: ri,gi,bi=int(val[0:2],16),int(val[2:4],16),int(val[4:6],16)
            except ValueError: return
            if self._busy: return
            self._busy=True; self._r.set(ri); self._g.set(gi); self._b.set(bi)
            self._h,self._s,self._v=colorsys.rgb_to_hsv(ri/255,gi/255,bi/255)
            self._render_sq(); self._render_hue(); self._refresh_cursors(); self._update_preview()
            self._busy=False

    def _ok(self):
        self.result=_ng_rgb_to_hex(self._r.get(),self._g.get(),self._b.get()).upper()
        self.destroy()


# ── NoteGen auto-gradient dialog ──────────────────────────────────────────────

class _NgAutoGradientDialog(tk.Toplevel):
    """Pick colour stops → interpolate across lanes → apply to a section.
    mode: 'guitar'  — 5 lanes, forced 1+5, optional midpoint 3
          'drums'   — combined: cymbals + toms side by side, each forced 1+4
          'sixfret' — 6 notes forced 1+6
    """

    _GUITAR_CFG = {
        "title":      "Auto Gradient — Guitar",
        "lanes":      ["green","red","yellow","blue","orange"],
        "lane_lbls":  ["1·G","2·R","3·Y","4·B","5·O"],
        "stop_lbls":  [("Note 1  (Green)","note_green"),
                       ("Note 3  (Yellow)","note_yellow"),
                       ("Note 5  (Orange)","note_orange")],
        "categories": [("Notes","note"),("Note Animations","note_anim"),
                       ("Sustains","sustain"),("Head Light","striker_head_light"),
                       ("Head Cover","striker_head_cover"),("Strikeline Cover","striker_cover")],
        "section":    "guitar",
        "has_mid":    True,
        "n_stops":    5,
    }
    _DRUMS_CYM = {
        "lanes":      ["red","yellow","blue","green"],
        "lane_lbls":  ["1·R","2·Y","3·B","4·G"],
        "stop_lbls":  [("Cymbal 1  (Red)","cym_red"),("Cymbal 4  (Green)","cym_green")],
        "categories": [("Cymbals","cym"),("Cymbal Anims","cym_anim")],
        "n_stops":    4,
    }
    _DRUMS_TOM = {
        "lanes":      ["red","yellow","blue","green"],
        "lane_lbls":  ["1·R","2·Y","3·B","4·G"],
        "stop_lbls":  [("Tom 1  (Red)","tom_red"),("Tom 4  (Green)","tom_green")],
        "categories": [("Toms","tom"),("Tom Anims","tom_anim")],
        "n_stops":    4,
    }
    _SF_CFG = {
        "title":   "Auto Gradient — Six Fret",
        "section": "sixfret",
    }
    _SF_WHITE = {
        "lanes":      ["white_left","white_mid","white_right"],
        "lane_lbls":  ["1·WL","2·WM","3·WR"],
        "stop_lbls":  [("White 1  (Left)","sf_note_white_left"),
                       ("White 3  (Right)","sf_note_white_right")],
        "categories": [("Notes","sf_note"),("Sustains","sf_sustain")],
        "n_stops":    3,
    }
    _SF_BLACK = {
        "lanes":      ["black_left","black_mid","black_right"],
        "lane_lbls":  ["1·BL","2·BM","3·BR"],
        "stop_lbls":  [("Black 1  (Left)","sf_note_black_left"),
                       ("Black 3  (Right)","sf_note_black_right")],
        "categories": [("Notes","sf_note"),("Sustains","sf_sustain")],
        "n_stops":    3,
    }

    def __init__(self, parent, current_colors: dict, mode: str = "guitar"):
        super().__init__(parent)
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        self.transient(parent)
        self.grab_set()
        self.result  = None   # list of dicts for drums, single dict otherwise
        self._mode   = mode
        self._colors = current_colors

        # Per-section stop vars
        def _sv(key, fallback):
            return tk.StringVar(value=current_colors.get(key, fallback).upper())

        if mode == "guitar":
            cfg = self._GUITAR_CFG
            self.title(cfg["title"])
            self._stop1    = _sv("note_green",  "#00FF00")
            self._stop_mid = _sv("note_yellow", "#FFFF00")
            self._stop2    = _sv("note_orange", "#FFB300")
            self._use_mid  = tk.BooleanVar(value=True)
            self._cat_vars = {lbl: tk.BooleanVar(value=True) for lbl, _ in cfg["categories"]}
            self._sw_refs  = {}; self._prev_sws = []
        elif mode == "drums":
            self.title("Auto Gradient — Drums")
            self._cym_stop1 = _sv("cym_red",   "#FF0000")
            self._cym_stop2 = _sv("cym_green",  "#00FF00")
            self._tom_stop1 = _sv("tom_red",   "#FF0000")
            self._tom_stop2 = _sv("tom_green",  "#00FF00")
            self._cym_cat_vars = {lbl: tk.BooleanVar(value=True) for lbl, _ in self._DRUMS_CYM["categories"]}
            self._tom_cat_vars = {lbl: tk.BooleanVar(value=True) for lbl, _ in self._DRUMS_TOM["categories"]}
            self._cym_sw_refs = {}; self._tom_sw_refs = {}
            self._cym_prev_sws = []; self._tom_prev_sws = []
        else:  # sixfret — split white / black
            self.title("Auto Gradient — Six Fret")
            self._sf_white_stop1 = _sv("sf_note_white_left",  "#FFFFFF")
            self._sf_white_stop2 = _sv("sf_note_white_right", "#FFFFFF")
            self._sf_black_stop1 = _sv("sf_note_black_left",  "#3F3F3F")
            self._sf_black_stop2 = _sv("sf_note_black_right", "#3F3F3F")
            self._sf_white_cat_vars = {lbl: tk.BooleanVar(value=True)
                                       for lbl, _ in self._SF_WHITE["categories"]}
            self._sf_black_cat_vars = {lbl: tk.BooleanVar(value=True)
                                       for lbl, _ in self._SF_BLACK["categories"]}
            self._sf_white_sw_refs = {}; self._sf_black_sw_refs = {}
            self._sf_white_prev_sws = []; self._sf_black_prev_sws = []

        self._build()
        self._refresh_preview()
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        ww, wh = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{px+(pw-ww)//2}+{py+(ph-wh)//2}")
        self.wait_window()

    # ── compute ───────────────────────────────────────────────────────────────
    def _compute(self):
        """For non-drums modes."""
        cfg = self._GUITAR_CFG if self._mode == "guitar" else self._SF_CFG
        n = cfg["n_stops"]
        if self._mode == "guitar" and self._use_mid.get():
            stops = [self._stop1.get(), self._stop_mid.get(), self._stop2.get()]
        else:
            stops = [self._stop1.get(), self._stop2.get()]
        return _interpolate_colors(stops, n)

    def _compute_cym(self):
        return _interpolate_colors([self._cym_stop1.get(), self._cym_stop2.get()], 4)

    def _compute_tom(self):
        return _interpolate_colors([self._tom_stop1.get(), self._tom_stop2.get()], 4)

    def _compute_sf_white(self):
        return _interpolate_colors([self._sf_white_stop1.get(), self._sf_white_stop2.get()], 3)

    def _compute_sf_black(self):
        return _interpolate_colors([self._sf_black_stop1.get(), self._sf_black_stop2.get()], 3)

    # ── build ─────────────────────────────────────────────────────────────────
    def _build(self):
        BG = C["bg"]; CARD = C["panel"]

        def sec_hdr(parent, text):
            tk.Label(parent, text=text, font=("Lato", 7, "bold"),
                     bg=CARD, fg=C["text_dim"]).pack(anchor="w", pady=(0, 6))

        def stop_row(parent, label, var, sw_dict):
            row = tk.Frame(parent, bg=CARD); row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=CARD, fg=C["text"],
                     font=FT, width=20, anchor="w").pack(side="left")
            sw = tk.Frame(row, bg=var.get(), width=34, height=22, cursor="hand2",
                          highlightbackground=C["border"], highlightthickness=1)
            sw.pack(side="left", padx=(0,5)); sw.pack_propagate(False)
            sw_dict[label] = sw
            RoundedButton(row, "Pick",
                          lambda v=var, l=label, d=sw_dict: self._pick(v, l, d),
                          bg_color=C["border"], hover_color=C["hover"],
                          text_color=C["text"], height=34, radius=12,
                          text_font=("Lato", 8), canvas_bg=CARD,
                          width=58).pack(side="left")

        def preview_strip(parent, lbls, prev_list):
            strip = tk.Frame(parent, bg=CARD); strip.pack(fill="x", pady=(4,0))
            for lbl in lbls:
                col = tk.Frame(strip, bg=CARD)
                col.pack(side="left", expand=True, fill="x", padx=1)
                sw = tk.Frame(col, bg="#333", height=28,
                              highlightbackground=C["border"], highlightthickness=1)
                sw.pack(fill="x"); sw.pack_propagate(False)
                tk.Label(col, text=lbl, bg=CARD, fg=C["text_dim"],
                         font=("Lato", 6)).pack(anchor="center")
                prev_list.append(sw)

        def cat_checks(parent, cat_vars):
            g = tk.Frame(parent, bg=CARD); g.pack(fill="x", pady=(4,0))
            for i, (lbl, _) in enumerate(cat_vars.items()):
                tk.Checkbutton(g, text=lbl, variable=cat_vars[lbl],
                               bg=CARD, fg=C["text_mid"], selectcolor=C["bg"],
                               activebackground=CARD, activeforeground=C["text"],
                               font=("Lato", 8), relief="flat").grid(
                    row=0, column=i, sticky="w", padx=(0, 12))

        outer = tk.Frame(self, bg=BG, padx=20, pady=16); outer.pack()

        if self._mode == "drums":
            # ── Combined cymbals + toms in a split card ───────────────────────
            split = tk.Frame(outer, bg=BG); split.pack(fill="x", pady=(0,10))

            for side_lbl, stop1, stop2, sw_dict, prev_list, cat_vars, dcfg in [
                ("CYMBALS", self._cym_stop1, self._cym_stop2,
                 self._cym_sw_refs, self._cym_prev_sws, self._cym_cat_vars, self._DRUMS_CYM),
                ("TOMS",    self._tom_stop1, self._tom_stop2,
                 self._tom_sw_refs, self._tom_prev_sws, self._tom_cat_vars, self._DRUMS_TOM),
            ]:
                box = tk.Frame(split, bg=CARD, padx=14, pady=12,
                               highlightbackground=C["border"], highlightthickness=1)
                box.pack(side="left", fill="both", expand=True, padx=(0 if side_lbl=="CYMBALS" else 6, 0))
                sec_hdr(box, side_lbl)
                stop_row(box, dcfg["stop_lbls"][0][0], stop1, sw_dict)
                stop_row(box, dcfg["stop_lbls"][1][0], stop2, sw_dict)
                tk.Label(box, text="PREVIEW", font=("Lato", 6, "bold"),
                         bg=CARD, fg=C["text_dim"]).pack(anchor="w", pady=(8,0))
                preview_strip(box, dcfg["lane_lbls"], prev_list)
                tk.Label(box, text="APPLY TO", font=("Lato", 6, "bold"),
                         bg=CARD, fg=C["text_dim"]).pack(anchor="w", pady=(8,0))
                cat_checks(box, cat_vars)

        elif self._mode == "sixfret":
            # ── Combined white + black in a split card ────────────────────────
            split = tk.Frame(outer, bg=BG); split.pack(fill="x", pady=(0,10))
            for side_lbl, stop1, stop2, sw_dict, prev_list, cat_vars, sfcfg in [
                ("WHITE", self._sf_white_stop1, self._sf_white_stop2,
                 self._sf_white_sw_refs, self._sf_white_prev_sws,
                 self._sf_white_cat_vars, self._SF_WHITE),
                ("BLACK", self._sf_black_stop1, self._sf_black_stop2,
                 self._sf_black_sw_refs, self._sf_black_prev_sws,
                 self._sf_black_cat_vars, self._SF_BLACK),
            ]:
                box = tk.Frame(split, bg=CARD, padx=14, pady=12,
                               highlightbackground=C["border"], highlightthickness=1)
                box.pack(side="left", fill="both", expand=True,
                         padx=(0 if side_lbl == "WHITE" else 6, 0))
                sec_hdr(box, side_lbl)
                stop_row(box, sfcfg["stop_lbls"][0][0], stop1, sw_dict)
                stop_row(box, sfcfg["stop_lbls"][1][0], stop2, sw_dict)
                tk.Label(box, text="PREVIEW", font=("Lato", 6, "bold"),
                         bg=CARD, fg=C["text_dim"]).pack(anchor="w", pady=(8,0))
                preview_strip(box, sfcfg["lane_lbls"], prev_list)
                tk.Label(box, text="APPLY TO", font=("Lato", 6, "bold"),
                         bg=CARD, fg=C["text_dim"]).pack(anchor="w", pady=(8,0))
                cat_checks(box, cat_vars)

        else:
            # ── Guitar single-section layout ──────────────────────────────────
            cfg = self._GUITAR_CFG

            sc = tk.Frame(outer, bg=CARD, padx=16, pady=12,
                          highlightbackground=C["border"], highlightthickness=1)
            sc.pack(fill="x", pady=(0,10))
            sec_hdr(sc, "GRADIENT STOPS")
            stop_row(sc, cfg["stop_lbls"][0][0], self._stop1, self._sw_refs)

            mid_lbl = cfg["stop_lbls"][1][0]
            mid_row = tk.Frame(sc, bg=CARD); mid_row.pack(fill="x", pady=3)
            tk.Label(mid_row, text=mid_lbl, bg=CARD, fg=C["text_dim"],
                     font=FT, width=20, anchor="w").pack(side="left")
            sw3 = tk.Frame(mid_row, bg=self._stop_mid.get(), width=34, height=22,
                           cursor="hand2", highlightbackground=C["border"], highlightthickness=1)
            sw3.pack(side="left", padx=(0,5)); sw3.pack_propagate(False)
            self._sw_refs[mid_lbl] = sw3
            self._pick_mid_btn = RoundedButton(
                mid_row, "Pick",
                lambda: self._pick(self._stop_mid, mid_lbl, self._sw_refs),
                bg_color=C["border"], hover_color=C["hover"],
                text_color=C["text"], height=34, radius=12,
                text_font=("Lato", 8), canvas_bg=CARD,
                width=58)
            self._pick_mid_btn.pack(side="left")
            tk.Checkbutton(mid_row, text="Use as midpoint",
                           variable=self._use_mid, command=self._on_mid_toggle,
                           bg=CARD, fg=C["text_mid"], selectcolor=C["bg"],
                           activebackground=CARD, font=("Lato", 8),
                           relief="flat").pack(side="left", padx=(10,0))
            self._on_mid_toggle()

            stop_row(sc, cfg["stop_lbls"][-1][0], self._stop2, self._sw_refs)

            pc = tk.Frame(outer, bg=CARD, padx=16, pady=12,
                          highlightbackground=C["border"], highlightthickness=1)
            pc.pack(fill="x", pady=(0,10))
            sec_hdr(pc, "GRADIENT PREVIEW")
            preview_strip(pc, cfg["lane_lbls"], self._prev_sws)

            ac = tk.Frame(outer, bg=CARD, padx=16, pady=12,
                          highlightbackground=C["border"], highlightthickness=1)
            ac.pack(fill="x", pady=(0,10))
            sec_hdr(ac, "APPLY TO")
            cat_checks(ac, self._cat_vars)

        # ── Buttons ───────────────────────────────────────────────────────────
        br = tk.Frame(outer, bg=BG); br.pack(fill="x", pady=(4,0))
        RoundedButton(br, "Cancel", self.destroy,
                      bg_color=C["card2"], hover_color=C["border"],
                      text_color=C["text_mid"], height=42, radius=16,
                      text_font=FT, canvas_bg=BG,
                      width=108).pack(side="right", padx=(4, 0))
        RoundedButton(br, "✓  Apply Gradient", self._ok,
                      bg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#fff", height=42, radius=16,
                      text_font=FTB, canvas_bg=BG,
                      width=185).pack(side="right")

    # ── helpers ───────────────────────────────────────────────────────────────
    def _on_mid_toggle(self):
        enabled = self._use_mid.get()
        self._pick_mid_btn.config(state="normal" if enabled else "disabled",
                                  fg=C["text"] if enabled else C["text_dim"])
        self._refresh_preview()

    def _pick(self, var, label, sw_dict):
        dlg = _ColorPickerDialog(self, var.get(), f"Pick — {label}")
        if dlg.result:
            var.set(dlg.result)
            if label in sw_dict:
                sw_dict[label].config(bg=dlg.result)
            self._refresh_preview()

    def _refresh_preview(self):
        if self._mode == "drums":
            try:    cg = self._compute_cym()
            except: cg = ["#666"] * 4
            try:    tg = self._compute_tom()
            except: tg = ["#666"] * 4
            for sw, c in zip(self._cym_prev_sws, cg): sw.config(bg=c)
            for sw, c in zip(self._tom_prev_sws, tg): sw.config(bg=c)
        elif self._mode == "sixfret":
            try:    wg = self._compute_sf_white()
            except: wg = ["#666"] * 3
            try:    bg_ = self._compute_sf_black()
            except: bg_ = ["#666"] * 3
            for sw, c in zip(self._sf_white_prev_sws, wg): sw.config(bg=c)
            for sw, c in zip(self._sf_black_prev_sws, bg_): sw.config(bg=c)
        else:
            try:    gradient = self._compute()
            except: gradient = ["#666"] * 5
            for sw, c in zip(self._prev_sws, gradient): sw.config(bg=c)

    def _ok(self):
        if self._mode == "drums":
            results = []
            try:    cg = self._compute_cym()
            except Exception as e:
                messagebox.showerror("Gradient Error", str(e), parent=self); return
            try:    tg = self._compute_tom()
            except Exception as e:
                messagebox.showerror("Gradient Error", str(e), parent=self); return
            cym_cats = [pfx for lbl, pfx in self._DRUMS_CYM["categories"]
                        if self._cym_cat_vars[lbl].get()]
            tom_cats = [pfx for lbl, pfx in self._DRUMS_TOM["categories"]
                        if self._tom_cat_vars[lbl].get()]
            if cym_cats:
                results.append({"section": "drums",
                                 "lane_map": dict(zip(self._DRUMS_CYM["lanes"], cg)),
                                 "categories": cym_cats})
            if tom_cats:
                results.append({"section": "drums",
                                 "lane_map": dict(zip(self._DRUMS_TOM["lanes"], tg)),
                                 "categories": tom_cats})
            if not results:
                messagebox.showwarning("Nothing selected",
                                       "Select at least one category to apply.", parent=self); return
            self.result = results
        elif self._mode == "sixfret":
            results = []
            try:    wg = self._compute_sf_white()
            except Exception as e:
                messagebox.showerror("Gradient Error", str(e), parent=self); return
            try:    bg_ = self._compute_sf_black()
            except Exception as e:
                messagebox.showerror("Gradient Error", str(e), parent=self); return
            w_cats = [pfx for lbl, pfx in self._SF_WHITE["categories"]
                      if self._sf_white_cat_vars[lbl].get()]
            b_cats = [pfx for lbl, pfx in self._SF_BLACK["categories"]
                      if self._sf_black_cat_vars[lbl].get()]
            if w_cats:
                results.append({"section": "sixfret",
                                 "lane_map": dict(zip(self._SF_WHITE["lanes"], wg)),
                                 "categories": w_cats})
            if b_cats:
                results.append({"section": "sixfret",
                                 "lane_map": dict(zip(self._SF_BLACK["lanes"], bg_)),
                                 "categories": b_cats})
            if not results:
                messagebox.showwarning("Nothing selected",
                                       "Select at least one category to apply.", parent=self); return
            self.result = results
        else:
            cfg = self._GUITAR_CFG
            try:    gradient = self._compute()
            except Exception as e:
                messagebox.showerror("Gradient Error", str(e), parent=self); return
            active_cats = [pfx for lbl, pfx in cfg["categories"]
                           if self._cat_vars[lbl].get()]
            if not active_cats:
                messagebox.showwarning("Nothing selected",
                                       "Select at least one category to apply.",
                                       parent=self); return
            self.result = [{"section":    cfg["section"],
                             "lane_map":   dict(zip(cfg["lanes"], gradient)),
                             "categories": active_cats}]
        self.destroy()


# ── NoteGen note card (visual note preview + 2 colour pickers) ────────────────

class _NgNoteCard(tk.Frame):
    """Canvas-based note preview card matching the React web editor's rendering.
    Uses multiply blend for body colour and source-in for light/anim colour."""
    W, H = 95, 50
    _SPRITE_BODY  = "note_body.png"
    _SPRITE_BASE  = "note_base.png"
    _SPRITE_LIGHT = "note_light.png"
    _sprite_cache: dict = {}

    def __init__(self, parent, section: str, body_key: str, light_key: str,
                 label: str, notegen_page, **kw):
        BG = C["bg"]
        super().__init__(parent, bg=BG, **kw)
        self._section   = section
        self._body_key  = body_key
        self._light_key = light_key
        self._page      = notegen_page
        self._readonly  = False
        self._photo     = None
        self._body_hex  = "#FFFFFF"
        self._light_hex = "#FFFFFF"

        cv_wrap = tk.Frame(self, bg="#1a1a2e",
                           highlightthickness=1, highlightbackground=C["border"])
        cv_wrap.pack(padx=10, pady=(10, 4))
        self._cv = tk.Canvas(cv_wrap, width=self.W, height=self.H,
                              bg="#1a1a2e", highlightthickness=0)
        self._cv.pack()

        short = (label.replace("note_","").replace("cym_","Cym ")
                      .replace("tom_","Tom ").replace("_"," ").title())
        tk.Label(self, text=short, bg=BG, fg=C["text_mid"],
                 font=("Lato", 8, "bold")).pack(pady=(0, 2))

        self._body_sw,  self._body_btn  = self._color_row(BG, "Body",  self._pick_body)
        self._light_sw, self._light_btn = self._color_row(BG, "Light", self._pick_light)
        self._cv.create_rectangle(0, 0, self.W, self.H, fill="#1a1a2e", outline="")

    def _color_row(self, bg, label, cmd):
        row = tk.Frame(self, bg=bg); row.pack(fill="x", padx=8, pady=2)
        tk.Label(row, text=label, bg=bg, fg=C["text_dim"],
                 font=("Lato", 7), width=5, anchor="w").pack(side="left")
        sw = tk.Frame(row, width=30, height=18, cursor="hand2",
                      highlightthickness=1, highlightbackground=C["border"])
        sw.pack(side="left", padx=(0, 4)); sw.pack_propagate(False)
        btn = RoundedButton(row, "Pick", cmd,
                            bg_color=C["border"], hover_color=C["hover"],
                            text_color=C["text"], height=30, radius=10,
                            text_font=("Lato", 7), canvas_bg=bg,
                            width=54)
        btn.pack(side="left")
        return sw, btn

    def _pick_body(self):
        if self._readonly: return
        dlg = _ColorPickerDialog(self._page, self._body_hex,
                                  f"Body — {self._body_key}")
        if dlg.result:
            self._page.on_color_changed(self._section, self._body_key, dlg.result)

    def _pick_light(self):
        if self._readonly: return
        dlg = _ColorPickerDialog(self._page, self._light_hex,
                                  f"Light — {self._light_key}")
        if dlg.result:
            self._page.on_color_changed(self._section, self._light_key, dlg.result)

    def update_colors(self, body_hex: str, light_hex: str):
        self._body_hex  = body_hex.upper()
        self._light_hex = light_hex.upper()
        self._body_sw.config(bg=body_hex)
        self._light_sw.config(bg=light_hex)
        self._render()

    def set_readonly(self, ro: bool):
        self._readonly = ro
        s = "disabled" if ro else "normal"; fg = C["text_dim"] if ro else C["text"]
        self._body_btn.config(state=s, fg=fg)
        self._light_btn.config(state=s, fg=fg)

    def _load_sprite(self, name: str):
        path = _NG_IMAGES_DIR / name
        key = str(path)
        if key in _NgNoteCard._sprite_cache:
            return _NgNoteCard._sprite_cache[key]
        if not _PIL_OK or not path.is_file(): return None
        from PIL import Image as _PI
        img = _PI.open(key).convert("RGBA").resize((self.W, self.H), _PI.LANCZOS)
        _NgNoteCard._sprite_cache[key] = img
        return img

    def _render(self):
        if not _PIL_OK: self._render_fallback(); return
        try:
            from PIL import ImageTk as _ITk
            out = _ng_composite_note_pil(
                self._load_sprite(self._SPRITE_BODY),
                self._load_sprite(self._SPRITE_BASE),
                self._load_sprite(self._SPRITE_LIGHT),
                self._body_hex, self._light_hex,
                (self.W, self.H))
            photo = _ITk.PhotoImage(out)
            self._photo = photo
            self._cv.delete("all")
            self._cv.create_image(0, 0, anchor="nw", image=photo)
        except Exception: self._render_fallback()

    def _render_fallback(self):
        self._cv.delete("all")
        self._cv.create_rectangle(2, 2, self.W-2, self.H-2,
                                   fill=self._body_hex, outline=self._light_hex, width=3)


# ── NoteGen scrollable frame ──────────────────────────────────────────────────

class _NgScrollFrame(tk.Frame):
    def __init__(self,parent,bg="",**kw):
        bg=bg or C["card"]
        super().__init__(parent,bg=bg,**kw)
        self._cv=tk.Canvas(self,bg=bg,highlightthickness=0,bd=0)
        self._vsb=ttk.Scrollbar(self,orient="vertical",command=self._cv.yview)
        self._cv.configure(yscrollcommand=self._vsb.set)
        self._vsb.pack(side="right",fill="y"); self._cv.pack(side="left",fill="both",expand=True)
        self.inner=tk.Frame(self._cv,bg=bg)
        self._win=self._cv.create_window((0,0),window=self.inner,anchor="nw")
        self.inner.bind("<Configure>",self._on_inner)
        self._cv.bind("<Configure>",self._on_canvas)
        self._cv.bind("<Enter>",lambda _: self._cv.bind_all("<MouseWheel>",self._scroll))
        self._cv.bind("<Leave>",lambda _: self._cv.unbind_all("<MouseWheel>"))

    def _on_inner(self,_=None): self._cv.configure(scrollregion=self._cv.bbox("all"))
    def _on_canvas(self,ev): self._cv.itemconfig(self._win,width=ev.width)
    def _scroll(self,ev): self._cv.yview_scroll(_scroll_units(ev),"units")
    def scroll_top(self): self._cv.yview_moveto(0)


# ── NoteGen collapsible group header ─────────────────────────────────────────

class _NgGroupHeader(tk.Frame):
    def __init__(self,parent,text,count=0,**kw):
        self._BG  = C["bg"]
        self._HOV = C["hover"]
        super().__init__(parent,bg=self._BG,cursor="hand2",**kw)
        self._expanded=True; self._children=None
        row=tk.Frame(self,bg=self._BG); row.pack(fill="x")
        tk.Frame(row,bg=C["accent"],width=3).pack(side="left",fill="y")
        self._chev=tk.Label(row,text="▾",bg=self._BG,fg=C["accent"],font=("Lato", 10))
        self._chev.pack(side="left",padx=(8,4))
        self._title=tk.Label(row,text=text,font=("Lato", 8, "bold"),bg=self._BG,fg=C["accent"],pady=8,anchor="w")
        self._title.pack(side="left",fill="x",expand=True)
        if count:
            badge=tk.Frame(row,bg=C["accent_dim"]); badge.pack(side="right",padx=(0,10))
            tk.Label(badge,text=f" {count} ",font=("Lato", 7, "bold"),bg=C["accent_dim"],fg=C["accent"]).pack(padx=2,pady=2)
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        for w in (self,row,self._chev,self._title):
            w.bind("<Enter>",self._h_on); w.bind("<Leave>",self._h_off); w.bind("<Button-1>",self._toggle)

    def _h_on(self,_=None):
        for w in (self,self._chev,self._title):
            try: w.config(bg=self._HOV)
            except: pass
    def _h_off(self,_=None):
        for w in (self,self._chev,self._title):
            try: w.config(bg=self._BG)
            except: pass
    def _toggle(self,_=None):
        self._expanded = not self._expanded
        self._chev.config(text="▾" if self._expanded else "▸")
        if self._children:
            if self._expanded:
                self._children.pack(fill="x", after=self)
            else:
                self._children.pack_forget()
    def attach(self,frame): self._children=frame


# ── NoteGen colour row ────────────────────────────────────────────────────────

class _NgColorRow(tk.Frame):
    _STEPS=8

    def __init__(self,parent,section,key,notegen_page,row_idx):
        _IDLE_ODD  = C["bg"]
        _IDLE_EVEN = C["panel"]
        self._HOV  = C["hover"]
        self._ACT  = C["selected"]
        idle=_IDLE_ODD if row_idx%2 else _IDLE_EVEN
        super().__init__(parent,bg=idle,cursor="hand2")
        self._section=section; self._key=key; self._page=notegen_page
        self._idle=idle; self._muted=False; self._anim_id=None; self._t=0.; self._going=0
        tk.Frame(self,bg=C["border"],height=1).pack(side="bottom",fill="x")
        self._sw=tk.Canvas(self,width=50,height=28,highlightthickness=0,bg="#000",cursor="hand2")
        self._sw.pack(side="left",padx=(12,10),pady=6)
        self._lbl=tk.Label(self,text=_ng_friendly(key),bg=idle,fg=C["text_mid"],font=FTS,anchor="w")
        self._lbl.pack(side="left",fill="x",expand=True,padx=(0,6))
        pill=tk.Frame(self,bg=C["card2"],highlightthickness=1,highlightbackground=C["border"])
        pill.pack(side="right",padx=(0,12),pady=6)
        self._var=tk.StringVar(value="#000000")
        self._entry=tk.Entry(pill,textvariable=self._var,font=("Lato", 9),width=8,
                             bg=C["card2"],fg=C["accent"],insertbackground=C["accent"],
                             relief="flat",bd=4,highlightthickness=0,cursor="hand2",
                             state="readonly",readonlybackground=C["card2"])
        self._entry.pack()
        self._entry.bind("<FocusIn>",lambda e: pill.config(highlightbackground=C["accent"]))
        self._entry.bind("<FocusOut>",lambda e: pill.config(highlightbackground=C["border"]))
        self._entry.bind("<Button-1>",self._copy_hex)
        self._pill=pill
        self._pick_btn=RoundedButton(self,"Pick Color",self._open_picker,
                                      bg_color=C["card2"],hover_color=C["accent"],
                                      text_color=C["text_mid"],height=36,radius=12,
                                      text_font=("Lato", 8),canvas_bg=C["card2"],
                                      width=100)
        self._pick_btn.pack(side="right",padx=(0,4))
        self._copied_lbl=tk.Label(self,text="Copied!",font=("Lato", 8, "bold"),bg=self._idle,fg=C["success"],padx=4)
        for w in (self,self._lbl,self._sw):
            w.bind("<Enter>",self._h_in); w.bind("<Leave>",self._h_out); w.bind("<Button-1>",self._click)
        self._var.trace_add("write",self._on_write)

    def _draw_sw(self,col):
        self._sw.delete("all"); self._sw.create_rectangle(0,0,50,28,fill=col,outline="")
        try: self._sw.create_rectangle(3,2,28,7,fill=_ng_lighten(col,1.8),outline="")
        except: pass
        self._sw.create_rectangle(0,0,49,27,outline=_ng_darken(col,0.5),fill="")

    def _animate(self):
        self._t=max(0.,min(1.,self._t+self._going/self._STEPS)); t=self._t*self._t*(3-2*self._t)
        bg=_ng_lerp_hex(self._idle,self._HOV,t); fg=_ng_lerp_hex(C["text_mid"],C["text"],t)
        self.config(bg=bg); self._lbl.config(bg=bg,fg=fg)
        if 0.<self._t<1.: self._anim_id=self.after(16,self._animate)
        else: self._anim_id=None

    def _h_in(self,_=None):
        self._going=+1
        if not self._anim_id: self._animate()
    def _h_out(self,_=None):
        self._going=-1
        if not self._anim_id: self._animate()
    def _click(self,_=None):
        self.config(bg=self._ACT); self._lbl.config(bg=self._ACT)
        self.after(80,self._h_in); self._open_picker()

    def _copy_hex(self,e=None):
        col=self.get_color()
        try: self.clipboard_clear(); self.clipboard_append(col)
        except: pass
        self._pill.config(highlightbackground=C["success"])
        self._copied_lbl.config(bg=self.cget("bg"))
        self._copied_lbl.pack(side="right",before=self._pill)
        def _hide():
            self._copied_lbl.pack_forget(); self._pill.config(highlightbackground=C["border"])
        if hasattr(self,"_copy_after_id"):
            try: self.after_cancel(self._copy_after_id)
            except: pass
        self._copy_after_id=self.after(900,_hide)
        return "break"

    def set_color(self,hex_str:str):
        self._muted=True; self._var.set(hex_str.upper())
        if _ng_valid_hex(hex_str): self._draw_sw(hex_str)
        self._muted=False

    def get_color(self): return self._var.get().strip().upper()

    def set_readonly(self,readonly):
        self._entry.config(state="disabled" if readonly else "readonly",
                           fg=C["text_dim"] if readonly else C["accent"],
                           readonlybackground=C["card2"],disabledbackground=C["card2"],
                           disabledforeground=C["text_dim"])
        self._pick_btn.config(state="disabled" if readonly else "normal")
        cur="" if readonly else "hand2"
        for w in (self,self._lbl,self._sw):
            w.config(cursor=cur)
            if readonly: w.unbind("<Enter>"); w.unbind("<Leave>"); w.unbind("<Button-1>")
            else:
                w.bind("<Enter>",self._h_in); w.bind("<Leave>",self._h_out)
                w.bind("<Button-1>",self._click)

    def _on_write(self,*_):
        if self._muted: return
        val=self._var.get().strip()
        if not val.startswith("#"): val="#"+val
        if _ng_valid_hex(val):
            self._draw_sw(val); self._page.on_color_changed(self._section,self._key,val.upper())

    def _open_picker(self,*_):
        cur=self.get_color()
        if not _ng_valid_hex(cur): cur="#FFFFFF"
        dlg=_ColorPickerDialog(self.winfo_toplevel(),cur,title=_ng_friendly(self._key))
        if dlg.result:
            self.set_color(dlg.result); self._page.on_color_changed(self._section,self._key,dlg.result)


# ── NoteGen section editor ────────────────────────────────────────────────────

class _NgSectionEditor(tk.Frame):
    def __init__(self,parent,section,notegen_page,**kw):
        super().__init__(parent,bg=C["bg"],**kw)
        self._rows: dict = {}
        self._sf=_NgScrollFrame(self,bg=C["bg"]); self._sf.pack(fill="both",expand=True)
        groups=_NG_GROUPS.get(section,[])
        if not groups: groups=[("All",list(_NG_DEFAULT_COLORS.get(section,{}).keys()))]
        row_idx=0
        for group_name,keys in groups:
            valid=[k for k in keys if k in _NG_DEFAULT_COLORS.get(section,{})]
            if not valid: continue
            hdr=_NgGroupHeader(self._sf.inner,group_name,count=len(valid)); hdr.pack(fill="x")
            cf=tk.Frame(self._sf.inner,bg=C["bg"]); cf.pack(fill="x"); hdr.attach(cf)
            for key in valid:
                row=_NgColorRow(cf,section,key,notegen_page,row_idx)
                row.pack(fill="x"); self._rows[key]=row; row_idx+=1

    def push(self,color_dict):
        for key,row in self._rows.items(): row.set_color(color_dict.get(key,"#FFFFFF"))
        self._sf.scroll_top()

    def set_readonly(self,readonly):
        for row in self._rows.values(): row.set_readonly(readonly)


# ── NoteGen highway preview ───────────────────────────────────────────────────

class _NgHighwayPreview(tk.Frame):
    """
    Live guitar highway preview — 1:1 port of CHNoteGen's _HighwayPreview.
    Notes at the bottom, sustains running full-height to the top edge,
    SP stripe across the very top.
    """
    def __init__(self, parent, notegen_page, **kw):
        super().__init__(parent, bg=C["panel"], **kw)
        self._page = notegen_page
        self._photo_cache: dict = {}
        self._cv = tk.Canvas(self, bg=C["bg"], highlightthickness=1,
                             highlightbackground=C["border"])
        self._cv.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._cv.bind("<Configure>", lambda _: self.refresh())

    # ── public ─────────────────────────────────────────────────────────────────
    def refresh(self):
        self._cv.delete("all")
        w, h = self._cv.winfo_width(), self._cv.winfo_height()
        if w < 20 or h < 20:
            return
        tab = getattr(self._page, "_ng_active_tab", "guitar")
        if tab == "drums":
            self._draw_drums(w, h)
        elif tab == "sixfret":
            self._draw_sixfret(w, h)
        else:
            self._draw_guitar(w, h)

    def clear_photo_cache(self, hex_color=None):
        if hex_color is None:
            self._photo_cache.clear()
        else:
            # key is now (body_hex, light_hex, w, h) — evict any entry involving this colour
            for k in [k for k in self._photo_cache
                      if k[0] == hex_color or k[1] == hex_color]:
                del self._photo_cache[k]

    # ── note sprite loader ──────────────────────────────────────────────────────
    def _get_note_photo(self, body_hex: str, light_hex: str, pixel_w: int, pixel_h: int):
        """Composite note sprites using pure PIL — no numpy required."""
        if not _PIL_OK:
            return None
        key = (body_hex.upper(), light_hex.upper(), pixel_w, pixel_h)
        if key in self._photo_cache:
            return self._photo_cache[key]
        try:
            from PIL import Image as _PI, ImageTk as _ITk

            def _load(name):
                p = _NG_IMAGES_DIR / name
                if p.is_file():
                    return _PI.open(str(p)).convert("RGBA")
                return None

            out = _ng_composite_note_pil(
                _load("note_body.png"),
                _load("note_base.png"),
                _load("note_light.png"),
                body_hex, light_hex,
                (pixel_w, pixel_h))

            photo = _ITk.PhotoImage(out)
            self._photo_cache[key] = photo
            return photo
        except Exception:
            return None

    # ── dome note shape (1:1 from CHNoteGen) ───────────────────────────────────
    def _draw_dome_note(self, cv, cx: int, cy: int, col: str, nr: int):
        sh = int(nr * 0.22)
        cv.create_oval(cx - nr, cy + sh, cx + nr, cy + sh + int(nr * 0.42),
                       fill="#000000", outline="")
        sk_h = int(nr * 0.30); sk_y = cy + int(nr * 0.20)
        cv.create_oval(cx - nr, sk_y - sk_h, cx + nr, sk_y + sk_h,
                       fill=_ng_darken(col, 0.50), outline="")
        dw = int(nr * 0.82); dh = int(nr * 0.72)
        cv.create_oval(cx - dw, cy - dh, cx + dw, cy + int(nr * 0.26),
                       fill=col, outline="")
        cv.create_oval(cx - dw, cy + int(nr * 0.10), cx + dw, cy + int(nr * 0.36),
                       fill=_ng_darken(col, 0.72), outline="")
        hl_w = int(nr * 0.44); hl_h = int(nr * 0.26)
        hl_x = cx - int(nr * 0.14); hl_y = cy - int(nr * 0.42)
        cv.create_oval(hl_x - hl_w, hl_y - hl_h, hl_x + hl_w, hl_y + hl_h,
                       fill=_ng_lighten(col, 1.85), outline="")
        gr = max(3, int(nr * 0.20)); gy = cy - int(nr * 0.10)
        cv.create_oval(cx - gr, gy - gr, cx + gr, gy + gr, fill="#FFFFFF", outline="")

    # ── lane backgrounds with beat lines (1:1 from CHNoteGen) ──────────────────
    def _draw_lanes(self, cv, w: int, h: int, n: int, lane_tints: list):
        lw = w / n
        for i in range(n):
            x1, x2 = int(i * lw), int((i + 1) * lw)
            bg = _ng_alpha_blend(lane_tints[i], C["bg"], 0.10)
            cv.create_rectangle(x1, 0, x2, h, fill=bg, outline="")
            if i > 0:
                cv.create_line(x1, 0, x1, h, fill=C["border"], width=1)
        for frac in [0.25, 0.42, 0.58, 0.74]:
            y = int(h * frac)
            cv.create_line(0, y, w, y, fill=C["border"], width=1, dash=(2, 12))

    # ── sustain bar with rounded caps (1:1 from CHNoteGen) ─────────────────────
    def _draw_sustain(self, cv, cx: int, top: int, bottom: int,
                      col: str, sw: int):
        cv.create_rectangle(cx - sw, top + sw, cx + sw, bottom - sw,
                            fill=col, outline="")
        cv.create_oval(cx - sw, top,            cx + sw, top    + sw * 2, fill=col, outline="")
        cv.create_oval(cx - sw, bottom - sw * 2, cx + sw, bottom,         fill=col, outline="")

    # ── guitar highway ────────────────────────────────────────────────────────
    def _draw_guitar(self, w: int, h: int):
        cv  = self._cv
        gc  = self._page._ng_active_colors().get("guitar", {})
        n   = len(_NG_GUITAR_LANES)
        lw  = w / n

        # Note sprites are 95×50 — scale to fit lane width nicely
        note_w  = max(40, min(95, int(lw * 0.85)))
        note_h  = max(21, int(note_w * 50 / 95))   # maintain 95:50 aspect ratio
        sw      = max(4, int(lw * 0.10))
        note_y  = h - note_h - 10
        sus_top = -sw
        sus_bot = note_y + note_h // 2   # sustain meets the note centre

        self._draw_lanes(cv, w, h, n,
                         [gc.get(f"note_{l}", "#333") for l in _NG_GUITAR_LANES])

        # Sustains (behind notes)
        for i, lane in enumerate(_NG_GUITAR_LANES):
            cx  = int(i * lw + lw / 2)
            col = gc.get(f"sustain_{lane}", "#888")
            self._draw_sustain(cv, cx, sus_top, sus_bot, col, sw)

        # SP stripe across the top
        cv.create_rectangle(0, 0, w, 4,
                            fill=gc.get("note_sp_active", "#00FFFF"), outline="")

        # Notes using new sprites
        for i, lane in enumerate(_NG_GUITAR_LANES):
            cx        = int(i * lw + lw / 2)
            body_hex  = gc.get(f"note_{lane}",      "#888")
            light_hex = gc.get(f"note_anim_{lane}", "#888")
            photo = self._get_note_photo(body_hex, light_hex, note_w, note_h)
            if photo is not None:
                cv.create_image(cx, note_y, image=photo, anchor="n")
            else:
                nr = note_h // 2
                self._draw_dome_note(cv, cx, note_y + nr, body_hex, nr)

    # ── drums highway (4×2: cymbals top row, toms bottom row) ────────────────
    def _draw_drums(self, w: int, h: int):
        cv = self._cv
        dc = self._page._ng_active_colors().get("drums", {})
        n  = 4
        lw = w / n

        note_w = max(40, min(95, int(lw * 0.85)))
        note_h = max(21, int(note_w * 50 / 95))
        sw     = max(4, int(lw * 0.10))

        row_h  = h / 2
        div_y  = int(row_h)

        # Note sits at bottom of each half-row
        cym_y  = div_y - note_h - sw      # note top (anchor "n") in cymbal row
        tom_y  = h     - note_h - sw      # note top in tom row

        LANES = ["red", "yellow", "blue", "green"]

        # Lane backgrounds
        for i, lane in enumerate(LANES):
            x1, x2 = int(i * lw), int((i + 1) * lw)
            tint = _ng_alpha_blend(dc.get(f"tom_{lane}", "#333"), C["bg"], 0.10)
            cv.create_rectangle(x1, 0, x2, h, fill=tint, outline="")
            if i > 0:
                cv.create_line(x1, 0, x1, h, fill=C["border"], width=1)

        # Horizontal divider
        cv.create_line(0, div_y, w, div_y, fill=C["border"], width=1, dash=(4, 8))

        # SP stripe at top
        cv.create_rectangle(0, 0, w, 4,
                            fill=dc.get("cym_sp_active", "#00FFFF"), outline="")

        # Cymbal sustains: from very top → cymbal note centre
        for i, lane in enumerate(LANES):
            cx  = int(i * lw + lw / 2)
            col = dc.get(f"cym_{lane}", "#888")
            self._draw_sustain(cv, cx, -sw, cym_y + note_h // 2, col, sw)

        # Tom sustains: from divider → tom note centre
        for i, lane in enumerate(LANES):
            cx  = int(i * lw + lw / 2)
            col = dc.get(f"tom_{lane}", "#888")
            self._draw_sustain(cv, cx, div_y + sw, tom_y + note_h // 2, col, sw)

        # Cymbals
        for i, lane in enumerate(LANES):
            cx        = int(i * lw + lw / 2)
            body_hex  = dc.get(f"cym_{lane}",      "#888")
            light_hex = dc.get(f"cym_anim_{lane}", "#888")
            photo = self._get_note_photo(body_hex, light_hex, note_w, note_h)
            if photo is not None:
                cv.create_image(cx, cym_y, image=photo, anchor="n")
            else:
                nr = note_h // 2
                self._draw_dome_note(cv, cx, cym_y + nr, body_hex, nr)

        # Toms
        for i, lane in enumerate(LANES):
            cx        = int(i * lw + lw / 2)
            body_hex  = dc.get(f"tom_{lane}",      "#888")
            light_hex = dc.get(f"tom_anim_{lane}", "#888")
            photo = self._get_note_photo(body_hex, light_hex, note_w, note_h)
            if photo is not None:
                cv.create_image(cx, tom_y, image=photo, anchor="n")
            else:
                nr = note_h // 2
                self._draw_dome_note(cv, cx, tom_y + nr, body_hex, nr)

        # Row labels
        cv.create_text(4, 6, text="Cymbals", font=("Lato", 7), fill=C["text_dim"], anchor="nw")
        cv.create_text(4, div_y + 6, text="Toms", font=("Lato", 7), fill=C["text_dim"], anchor="nw")

    # ── six fret highway (2×3: white/black columns, left/mid/right rows) ─────
    def _draw_sixfret(self, w: int, h: int):
        cv = self._cv
        sc = self._page._ng_active_colors().get("sixfret", {})

        n_cols = 2
        n_rows = 3
        col_w  = w / n_cols
        row_h  = h / n_rows

        note_w = max(30, min(95, int(col_w * 0.75)))
        note_h = max(16, int(note_w * 50 / 95))
        sw     = max(3, int(col_w * 0.08))

        POSITIONS  = ["left", "mid", "right"]
        WHITE_TINT = "#e8e8e8"
        BLACK_TINT = "#3a3a3a"

        # Column backgrounds
        for col_i, bg_tint in enumerate([WHITE_TINT, BLACK_TINT]):
            x1, x2 = int(col_i * col_w), int((col_i + 1) * col_w)
            cv.create_rectangle(x1, 0, x2, h,
                                fill=_ng_alpha_blend(bg_tint, C["bg"], 0.08), outline="")
        cv.create_line(int(col_w), 0, int(col_w), h, fill=C["border"], width=1)

        # Horizontal dividers between rows
        for row_i in range(1, n_rows):
            y = int(row_i * row_h)
            cv.create_line(0, y, w, y, fill=C["border"], width=1, dash=(3, 8))

        # SP stripe at very top
        cv.create_rectangle(0, 0, w, 4,
                            fill=sc.get("sf_note_sp_active", "#00FFFF"), outline="")

        for row_i, pos in enumerate(POSITIONS):
            row_top  = int(row_i * row_h)
            row_bot  = int((row_i + 1) * row_h)
            # Note sits at bottom of cell
            note_top = row_bot - note_h - sw
            # Sustain runs from very top of cell (bleeding above for row 0) to note centre
            sus_top  = (-sw) if row_i == 0 else row_top
            sus_bot  = note_top + note_h // 2

            for col_i, col_type in enumerate(["white", "black"]):
                cx = int(col_i * col_w + col_w / 2)

                # Sustain
                self._draw_sustain(cv, cx, sus_top, sus_bot,
                                   sc.get(f"sf_sustain_{pos}", "#888"), sw)

                # Note
                body_hex = sc.get(f"sf_note_{col_type}_{pos}", "#888")
                photo = self._get_note_photo(body_hex, body_hex, note_w, note_h)
                if photo is not None:
                    cv.create_image(cx, note_top, image=photo, anchor="n")
                else:
                    nr = note_h // 2
                    self._draw_dome_note(cv, cx, note_top + nr, body_hex, nr)

        # Column labels
        for col_i, label in enumerate(["White", "Black"]):
            cx = int(col_i * col_w + col_w / 2)
            cv.create_text(cx, h - 2, text=label,
                           font=("Lato", 7), fill=C["text_dim"], anchor="s")





# ─────────────────────────────────────────────────────────────────────────────
class CHNoteGenMixin:
    """
    CHSuite mixin: methods that build and operate the CHNoteGen page.

    Methods on this mixin are merged into the main CHSuite class via multiple
    inheritance.  All references to ``self`` resolve against that combined
    class — these methods only work when the mixin is composed into CHSuite,
    never when used standalone.
    """

    def _build_page_notegen(self):
        page = tk.Frame(self._content, bg=C["bg"])
        self._pages["notegen"] = page

        BG_TITLE = C["bg"]
        BG_PROF  = C["panel"]

        # ── Title bar ─────────────────────────────────────────────────────────
        title = tk.Frame(page, bg=BG_TITLE); title.pack(fill="x")
        tk.Frame(title, bg=C["accent"], height=2).pack(fill="x", side="bottom")
        left_t = tk.Frame(title, bg=BG_TITLE); left_t.pack(side="left", padx=18, pady=11)
        tk.Label(left_t, text="CH", font=("Lato", 18, "bold"),
                 bg=BG_TITLE, fg=C["accent"]).pack(side="left")
        tk.Label(left_t, text="NoteGen", font=("Lato", 18, "bold"),
                 bg=BG_TITLE, fg=C["text"]).pack(side="left")
        tk.Label(left_t, text="  Guitar Color Editor",
                 font=("Lato", 9), bg=BG_TITLE, fg=C["text_dim"]).pack(side="left", pady=(5,0))
        tk.Label(title, text="Ctrl+S  Export",
                 font=("Lato", 8), bg=BG_TITLE, fg=C["text_dim"]).pack(side="right", padx=18)

        # ── Profile bar ───────────────────────────────────────────────────────
        pbar = tk.Frame(page, bg=BG_PROF); pbar.pack(fill="x")
        tk.Frame(pbar, bg=C["border"], height=1).pack(fill="x", side="bottom")

        # Row 1: profile picker + profile management buttons
        pi = tk.Frame(pbar, bg=BG_PROF); pi.pack(fill="x", padx=14, pady=(8, 3))

        pw = tk.Frame(pi, bg=BG_PROF); pw.pack(side="left")
        tk.Label(pw, text="PROFILE", font=("Lato", 7, "bold"),
                 bg=BG_PROF, fg=C["text_dim"]).pack(anchor="w")
        self._ng_prof_var = tk.StringVar()
        self._ng_prof_cb  = StyledDropdown(pw, textvariable=self._ng_prof_var,
                                           state="readonly", width=22, font=FT,
                                           canvas_bg=C["card2"], height=32)
        self._ng_prof_cb.pack()
        self._ng_prof_cb.bind("<<ComboboxSelected>>", self._ng_on_prof_selected)

        tk.Frame(pi, bg=C["border"], width=1, height=34).pack(side="left", padx=10)

        def _pb(parent, text, cmd, style="ghost"):
            styles = {"ghost":  (C["card2"],  C["hover"],       C["text_mid"]),
                      "accent": (C["accent"], C["accent_dim"],  "#fff"),
                      "danger": ("#1a0808",   "#2c0f0f",        "#d45555")}
            bg, hbg, fg = styles[style]
            b = RoundedButton(parent, text, cmd,
                              bg_color=bg, hover_color=hbg,
                              text_color=fg, height=32, radius=12,
                              text_font=("Lato", 8), canvas_bg=BG_PROF)
            b.pack(side="left", padx=2)
            return b

        _pb(pi, "+ New",        self._ng_prof_new)
        _pb(pi, "⎘ Duplicate",  self._ng_prof_duplicate)
        self._ng_rename_btn = _pb(pi, "✎ Rename", self._ng_prof_rename)
        self._ng_delete_btn = _pb(pi, "✕ Delete", self._ng_prof_delete, "danger")

        self._ng_status_var = tk.StringVar(value="")
        self._ng_status_lbl = tk.Label(pi, textvariable=self._ng_status_var,
                                        font=("Lato", 8), bg=BG_PROF, fg=C["text_dim"])
        self._ng_status_lbl.pack(side="right", padx=6)

        # Row 2: file operations + tools
        pi2 = tk.Frame(pbar, bg=BG_PROF); pi2.pack(fill="x", padx=14, pady=(0, 8))
        _pb(pi2, "↑ Import .ini", self._ng_import_ini)
        _pb(pi2, "↓ Export .ini (Ctrl+S)", self._ng_export_ini, "accent")
        tk.Frame(pi2, bg=C["border"], width=1, height=28).pack(side="left", padx=10)
        # Auto Gradient styled with accent3 colour
        _ag = RoundedButton(pi2, "✦ Auto Gradient", self._ng_auto_gradient,
                            bg_color=C["card2"], hover_color=C["hover"],
                            text_color=C["accent3"], height=32, radius=12,
                            text_font=("Lato", 8), canvas_bg=BG_PROF)
        _ag.pack(side="left", padx=2)
        tk.Frame(pi2, bg=C["border"], width=1, height=28).pack(side="left", padx=10)
        _pb(pi2, "📁 Open Folder", self._ng_open_profile_dir)
        _pb(pi2, "↻ Refresh", self._ng_refresh_profiles)

        # ── Read-only banner ──────────────────────────────────────────────────
        self._ng_ro_bar = tk.Frame(page, bg=C["selected"]); ro_i = tk.Frame(self._ng_ro_bar, bg=C["selected"])
        ro_i.pack(fill="x", padx=14, pady=6)
        tk.Label(ro_i, text="🔒  Read-only profile", font=("Lato", 8, "bold"),
                 bg=C["selected"], fg=C["accent"]).pack(side="left")
        tk.Label(ro_i, text=" — duplicate or create a new profile to edit colours.",
                 font=("Lato", 8), bg=C["selected"], fg=C["accent_dim"]).pack(side="left")
        RoundedButton(ro_i, "⎘ Duplicate now", self._ng_prof_duplicate,
                      bg_color=C["accent"], hover_color=C["accent_dim"],
                      text_color="#fff", height=36, radius=14,
                      text_font=("Lato", 8), canvas_bg=C["selected"],
                      width=140).pack(side="right")

        # ── Main body: paned (editor left, preview right) ─────────────────────
        body = tk.PanedWindow(page, orient="horizontal",
                              bg=C["bg"], sashwidth=4, sashrelief="flat", handlesize=0)
        body.pack(fill="both", expand=True)
        left  = tk.Frame(body, bg=C["bg"])
        right = tk.Frame(body, bg=C["panel"])
        body.add(left,  minsize=380, width=640, stretch="always")
        body.add(right, minsize=300, width=480, stretch="always")

        # ── Editor (Guitar + Drums + Six Fret + Effects tabs) ────────────────
        TABS = [("🎸  Guitar","guitar"), ("🥁  Drums","drums"),
                ("🎮  Six Fret","sixfret"), ("✨  Effects","other")]
        self._ng_tab_lbls = {}; self._ng_active_tab = "guitar"
        BG = C["bg"]
        tab_bar = tk.Frame(left, bg=BG); tab_bar.pack(fill="x", side="top")
        self._ng_ind_cv = tk.Canvas(tab_bar, height=2, bg=BG, highlightthickness=0)
        self._ng_ind_cv.pack(fill="x", side="bottom")
        self._ng_ind_rect = self._ng_ind_cv.create_rectangle(0,0,0,2,fill=C["accent"],outline="")
        self._ng_ind_x0 = self._ng_ind_x1 = 0.
        self._ng_ind_tx0= self._ng_ind_tx1= 0.
        self._ng_ind_aid= None
        tab_row = tk.Frame(tab_bar, bg=BG); tab_row.pack(fill="x")
        self._ng_tab_bounds = {}
        content = tk.Frame(left, bg=BG); content.pack(fill="both", expand=True)

        self._ng_note_cards = {}  # unused in this layout, kept for compat

        def _ng_switch(section):
            self._ng_active_tab = section
            for s,lbl in self._ng_tab_lbls.items():
                lbl.config(fg=C["text"] if s==section else C["text_dim"],
                           font=("Lato", 9, "bold") if s==section else ("Lato", 9))
            if section in self._ng_tab_bounds:
                x0,x1=self._ng_tab_bounds[section]; self._ng_slide_to(x0,x1)
            for s,ed in self._ng_editors.items(): ed.pack_forget()
            self._ng_editors[section].pack(fill="both", expand=True, in_=content)
            if hasattr(self, "_ng_preview"):
                self._ng_preview.refresh()

        for tab_label, section in TABS:
            lbl = tk.Label(tab_row, text=tab_label, font=("Lato", 9), bg=BG,
                           fg=C["text_dim"], padx=18, pady=12, cursor="hand2")
            lbl.pack(side="left"); self._ng_tab_lbls[section] = lbl
            def _bind(l,s):
                l.bind("<Enter>", lambda e,_s=s: l.config(fg=C["text_mid"]) if self._ng_active_tab!=_s else None)
                l.bind("<Leave>", lambda e,_s=s: l.config(fg=C["text_dim"]) if self._ng_active_tab!=_s else None)
                l.bind("<Button-1>", lambda e,sec=s: _ng_switch(sec))
            _bind(lbl, section)
        tk.Frame(tab_bar, bg=C["border"], height=1).pack(fill="x", side="bottom")

        def _init_bounds(_=None):
            tab_row.update_idletasks()
            for s,lbl in self._ng_tab_lbls.items():
                x0=lbl.winfo_x(); x1=x0+lbl.winfo_width(); self._ng_tab_bounds[s]=(x0,x1)
            x0,x1=self._ng_tab_bounds.get("guitar",(0,120))
            self._ng_ind_x0=self._ng_ind_x1=x0; self._ng_ind_tx0=self._ng_ind_tx1=x1
            self._ng_ind_cv.coords(self._ng_ind_rect,x0,0,x1,2)
        tab_row.bind("<Configure>", _init_bounds)

        for _, section in TABS:
            ed = _NgSectionEditor(content, section, self)
            self._ng_editors[section] = ed
        _ng_switch("guitar")
        self._ng_tab_lbls["guitar"].config(fg=C["text"], font=("Lato", 9, "bold"))

        # ── Preview ───────────────────────────────────────────────────────────
        hdr_r = tk.Frame(right, bg=C["panel"]); hdr_r.pack(fill="x", padx=8, pady=(8,2))
        tk.Label(hdr_r, text="LIVE PREVIEW", font=FTB,
                 bg=C["panel"], fg=C["accent2"]).pack(side="left")
        self._ng_preview = _NgHighwayPreview(right, self)
        self._ng_preview.pack(fill="both", expand=True)

        # ── Init profiles ─────────────────────────────────────────────────────
        page.bind("<Control-s>", lambda _: self._ng_export_ini())
        self._ng_refresh_profile_list()
        self._ng_select_profile(_NG_DEFAULT_PROFILE_NAME)

    # ── NoteGen tab slider ────────────────────────────────────────────────────
    def _ng_slide_to(self, tx0, tx1):
        self._ng_ind_tx0=tx0; self._ng_ind_tx1=tx1
        if self._ng_ind_aid: self.after_cancel(self._ng_ind_aid); self._ng_ind_aid=None
        self._ng_do_slide()

    def _ng_do_slide(self):
        sp=0.20
        self._ng_ind_x0 += (self._ng_ind_tx0-self._ng_ind_x0)*sp
        self._ng_ind_x1 += (self._ng_ind_tx1-self._ng_ind_x1)*sp
        self._ng_ind_cv.coords(self._ng_ind_rect,self._ng_ind_x0,0,self._ng_ind_x1,2)
        if abs(self._ng_ind_tx0-self._ng_ind_x0)>0.5 or abs(self._ng_ind_tx1-self._ng_ind_x1)>0.5:
            self._ng_ind_aid=self.after(13,self._ng_do_slide)
        else:
            self._ng_ind_x0,self._ng_ind_x1=self._ng_ind_tx0,self._ng_ind_tx1
            self._ng_ind_cv.coords(self._ng_ind_rect,self._ng_ind_x0,0,self._ng_ind_x1,2)
            self._ng_ind_aid=None

    # ── NoteGen helpers called by child widgets ───────────────────────────────
    def _ng_active_colors(self) -> dict:
        return self._ng_active_colors_data

    def on_color_changed(self, section:str, key:str, hex_val:str):
        """Called by _NgColorRow when a colour is picked."""
        if self._ng_active_name == _NG_DEFAULT_PROFILE_NAME: return
        if not _ng_valid_hex(hex_val): return
        old_val = self._ng_active_colors_data.get(section,{}).get(key,"")
        self._ng_active_colors_data.setdefault(section,{})[key] = hex_val.upper()
        self._ng_profiles[self._ng_active_name] = copy.deepcopy(self._ng_active_colors_data)
        _ng_save_profiles(self._ng_profiles)
        if section == "guitar" and old_val:
            self._ng_preview.clear_photo_cache(old_val.upper())
        self._ng_preview.refresh()

    def _ng_refresh_note_cards(self):
        """Push current colours to editors and refresh the highway preview."""
        for section, ed in self._ng_editors.items():
            ed.push(self._ng_active_colors_data.get(section, {}))
        self._ng_preview.refresh()

    # ── NoteGen profile management ────────────────────────────────────────────
    def _ng_is_default(self): return self._ng_active_name == _NG_DEFAULT_PROFILE_NAME

    def _ng_refresh_profile_list(self):
        # Guard: _ng_prof_cb is created in _build_page_notegen(), which runs
        # after _load_initial_profile().  Skip if the widget doesn't exist yet.
        if not hasattr(self, "_ng_prof_cb"):
            return
        names=[_NG_DEFAULT_PROFILE_NAME]+sorted(self._ng_profiles.keys())
        self._ng_prof_cb["values"]=names
        if self._ng_prof_var.get() not in names: self._ng_prof_var.set(_NG_DEFAULT_PROFILE_NAME)

    def _ng_select_profile(self, name:str):
        self._ng_active_name=name; self._ng_prof_var.set(name)
        if name==_NG_DEFAULT_PROFILE_NAME:
            self._ng_active_colors_data=_ng_fresh_colors()
        else:
            saved=self._ng_profiles.get(name,{}); colors=_ng_fresh_colors()
            for section in colors:
                if section in saved: colors[section].update(saved[section])
            self._ng_active_colors_data=colors
        is_ro=self._ng_is_default()
        if is_ro: self._ng_ro_bar.pack(fill="x")
        else: self._ng_ro_bar.pack_forget()
        self._ng_rename_btn.config(state="normal" if not is_ro else "disabled",
                                    fg="#fff" if not is_ro else C["text_dim"])
        self._ng_delete_btn.config(state="normal" if not is_ro else "disabled",
                                    fg="#fff" if not is_ro else C["text_dim"])
        for section,ed in self._ng_editors.items():
            ed.push(self._ng_active_colors_data.get(section,{}))
            ed.set_readonly(is_ro)
        self.after(80, self._ng_preview.refresh)
        self._ng_status(f"Profile: {name}")

    def _ng_on_prof_selected(self,_=None): self._ng_select_profile(self._ng_prof_var.get())

    def _ng_validate_prof_name(self, name: str) -> bool:
        """Return True if name is safe to use as a Clone Hero .ini filename.
        Purely numeric names (e.g. '3', '42') are rejected because Clone Hero
        ignores profiles whose filename stem is only digits."""
        fname = name.replace(" ", "_")
        if fname.isdigit():
            messagebox.showwarning(
                "Invalid profile name",
                f"'{name}' would export as '{fname}.ini'.\n\n"
                "Clone Hero ignores profiles with purely numeric filenames.\n"
                "Please use a name that contains at least one letter.",
                parent=self)
            return False
        return True

    def _ng_prof_new(self):
        name=simpledialog.askstring("New Profile","Profile name:",parent=self)
        if not name: return
        name=name.strip()
        if name==_NG_DEFAULT_PROFILE_NAME:
            messagebox.showwarning("Reserved","That name is reserved.",parent=self); return
        if not self._ng_validate_prof_name(name): return
        if name in self._ng_profiles:
            messagebox.showwarning("Exists",f"'{name}' already exists.",parent=self); return
        self._ng_profiles[name]=copy.deepcopy(self._ng_active_colors_data)
        _ng_save_profiles(self._ng_profiles); self._ng_refresh_profile_list()
        self._ng_select_profile(name); self._ng_status(f"Created '{name}'.")

    def _ng_prof_duplicate(self):
        name=simpledialog.askstring("Duplicate Profile",
                                     f"New name (duplicating '{self._ng_active_name}'):",parent=self)
        if not name: return
        name=name.strip()
        if not name or name==_NG_DEFAULT_PROFILE_NAME: return
        if not self._ng_validate_prof_name(name): return
        if name in self._ng_profiles:
            messagebox.showwarning("Exists",f"'{name}' already exists.",parent=self); return
        self._ng_profiles[name]=copy.deepcopy(self._ng_active_colors_data)
        _ng_save_profiles(self._ng_profiles); self._ng_refresh_profile_list()
        self._ng_select_profile(name); self._ng_status(f"Duplicated as '{name}'.")

    def _ng_prof_rename(self):
        if self._ng_is_default(): return
        new=simpledialog.askstring("Rename Profile",f"Rename '{self._ng_active_name}' to:",parent=self)
        if not new: return
        new=new.strip()
        if not new or new==_NG_DEFAULT_PROFILE_NAME: return
        if not self._ng_validate_prof_name(new): return
        if new in self._ng_profiles:
            messagebox.showwarning("Exists",f"'{new}' already exists.",parent=self); return
        old=self._ng_active_name; self._ng_profiles[new]=self._ng_profiles.pop(old)
        _ng_save_profiles(self._ng_profiles); self._ng_active_name=new
        self._ng_refresh_profile_list(); self._ng_prof_var.set(new)
        self._ng_status(f"Renamed to '{new}'.")

    def _ng_prof_delete(self):
        if self._ng_is_default(): return
        if not messagebox.askyesno("Delete Profile",f"Delete '{self._ng_active_name}'?",parent=self): return
        self._ng_profiles.pop(self._ng_active_name,None)
        _ng_save_profiles(self._ng_profiles); self._ng_refresh_profile_list()
        self._ng_select_profile(_NG_DEFAULT_PROFILE_NAME)

    def _ng_import_ini(self):
        path=filedialog.askopenfilename(title="Import Colors .ini",
                                        filetypes=[("INI files","*.ini"),("All files","*.*")],parent=self)
        if not path: return
        parsed=_ng_parse_ini(path)
        if not any(parsed.get(s) for s in _NG_DEFAULT_COLORS):
            messagebox.showerror("Parse Error","No recognisable colour sections found.",parent=self); return
        name=simpledialog.askstring("Import .ini",f"Importing '{Path(path).name}'\n\nSave as profile name:",parent=self)
        if name is None: return
        name=name.strip()
        if not name:
            if self._ng_is_default():
                messagebox.showwarning("Read-Only","Cannot overwrite the Default profile.",parent=self); return
            target=self._ng_active_name
        else:
            target=name
        colors=_ng_fresh_colors()
        for section in colors:
            if section in parsed: colors[section].update(parsed[section])
        self._ng_profiles[target]=copy.deepcopy(colors)
        _ng_save_profiles(self._ng_profiles); self._ng_refresh_profile_list()
        self._ng_select_profile(target); self._ng_status(f"Imported '{Path(path).name}' → '{target}'.")

    def _ng_export_ini(self,_=None):
        ini_str = _ng_generate_ini(self._ng_active_colors_data)
        fname   = self._ng_active_name.replace(" ", "_") + ".ini"

        colors_dir = self._ng_find_colors_dir()
        if colors_dir is None:
            messagebox.showerror(
                "Colors folder not found",
                "CHSuite could not find your Clone Hero  Custom/Colors  folder.\n\n"
                "Make sure Clone Hero is registered in CHManager, or set your "
                "install directory there first.",
                parent=self)
            return

        dest = colors_dir / fname
        try:
            dest.write_text(ini_str, encoding="utf-8")
            self._ng_status(f"Exported → '{fname}'.")
            messagebox.showinfo("Exported", f"Saved to:\n{dest}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self)

    def _ng_status(self, msg:str):
        self._ng_status_var.set(msg)
        self._ng_status_lbl.config(fg=C["accent"])
        self.after(2000, lambda: self._ng_status_lbl.config(fg=C["text_dim"])
                   if hasattr(self,"_ng_status_lbl") else None)

    # ── NoteGen open profile folder + auto-import ─────────────────────────────
    def _ng_import_ini_files(self) -> int:
        """Scan both Colors dirs and import any .ini not already in profiles.
        Returns the number of newly imported profiles."""
        imported = []
        for colors_dir in self._ng_colors_dirs():
            if not colors_dir.is_dir():
                continue
            for ini_path in sorted(colors_dir.glob("*.ini")):
                profile_name = ini_path.stem
                if profile_name == _NG_DEFAULT_PROFILE_NAME:
                    continue
                if profile_name in self._ng_profiles:
                    continue
                parsed = _ng_parse_ini(str(ini_path))
                if not any(parsed.get(s) for s in _NG_DEFAULT_COLORS):
                    continue
                colors = _ng_fresh_colors()
                for section in colors:
                    if section in parsed:
                        colors[section].update(parsed[section])
                self._ng_profiles[profile_name] = copy.deepcopy(colors)
                imported.append(profile_name)
        if imported:
            _ng_save_profiles(self._ng_profiles)
            self._ng_refresh_profile_list()
        return len(imported)

    def _ng_open_profile_dir(self):
        """Auto-import any new .ini profiles then open the Colors folder in Explorer."""
        n = self._ng_import_ini_files()
        if n:
            self._ng_status(f"Imported {n} profile(s).")

        dirs_to_scan = self._ng_colors_dirs()
        folder = next((d for d in dirs_to_scan if d.is_dir()), None) or _app_dir()
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            messagebox.showerror("Open Folder", str(e), parent=self)

    def _ng_refresh_profiles(self):
        """Scan Colors folders and import any new .ini profiles, then report."""
        n = self._ng_import_ini_files()
        if n:
            self._ng_status(f"↻ Imported {n} new profile(s).")
        else:
            self._ng_status("↻ No new profiles found.")

    def _ng_find_colors_dir(self) -> "Path | None":
        """Return the first existing Custom/Colors dir from the two known locations."""
        return next((d for d in self._ng_colors_dirs() if d.is_dir()), None)

    def _ng_colors_dirs(self) -> list:
        """Return [base/Custom/Colors, base/PlayerData/Custom/Colors] for the
        detected Clone Hero install base. Both paths are returned regardless of
        whether they exist — callers check .is_dir() themselves."""
        base = None
        for key in ("ch_default_install", "ch_install_dir"):
            d = self._cfg.get(key, "")
            if d and Path(d).is_dir():
                base = Path(d); break
        if base is None:
            dp = self._cfg.get("default_data_path", "")
            if dp and Path(dp).is_dir():
                base = Path(dp).parent
        if base is None:
            for inst in _read_installs():
                d = inst.get("directoryPath", "")
                if d and Path(d).is_dir():
                    base = Path(d); break
        # macOS fallback: Clone Hero stores Custom/ inside ~/Clone Hero/
        if base is None and _IS_MAC:
            mac_home = Path.home() / "Clone Hero"
            if mac_home.is_dir():
                base = mac_home
            else:
                base = mac_home          # return path even if not yet created
        if base is None:
            return []
        return [
            base / "Custom" / "Colors",
            base / "PlayerData" / "Custom" / "Colors",
        ]
    def _ng_auto_gradient(self):
        if self._ng_is_default():
            messagebox.showwarning("Read-Only",
                "Duplicate or create a new profile before applying a gradient.",
                parent=self); return
        tab    = self._ng_active_tab
        colors = self._ng_active_colors_data
        if tab == "drums":
            dlg = _NgAutoGradientDialog(self, colors.get("drums", {}), mode="drums")
        elif tab == "sixfret":
            dlg = _NgAutoGradientDialog(self, colors.get("sixfret", {}), mode="sixfret")
        else:
            dlg = _NgAutoGradientDialog(self, colors.get("guitar", {}), mode="guitar")
        if dlg.result is None: return
        for r in dlg.result:
            self._ng_apply_gradient_colors(r)

    def _ng_apply_gradient_colors(self, result: dict):
        section    = result["section"]
        lane_map   = result["lane_map"]
        categories = result["categories"]
        sec_data   = self._ng_active_colors_data.setdefault(section, {})
        for lane, hex_c in lane_map.items():
            if not hex_c: continue
            hex_c = hex_c.upper()
            for pfx in categories:
                key = f"{pfx}_{lane}"
                if key in sec_data:
                    sec_data[key] = hex_c
        self._ng_profiles[self._ng_active_name] = copy.deepcopy(self._ng_active_colors_data)
        _ng_save_profiles(self._ng_profiles)
        self._ng_refresh_note_cards()
        self._ng_status("Auto gradient applied ✦")

    # ══════════════════════════════════════════════════════════════════════════
    #  PAGE 4 — BAD SONGS CLEANER
    # ══════════════════════════════════════════════════════════════════════════
