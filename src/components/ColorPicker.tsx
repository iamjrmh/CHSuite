import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Pipette } from "lucide-react";

const POPOVER_W = 224;
const POPOVER_H = 260;

function clamp01(n: number) {
  return Math.min(1, Math.max(0, n));
}

function isValidHex(v: string) {
  return /^#[0-9a-fA-F]{6}$/.test(v);
}

function hexToHsv(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  let hue = 0;
  if (d !== 0) {
    if (max === r) hue = ((g - b) / d) % 6;
    else if (max === g) hue = (b - r) / d + 2;
    else hue = (r - g) / d + 4;
    hue *= 60;
    if (hue < 0) hue += 360;
  }
  const sat = max === 0 ? 0 : d / max;
  return [hue, sat * 100, max * 100];
}

function hsvToHex(h: number, s: number, v: number): string {
  const ss = s / 100;
  const vv = v / 100;
  const c = vv * ss;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = vv - c;
  let [r, g, b] = [0, 0, 0];
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  const channel = (n: number) => Math.round((n + m) * 255).toString(16).padStart(2, "0");
  return `#${channel(r)}${channel(g)}${channel(b)}`.toUpperCase();
}

export function ColorPicker({ value, onChange }: { value: string; onChange: (hex: string) => void }) {
  const safeValue = isValidHex(value) ? value.toUpperCase() : "#FFFFFF";
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const [origin, setOrigin] = useState("top left");
  const [hue, setHue] = useState(0);
  const [sat, setSat] = useState(0);
  const [val, setVal] = useState(100);
  const [hexInput, setHexInput] = useState(safeValue);

  const swatchRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const svRef = useRef<HTMLDivElement>(null);
  const hueRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef<"sv" | "hue" | null>(null);

  // Re-derive HSV from the incoming hex whenever the picker isn't actively open/dragging.
  useEffect(() => {
    if (open) return;
    const [h, s, v] = hexToHsv(safeValue);
    setHue(h);
    setSat(s);
    setVal(v);
    setHexInput(safeValue);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, open]);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      const target = e.target as Node;
      if (popRef.current?.contains(target) || swatchRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function openPicker() {
    const rect = swatchRef.current?.getBoundingClientRect();
    if (rect) {
      let left = rect.left;
      const flippedLeft = left + POPOVER_W > window.innerWidth - 12;
      if (flippedLeft) left = window.innerWidth - POPOVER_W - 12;
      let top = rect.bottom + 8;
      const flippedUp = top + POPOVER_H > window.innerHeight - 12;
      if (flippedUp) top = rect.top - POPOVER_H - 8;
      setPos({ top: Math.max(12, top), left: Math.max(12, left) });
      // Scale in from whichever corner is nearest the trigger, so it reads
      // as growing out of the swatch instead of appearing at a fixed spot.
      setOrigin(`${flippedUp ? "bottom" : "top"} ${flippedLeft ? "right" : "left"}`);
    }
    setOpen(true);
  }

  function commit(h: number, s: number, v: number) {
    const hex = hsvToHex(h, s, v);
    setHexInput(hex);
    onChange(hex);
  }

  function applySv(clientX: number, clientY: number) {
    const rect = svRef.current?.getBoundingClientRect();
    if (!rect) return;
    const s = clamp01((clientX - rect.left) / rect.width) * 100;
    const v = (1 - clamp01((clientY - rect.top) / rect.height)) * 100;
    setSat(s);
    setVal(v);
    commit(hue, s, v);
  }

  function applyHue(clientX: number) {
    const rect = hueRef.current?.getBoundingClientRect();
    if (!rect) return;
    const h = clamp01((clientX - rect.left) / rect.width) * 360;
    setHue(h);
    commit(h, sat, val);
  }

  function handleSvDown(e: React.PointerEvent) {
    (e.target as Element).setPointerCapture(e.pointerId);
    draggingRef.current = "sv";
    applySv(e.clientX, e.clientY);
  }

  function handleHueDown(e: React.PointerEvent) {
    (e.target as Element).setPointerCapture(e.pointerId);
    draggingRef.current = "hue";
    applyHue(e.clientX);
  }

  function handlePointerMove(e: React.PointerEvent) {
    if (draggingRef.current === "sv") applySv(e.clientX, e.clientY);
    else if (draggingRef.current === "hue") applyHue(e.clientX);
  }

  function handlePointerUp() {
    draggingRef.current = null;
  }

  function handleHexInput(v: string) {
    const upper = v.toUpperCase();
    setHexInput(upper);
    if (isValidHex(upper)) {
      onChange(upper);
      const [h, s, vv] = hexToHsv(upper);
      setHue(h);
      setSat(s);
      setVal(vv);
    }
  }

  const pureHue = hsvToHex(hue, 100, 100);

  return (
    <>
      <button
        ref={swatchRef}
        type="button"
        onClick={() => (open ? setOpen(false) : openPicker())}
        className="relative h-7 w-7 flex-none rounded-md"
        style={{ background: safeValue, border: "2px solid var(--border2)" }}
        aria-label="Pick color"
      >
        <span
          className="pointer-events-none absolute -bottom-1 -right-1 grid h-3.5 w-3.5 place-items-center rounded-full"
          style={{ background: "var(--card2)", border: "1px solid var(--border2)" }}
        >
          <Pipette size={8} style={{ color: "var(--text)" }} />
        </span>
      </button>
      {open &&
        createPortal(
          <div
            ref={popRef}
            className="pop-in fixed z-50 rounded-[14px] p-3.5"
            style={{
              top: pos.top,
              left: pos.left,
              width: POPOVER_W,
              background: "var(--card)",
              border: "1px solid var(--border2)",
              boxShadow: "0 20px 45px -12px rgba(0,0,0,0.55)",
              transformOrigin: origin,
            }}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
          >
            <div
              ref={svRef}
              className="relative h-36 w-full cursor-crosshair rounded-lg"
              style={{ background: `linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, transparent), ${pureHue}` }}
              onPointerDown={handleSvDown}
            >
              <div
                className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white"
                style={{ left: `${sat}%`, top: `${100 - val}%`, boxShadow: "0 0 0 1px rgba(0,0,0,0.4)" }}
              />
            </div>
            <div
              ref={hueRef}
              className="relative mt-3 h-3 w-full cursor-pointer rounded-full"
              style={{ background: "linear-gradient(to right, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00)" }}
              onPointerDown={handleHueDown}
            >
              <div
                className="pointer-events-none absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white"
                style={{ left: `${(hue / 360) * 100}%`, background: pureHue, boxShadow: "0 0 0 1px rgba(0,0,0,0.4)" }}
              />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <div className="h-8 w-8 flex-none rounded-md" style={{ background: hexInput, border: "1px solid var(--border2)" }} />
              <input
                className="input flex-1 font-mono text-[12px]"
                style={{ height: 32, padding: "0 8px" }}
                value={hexInput}
                onChange={(e) => handleHexInput(e.target.value)}
              />
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
