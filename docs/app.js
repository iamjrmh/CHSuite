/* ============================================================
   CHSuiteLiteLite Lite  —  app.js
   Browser-native implementation (no Python)
   ============================================================ */

"use strict";

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  mc: { assetBytes: null, assetName: null, imgBytes: null, imgName: null, textures: [] },
  ng: { mode: "gradient" },
  notegen: { section: "guitar", colors: null },
};

// ── Supported Backgrounds (from Instructions.txt) ─────────────────────────────
const SUPPORTED_BACKGROUNDS = [
  { name: "Black", minWidth: 1920, minHeight: 1080, exactWidth: 1920, exactHeight: 1080, sourceFile: "sharedassets1.assets", editable: false },
  { name: "Spray", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Pastel Burst", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Groovy", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Grains", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Blue Rays", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Alien", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Autumn", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Light", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Dark", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Classic", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Surfer", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "SurferAlt", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Rainbow", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Animated", minWidth: 1920, minHeight: 1080, sourceFile: "sharedassets1.assets", editable: true },
  { name: "Logo_Transparent", minWidth: 2030, minHeight: 1328, exactWidth: 2030, exactHeight: 1328, sourceFile: "globalgamemanagers.assets", editable: true },
];

// ── Default Note Colors (from CHSuiteLiteLiteLite.py) ───────────────────────────────
const DEFAULT_COLORS = {
  guitar: {
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
  drums: {
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
  sixfret: {
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
  other: {
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
};

// ── Navigation ─────────────────────────────────────────────────────────────────
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${tab}`)?.classList.add("active");
  });
});

document.querySelectorAll("[data-goto]").forEach(el => {
  el.addEventListener("click", e => {
    e.preventDefault();
    const target = el.dataset.goto;
    const btn = document.querySelector(`.nav-btn[data-tab="${target}"]`);
    if (btn) btn.click();
  });
});

// ── Toast ──────────────────────────────────────────────────────────────────────
let _toastTimer;
function toast(msg, duration = 2500) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), duration);
}

// ── Drop zone helper ───────────────────────────────────────────────────────────
function setupDropZone(dropEl, inputEl, pillEl, accept, onFile, onError) {
  dropEl.addEventListener("click", () => inputEl.click());
  dropEl.addEventListener("dragover", e => { e.preventDefault(); dropEl.classList.add("drag-over"); });
  dropEl.addEventListener("dragleave", () => dropEl.classList.remove("drag-over"));
  dropEl.addEventListener("drop", e => {
    e.preventDefault(); dropEl.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });
  inputEl.addEventListener("change", () => {
    if (inputEl.files[0]) handleFile(inputEl.files[0]);
  });

  function handleFile(file) {
    // Validate file type
    if (accept && !accept.test(file.name)) {
      if (onError) onError(file.name);
      return;
    }
    if (pillEl) {
      pillEl.innerHTML = `<svg viewBox="0 0 12 12" fill="none"><path d="M2 6h8M6 2v8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" transform="rotate(45 6 6)"/></svg> ${file.name}`;
      pillEl.classList.remove("hidden");
    }
    onFile(file);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// NAME GEN (JavaScript Implementation)
// ══════════════════════════════════════════════════════════════════════════════

function hexToRgb(hex) {
  const h = hex.replace("#", "");
  if (h.length === 3) {
    return [parseInt(h[0]+h[0], 16) / 255, parseInt(h[1]+h[1], 16) / 255, parseInt(h[2]+h[2], 16) / 255];
  }
  return [parseInt(h.substr(0,2), 16) / 255, parseInt(h.substr(2,2), 16) / 255, parseInt(h.substr(4,2), 16) / 255];
}

function rgbToHex(rgb) {
  return "#" + rgb.map(c => {
    const v = Math.min(255, Math.max(0, Math.round(c * 255)));
    return v.toString(16).padStart(2, "0");
  }).join("").toUpperCase();
}

function interpolateColors(hexColors, steps) {
  const rgbColors = hexColors.map(hexToRgb);
  if (rgbColors.length < 2) return hexColors;

  const segments = rgbColors.length - 1;
  const stepsPerSeg = Math.floor(steps / segments);
  const extra = steps % segments;
  const result = [];

  for (let i = 0; i < segments; i++) {
    const start = rgbColors[i];
    const end = rgbColors[i + 1];
    const cur = stepsPerSeg + (i < extra ? 1 : 0);
    for (let j = 0; j < cur; j++) {
      const t = j / Math.max(cur - 1, 1);
      const r = start[0] + (end[0] - start[0]) * t;
      const g = start[1] + (end[1] - start[1]) * t;
      const b = start[2] + (end[2] - start[2]) * t;
      result.push(rgbToHex([r, g, b]));
    }
  }
  return result.slice(0, steps);
}

function generateGradientName(name, colors, bold, italic, underline, strike, size, spacing) {
  const gradient = interpolateColors(colors, name.length);
  let segments = gradient.map((c, i) => `<color=${c}>${name[i]}</color>`);
  let styled = segments.join("");
  if (bold) styled = `<b>${styled}</b>`;
  if (italic) styled = `<i>${styled}</i>`;
  if (underline) styled = `<u>${styled}</u>`;
  if (strike) styled = `<s>${styled}</s>`;
  if (size) styled = `<size=${size}>${styled}</size>`;
  if (spacing) styled = `<cspace=${spacing}>${styled}</cspace>`;
  return { result: styled, gradient };
}

function generateIndividualName(letters, globalSize, globalSpacing) {
  let segments = [];
  let colors = [];
  letters.forEach(ld => {
    const char = ld.char;
    let color = ld.color;
    if (!color.startsWith("#")) color = "#" + color;
    let sc = `<color=${color}>${char}</color>`;
    if (ld.bold) sc = `<b>${sc}</b>`;
    if (ld.italic) sc = `<i>${sc}</i>`;
    if (ld.underline) sc = `<u>${sc}</u>`;
    if (ld.strike) sc = `<s>${sc}</s>`;
    segments.push(sc);
    colors.push(color);
  });
  let result = segments.join("");
  if (globalSize) result = `<size=${globalSize}>${result}</size>`;
  if (globalSpacing) result = `<cspace=${globalSpacing}>${result}</cspace>`;
  return { result, gradient: colors };
}

// Mode toggle
document.getElementById("ng-mode-toggle").querySelectorAll(".toggle-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#ng-mode-toggle .toggle-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.ng.mode = btn.dataset.mode;
    document.getElementById("ng-gradient-panel").style.display = state.ng.mode === "gradient" ? "" : "none";
    document.getElementById("ng-individual-panel").style.display = state.ng.mode === "individual" ? "" : "none";
  });
});

// Gradient color stops
function colorStopHTML(idx, hex) {
  return `<div class="color-stop" data-idx="${idx}">
    <input type="color" value="${hex}" class="color-swatch" />
    <span class="color-hex">${hex.toUpperCase()}</span>
    <button class="color-remove" title="Remove">×</button>
  </div>`;
}

function attachColorStopListeners(stopEl) {
  const swatch = stopEl.querySelector(".color-swatch");
  const hexSpan = stopEl.querySelector(".color-hex");
  const removeBtn = stopEl.querySelector(".color-remove");

  swatch.addEventListener("input", () => {
    hexSpan.textContent = swatch.value.toUpperCase();
  });
  removeBtn.addEventListener("click", () => {
    const list = document.getElementById("ng-color-stops");
    if (list.children.length > 2) {
      stopEl.remove();
    } else {
      toast("At least 2 color stops required.");
    }
  });
}

document.querySelectorAll(".color-stop").forEach(el => attachColorStopListeners(el));

document.getElementById("ng-add-stop").addEventListener("click", () => {
  const list = document.getElementById("ng-color-stops");
  if (list.children.length >= 8) { toast("Maximum 8 color stops."); return; }
  const newEl = document.createElement("div");
  newEl.innerHTML = colorStopHTML(list.children.length, "#ffffff");
  const stop = newEl.firstElementChild;
  list.appendChild(stop);
  attachColorStopListeners(stop);
});

// Per-letter grid
document.getElementById("ng-indiv-name").addEventListener("input", e => {
  buildLetterGrid(e.target.value);
});

function buildLetterGrid(name) {
  const grid = document.getElementById("ng-letter-grid");
  grid.innerHTML = "";
  const colors = ["#FF0066","#FF6600","#FFCC00","#00CC66","#0066FF","#9900FF","#FF3399","#00CCFF"];
  name.split("").forEach((char, i) => {
    const hex = colors[i % colors.length];
    const cell = document.createElement("div");
    cell.className = "letter-cell";
    cell.dataset.char = char;
    cell.innerHTML = `
      <span class="letter-cell-char">${char === " " ? "·" : char}</span>
      <input type="color" value="${hex}" />
      <span class="letter-cell-hex">${hex}</span>
    `;
    const swatch = cell.querySelector("input[type=color]");
    const hexSpan = cell.querySelector(".letter-cell-hex");
    swatch.addEventListener("input", () => { hexSpan.textContent = swatch.value.toUpperCase(); });
    grid.appendChild(cell);
  });
}

// Generate button
document.getElementById("ng-generate-btn").addEventListener("click", runNameGen);

function runNameGen() {
  try {
    let result;
    if (state.ng.mode === "gradient") {
      const name = document.getElementById("ng-name").value.trim();
      if (!name) { toast("Enter a name first."); return; }
      const stops = Array.from(document.querySelectorAll("#ng-color-stops .color-stop"));
      const colors = stops.map(s => s.querySelector(".color-swatch").value);
      if (colors.length < 2) { toast("At least 2 colors required."); return; }

      result = generateGradientName(
        name, colors,
        document.getElementById("ng-bold").checked,
        document.getElementById("ng-italic").checked,
        document.getElementById("ng-underline").checked,
        document.getElementById("ng-strike").checked,
        document.getElementById("ng-size").value || null,
        document.getElementById("ng-spacing").value || null
      );
    } else {
      const indivName = document.getElementById("ng-indiv-name").value;
      if (!indivName) { toast("Enter a name first."); return; }
      const letters = Array.from(document.querySelectorAll("#ng-letter-grid .letter-cell")).map(cell => ({
        char: cell.dataset.char,
        color: cell.querySelector("input[type=color]").value,
        bold: false, italic: false, underline: false, strike: false,
      }));
      result = generateIndividualName(
        letters,
        document.getElementById("ng-indiv-size").value || null,
        document.getElementById("ng-indiv-spacing").value || null
      );
    }

    // Display
    document.getElementById("ng-output").style.display = "";
    document.getElementById("ng-result-code").textContent = result.result;
    renderNamePreview(result.result, result.gradient || []);
  } catch (err) {
    console.error(err);
    toast("⚠ Generation error: " + err.message, 4000);
  }
}

function renderNamePreview(taggedStr, gradient) {
  const bar = document.getElementById("ng-preview-bar");

  function snapshot(s) {
    return {
      color: s.color.length ? s.color[s.color.length - 1] : null,
      bold: s.bold > 0,
      italic: s.italic > 0,
      underline: s.underline > 0,
      strike: s.strike > 0,
      size: s.size.length ? s.size[s.size.length - 1] : null,
      cspace: s.cspace.length ? s.cspace[s.cspace.length - 1] : null,
    };
  }

  // Parse the Unity rich-text tag string into a list of character tokens,
  // each carrying its own style state.
  const tokens = [];
  const styleStack = { color: [], bold: 0, italic: 0, underline: 0, strike: 0, size: [], cspace: [] };

  let i = 0;
  const str = taggedStr.replace(/[\x00-\x1f]/g, "");

  while (i < str.length) {
    if (str[i] === "<") {
      const closeIdx = str.indexOf(">", i);
      if (closeIdx === -1) { tokens.push({ ch: str[i], style: snapshot(styleStack) }); i++; continue; }
      const tag = str.slice(i + 1, closeIdx);
      i = closeIdx + 1;

      if (tag.startsWith("/")) {
        const tagName = tag.slice(1).toLowerCase();
        if (tagName === "b") styleStack.bold = Math.max(0, styleStack.bold - 1);
        else if (tagName === "i") styleStack.italic = Math.max(0, styleStack.italic - 1);
        else if (tagName === "u") styleStack.underline = Math.max(0, styleStack.underline - 1);
        else if (tagName === "s") styleStack.strike = Math.max(0, styleStack.strike - 1);
        else if (tagName === "color") styleStack.color.pop();
        else if (tagName === "size") styleStack.size.pop();
        else if (tagName === "cspace") styleStack.cspace.pop();
      } else if (tag === "b") { styleStack.bold++; }
        else if (tag === "i") { styleStack.italic++; }
        else if (tag === "u") { styleStack.underline++; }
        else if (tag === "s") { styleStack.strike++; }
        else if (tag.startsWith("color=")) { styleStack.color.push(tag.slice(6)); }
        else if (tag.startsWith("size=")) { styleStack.size.push(parseFloat(tag.slice(5))); }
        else if (tag.startsWith("cspace=")) { styleStack.cspace.push(parseFloat(tag.slice(7))); }
    } else {
      tokens.push({ ch: str[i], style: snapshot(styleStack) });
      i++;
    }
  }

  // If no per-character colors from tags, fall back to gradient array
  const plainChars = tokens.map(t => t.ch);
  const fallbackColors = gradient.length >= plainChars.length
    ? gradient
    : plainChars.map((_, idx) => `hsl(${idx * 40 % 360},100%,65%)`);

  bar.innerHTML = tokens.map((token, idx) => {
    const { ch, style } = token;
    const color = style.color || fallbackColors[idx] || "#fff";

    const cssProps = [`color:${color}`];
    if (style.bold) cssProps.push("font-weight:bold");
    if (style.italic) cssProps.push("font-style:italic");

    const textDecors = [];
    if (style.underline) textDecors.push("underline");
    if (style.strike) textDecors.push("line-through");
    if (textDecors.length) cssProps.push(`text-decoration:${textDecors.join(" ")}`);

    if (style.size) cssProps.push(`font-size:${style.size}px`);
    if (style.cspace != null) cssProps.push(`letter-spacing:${style.cspace}px`);

    const display = ch === " " ? "&nbsp;" : ch;
    return `<span style="${cssProps.join(";")}">${display}</span>`;
  }).join("");
}

// Copy button
document.getElementById("ng-copy-btn").addEventListener("click", () => {
  const code = document.getElementById("ng-result-code").textContent;
  navigator.clipboard.writeText(code).then(() => {
    const btn = document.getElementById("ng-copy-btn");
    btn.classList.add("copied");
    btn.innerHTML = `<svg viewBox="0 0 20 20" fill="none" width="14" height="14"><path d="M4 10l4 4 8-8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg> Copied!`;
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.innerHTML = `<svg viewBox="0 0 20 20" fill="none" width="14" height="14"><rect x="6" y="6" width="10" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M4 14H3a1 1 0 01-1-1V3a1 1 0 011-1h10a1 1 0 011 1v1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Copy`;
    }, 2000);
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// NOTE GEN (JavaScript Implementation)
// ══════════════════════════════════════════════════════════════════════════════

// Clone-Hero-style preview (matches updated /Example: 3 stacked canvases + composite ops)
const NOTE_PREVIEW_SPRITES = {
  base: "Images/note_base.png",
  body: "Images/note_body.png",
  light: "Images/note_light.png",
};

const NOTE_W = 95;
const NOTE_H = 50;

let _notePreviewInjectedCss = false;
let _noteImgsLoaded = false;
let _noteImgBase = null;
let _noteImgBody = null;
let _noteImgLight = null;

function ensureNotePreviewCss() {
  if (_notePreviewInjectedCss) return;
  _notePreviewInjectedCss = true;
  const style = document.createElement("style");
  style.textContent = `
    .ch-notes-preview {
      display: flex;
      gap: 10px;
      align-items: center;
      justify-content: center;
      padding: 6px 0;
      background: transparent;
      max-width: 100%;
      overflow-x: auto;
    }
    .ch-note-group {
      position: relative;
      width: ${NOTE_W}px;
      height: ${NOTE_H}px;
      flex: 0 0 auto;
      pointer-events: none;
    }
    .ch-note-canvas {
      position: absolute;
      left: 0;
      top: 0;
      width: ${NOTE_W}px;
      height: ${NOTE_H}px;
    }
    .ch-note-canvas.body { z-index: 1; }
    .ch-note-canvas.base { z-index: 2; }
    .ch-note-canvas.light { z-index: 3; }
  `;
  document.head.appendChild(style);
}

function _createImage(src) {
  const img = new Image();
  img.src = src;
  return img;
}

function loadNotePreviewImages() {
  if (_noteImgsLoaded) return Promise.resolve();
  if (_noteImgBase && _noteImgBody && _noteImgLight) {
    return new Promise(resolve => {
      let loaded = 0;
      const done = () => {
        loaded++;
        if (loaded === 3) {
          _noteImgsLoaded = true;
          resolve();
        }
      };
      _noteImgBase.onload = done;
      _noteImgBody.onload = done;
      _noteImgLight.onload = done;
    });
  }

  return new Promise(resolve => {
    let loaded = 0;
    const done = () => {
      loaded++;
      if (loaded === 3) {
        _noteImgsLoaded = true;
        resolve();
      }
    };

    _noteImgBase = _createImage(NOTE_PREVIEW_SPRITES.base);
    _noteImgBody = _createImage(NOTE_PREVIEW_SPRITES.body);
    _noteImgLight = _createImage(NOTE_PREVIEW_SPRITES.light);

    _noteImgBase.onload = done;
    _noteImgBody.onload = done;
    _noteImgLight.onload = done;
  });
}

function tintNoteBody(canvas, img, color) {
  const ctx = canvas.getContext("2d");
  const tmpCanvas = document.createElement("canvas");
  tmpCanvas.width = NOTE_W;
  tmpCanvas.height = NOTE_H;
  const tmpCtx = tmpCanvas.getContext("2d");

  ctx.clearRect(0, 0, NOTE_W, NOTE_H);
  ctx.drawImage(img, 0, 0);

  tmpCtx.drawImage(img, 0, 0);
  tmpCtx.globalCompositeOperation = "source-atop";
  tmpCtx.fillStyle = color;
  tmpCtx.fillRect(0, 0, NOTE_W, NOTE_H);

  ctx.globalCompositeOperation = "multiply";
  ctx.drawImage(tmpCanvas, 0, 0);
  ctx.globalCompositeOperation = "source-over";
}

function tintNoteLight(canvas, img, color) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, NOTE_W, NOTE_H);
  ctx.drawImage(img, 0, 0);
  ctx.globalCompositeOperation = "source-in";
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, NOTE_W, NOTE_H);
  ctx.globalCompositeOperation = "source-over";
}

