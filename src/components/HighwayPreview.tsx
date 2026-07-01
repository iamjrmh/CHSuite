import { useEffect, useRef } from "react";

type ColorMap = Record<string, string>;

interface Theme {
  bg: string;
  border: string;
  textDim: string;
}

const GUITAR_LANES = ["green", "red", "yellow", "blue", "orange"];
const DRUM_LANES = ["red", "yellow", "blue", "green"];
const SIXFRET_ROWS = ["left", "mid", "right"];

const SPRITE_FILES: Record<"body" | "base" | "light", string> = {
  body: "/assets/images/note_body.png",
  base: "/assets/images/note_base.png",
  light: "/assets/images/note_light.png",
};

type Sprites = Record<"body" | "base" | "light", HTMLImageElement>;

let spritePromise: Promise<Sprites> | null = null;
function loadSprites(): Promise<Sprites> {
  if (!spritePromise) {
    spritePromise = Promise.all(
      (Object.entries(SPRITE_FILES) as [keyof Sprites, string][]).map(
        ([key, src]) =>
          new Promise<[keyof Sprites, HTMLImageElement]>((resolve) => {
            const img = new Image();
            img.onload = () => resolve([key, img]);
            img.onerror = () => resolve([key, img]);
            img.src = src;
          }),
      ),
    ).then((entries) => Object.fromEntries(entries) as Sprites);
  }
  return spritePromise;
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function safeHex(v: string | undefined, fallback: string) {
  return v && /^#[0-9a-fA-F]{6}$/.test(v) ? v : fallback;
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16) || 0, parseInt(h.slice(2, 4), 16) || 0, parseInt(h.slice(4, 6), 16) || 0];
}

function alphaBlend(hex: string, bg: string, alpha: number): string {
  const [r1, g1, b1] = hexToRgb(hex);
  const [r2, g2, b2] = hexToRgb(bg);
  const c = (a: number, b: number) => clamp(Math.round(a * alpha + b * (1 - alpha)), 0, 255).toString(16).padStart(2, "0");
  return `#${c(r1, r2)}${c(g1, g2)}${c(b1, b2)}`;
}

/** Composite note_body (multiply-tinted) → note_base (untinted) → note_light (source-in tinted). */
function compositeNote(sprites: Sprites, bodyHex: string, lightHex: string, w: number, h: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;

  if (sprites.body.complete && sprites.body.naturalWidth) {
    ctx.drawImage(sprites.body, 0, 0, w, h);
    ctx.globalCompositeOperation = "multiply";
    ctx.fillStyle = bodyHex;
    ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = "destination-in";
    ctx.drawImage(sprites.body, 0, 0, w, h);
    ctx.globalCompositeOperation = "source-over";
  }

  if (sprites.base.complete && sprites.base.naturalWidth) {
    ctx.drawImage(sprites.base, 0, 0, w, h);
  }

  if (sprites.light.complete && sprites.light.naturalWidth) {
    const lightCanvas = document.createElement("canvas");
    lightCanvas.width = w;
    lightCanvas.height = h;
    const lctx = lightCanvas.getContext("2d")!;
    lctx.drawImage(sprites.light, 0, 0, w, h);
    lctx.globalCompositeOperation = "source-in";
    lctx.fillStyle = lightHex;
    lctx.fillRect(0, 0, w, h);
    ctx.drawImage(lightCanvas, 0, 0);
  }

  return canvas;
}

function getNoteSprite(
  cache: Map<string, HTMLCanvasElement>,
  sprites: Sprites,
  bodyHex: string,
  lightHex: string,
  w: number,
  h: number,
): HTMLCanvasElement {
  const key = `${bodyHex}|${lightHex}|${w}|${h}`;
  let sprite = cache.get(key);
  if (!sprite) {
    sprite = compositeNote(sprites, bodyHex, lightHex, w, h);
    cache.set(key, sprite);
  }
  return sprite;
}

function drawLanes(ctx: CanvasRenderingContext2D, w: number, h: number, n: number, laneTints: string[], theme: Theme) {
  const lw = w / n;
  for (let i = 0; i < n; i++) {
    const x1 = Math.floor(i * lw);
    const x2 = Math.floor((i + 1) * lw);
    ctx.fillStyle = alphaBlend(laneTints[i], theme.bg, 0.1);
    ctx.fillRect(x1, 0, x2 - x1, h);
    if (i > 0) {
      ctx.strokeStyle = theme.border;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x1 + 0.5, 0);
      ctx.lineTo(x1 + 0.5, h);
      ctx.stroke();
    }
  }
  ctx.strokeStyle = theme.border;
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 12]);
  for (const frac of [0.25, 0.42, 0.58, 0.74]) {
    const y = Math.floor(h * frac) + 0.5;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);
}

