// Pure colored-name generation (TextMesh Pro markup), ported from the original
// CHNameGen. Runs entirely client-side - no backend round-trip for preview.

export interface LetterStyle {
  char: string;
  color: string;
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strike: boolean;
}

function hexToRgbF(hex: string): [number, number, number] {
  let h = hex.replace("#", "");
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  const n = parseInt(h || "ffffff", 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

function rgbFToHex(rgb: [number, number, number]): string {
  const c = (v: number) =>
    Math.min(255, Math.max(0, Math.round(v * 255)))
      .toString(16)
      .padStart(2, "0");
  return `#${c(rgb[0])}${c(rgb[1])}${c(rgb[2])}`.toUpperCase();
}

/** Interpolate a smooth gradient of `steps` hex colors across the stops. */
export function interpolateColors(stops: string[], steps: number): string[] {
  const cols = stops.filter(Boolean).map(hexToRgbF);
  if (cols.length === 0) return [];
  if (cols.length === 1 || steps <= 1)
    return Array.from({ length: Math.max(1, steps) }, () => rgbFToHex(cols[0]));

  const out: string[] = [];
  const segments = cols.length - 1;
  for (let i = 0; i < segments; i++) {
    const start = cols[i];
    const end = cols[i + 1];
    const segSteps = Math.ceil(steps / segments);
    for (let s = 0; s < segSteps; s++) {
      const t = segSteps === 1 ? 0 : s / (segSteps - 1);
      out.push(
        rgbFToHex([
          start[0] + (end[0] - start[0]) * t,
          start[1] + (end[1] - start[1]) * t,
          start[2] + (end[2] - start[2]) * t,
        ]),
      );
    }
  }
  return out.slice(0, steps);
}

export interface StyleFlags {
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strike?: boolean;
}

function wrapStyle(inner: string, s: StyleFlags): string {
  let out = inner;
  if (s.bold) out = `<b>${out}</b>`;
  if (s.italic) out = `<i>${out}</i>`;
  if (s.underline) out = `<u>${out}</u>`;
  if (s.strike) out = `<s>${out}</s>`;
  return out;
}

function sizeSpacingWrap(
  inner: string,
  size?: number,
  spacing?: number,
): string {
  let out = inner;
  if (spacing && spacing !== 0) out = `<cspace=${spacing}>${out}</cspace>`;
  if (size && size > 0) out = `<size=${size}>${out}</size>`;
  return out;
}

export interface GradientOptions extends StyleFlags {
  size?: number;
  spacing?: number;
}

/** Gradient mode: smooth color sweep across the whole name. */
export function generateGradient(
  name: string,
  stops: string[],
  opts: GradientOptions = {},
): { markup: string; colors: string[] } {
  if (!name) return { markup: "", colors: [] };
  const colors = interpolateColors(stops.length ? stops : ["#FFFFFF"], name.length);
  const segments = [...name].map(
    (ch, i) => `<color=${colors[i] || colors[colors.length - 1]}>${ch}</color>`,
  );
  let markup = wrapStyle(segments.join(""), opts);
  markup = sizeSpacingWrap(markup, opts.size, opts.spacing);
  return { markup, colors };
}

/** Per-letter mode: each character carries its own color + styling. */
export function generatePerLetter(
  letters: LetterStyle[],
  globalSize?: number,
  globalSpacing?: number,
): { markup: string; colors: string[] } {
  const colors: string[] = [];
  const segments = letters.map((ld) => {
    colors.push(ld.color);
    const colored = `<color=${ld.color}>${ld.char}</color>`;
    return wrapStyle(colored, ld);
  });
  let markup = sizeSpacingWrap(segments.join(""), globalSize, globalSpacing);
  return { markup, colors };
}

/** Strip markup back to plain readable text (for previews / labels). */
export function stripMarkup(markup: string): string {
  return markup.replace(
    /<\/?(color|b|i|u|s|size|cspace)[^>]*>/g,
    "",
  );
}