function drawNoteBase(canvas, img) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, NOTE_W, NOTE_H);
  ctx.drawImage(img, 0, 0);
}

function initNoteDomPreview() {
  ensureNotePreviewCss();

  const wrapper = document.getElementById("note-preview");
  if (!wrapper) return;

  const legacyCanvas = document.getElementById("note-preview-canvas");
  if (legacyCanvas) legacyCanvas.style.display = "none";

  let preview = wrapper.querySelector(".ch-notes-preview");
  if (!preview) {
    preview = document.createElement("div");
    preview.className = "ch-notes-preview";
    wrapper.prepend(preview);
  }

  const order = ["note_green", "note_red", "note_yellow", "note_blue", "note_orange"];
  const labels = { note_green:"Green", note_red:"Red", note_yellow:"Yellow", note_blue:"Blue", note_orange:"Orange" };
  const defaults = { note_green:"#00FF00", note_red:"#FF0000", note_yellow:"#FFFF00", note_blue:"#0089FF", note_orange:"#FFB300" };

  preview.innerHTML = order.map(k => `
    <div class="ch-note-group" data-note-key="${k}">
      <canvas class="ch-note-canvas light" data-layer="light" width="${NOTE_W}" height="${NOTE_H}"></canvas>
      <canvas class="ch-note-canvas base"  data-layer="base"  width="${NOTE_W}" height="${NOTE_H}"></canvas>
      <canvas class="ch-note-canvas body"  data-layer="body"  width="${NOTE_W}" height="${NOTE_H}"></canvas>
      <span class="ch-note-label">${labels[k]}</span>
      <button class="ch-note-swatch" data-note-key="${k}" style="background:${defaults[k]}" title="Pick colour for ${labels[k]}"></button>
    </div>
  `).join("");

  // Wire swatch buttons to custom colour picker
  preview.querySelectorAll(".ch-note-swatch").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const key = btn.dataset.noteKey;
      const hiddenPicker = document.querySelector(`.note-color-picker[data-key="${key}"]`);
      const currentHex = hiddenPicker ? hiddenPicker.value : btn.style.background;
      ccpOpen(btn, currentHex, hex => {
        btn.style.background = hex;
        if (hiddenPicker) { hiddenPicker.value = hex; }
        updateNoteDomPreviewFromPickers();
      });
    });
  });

  loadNotePreviewImages().then(() => {
    preview.querySelectorAll('.ch-note-group canvas[data-layer="base"]').forEach(c => drawNoteBase(c, _noteImgBase));
    updateNoteDomPreviewFromPickers();
  });
}