function drawSustain(ctx: CanvasRenderingContext2D, cx: number, top: number, bottom: number, col: string, sw: number) {
  ctx.fillStyle = col;
  ctx.fillRect(cx - sw, top + sw, sw * 2, bottom - sw - (top + sw));
  ctx.beginPath();
  ctx.ellipse(cx, top + sw, sw, sw, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.ellipse(cx, bottom - sw, sw, sw, 0, 0, Math.PI * 2);
  ctx.fill();
}

function drawGuitar(ctx: CanvasRenderingContext2D, w: number, h: number, colors: ColorMap, theme: Theme, sprites: Sprites, cache: Map<string, HTMLCanvasElement>) {
  const lanes = GUITAR_LANES;
  const n = lanes.length;
  const lw = w / n;
  const noteW = clamp(Math.round(lw * 0.85), 40, 95);
  const noteH = Math.max(21, Math.round((noteW * 50) / 95));
  const sw = Math.max(4, Math.round(lw * 0.1));
  const noteY = h - noteH - 10;
  const susTop = -sw;
  const susBot = noteY + noteH / 2;

  drawLanes(ctx, w, h, n, lanes.map((l) => safeHex(colors[`note_${l}`], "#333")), theme);

  lanes.forEach((lane, i) => {
    const cx = Math.round(i * lw + lw / 2);
    drawSustain(ctx, cx, susTop, susBot, safeHex(colors[`sustain_${lane}`], "#888"), sw);
  });

  ctx.fillStyle = safeHex(colors.note_sp_active, "#00FFFF");
  ctx.fillRect(0, 0, w, 4);

  lanes.forEach((lane, i) => {
    const cx = Math.round(i * lw + lw / 2);
    const bodyHex = safeHex(colors[`note_${lane}`], "#888");
    const lightHex = safeHex(colors[`note_anim_${lane}`], "#888");
    const sprite = getNoteSprite(cache, sprites, bodyHex, lightHex, noteW, noteH);
    ctx.drawImage(sprite, cx - noteW / 2, noteY);
  });
}

function drawDrums(ctx: CanvasRenderingContext2D, w: number, h: number, colors: ColorMap, theme: Theme, sprites: Sprites, cache: Map<string, HTMLCanvasElement>) {
  const lanes = DRUM_LANES;
  const n = lanes.length;
  const lw = w / n;
  const noteW = clamp(Math.round(lw * 0.85), 40, 95);
  const noteH = Math.max(21, Math.round((noteW * 50) / 95));
  const sw = Math.max(4, Math.round(lw * 0.1));
  const rowH = h / 2;
  const divY = Math.round(rowH);
  const cymY = divY - noteH - sw;
  const tomY = h - noteH - sw;

  for (let i = 0; i < n; i++) {
    const x1 = Math.floor(i * lw);
    const x2 = Math.floor((i + 1) * lw);
    ctx.fillStyle = alphaBlend(safeHex(colors[`tom_${lanes[i]}`], "#333"), theme.bg, 0.1);
    ctx.fillRect(x1, 0, x2 - x1, h);
    if (i > 0) {
      ctx.strokeStyle = theme.border;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x1 + 0.5, 0);
      ctx.lineTo(x1 + 0.5, h);
      ctx.stroke();
    }
  }

  ctx.strokeStyle = theme.border;
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 8]);
  ctx.beginPath();
  ctx.moveTo(0, divY + 0.5);
  ctx.lineTo(w, divY + 0.5);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = safeHex(colors.cym_sp_active, "#00FFFF");
  ctx.fillRect(0, 0, w, 4);

  lanes.forEach((lane, i) => {
    const cx = Math.round(i * lw + lw / 2);
    drawSustain(ctx, cx, -sw, cymY + noteH / 2, safeHex(colors[`cym_${lane}`], "#888"), sw);
  });
  lanes.forEach((lane, i) => {
    const cx = Math.round(i * lw + lw / 2);
    drawSustain(ctx, cx, divY + sw, tomY + noteH / 2, safeHex(colors[`tom_${lane}`], "#888"), sw);
  });

  lanes.forEach((lane, i) => {
    const cx = Math.round(i * lw + lw / 2);
    const sprite = getNoteSprite(cache, sprites, safeHex(colors[`cym_${lane}`], "#888"), safeHex(colors[`cym_anim_${lane}`], "#888"), noteW, noteH);
    ctx.drawImage(sprite, cx - noteW / 2, cymY);
  });
  lanes.forEach((lane, i) => {
    const cx = Math.round(i * lw + lw / 2);
    const sprite = getNoteSprite(cache, sprites, safeHex(colors[`tom_${lane}`], "#888"), safeHex(colors[`tom_anim_${lane}`], "#888"), noteW, noteH);
    ctx.drawImage(sprite, cx - noteW / 2, tomY);
  });

  ctx.fillStyle = theme.textDim;
  ctx.font = "10px Inter, system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText("Cymbals", 4, 4);
  ctx.fillText("Toms", 4, divY + 4);
}

