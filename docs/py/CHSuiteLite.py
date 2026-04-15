"""
CHSuite Lite  by JURMR
======================
Browser-based (Pyodide) version of CHSuite.

Exposed functions (called from JavaScript):
  generate_name(params_json)        -> result dict as JSON string
  generate_notes_ini(colors_json)   -> .ini file content as string
  process_menu(asset_bytes, image_bytes, asset_name) -> modified asset bytes
"""

import re
import json
import copy
import colorsys

# ── Color helpers ─────────────────────────────────────────────────────────────

def _hex_to_rgb_f(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def _rgb_f_to_hex(rgb: tuple) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        min(255, max(0, int(round(rgb[0] * 255)))),
        min(255, max(0, int(round(rgb[1] * 255)))),
        min(255, max(0, int(round(rgb[2] * 255))))
    )

def _interpolate_colors(hex_colors: list, steps: int) -> list:
    rgb_colors = [_hex_to_rgb_f(c) for c in hex_colors if c]
    if len(rgb_colors) < 2:
        raise ValueError("At least a start and end color are required.")
    segments = len(rgb_colors) - 1
    steps_per_seg = steps // segments
    extra = steps % segments
    result = []
    for i in range(segments):
        start = rgb_colors[i]; end = rgb_colors[i + 1]
        cur = steps_per_seg + (1 if i < extra else 0)
        for j in range(cur):
            t = j / max(cur - 1, 1)
            r = start[0] + (end[0] - start[0]) * t
            g = start[1] + (end[1] - start[1]) * t
            b = start[2] + (end[2] - start[2]) * t
            result.append(_rgb_f_to_hex((r, g, b)))
    return result[:steps]

# ── Name Generator ────────────────────────────────────────────────────────────

def _generate_gradient_name(name, colors, bold=False, italic=False,
                              underline=False, strike=False,
                              size=None, spacing=None):
    if len(name) == 0:
        return "", []
    gradient = _interpolate_colors(colors, len(name))
    segments = [f"<color={c}>{ch}</color>" for c, ch in zip(gradient, name)]
    styled = "".join(segments)
    if bold:      styled = f"<b>{styled}</b>"
    if italic:    styled = f"<i>{styled}</i>"
    if underline: styled = f"<u>{styled}</u>"
    if strike:    styled = f"<s>{styled}</s>"
    if size:      styled = f"<size={size}>{styled}</size>"
    if spacing:   styled = f"<cspace={spacing}>{styled}</cspace>"
    return styled, gradient

def _generate_individual_name(letters_data, global_size=None, global_spacing=None):
    segments = []; colors = []
    for ld in letters_data:
        char = ld["char"]; color = ld["color"]
        if not color.startswith("#"): color = "#" + color
        sc = f"<color={color}>{char}</color>"
        if ld.get("bold"):      sc = f"<b>{sc}</b>"
        if ld.get("italic"):    sc = f"<i>{sc}</i>"
        if ld.get("underline"): sc = f"<u>{sc}</u>"
        if ld.get("strike"):    sc = f"<s>{sc}</s>"
        segments.append(sc); colors.append(color)
    result = "".join(segments)
    if global_size:    result = f"<size={global_size}>{result}</size>"
    if global_spacing: result = f"<cspace={global_spacing}>{result}</cspace>"
    return result, colors

def generate_name(params_json: str) -> str:
    """
    params_json: JSON string with keys:
      mode: "gradient" | "individual"
      For gradient:
        name, colors (list of hex), bold, italic, underline, strike, size, spacing
      For individual:
        letters (list of {char, color, bold, italic, underline, strike}),
        global_size, global_spacing
    Returns JSON: {result, gradient, error}
    """
    try:
        p = json.loads(params_json)
        mode = p.get("mode", "gradient")
        if mode == "gradient":
            name = p.get("name", "")
            colors = p.get("colors", ["#FF0000", "#0000FF"])
            if len(name) == 0:
                return json.dumps({"error": "Name cannot be empty"})
            if len(colors) < 2:
                return json.dumps({"error": "At least 2 colors required"})
            result, gradient = _generate_gradient_name(
                name, colors,
                bold=p.get("bold", False),
                italic=p.get("italic", False),
                underline=p.get("underline", False),
                strike=p.get("strike", False),
                size=p.get("size") or None,
                spacing=p.get("spacing") or None,
            )
            return json.dumps({"result": result, "gradient": gradient})
        else:
            letters = p.get("letters", [])
            if not letters:
                return json.dumps({"error": "No letters provided"})
            result, colors = _generate_individual_name(
                letters,
                global_size=p.get("global_size") or None,
                global_spacing=p.get("global_spacing") or None,
            )
            return json.dumps({"result": result, "gradient": colors})
    except Exception as e:
        return json.dumps({"error": str(e)})

# ── Note Color INI Generator ───────────────────────────────────────────────────