function updateNoteDomPreviewFromPickers() {
  const root = document.querySelector("#note-preview .ch-notes-preview");
  if (!root || !_noteImgsLoaded) return;

  const pickers = Array.from(document.querySelectorAll(".note-color-picker"));
  for (const picker of pickers) {
    const key = picker.dataset.key;
    const group = root.querySelector(`.ch-note-group[data-note-key="${key}"]`);
    if (!group) continue;

    const bodyCanvas = group.querySelector('canvas[data-layer="body"]');
    const lightCanvas = group.querySelector('canvas[data-layer="light"]');
    const bodyColor = picker.value;

    if (bodyCanvas) tintNoteBody(bodyCanvas, _noteImgBody, bodyColor);
    if (lightCanvas) tintNoteLight(lightCanvas, _noteImgLight, bodyColor);

    // Keep swatch button in sync
    const swatch = group.querySelector(".ch-note-swatch");
    if (swatch) swatch.style.background = bodyColor;

    if (state.notegen.colors?.guitar) {
      state.notegen.colors.guitar[key] = bodyColor.toUpperCase();
    }
  }
}

function syncNotePreviewPickersFromState() {
  const g = state.notegen.colors?.guitar;
  if (!g) return;
  document.querySelectorAll(".note-color-picker").forEach(picker => {
    const key = picker.dataset.key;
    if (key && g[key]) picker.value = g[key];
  });
  updateNoteDomPreviewFromPickers();
}