function drawSixfret(ctx: CanvasRenderingContext2D, w: number, h: number, colors: ColorMap, theme: Theme, sprites: Sprites, cache: Map<string, HTMLCanvasElement>) {
  const nCols = 2;
  const nRows = 3;
  const colW = w / nCols;
  const rowH = h / nRows;
  const noteW = clamp(Math.round(colW * 0.75), 30, 95);
  const noteH = Math.max(16, Math.round((noteW * 50) / 95));
  const sw = Math.max(3, Math.round(colW * 0.08));
  const WHITE_TINT = "#e8e8e8";
  const BLACK_TINT = "#3a3a3a";

  [WHITE_TINT, BLACK_TINT].forEach((tint, colI) => {
    const x1 = Math.floor(colI * colW);
    const x2 = Math.floor((colI + 1) * colW);
    ctx.fillStyle = alphaBlend(tint, theme.bg, 0.08);
    ctx.fillRect(x1, 0, x2 - x1, h);
  });
  ctx.strokeStyle = theme.border;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(Math.round(colW) + 0.5, 0);
  ctx.lineTo(Math.round(colW) + 0.5, h);
  ctx.stroke();

  ctx.setLineDash([3, 8]);
  for (let rowI = 1; rowI < nRows; rowI++) {
    const y = Math.round(rowI * rowH) + 0.5;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);

  ctx.fillStyle = safeHex(colors.sf_note_sp_active, "#00FFFF");
  ctx.fillRect(0, 0, w, 4);

  SIXFRET_ROWS.forEach((pos, rowI) => {
    const rowTop = Math.round(rowI * rowH);
    const rowBot = Math.round((rowI + 1) * rowH);
    const noteTop = rowBot - noteH - sw;
    const susTop = rowI === 0 ? -sw : rowTop;
    const susBot = noteTop + noteH / 2;

    (["white", "black"] as const).forEach((colType, colI) => {
      const cx = Math.round(colI * colW + colW / 2);
      drawSustain(ctx, cx, susTop, susBot, safeHex(colors[`sf_sustain_${pos}`], "#888"), sw);
      const bodyHex = safeHex(colors[`sf_note_${colType}_${pos}`], "#888");
      const sprite = getNoteSprite(cache, sprites, bodyHex, bodyHex, noteW, noteH);
      ctx.drawImage(sprite, cx - noteW / 2, noteTop);
    });
  });

  ctx.fillStyle = theme.textDim;
  ctx.font = "10px Inter, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ["White", "Black"].forEach((label, colI) => {
    const cx = Math.round(colI * colW + colW / 2);
    ctx.fillText(label, cx, h - 2);
  });
}

export function HighwayPreview({
  section,
  colors,
  className,
}: {
  section: "guitar" | "drums" | "sixfret" | "other" | string;
  colors: ColorMap;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const spriteCacheRef = useRef<Map<string, HTMLCanvasElement>>(new Map());
  const spritesRef = useRef<Sprites | null>(null);
  const colorsRef = useRef(colors);
  const sectionRef = useRef(section);
  colorsRef.current = colors;
  sectionRef.current = section;

  useEffect(() => {
    let cancelled = false;
    loadSprites().then((s) => {
      if (!cancelled) {
        spritesRef.current = s;
        redraw();
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function redraw() {
    const canvas = canvasRef.current;
    if (!canvas || !spritesRef.current) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(1, Math.round(rect.width));
    const h = Math.max(1, Math.round(rect.height));
    if (w < 20 || h < 20) return;
    const pw = Math.round(w * dpr);
    const ph = Math.round(h * dpr);
    if (canvas.width !== pw || canvas.height !== ph) {
      canvas.width = pw;
      canvas.height = ph;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const style = getComputedStyle(canvas);
    const theme: Theme = {
      bg: safeHex(style.getPropertyValue("--bg").trim(), "#0c0e13"),
      border: safeHex(style.getPropertyValue("--border").trim(), "#252b3d"),
      textDim: safeHex(style.getPropertyValue("--text-dim").trim(), "#636b82"),
    };

    const sec = sectionRef.current;
    const c = colorsRef.current;
    if (sec === "drums") drawDrums(ctx, w, h, c, theme, spritesRef.current, spriteCacheRef.current);
    else if (sec === "sixfret") drawSixfret(ctx, w, h, c, theme, spritesRef.current, spriteCacheRef.current);
    else drawGuitar(ctx, w, h, c, theme, spritesRef.current, spriteCacheRef.current);
  }

  useEffect(() => {
    redraw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, colors]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => redraw());
    ro.observe(canvas);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const mo = new MutationObserver(() => redraw());
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["style", "class"] });
    return () => mo.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <canvas ref={canvasRef} className={className} style={{ display: "block", width: "100%", height: "100%" }} />;
}