_SECTION_ORDER = ["sixfret", "drums", "other", "guitar"]

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
        "note_kick":"#FF4600","note_anim_kick":"#FFFF00",
        "note_kick_sp_active":"#009178","note_kick_sp_phrase":"#FF4600",
        "note_kick_sp_phrase_active":"#FFFFFF",
        "cym_green":"#0CFF0C","cym_red":"#FF4663","cym_yellow":"#FFE531","cym_blue":"#1D63FF",
        "cym_anim_green":"#A5FF7B","cym_anim_red":"#FF8B8B",
        "cym_anim_yellow":"#FFEF5B","cym_anim_blue":"#609EFF",
        "cym_sp_active":"#7CFFD6","cym_sp_phrase":"#7CFFD6","cym_sp_phrase_active":"#7CFFD6",
        "tom_green":"#00FF00","tom_red":"#FF0000","tom_yellow":"#FFFF00","tom_blue":"#0089FF",
        "tom_anim_green":"#19FF19","tom_anim_red":"#FF2F2F",
        "tom_anim_yellow":"#FFFF26","tom_anim_blue":"#2685FF",
        "tom_sp_active":"#00FFFF","tom_sp_phrase":"#00FFFF","tom_sp_phrase_active":"#00FFFF",
    },
    "sixfret": {
        "sf_note_hopo":"#00FFFF",
        "sf_note_white_right":"#FFFFFF","sf_note_white_mid":"#FFFFFF","sf_note_white_left":"#FFFFFF",
        "sf_note_black_right":"#3F3F3F","sf_note_black_mid":"#3F3F3F","sf_note_black_left":"#3F3F3F",
        "sf_note_open":"#FFFFFF",
        "sf_note_sp_active":"#00FFFF","sf_note_sp_phrase":"#00FFFF","sf_note_sp_phrase_active":"#00FFFF",
        "sf_sustain_right":"#FFFFFF","sf_sustain_mid":"#FFFFFF","sf_sustain_left":"#FFFFFF",
        "sf_sustain_open":"#FFFFFF",
        "sf_sustain_sp_active":"#00FFFF","sf_sustain_sp_phrase":"#00FFFF","sf_sustain_sp_phrase_active":"#00FFFF",
        "sf_striker_base_white_right":"#FFFFFF","sf_striker_base_white_mid":"#FFFFFF",
        "sf_striker_base_white_left":"#FFFFFF","sf_striker_base_black_right":"#3F3F3F",
        "sf_striker_base_black_mid":"#3F3F3F","sf_striker_base_black_left":"#3F3F3F",
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

def get_default_colors() -> str:
    """Return default color dict as JSON."""
    return json.dumps(copy.deepcopy(_NG_DEFAULT_COLORS))

def generate_notes_ini(colors_json: str) -> str:
    """
    colors_json: JSON string of {section: {key: hex_value, ...}, ...}
    Returns: .ini file content as a string
    """
    try:
        colors = json.loads(colors_json)
        lines = []
        for section in _SECTION_ORDER:
            if section not in colors:
                continue
            lines.append(f"[{section}]")
            for key, val in colors[section].items():
                lines.append(f"{key} = {val}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"; Error generating INI: {e}"

def parse_notes_ini(ini_text: str) -> str:
    """
    Parse a Colors.ini file content and return JSON of colors dict.
    """
    try:
        result = {}
        current_section = None
        for line in ini_text.splitlines():
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].lower()
                result[current_section] = {}
            elif "=" in line and current_section:
                key, _, val = line.partition("=")
                key = key.strip().lower()
                val = val.strip().upper()
                if val:
                    result[current_section][key] = val
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})

# ── Menu Changer (UnityPy-based, Pyodide-compatible) ─────────────────────────

def process_menu(asset_bytes: bytes, image_bytes: bytes, asset_name: str) -> bytes:
    """
    Replace a Texture2D named `asset_name` inside a Unity .assets file.
    asset_bytes: raw bytes of the .assets file
    image_bytes: raw PNG/JPG bytes of the replacement image
    asset_name:  name of the texture to replace (e.g. "MainMenuBackground")
    Returns: modified .assets file bytes, or raises on error.
    """
    try:
        import UnityPy
        from PIL import Image
        import io

        env = UnityPy.load(asset_bytes)
        replaced = False
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                data = obj.read()
                name = getattr(data, "m_Name", None) or getattr(data, "name", None)
                if name and name.lower() == asset_name.lower():
                    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
                    data.image = img
                    data.save()
                    replaced = True
                    break

        if not replaced:
            raise ValueError(f"Texture '{asset_name}' not found in asset file.")

        out = io.BytesIO()
        for fpath, data in env.file.files.items():
            out.write(data)
        # Use UnityPy's proper serialization
        out_buf = io.BytesIO()
        env.file.save(out_buf)
        return out_buf.getvalue()
    except Exception as e:
        raise RuntimeError(f"process_menu failed: {e}")

def list_textures(asset_bytes: bytes) -> str:
    """List all Texture2D names in a .assets file. Returns JSON list."""
    try:
        import UnityPy
        env = UnityPy.load(asset_bytes)
        names = []
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                try:
                    data = obj.read()
                    name = getattr(data, "m_Name", None) or getattr(data, "name", None)
                    if name:
                        names.append(name)
                except Exception:
                    pass
        return json.dumps(names)
    except Exception as e:
        return json.dumps({"error": str(e)})