// Set up color picker listeners for all 5 notes
document.querySelectorAll(".note-color-picker").forEach(picker => {
  picker.addEventListener("input", () => {
    updateNoteDomPreviewFromPickers();
  });
});

// Initialize CHNoteGen preview
initNoteDomPreview();

const _NG_FRIENDLY = {
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
  "cym_green":"Cymbal · Green","cym_red":"Cymbal · Red","cym_yellow":"Cymbal · Yellow","cym_blue":"Cymbal · Blue",
  "cym_anim_green":"Cymbal Anim · Green","cym_anim_red":"Cymbal Anim · Red",
  "cym_anim_yellow":"Cymbal Anim · Yellow","cym_anim_blue":"Cymbal Anim · Blue",
  "cym_sp_active":"Cymbal · SP Active","cym_sp_phrase":"Cymbal · SP Phrase","cym_sp_phrase_active":"Cymbal · SP Phrase Active",
  "tom_green":"Tom · Green","tom_red":"Tom · Red","tom_yellow":"Tom · Yellow","tom_blue":"Tom · Blue",
  "tom_anim_green":"Tom Anim · Green","tom_anim_red":"Tom Anim · Red",
  "tom_anim_yellow":"Tom Anim · Yellow","tom_anim_blue":"Tom Anim · Blue",
  "tom_sp_active":"Tom · SP Active","tom_sp_phrase":"Tom · SP Phrase","tom_sp_phrase_active":"Tom · SP Phrase Active",
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
  "sf_note_white_left":"SF Note · White Left","sf_note_white_mid":"SF Note · White Mid","sf_note_white_right":"SF Note · White Right",
  "sf_note_black_left":"SF Note · Black Left","sf_note_black_mid":"SF Note · Black Mid","sf_note_black_right":"SF Note · Black Right",
  "sf_note_sp_active":"SF Note · SP Active","sf_note_sp_phrase":"SF Note · SP Phrase","sf_note_sp_phrase_active":"SF Note · SP Phrase Active",
  "sf_sustain_open":"SF Sustain · Open","sf_sustain_left":"SF Sustain · Left","sf_sustain_mid":"SF Sustain · Mid","sf_sustain_right":"SF Sustain · Right",
  "sf_sustain_sp_active":"SF Sustain · SP Active","sf_sustain_sp_phrase":"SF Sustain · SP Phrase","sf_sustain_sp_phrase_active":"SF Sustain · SP Phrase Active",
  "sf_striker_base_white_left":"SF Strikeline Base · White Left","sf_striker_base_white_mid":"SF Strikeline Base · White Mid",
  "sf_striker_base_white_right":"SF Strikeline Base · White Right",
  "sf_striker_base_black_left":"SF Strikeline Base · Black Left","sf_striker_base_black_mid":"SF Strikeline Base · Black Mid",
  "sf_striker_base_black_right":"SF Strikeline Base · Black Right",
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
  "leaderboard_first":"Leaderboard · 1st","leaderboard_second":"Leaderboard · 2nd","leaderboard_third":"Leaderboard · 3rd",
  "sp_gain_lightning":"SP Gain Lightning","sp_gain_lightning_secondary":"SP Gain Lightning 2",
};

function friendlyName(key) {
  return _NG_FRIENDLY[key] || key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// Section tabs
document.querySelectorAll(".section-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".section-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    state.notegen.section = tab.dataset.section;
    renderColorEditor();
  });
});

function renderColorEditor() {
  const editor = document.getElementById("ng-color-editor");
  const section = state.notegen.section;
  const colors = state.notegen.colors;
  if (!colors || !colors[section]) { editor.innerHTML = "<p style='color:var(--text-dim);font-size:.85rem'>Loading…</p>"; return; }

  const sectionColors = colors[section];
  editor.innerHTML = "";

  const grouped = groupKeys(Object.keys(sectionColors));
  grouped.forEach(group => {
    const groupEl = document.createElement("div");
    groupEl.className = "color-group";
    if (group.label) {
      const title = document.createElement("div");
      title.className = "color-group-title";
      title.textContent = group.label;
      groupEl.appendChild(title);
    }
    const rows = document.createElement("div");
    rows.className = "color-rows";
    group.keys.forEach(key => {
      const hex = (sectionColors[key] || "#FFFFFF").toUpperCase();
      const row = document.createElement("div");
      row.className = "color-row";
      row.innerHTML = `
        <input type="color" class="color-row-swatch" value="${hex}" data-key="${key}" />
        <span class="color-row-label">${friendlyName(key)}</span>
        <span class="color-row-hex">${hex}</span>
      `;
      const swatch = row.querySelector("input[type=color]");
      const hexSpan = row.querySelector(".color-row-hex");
      swatch.addEventListener("input", () => {
        const newHex = swatch.value.toUpperCase();
        hexSpan.textContent = newHex;
        state.notegen.colors[section][key] = newHex;
      });
      rows.appendChild(row);
    });
    groupEl.appendChild(rows);
    editor.appendChild(groupEl);
  });
}

function groupKeys(keys) {
  const groups = {};
  const order = [];
  keys.forEach(k => {
    const prefix = k.split("_").slice(0, 2).join("_");
    if (!groups[prefix]) { groups[prefix] = []; order.push(prefix); }
    groups[prefix].push(k);
  });
  const result = [];
  order.forEach(prefix => {
    const items = groups[prefix];
    const label = prefix.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    result.push({ label, keys: items });
  });
  return result;
}

// Parse INI
function parseIni(text) {
  const result = {};
  let currentSection = null;
  const lines = text.split(/\r?\n/);
  for (let line of lines) {
    line = line.trim();
    if (!line || line.startsWith(";")) continue;
    if (line.startsWith("[") && line.endsWith("]")) {
      currentSection = line.slice(1, -1).toLowerCase();
      result[currentSection] = {};
    } else if (currentSection && line.includes("=")) {
      const idx = line.indexOf("=");
      const key = line.substring(0, idx).trim().toLowerCase();
      const val = line.substring(idx + 1).trim().toUpperCase();
      if (val) result[currentSection][key] = val;
    }
  }
  return result;
}

