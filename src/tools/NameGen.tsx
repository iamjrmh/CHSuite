import { useMemo, useState } from "react";
import {
  Copy,
  Check,
  Plus,
  X,
  Download,
  Bold,
  Italic,
  Underline,
  Strikethrough,
  Type,
} from "lucide-react";
import { Page, Card, SectionLabel, Spinner } from "../components/ui";
import { useToast } from "../components/Toast";
import { api, ApiError } from "../lib/api";
import {
  generateGradient,
  generatePerLetter,
  interpolateColors,
  type LetterStyle,
} from "../lib/namegen";

type Mode = "gradient" | "perletter";
interface Flags {
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strike: boolean;
}
const NO_FLAGS: Flags = { bold: false, italic: false, underline: false, strike: false };

export function NameGen() {
  const toast = useToast();
  const [mode, setMode] = useState<Mode>("gradient");
  const [name, setName] = useState("JURMR");

  // Gradient state
  const [stops, setStops] = useState<string[]>(["#6C3BFF", "#FF3B8A"]);
  const [gFlags, setGFlags] = useState<Flags>(NO_FLAGS);
  const [size, setSize] = useState("");
  const [spacing, setSpacing] = useState("");

  // Per-letter state
  const [letters, setLetters] = useState<LetterStyle[]>(() => seedLetters("JURMR"));

  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);

  const result = useMemo(() => {
    const sz = size ? parseInt(size) : undefined;
    const sp = spacing ? parseFloat(spacing) : undefined;
    if (mode === "gradient") {
      return generateGradient(name, stops, { ...gFlags, size: sz, spacing: sp });
    }
    return generatePerLetter(letters.slice(0, name.length), sz, sp);
  }, [mode, name, stops, gFlags, size, spacing, letters]);

  const preview = useMemo(() => {
    if (mode === "gradient") {
      const cols = interpolateColors(stops.length ? stops : ["#fff"], name.length || 1);
      return [...name].map((ch, i) => ({ ch, color: cols[i] || cols[cols.length - 1], ...gFlags }));
    }
    return [...name].map((ch, i) => {
      const l = letters[i];
      return l ? { ...l, ch } : { ch, color: "#ffffff", ...NO_FLAGS };
    });
  }, [mode, name, stops, gFlags, letters]);

  function onNameChange(v: string) {
    setName(v);
    setLetters((prev) => {
      const next = [...v].map((ch, i) =>
        prev[i] ? { ...prev[i], char: ch } : { char: ch, color: rainbow(i, v.length), ...NO_FLAGS },
      );
      return next;
    });
  }

  async function copy() {
    await navigator.clipboard.writeText(result.markup);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  }

  async function doExport() {
    if (!result.markup) {
      toast.warn("Nothing to export", "Enter a name first.");
      return;
    }
    setExporting(true);
    try {
      const res = await api.post<{ path: string; profile: string; created: boolean }>(
        "/namegen/export",
        { markup: result.markup },
      );
      toast.success(
        res.created ? "Created new profile" : "Profile updated",
        `${res.profile} in ${res.path}`,
      );
    } catch (e) {
      const err = e as ApiError;
      toast.error("Export failed", err.message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <Page
      title="CHNameGen"
      subtitle="Design colored player names and export them to profiles.ini"
      icon={<Type size={20} />}
      actions={
        <>
          <button className="btn btn-ghost" onClick={copy} disabled={!result.markup}>
            {copied ? <Check size={15} /> : <Copy size={15} />}
            {copied ? "Copied" : "Copy markup"}
          </button>
          <button className="btn btn-primary" onClick={doExport} disabled={exporting || !result.markup}>
            {exporting ? <Spinner size={15} /> : <Download size={15} />}
            Export
          </button>
        </>
      }
    >
      {/* Live preview */}
      <Card className="mb-4 flex min-h-[120px] items-center justify-center overflow-hidden" pad={false}>
        <div
          className="flex w-full items-center justify-center px-6 py-10"
          style={{
            background:
              "radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 70%)",
          }}
        >
          <div className="text-[40px] font-bold leading-none tracking-tight" style={{ wordBreak: "break-all" }}>
            {preview.length === 0 ? (
              <span style={{ color: "var(--text-dim)", fontSize: 16, fontWeight: 500 }}>
                Type a name to preview it
              </span>
            ) : (
              preview.map((p, i) => (
                <span
                  key={i}
                  style={{
                    color: p.color,
                    fontWeight: p.bold ? 800 : 700,
                    fontStyle: p.italic ? "italic" : "normal",
                    textDecoration: [
                      p.underline ? "underline" : "",
                      p.strike ? "line-through" : "",
                    ].filter(Boolean).join(" ") || "none",
                  }}
                >
                  {p.ch === " " ? " " : p.ch}
                </span>
              ))
            )}
          </div>
        </div>
      </Card>

      {/* Mode tabs */}
      <div className="mb-4 inline-flex rounded-[12px] p-1" style={{ background: "var(--card2)", border: "1px solid var(--border)" }}>
        <Tab active={mode === "gradient"} onClick={() => setMode("gradient")}>Gradient</Tab>
        <Tab active={mode === "perletter"} onClick={() => setMode("perletter")}>Per-Letter</Tab>
      </div>

      <div className="grid grid-cols-[1fr_320px] gap-4">
        {/* Left controls */}
        <Card>
          <SectionLabel>Name</SectionLabel>
          <input
            className="input mb-5"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Enter your player name"
            maxLength={48}
          />

          {mode === "gradient" ? (
            <GradientControls stops={stops} setStops={setStops} flags={gFlags} setFlags={setGFlags} />
          ) : (
            <PerLetterControls letters={letters.slice(0, name.length)} setLetters={setLetters} />
          )}
        </Card>

        {/* Right: shared options + output */}
        <div className="flex flex-col gap-4">
          <Card>
            <SectionLabel>Sizing (optional)</SectionLabel>
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="mb-1 block text-[11px]" style={{ color: "var(--text-dim)" }}>Font size</label>
                <input className="input" value={size} onChange={(e) => setSize(e.target.value.replace(/\D/g, ""))} placeholder="auto" inputMode="numeric" />
              </div>
              <div>
                <label className="mb-1 block text-[11px]" style={{ color: "var(--text-dim)" }}>Char spacing</label>
                <input className="input" value={spacing} onChange={(e) => setSpacing(e.target.value)} placeholder="0" />
              </div>
            </div>
          </Card>
          <Card className="flex min-h-0 flex-1 flex-col">
            <SectionLabel>Generated markup</SectionLabel>
            <textarea
              className="input allow-select min-h-[120px] flex-1 font-mono text-[11.5px]"
              readOnly
              value={result.markup}
              placeholder="Your TextMesh Pro markup appears here"
              style={{ fontFamily: "ui-monospace, Consolas, monospace" }}
            />
          </Card>
        </div>
      </div>
    </Page>
  );
}

function GradientControls({
  stops,
  setStops,
  flags,
  setFlags,
}: {
  stops: string[];
  setStops: (s: string[]) => void;
  flags: Flags;
  setFlags: (f: Flags) => void;
}) {
  return (
    <>
      <div className="mb-5 flex items-center justify-between">
        <SectionLabel>Color stops</SectionLabel>
        {stops.length < 5 && (
          <button className="btn btn-ghost btn-sm" onClick={() => setStops([...stops, "#00D4AA"])}>
            <Plus size={14} /> Add
          </button>
        )}
      </div>
      <div className="mb-5 flex flex-col gap-2">
        {stops.map((c, i) => (
          <div key={i} className="flex items-center gap-2.5">
            <Swatch value={c} onChange={(v) => setStops(stops.map((x, j) => (j === i ? v : x)))} />
            <input
              className="input font-mono text-[12.5px]"
              value={c.toUpperCase()}
              onChange={(e) => setStops(stops.map((x, j) => (j === i ? e.target.value : x)))}
            />
            {stops.length > 2 && (
              <button
                className="grid h-9 w-9 flex-none place-items-center rounded-lg transition-colors"
                style={{ color: "var(--text-dim)", background: "var(--card2)", border: "1px solid var(--border)" }}
                onClick={() => setStops(stops.filter((_, j) => j !== i))}
                aria-label="Remove stop"
              >
                <X size={15} />
              </button>
            )}
          </div>
        ))}
      </div>
      <SectionLabel>Style</SectionLabel>
      <StyleToggles flags={flags} setFlags={setFlags} />
    </>
  );
}

function PerLetterControls({
  letters,
  setLetters,
}: {
  letters: LetterStyle[];
  setLetters: React.Dispatch<React.SetStateAction<LetterStyle[]>>;
}) {
  if (letters.length === 0)
    return <div className="text-[13px]" style={{ color: "var(--text-dim)" }}>Enter a name to edit each letter.</div>;
  return (
    <div className="flex flex-col gap-2">
      <SectionLabel>Per-letter styling</SectionLabel>
      {letters.map((l, i) => (
        <div key={i} className="flex items-center gap-2.5 rounded-[10px] p-1.5" style={{ background: "var(--card2)", border: "1px solid var(--border)" }}>
          <div className="grid h-8 w-8 flex-none place-items-center rounded-md text-[15px] font-bold" style={{ background: "var(--bg)", color: l.color }}>
            {l.char === " " ? "·" : l.char}
          </div>
          <Swatch value={l.color} onChange={(v) => setLetters((p) => p.map((x, j) => (j === i ? { ...x, color: v } : x)))} />
          <input
            className="input font-mono text-[12px]"
            value={l.color.toUpperCase()}
            onChange={(e) => setLetters((p) => p.map((x, j) => (j === i ? { ...x, color: e.target.value } : x)))}
          />
          <StyleToggles
            small
            flags={l}
            setFlags={(f) => setLetters((p) => p.map((x, j) => (j === i ? { ...x, ...f } : x)))}
          />
        </div>
      ))}
    </div>
  );
}

function StyleToggles({
  flags,
  setFlags,
  small,
}: {
  flags: Flags;
  setFlags: (f: Flags) => void;
  small?: boolean;
}) {
  const items: [keyof Flags, typeof Bold][] = [
    ["bold", Bold],
    ["italic", Italic],
    ["underline", Underline],
    ["strike", Strikethrough],
  ];
  const sz = small ? 30 : 40;
  return (
    <div className="flex gap-1.5">
      {items.map(([key, Icon]) => {
        const on = flags[key];
        return (
          <button
            key={key}
            onClick={() => setFlags({ ...flags, [key]: !on })}
            className="grid flex-none place-items-center rounded-lg transition-colors"
            style={{
              width: sz,
              height: sz,
              background: on ? "var(--accent)" : "var(--card2)",
              color: on ? "#fff" : "var(--text-mid)",
              border: `1px solid ${on ? "var(--accent)" : "var(--border)"}`,
            }}
            aria-pressed={on}
            aria-label={key}
          >
            <Icon size={small ? 13 : 15} />
          </button>
        );
      })}
    </div>
  );
}

function Swatch({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label
      className="relative grid h-9 w-9 flex-none cursor-pointer place-items-center rounded-lg"
      style={{ background: value, border: "2px solid var(--border2)" }}
    >
      <input
        type="color"
        value={/^#[0-9a-fA-F]{6}$/.test(value) ? value : "#ffffff"}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 cursor-pointer opacity-0"
      />
    </label>
  );
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="rounded-[9px] px-5 py-1.5 text-[13px] font-semibold transition-colors"
      style={{
        background: active ? "var(--accent)" : "transparent",
        color: active ? "#fff" : "var(--text-mid)",
      }}
    >
      {children}
    </button>
  );
}

function seedLetters(name: string): LetterStyle[] {
  return [...name].map((ch, i) => ({ char: ch, color: rainbow(i, name.length), ...NO_FLAGS }));
}
function rainbow(i: number, n: number): string {
  const hue = n <= 1 ? 270 : (i / n) * 320;
  return hslToHex(hue, 85, 60);
}
function hslToHex(h: number, s: number, l: number): string {
  s /= 100; l /= 100;
  const k = (n: number) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  const c = (n: number) => Math.round(255 * f(n)).toString(16).padStart(2, "0");
  return `#${c(0)}${c(8)}${c(4)}`.toUpperCase();
}
