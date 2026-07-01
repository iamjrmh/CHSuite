// Runtime theme engine.
//
// The 25 theme JSONs (color-token maps) live under /assets/themes. Applying a
// theme just writes each token to its matching CSS custom property on :root, so
// the entire UI recolors instantly with no re-render.

const THEME_KEYS = [
  "bg",
  "panel",
  "card",
  "card2",
  "sidebar",
  "border",
  "border2",
  "accent",
  "accent_dim",
  "accent2",
  "accent3",
  "text",
  "text_dim",
  "text_mid",
  "success",
  "warn",
  "error",
  "selected",
  "hover",
  "nav_active",
  "nav_hover",
] as const;

export interface Theme {
  _name?: string;
  _description?: string;
  [k: string]: string | undefined;
}

const cache = new Map<string, Theme>();

export async function listThemes(): Promise<string[]> {
  try {
    const res = await fetch("/assets/themes/index.json");
    const names = (await res.json()) as string[];
    if (Array.isArray(names) && names.length) return names;
  } catch {
    /* fall through */
  }
  return ["Default"];
}

export async function loadTheme(name: string): Promise<Theme | null> {
  if (cache.has(name)) return cache.get(name)!;
  try {
    const res = await fetch(`/assets/themes/${encodeURIComponent(name)}.json`);
    if (!res.ok) return null;
    const theme = (await res.json()) as Theme;
    cache.set(name, theme);
    return theme;
  } catch {
    return null;
  }
}

/** Write a theme's tokens onto :root as CSS variables. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  for (const key of THEME_KEYS) {
    const value = theme[key];
    if (typeof value === "string" && value.startsWith("#")) {
      // accent_dim -> --accent-dim, nav_active -> --nav-active
      root.style.setProperty(`--${key.replace(/_/g, "-")}`, value);
    }
  }
}

export async function setTheme(name: string): Promise<boolean> {
  const theme = await loadTheme(name);
  if (!theme) return false;
  applyTheme(theme);
  return true;
}

/** Convenience: load a theme just to read its swatch colors (for pickers). */
export async function themeSwatch(
  name: string,
): Promise<{ accent: string; accent2: string; bg: string; card: string } | null> {
  const t = await loadTheme(name);
  if (!t) return null;
  return {
    accent: t.accent || "#6c3bff",
    accent2: t.accent2 || "#ff3b8a",
    bg: t.bg || "#0c0e13",
    card: t.card || "#181c28",
  };
}