// Generate INI
function generateIni(colors) {
  const sectionOrder = ["sixfret", "drums", "other", "guitar"];
  const lines = [];
  for (const section of sectionOrder) {
    if (!colors[section]) continue;
    lines.push(`[${section}]`);
    for (const [key, val] of Object.entries(colors[section])) {
      lines.push(`${key} = ${val}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

// Import INI
setupDropZone(
  document.getElementById("notegen-ini-drop"),
  document.getElementById("notegen-ini-input"),
  null, /\.ini$|\.txt$/,
  file => {
    const reader = new FileReader();
    reader.onload = e => {
      try {
        const parsed = parseIni(e.target.result);
        Object.keys(parsed).forEach(sec => {
          if (!state.notegen.colors[sec]) state.notegen.colors[sec] = {};
          Object.assign(state.notegen.colors[sec], parsed[sec]);
        });
        syncNotePreviewPickersFromState();
        toast("✓ INI imported.");
      } catch (err) {
        toast("⚠ Could not parse INI: " + err.message);
      }
    };
    reader.readAsText(file);
  }
);

// Export button
document.getElementById("ng-export-btn").addEventListener("click", () => {
  try {
    const iniContent = generateIni(state.notegen.colors);
    const blob = new Blob([iniContent], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "Colors.ini";
    a.click();
    toast("✓ Colors.ini exported!");
  } catch (err) {
    toast("⚠ Export failed: " + err.message, 4000);
  }
});

// Reset to defaults (button may be removed in simplified UI)
const _ngResetBtn = document.getElementById("ng-reset-btn");
if (_ngResetBtn) {
  _ngResetBtn.addEventListener("click", () => {
    state.notegen.colors = JSON.parse(JSON.stringify(DEFAULT_COLORS));
    syncNotePreviewPickersFromState();
    toast("Reset to defaults.");
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// MENU CHANGER (Server-Side Processing)
// ══════════════════════════════════════════════════════════════════════════════

const MC_BACKGROUNDS = [
  { name: "Spray", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Pastel Burst", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Groovy", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Grains", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Blue Rays", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Alien", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Autumn", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Light", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Dark", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Classic", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Surfer", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "SurferAlt", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Rainbow", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Animated", minWidth: 1920, minHeight: 1080, exactWidth: null, exactHeight: null },
  { name: "Logo_Transparent", minWidth: 2030, minHeight: 1328, exactWidth: 2030, exactHeight: 1328 },
];

// Check if new server-side UI elements exist
const _mcServerEnabled = !!document.getElementById("mc-background-select") && !!document.getElementById("mc-img-drop");

if (_mcServerEnabled) {
  // State for server-side processing
  const mcState = {
    background: null,
    imgBytes: null,
    imgName: null,
    imgUrl: null,
    workflowRunId: null,
    pollInterval: null,
  };

  // Elements
  const mcBgSelect = document.getElementById("mc-background-select");
  const mcBgInfo = document.getElementById("mc-bg-info");
  const mcBgInfoSize = mcBgInfo?.querySelector(".mc-bg-size");
  const mcImgDrop = document.getElementById("mc-img-drop");
  const mcImgInput = document.getElementById("mc-img-input");
  const mcImgPill = document.getElementById("mc-img-pill");
  const mcImgError = document.getElementById("mc-img-error");
  const mcPreviewRow = document.getElementById("mc-preview-row");
  const mcPreviewCanvas = document.getElementById("mc-preview-canvas");
  const mcPreviewHint = document.getElementById("mc-preview-hint");
  const mcProcessBtn = document.getElementById("mc-process-btn");
  const mcOutput = document.getElementById("mc-output");
  const mcStatus = document.getElementById("mc-status");
  const mcDownloadBtn = document.getElementById("mc-download-btn");
  const mcErrorMsg = document.getElementById("mc-error-msg");

  // Background selection
  mcBgSelect?.addEventListener("change", () => {
    const bgName = mcBgSelect.value;
    mcState.background = bgName;

    if (bgName && mcBgInfo) {
      const bg = MC_BACKGROUNDS.find(b => b.name === bgName);
      if (bg) {
        mcBgInfo.style.display = "";
        if (bg.exactWidth && bg.exactHeight) {
          mcBgInfoSize.textContent = `Required size: ${bg.exactWidth}×${bg.exactHeight} (exact)`;
        } else {
          mcBgInfoSize.textContent = `Minimum size: ${bg.minWidth}×${bg.minHeight}`;
        }
      }
    } else if (mcBgInfo) {
      mcBgInfo.style.display = "none";
    }

    updateMcButton();
  });

  // Image drop zone setup
  if (mcImgDrop && mcImgInput) {
    setupDropZone(
      mcImgDrop, mcImgInput, mcImgPill, /\.(png|jpg|jpeg)$/i,
      async file => {
        const buf = await file.arrayBuffer();
        mcState.imgBytes = new Uint8Array(buf);
        mcState.imgName = file.name;

        // Create a data URL for preview
        const blob = new Blob([mcState.imgBytes]);
        mcState.imgUrl = URL.createObjectURL(blob);

        if (mcImgError) mcImgError.style.display = "none";

        // Show preview
        showReplacementPreview();
        updateMcButton();
      },
      fileName => {
        if (mcImgError) {
          mcImgError.textContent = `Invalid file type. Only PNG/JPG allowed: ${fileName}`;
          mcImgError.style.display = "block";
        }
        toast("⚠ Only PNG/JPG files are allowed");
      }
    );
  }

  // Show replacement image preview
  function showReplacementPreview() {
    if (!mcState.imgUrl || !mcPreviewCanvas || !mcPreviewHint) return;

    const img = new Image();
    img.onload = () => {
      const ctx = mcPreviewCanvas.getContext("2d");
      const scale = Math.min(mcPreviewCanvas.width / img.width, mcPreviewCanvas.height / img.height);
      const w = img.width * scale;
      const h = img.height * scale;
      const x = (mcPreviewCanvas.width - w) / 2;
      const y = (mcPreviewCanvas.height - h) / 2;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, mcPreviewCanvas.width, mcPreviewCanvas.height);
      ctx.drawImage(img, x, y, w, h);
      mcPreviewHint.textContent = `Replacement: ${img.width}×${img.height}px`;
    };
    img.onerror = () => {
      mcPreviewHint.textContent = "Could not load preview";
    };
    img.src = mcState.imgUrl;

    if (mcPreviewRow) mcPreviewRow.style.display = "";
  }

  // Validate image size against selected background
  async function validateImageSize() {
    if (!mcState.imgBytes || !mcState.background) return true;

    const bg = MC_BACKGROUNDS.find(b => b.name === mcState.background);
    if (!bg) return false;

    return new Promise(resolve => {
      const blob = new Blob([mcState.imgBytes]);
      const img = new Image();
      img.onload = () => {
        const w = img.width;
        const h = img.height;

        if (bg.exactWidth && bg.exactHeight) {
          if (w !== bg.exactWidth || h !== bg.exactHeight) {
            if (mcImgError) {
              mcImgError.textContent = `Image must be exactly ${bg.exactWidth}×${bg.exactHeight}, got ${w}×${h}`;
              mcImgError.style.display = "block";
            }
            resolve(false);
            return;
          }
        } else {
          if (w < bg.minWidth || h < bg.minHeight) {
            if (mcImgError) {
              mcImgError.textContent = `Image must be at least ${bg.minWidth}×${bg.minHeight}, got ${w}×${h}`;
              mcImgError.style.display = "block";
            }
            resolve(false);
            return;
          }
        }

        if (mcImgError) mcImgError.style.display = "none";
        resolve(true);
      };
      img.onerror = () => resolve(false);
      img.src = URL.createObjectURL(blob);
    });
  }

  // Update process button state
  function updateMcButton() {
    const hasBg = !!mcState.background;
    const hasImg = !!mcState.imgBytes;
    if (mcProcessBtn) mcProcessBtn.disabled = !(hasBg && hasImg);
  }

  // Upload image to a temporary hosting service (uses data URL via Blob)
  // For GitHub Actions, we need a URL. Using a simple approach: trigger with data
  // Note: In production, this would upload to a service like tmpfiles.org or similar
  async function getImageUrl(file) {
    // For now, we'll use a data URL approach - the workflow can be triggered
    // with the image data directly or we can upload to a simple host
    // This is a placeholder - in production, use a file upload service
    return URL.createObjectURL(file);
  }

  // Trigger GitHub workflow via repository dispatch
  async function triggerWorkflow() {
    const owner = "iamjrmh";
    const repo = "CHSuite";

    // For the workflow dispatch, we need to provide a replacement URL
    // Since we can't easily upload files from browser to a URL, we'll use a workaround:
    // Encode the image as base64 and pass it differently, or use a simple upload service

    // For now, show a message that this requires server-side file hosting
    // In production: upload to tmpfiles.org or similar
    toast("Setting up workflow trigger...");

    // This is a simplified trigger - in production, you'd upload the image first
    // and then trigger with the URL
    const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/dispatches`, {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer GITHUB_TOKEN", // User would need to provide this
        "X-GitHub-Api-Version": "2022-11-28"
      },
      body: JSON.stringify({
        event_type: "chmenuchanger",
        client_payload: {
          background: mcState.background,
          // In production: use a real URL after uploading
          replacement_url: mcState.imgUrl
        }
      })
    });

    return response.ok;
  }

  // Process button handler
  mcProcessBtn?.addEventListener("click", async () => {
    if (!mcState.background || !mcState.imgBytes) return;

    // Validate image size
    const valid = await validateImageSize();
    if (!valid) return;

    // Show processing state
    if (mcOutput) mcOutput.style.display = "";
    if (mcStatus) mcStatus.textContent = "Processing... This may take a minute.";
    if (mcDownloadBtn) mcDownloadBtn.style.display = "none";
    if (mcProcessBtn) mcProcessBtn.disabled = true;

    // Note: The actual workflow triggering requires a GitHub token or file hosting
    // For now, show instructions for manual workflow trigger
    if (mcStatus) {
      mcStatus.innerHTML = `
        <div style="color: var(--text-mid);">
          To process your background:<br/><br/>
          1. Upload your image to a public URL<br/>
          2. Go to <a href="https://github.com/iamjrmh/CHSuite/actions/workflows/chmenuchanger.yml" target="_blank" style="color:var(--accent);">GitHub Actions</a><br/>
          3. Click "Run workflow" with your image URL<br/><br/>
          <em>Or download the full <a href="https://github.com/iamjrmh/CHSuite" target="_blank" style="color:var(--accent);">CHSuite app</a> for direct processing.</em>
        </div>
      `;
    }
    if (mcProcessBtn) mcProcessBtn.disabled = false;

    toast("Please use GitHub Actions to process");
  });
}

