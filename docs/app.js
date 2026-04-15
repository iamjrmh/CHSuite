/* ============================================================
   CHSuite Lite  —  app.js
   Pyodide integration + all tool logic
   ============================================================ */

"use strict";

// ── State ─────────────────────────────────────────────────────────────────────
let pyodide = null;
let pyReady = false;

const state = {
  ng: { mode: "gradient" },
  notegen: { section: "guitar", colors: null },
};

// ── Pyodide bootstrap ─────────────────────────────────────────────────────────
async function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`Failed to load script: ${src}`));
    document.head.appendChild(s);
  });
}

async function fetchPy(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status} fetching ${url}`);
  return r.text();
}

async function initPyodide() {
  const dot  = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  dot.className = "status-dot loading";
  text.textContent = "Loading Python…";

  try {
    await loadScript("https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js");
    pyodide = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/" });

    // Load stub files (with HTTP status checks so 404s don't reach runPython)
    const [ws, rt, cs] = await Promise.all([
      fetchPy("py/write_spec.py"),
      fetchPy("py/rthook_texture2d.py"),
      fetchPy("py/CHSuiteLite.py"),
    ]);

    pyodide.runPython(ws);
    pyodide.runPython(rt);
    pyodide.runPython(cs);

    // Seed notegen default colors
    const defaultColorsJson = pyodide.runPython("get_default_colors()");
    state.notegen.colors = JSON.parse(defaultColorsJson);

    pyReady = true;
    dot.className = "status-dot ready";
    text.textContent = "Python ready";

    // Trigger initial notegen render
    renderColorEditor();
  } catch (err) {
    dot.className = "status-dot error";
    text.textContent = "Load failed";
    console.error("Pyodide init error:", err);
    toast("⚠ Python engine failed to load. Some features may be unavailable.", 5000);
  }
}

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
function setupDropZone(dropEl, inputEl, pillEl, accept, onFile) {
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
    if (pillEl) {
      pillEl.innerHTML = `<svg viewBox="0 0 12 12" fill="none"><path d="M2 6h8M6 2v8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" transform="rotate(45 6 6)"/></svg> ${file.name}`;
      pillEl.classList.remove("hidden");
    }
    onFile(file);
  }
}

// ── ██████████████████  NAME GEN  ████████████████████████████────────────────

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
  const existing = Array.from(grid.children);
  const existingChars = existing.map(el => el.dataset.char);

  // Remove cells for chars that are gone
  existing.forEach(el => {
    if (!name.includes(el.dataset.char) && !name.split("").some((c, i) => {
      return c === el.dataset.char;
    })) { /* keep for now */ }
  });

  // Rebuild fresh (simple approach)
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
document.getElementById("ng-generate-btn").addEventListener("click", () => {
  if (!pyReady) { toast("Python not ready."); return; }
  runNameGen();
});

function runNameGen() {
  try {
    let params;
    if (state.ng.mode === "gradient") {
      const name = document.getElementById("ng-name").value.trim();
      if (!name) { toast("Enter a name first."); return; }
      const stops = Array.from(document.querySelectorAll("#ng-color-stops .color-stop"));
      const colors = stops.map(s => s.querySelector(".color-swatch").value);
      params = {
        mode: "gradient", name, colors,
        bold:      document.getElementById("ng-bold").checked,
        italic:    document.getElementById("ng-italic").checked,
        underline: document.getElementById("ng-underline").checked,
        strike:    document.getElementById("ng-strike").checked,
        size:      document.getElementById("ng-size").value || null,
        spacing:   document.getElementById("ng-spacing").value || null,
      };
    } else {
      const indivName = document.getElementById("ng-indiv-name").value;
      if (!indivName) { toast("Enter a name first."); return; }
      const letters = Array.from(document.querySelectorAll("#ng-letter-grid .letter-cell")).map(cell => ({
        char:      cell.dataset.char,
        color:     cell.querySelector("input[type=color]").value,
        bold: false, italic: false, underline: false, strike: false,
      }));
      params = {
        mode: "individual", letters,
        global_size:    document.getElementById("ng-indiv-size").value || null,
        global_spacing: document.getElementById("ng-indiv-spacing").value || null,
      };
    }

    pyodide.globals.set("_ng_params", JSON.stringify(params));
    const resultJson = pyodide.runPython("generate_name(_ng_params)");
    const result = JSON.parse(resultJson);

    if (result.error) { toast("⚠ " + result.error); return; }

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
  // Strip tags and rebuild with colored spans
  const name = taggedStr.replace(/<[^>]+>/g, "").replace(/[\x00-\x1f]/g, "");
  const chars = name.split("");
  const colors = gradient.length >= chars.length ? gradient : chars.map((_, i) => `hsl(${i * 40 % 360},100%,65%)`);
  bar.innerHTML = chars.map((ch, i) => `<span style="color:${colors[i] || '#fff'}">${ch === " " ? "&nbsp;" : ch}</span>`).join("");
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

// ── ██████████████████  NOTE GEN  ████████████████████████████────────────────

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
  "note_overlay_kick_sp_phrase":"Kick Overlay · SP Phrase","note_overlay_kick_sp_active":"Kick Overlay · SP Active",
  "sf_striker_background_left":"SF Strikeline BG · Left","sf_striker_background_mid":"SF Strikeline BG · Mid","sf_striker_background_right":"SF Strikeline BG · Right",
  "note_anim_kick_sp_active":"Kick Anim · SP Active","note_anim_kick_sp_phrase":"Kick Anim · SP Phrase",
  "note_anim_kick_sp_phrase_active":"Kick Anim · SP Phrase Active",
  "note_anim_kick_sp_phrase":"Kick Anim · SP Phrase",
  "sf_note_tap_open":"SF Tap · Open",
  "sf_note_tap_white_left":"SF Tap · White Left","sf_note_tap_white_mid":"SF Tap · White Mid","sf_note_tap_white_right":"SF Tap · White Right",
  "sf_note_tap_black_left":"SF Tap · Black Left","sf_note_tap_black_mid":"SF Tap · Black Mid","sf_note_tap_black_right":"SF Tap · Black Right",
  "cym_anim_sp_active":"Cymbal Anim · SP Active","cym_anim_sp_phrase":"Cymbal Anim · SP Phrase",
  "cym_anim_sp_phrase_active":"Cymbal Anim · SP Phrase Active",
  "tom_anim_sp_active":"Tom Anim · SP Active","tom_anim_sp_phrase":"Tom Anim · SP Phrase",
  "tom_anim_sp_phrase_active":"Tom Anim · SP Phrase Active",
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
  const colors  = state.notegen.colors;
  if (!colors || !colors[section]) { editor.innerHTML = "<p style='color:var(--text-dim);font-size:.85rem'>Loading…</p>"; return; }

  const sectionColors = colors[section];
  editor.innerHTML = "";

  // Group keys visually (by prefix pattern)
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
  // Group by first word prefix
  const groups = {};
  const order  = [];
  keys.forEach(k => {
    const prefix = k.split("_").slice(0, 2).join("_");
    if (!groups[prefix]) { groups[prefix] = []; order.push(prefix); }
    groups[prefix].push(k);
  });
  // Merge tiny groups
  const result = [];
  order.forEach(prefix => {
    const items = groups[prefix];
    const label = prefix.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    result.push({ label, keys: items });
  });
  return result;
}

// Import INI
setupDropZone(
  document.getElementById("notegen-ini-drop"),
  document.getElementById("notegen-ini-input"),
  null, ".ini",
  async file => {
    const text = await file.text();
    if (!pyReady) { toast("Python not ready."); return; }
    pyodide.globals.set("_ini_text", text);
    const resultJson = pyodide.runPython("parse_notes_ini(_ini_text)");
    const parsed = JSON.parse(resultJson);
    if (parsed.error) { toast("⚠ Could not parse INI: " + parsed.error); return; }
    // Merge with defaults (keep defaults for keys not in file)
    Object.keys(parsed).forEach(sec => {
      if (!state.notegen.colors[sec]) state.notegen.colors[sec] = {};
      Object.assign(state.notegen.colors[sec], parsed[sec]);
    });
    renderColorEditor();
    toast("✓ INI imported.");
  }
);

// Export button
document.getElementById("ng-export-btn").addEventListener("click", () => {
  if (!pyReady) { toast("Python not ready."); return; }
  try {
    pyodide.globals.set("_colors_json", JSON.stringify(state.notegen.colors));
    const iniContent = pyodide.runPython("generate_notes_ini(_colors_json)");
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

// Reset to defaults
document.getElementById("ng-reset-btn").addEventListener("click", () => {
  if (!pyReady) { toast("Python not ready."); return; }
  const defaultColorsJson = pyodide.runPython("get_default_colors()");
  state.notegen.colors = JSON.parse(defaultColorsJson);
  renderColorEditor();
  toast("Reset to defaults.");
});

// ── Boot ───────────────────────────────────────────────────────────────────────
initPyodide();