// ── Sidebar toggle ─────────────────────────────────────────────────────────────
(function () {
  const sidebar      = document.getElementById("sidebar");
  const overlay      = document.getElementById("sidebar-overlay");
  const toggleBtn    = document.getElementById("sidebar-toggle");
  const mobileFab    = document.getElementById("mobile-fab");

  const isMobile = () => window.innerWidth <= 768;

  function openSidebar() {
    sidebar.classList.remove("collapsed");
    if (isMobile()) overlay.classList.add("active");
    mobileFab.classList.add("hidden");
  }

  function closeSidebar() {
    sidebar.classList.add("collapsed");
    overlay.classList.remove("active");
    if (isMobile()) mobileFab.classList.remove("hidden");
  }

  function toggleSidebar() {
    if (sidebar.classList.contains("collapsed")) openSidebar();
    else closeSidebar();
  }

  toggleBtn.addEventListener("click", toggleSidebar);
  mobileFab.addEventListener("click", openSidebar);
  overlay.addEventListener("click", closeSidebar);

  // Close sidebar on mobile when a nav item is selected
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (isMobile()) closeSidebar();
    });
  });

  // On resize: clean up states that don't apply to the new breakpoint
  window.addEventListener("resize", () => {
    if (!isMobile()) {
      overlay.classList.remove("active");
      mobileFab.classList.add("hidden");
    } else {
      if (sidebar.classList.contains("collapsed")) mobileFab.classList.remove("hidden");
      else mobileFab.classList.add("hidden");
    }
  });

  // Start collapsed on mobile
  if (isMobile()) {
    sidebar.classList.add("collapsed");
    mobileFab.classList.remove("hidden");
  }
})();

// ── Clone Hero Version Checker ─────────────────────────────────────────────────

// Known asset filenames per platform — matched exactly where possible to avoid
// catching unrelated files (e.g. a generic .dmg from an old release format).
const CH_ASSET_FILTERS = {
  ios: r => r.assets?.find(a => a.name.endsWith(".ipa")),

  android: r => r.assets?.find(a => a.name.endsWith(".apk")),

    // Linux: old standalone tar OR newer xz archive (check both casings seen in releases)
  linux: r => r.assets?.find(a =>
    a.name === "Linux.x86_64-Standalone.tar" ||
    a.name === "clonehero-linux.tar.xz" ||
    a.name === "CloneHero-linux.tar.xz"
  ),

  // macOS: match zip, versioned dmg (PTB pattern), or the generic mac dmg.
  // Priority: zip > versioned dmg > generic dmg, to prefer newer release formats.
  macos: r => {
    const assets = r.assets ?? [];
    return (
      assets.find(a => a.name === "CloneHero-mac.zip") ||
      assets.find(a => a.name.startsWith("CloneHero") && a.name.endsWith(".dmg") && a.name !== "CloneHero-mac.dmg") ||
      assets.find(a => a.name === "CloneHero-mac.dmg")
    ) ?? null;
  },

  windows: r => {
    const assets = r.assets ?? [];
    const x64 = assets.find(a => a.name === "CloneHero-Win-x64.zip" || a.name === "CloneHero-win64.exe");
    const x32 = assets.find(a => a.name === "clonehero-win32.7z" || a.name === "CloneHero-win32.exe");
    return x64 || x32 ? { x64, x32 } : null;
  },
};

let _chReleasesCache = null;

async function getCHReleases() {
  if (_chReleasesCache) return _chReleasesCache;
  // Fetch up to 100 (GitHub max per page) and explicitly sort by published_at descending,
  // since the API's default ordering is not guaranteed to be newest-first.
  const res = await fetch("https://api.github.com/repos/clonehero-game/releases/releases?per_page=100&page=1");
  if (!res.ok) throw new Error("GitHub API error: " + res.status);
  const releases = await res.json();

  // Sort newest-first. Primary: published_at date. Secondary: semver-style version
  // parsed from tag_name so that e.g. V1.0.0.4080 sorts after V0.21.6.0 even if
  // GitHub's published_at timestamps are unreliable (edited releases, etc.).
  function parseVersion(tag) {
    // Extract numeric parts from tags like "V1.0.0.4080", "v1.1.0.5977-PTB", "CloneHeroLauncher"
    const nums = tag.replace(/[^0-9.]/g, ".").split(".").filter(Boolean).map(Number);
    // Pad to 4 parts
    while (nums.length < 4) nums.push(0);
    return nums;
  }
  function cmpVersions(a, b) {
    const va = parseVersion(a.tag_name), vb = parseVersion(b.tag_name);
    for (let i = 0; i < 4; i++) {
      if (vb[i] !== va[i]) return vb[i] - va[i];
    }
    return 0;
  }
  releases.sort((a, b) => {
    const dateDiff = new Date(b.published_at) - new Date(a.published_at);
    // If dates are more than 7 days apart, trust the date
    if (Math.abs(dateDiff) > 7 * 24 * 3600 * 1000) return dateDiff;
    // Otherwise use version number as tiebreaker
    return cmpVersions(a, b);
  });

  _chReleasesCache = releases;
  return _chReleasesCache;
}

function buildVersionCard(release, assetOrObj, platform) {
  const isPrerelease = release.prerelease;
  const label = isPrerelease ? "Pre-release" : "Release";
  const badgeClass = isPrerelease ? "vc-badge-ptb" : "vc-badge-release";
  const tag = release.tag_name;

  let downloadLinks = "";

  if (platform === "windows" && assetOrObj && (assetOrObj.x64 || assetOrObj.x32)) {
    if (assetOrObj.x64) {
      const ext = assetOrObj.x64.name.split(".").pop();
      downloadLinks += `<a href="${assetOrObj.x64.browser_download_url}" class="btn btn-primary btn-sm vc-dl-btn" target="_blank" rel="noopener">
        <svg viewBox="0 0 20 20" fill="none" width="13" height="13"><path d="M10 2v12M10 14l-4-4M10 14l4-4M3 17h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        Download x64 (.${ext})
      </a>`;
    }
    if (assetOrObj.x32) {
      const ext = assetOrObj.x32.name.split(".").pop();
      downloadLinks += `<a href="${assetOrObj.x32.browser_download_url}" class="btn btn-ghost btn-sm vc-dl-btn" target="_blank" rel="noopener">
        <svg viewBox="0 0 20 20" fill="none" width="13" height="13"><path d="M10 2v12M10 14l-4-4M10 14l4-4M3 17h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        Download x86 (.${ext})
      </a>`;
    }
  } else if (assetOrObj && assetOrObj.browser_download_url) {
    const ext = assetOrObj.name.split(".").pop();
    downloadLinks = `<a href="${assetOrObj.browser_download_url}" class="btn btn-primary btn-sm vc-dl-btn" target="_blank" rel="noopener">
      <svg viewBox="0 0 20 20" fill="none" width="13" height="13"><path d="M10 2v12M10 14l-4-4M10 14l4-4M3 17h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      Download (.${ext})
    </a>`;
  }

  return `<div class="vc-card">
    <div class="vc-card-header">
      <span class="vc-tag">${tag}</span>
      <span class="vc-badge ${badgeClass}">${label}</span>
    </div>
    <div class="vc-card-actions">${downloadLinks}</div>
  </div>`;
}

async function runVersionCheck(platform) {
  const resultEl = document.getElementById(`vc-${platform}-result`);
  const btn = document.querySelector(`.ch-version-btn[data-platform="${platform}"]`);
  if (!resultEl || !btn) return;

  btn.disabled = true;
  btn.innerHTML = `<svg viewBox="0 0 20 20" fill="none" width="14" height="14" class="spin"><path d="M10 2a8 8 0 010 16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg> Checking…`;
  resultEl.style.display = "none";

  try {
    const releases = await getCHReleases();
    const filter = CH_ASSET_FILTERS[platform];

    // Find latest regular release and latest pre-release separately.
    // Skip drafts — they are not publicly available.
    let latestRelease = null, latestPrerelease = null;
    for (const r of releases) {
      if (r.draft) continue;
      const asset = filter(r);
      if (!asset) continue;
      if (!r.prerelease && !latestRelease) latestRelease = { release: r, asset };
      if (r.prerelease && !latestPrerelease) latestPrerelease = { release: r, asset };
      if (latestRelease && latestPrerelease) break;
    }

    let html = "";
    if (latestRelease) html += buildVersionCard(latestRelease.release, latestRelease.asset, platform);
    if (latestPrerelease) html += buildVersionCard(latestPrerelease.release, latestPrerelease.asset, platform);

    if (!html) {
      html = `<div class="vc-error">No matching builds found for this platform.</div>`;
    }

    resultEl.innerHTML = html;
    resultEl.style.display = "block";
  } catch (e) {
    resultEl.innerHTML = `<div class="vc-error">Failed to fetch releases. <a href="https://github.com/clonehero-game/releases/releases" target="_blank" rel="noopener">Check manually →</a></div>`;
    resultEl.style.display = "block";
  }

  btn.disabled = false;
  btn.innerHTML = `<svg viewBox="0 0 20 20" fill="none" width="14" height="14"><path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 3v5l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg> Check Latest Clone Hero Version`;
}

document.querySelectorAll(".ch-version-btn").forEach(btn => {
  btn.addEventListener("click", () => runVersionCheck(btn.dataset.platform));
});

// ── Accordion ──────────────────────────────────────────────────────────────────
document.querySelectorAll(".accordion-header").forEach(btn => {
  btn.addEventListener("click", () => {
    const item = btn.closest(".accordion-item");
    item.classList.toggle("open");
  });
});

// ══════════════════════════════════════════════════════════════════════════════
// CUSTOM COLOR PICKER (ccpOpen / ccpClose)
// ══════════════════════════════════════════════════════════════════════════════

(function () {
  /* ── HSV ↔ RGB helpers ──────────────────────────────────────────── */
  function hsvToRgb(h, s, v) {
    const i = Math.floor(h / 60) % 6;
    const f = h / 60 - Math.floor(h / 60);
    const p = v * (1 - s);
    const q = v * (1 - f * s);
    const t = v * (1 - (1 - f) * s);
    const table = [[v,t,p],[q,v,p],[p,v,t],[p,q,v],[t,p,v],[v,p,q]];
    const [r,g,b] = table[i];
    return [Math.round(r*255), Math.round(g*255), Math.round(b*255)];
  }

  function rgbToHsv(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r,g,b), min = Math.min(r,g,b), d = max - min;
    let h = 0;
    if (d > 0) {
      if (max === r) h = ((g - b) / d + 6) % 6;
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h *= 60;
    }
    return [h, max === 0 ? 0 : d / max, max];
  }

  function hexToRgbArr(hex) {
    const h = hex.replace("#","");
    if (h.length === 3) return [parseInt(h[0]+h[0],16), parseInt(h[1]+h[1],16), parseInt(h[2]+h[2],16)];
    return [parseInt(h.substr(0,2),16), parseInt(h.substr(2,2),16), parseInt(h.substr(4,2),16)];
  }

  function rgbToHex(r, g, b) {
    return "#" + [r,g,b].map(v => Math.round(v).toString(16).padStart(2,"0")).join("").toUpperCase();
  }

  /* ── State ──────────────────────────────────────────────────────── */
  let _h = 0, _s = 1, _v = 1;
  let _onChange = null;
  let _anchorEl = null;

  const popup    = document.getElementById("ccp-popup");
  const svCanvas = document.getElementById("ccp-sv-canvas");
  const hueCanvas= document.getElementById("ccp-hue-canvas");
  const svCursor = document.getElementById("ccp-sv-cursor");
  const hueCursor= document.getElementById("ccp-hue-cursor");
  const prevSwatch= document.getElementById("ccp-preview-swatch");
  const hexInput = document.getElementById("ccp-hex-input");
  const rInput   = document.getElementById("ccp-r-input");
  const gInput   = document.getElementById("ccp-g-input");
  const bInput   = document.getElementById("ccp-b-input");

  if (!popup) return; // safety guard

  /* ── Draw SV gradient ───────────────────────────────────────────── */
  function drawSV() {
    const W = svCanvas.width, H = svCanvas.height;
    const ctx = svCanvas.getContext("2d");
    // Base hue
    const [hr, hg, hb] = hsvToRgb(_h, 1, 1);
    ctx.fillStyle = `rgb(${hr},${hg},${hb})`;
    ctx.fillRect(0, 0, W, H);
    // White → transparent (left to right)
    const gW = ctx.createLinearGradient(0,0,W,0);
    gW.addColorStop(0, "rgba(255,255,255,1)");
    gW.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = gW;
    ctx.fillRect(0, 0, W, H);
    // Transparent → black (top to bottom)
    const gB = ctx.createLinearGradient(0,0,0,H);
    gB.addColorStop(0, "rgba(0,0,0,0)");
    gB.addColorStop(1, "rgba(0,0,0,1)");
    ctx.fillStyle = gB;
    ctx.fillRect(0, 0, W, H);
  }

  /* ── Draw hue rainbow ───────────────────────────────────────────── */
  function drawHue() {
    const W = hueCanvas.width, H = hueCanvas.height;
    const ctx = hueCanvas.getContext("2d");
    const g = ctx.createLinearGradient(0, 0, W, 0);
    for (let i = 0; i <= 360; i += 30) {
      const [r,gg,b] = hsvToRgb(i, 1, 1);
      g.addColorStop(i/360, `rgb(${r},${gg},${b})`);
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }

  /* ── Update cursors & UI ────────────────────────────────────────── */
  function updateUI() {
    const W = svCanvas.width, H = svCanvas.height;
    const x = _s * W, y = (1 - _v) * H;
    svCursor.style.left = x + "px";
    svCursor.style.top  = y + "px";
    hueCursor.style.left = (_h / 360) * hueCanvas.width + "px";

    const [r,g,b] = hsvToRgb(_h, _s, _v);
    const hex = rgbToHex(r,g,b);

    prevSwatch.style.background = hex;
    hexInput.value = hex;
    rInput.value = r;
    gInput.value = g;
    bInput.value = b;

    if (_onChange) _onChange(hex);
  }

  /* ── SV drag ────────────────────────────────────────────────────── */
  function handleSVDrag(e) {
    const rect = svCanvas.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top)  / rect.height));
    _s = x; _v = 1 - y;
    updateUI();
  }
  let _svDragging = false;
  svCanvas.addEventListener("mousedown", e => { _svDragging = true; handleSVDrag(e); });
  document.addEventListener("mousemove", e => { if (_svDragging) handleSVDrag(e); });
  document.addEventListener("mouseup",   () => { _svDragging = false; });

  /* ── Hue drag ───────────────────────────────────────────────────── */
  function handleHueDrag(e) {
    const rect = hueCanvas.getBoundingClientRect();
    _h = Math.max(0, Math.min(360, (e.clientX - rect.left) / rect.width * 360));
    drawSV();
    updateUI();
  }
  let _hueDragging = false;
  hueCanvas.addEventListener("mousedown", e => { _hueDragging = true; handleHueDrag(e); });
  document.addEventListener("mousemove",  e => { if (_hueDragging) handleHueDrag(e); });
  document.addEventListener("mouseup",    () => { _hueDragging = false; });

  /* ── Hex input ──────────────────────────────────────────────────── */
  hexInput.addEventListener("input", () => {
    const raw = hexInput.value.replace(/[^0-9a-fA-F#]/g,"");
    const clean = raw.startsWith("#") ? raw : "#" + raw;
    if (/^#[0-9a-fA-F]{6}$/.test(clean)) {
      const [r,g,b] = hexToRgbArr(clean);
      [_h, _s, _v] = rgbToHsv(r,g,b);
      drawSV();
      updateUI();
      hexInput.value = clean.toUpperCase();
    }
  });
  hexInput.addEventListener("keydown", e => { if (e.key === "Escape") ccpClose(); });

  /* ── RGB inputs ─────────────────────────────────────────────────── */
  [rInput, gInput, bInput].forEach(inp => {
    inp.addEventListener("input", () => {
      const r = Math.min(255,Math.max(0,+rInput.value||0));
      const g = Math.min(255,Math.max(0,+gInput.value||0));
      const b = Math.min(255,Math.max(0,+bInput.value||0));
      [_h, _s, _v] = rgbToHsv(r,g,b);
      drawSV();
      updateUI();
    });
  });

  /* ── Position popup near anchor ─────────────────────────────────── */
  function positionPopup(anchor) {
    const rect = anchor.getBoundingClientRect();
    const pW = 244, pH = 230; // approximate popup size
    let top  = rect.bottom + 8;
    let left = rect.left;
    if (left + pW > window.innerWidth  - 8) left  = window.innerWidth  - pW - 8;
    if (top  + pH > window.innerHeight - 8) top   = rect.top - pH - 8;
    if (left < 8) left = 8;
    if (top  < 8) top  = 8;
    popup.style.top  = top  + "px";
    popup.style.left = left + "px";
  }

  /* ── Public API ─────────────────────────────────────────────────── */
  window.ccpOpen = function(anchor, initialHex, onChange) {
    _anchorEl = anchor;
    _onChange  = onChange;
    const [r,g,b] = hexToRgbArr(initialHex || "#FF0000");
    [_h, _s, _v] = rgbToHsv(r,g,b);
    drawHue();
    drawSV();
    popup.style.display = "block";
    positionPopup(anchor);
    updateUI();
  };

  window.ccpClose = function() {
    popup.style.display = "none";
    _anchorEl = null;
    _onChange  = null;
  };

  /* ── Close on outside click ─────────────────────────────────────── */
  document.addEventListener("mousedown", e => {
    if (popup.style.display === "none") return;
    if (!popup.contains(e.target) && e.target !== _anchorEl) {
      ccpClose();
    }
  });
})();

// ── Boot ───────────────────────────────────────────────────────────────────────
function initApp() {
  // Initialize notegen colors
  state.notegen.colors = JSON.parse(JSON.stringify(DEFAULT_COLORS));
  syncNotePreviewPickersFromState();
  toast("CHSuiteLiteLite Lite loaded");
}

initApp();