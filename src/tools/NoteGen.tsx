import { useEffect, useMemo, useRef, useState } from "react";
import { Palette, Download, RotateCcw, Search } from "lucide-react";
import { Page, Card, SectionLabel, Spinner } from "../components/ui";
import { HighwayPreview } from "../components/HighwayPreview";
import { ColorPicker } from "../components/ColorPicker";
import { useToast } from "../components/Toast";
import { api, ApiError } from "../lib/api";

type Colors = Record<string, Record<string, string>>;
interface NoteGenData {
  _NG_DEFAULT_COLORS: Colors;
  _NG_FRIENDLY: Record<string, string>;
  _SECTION_ORDER: string[];
}
interface Profile {
  name: string;
  colors: Colors;
}

const DEFAULT_PROFILE = "Default";
const NEW_PROFILE_OPTION = "__new__";

const TAB_ORDER = ["guitar", "sixfret", "drums", "other"];

const SECTION_LABELS: Record<string, string> = {
  guitar: "Guitar",
  drums: "Drums",
  sixfret: "6-Fret",
  other: "Effects",
};

/** The primary strike-color keys (Note/Cymbal/Tom/Kick), excluding animation, overlay, and tap variants. */
function isPrimaryNoteKey(section: string, key: string): boolean {
  if (key.includes("_anim_") || key.startsWith("note_anim_")) return false;
  if (key.includes("_overlay_") || key.startsWith("note_overlay_")) return false;
  if (key.includes("_tap_")) return false;
  switch (section) {
    case "guitar":
      return key.startsWith("note_");
    case "drums":
      return key.startsWith("note_kick") || key.startsWith("cym_") || key.startsWith("tom_");
    case "sixfret":
      return key.startsWith("sf_note_");
    default:
      return false;
  }
}

export function NoteGen() {
  const toast = useToast();
  const [data, setData] = useState<NoteGenData | null>(null);
  const [colors, setColors] = useState<Colors>({});
  const [section, setSection] = useState("guitar");
  const [profileName, setProfileName] = useState(DEFAULT_PROFILE);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [creatingProfile, setCreatingProfile] = useState(false);
  const [newProfileName, setNewProfileName] = useState("");
  const [filter, setFilter] = useState("");
  const [exporting, setExporting] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);
  const [previewHeight, setPreviewHeight] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/assets/notegen_data.json");
        const json = (await res.json()) as NoteGenData;
        setData(json);
        setColors(structuredClone(json._NG_DEFAULT_COLORS));
        const order = json._SECTION_ORDER || Object.keys(json._NG_DEFAULT_COLORS);
        setSection(order.includes("guitar") ? "guitar" : order[0]);
      } catch {
        toast.error("Could not load note color data");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Size the sticky preview panel to fill the remaining viewport height, so it
  // reads as a persistent full-height panel like the original rather than a
  // small fixed box. `data` starts null and the row (with rowRef) doesn't
  // exist in the DOM until it loads, so this must re-run once data arrives -
  // an empty dep array would measure a null ref on the loading placeholder
  // and never fire again.
  useEffect(() => {
    const el = rowRef.current;
    if (!el) return;
    const update = () => {
      const rect = el.getBoundingClientRect();
      setPreviewHeight(Math.max(360, window.innerHeight - rect.top - 32));
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [data]);

  // Auto-detect saved colour profiles the same way the original CHSuite does -
  // scanning Clone Hero's Custom/Colors folders for exported .ini files.
  useEffect(() => {
    (async () => {
      setProfilesLoading(true);
      try {
        const res = await api.get<{ profiles: Profile[] }>("/notegen/profiles");
        setProfiles(res.profiles);
      } catch {
        // Best-effort - Clone Hero may not be installed/detected yet.
      } finally {
        setProfilesLoading(false);
      }
    })();
  }, []);

  const sections = useMemo(() => TAB_ORDER.filter((s) => colors[s]), [colors]);

  const keys = useMemo(() => {
    if (!data || !colors[section]) return [];
    const q = filter.trim().toLowerCase();
    const filtered = Object.keys(colors[section]).filter((k) => {
      if (!q) return true;
      const label = (data._NG_FRIENDLY[k] || k).toLowerCase();
      return label.includes(q) || k.toLowerCase().includes(q);
    });
    return filtered.sort((a, b) => Number(isPrimaryNoteKey(section, b)) - Number(isPrimaryNoteKey(section, a)));
  }, [data, colors, section, filter]);

  function setColor(sec: string, key: string, value: string) {
    setColors((c) => ({ ...c, [sec]: { ...c[sec], [key]: value } }));
  }

  function reset() {
    if (data) setColors(structuredClone(data._NG_DEFAULT_COLORS));
    toast.info("Reset to defaults");
  }

  function loadProfile(name: string) {
    if (name === NEW_PROFILE_OPTION) {
      setNewProfileName(profileName === DEFAULT_PROFILE ? "" : profileName);
      setCreatingProfile(true);
      return;
    }
    if (!data) return;
    if (name === DEFAULT_PROFILE) {
      setColors(structuredClone(data._NG_DEFAULT_COLORS));
      setProfileName(DEFAULT_PROFILE);
      return;
    }
    const profile = profiles.find((p) => p.name === name);
    if (!profile) return;
    const merged = structuredClone(data._NG_DEFAULT_COLORS);
    for (const sec of Object.keys(merged)) {
      if (profile.colors[sec]) Object.assign(merged[sec], profile.colors[sec]);
    }
    setColors(merged);
    setProfileName(name);
  }

  function confirmNewProfile() {
    const name = newProfileName.trim();
    if (name) setProfileName(name);
    setCreatingProfile(false);
  }

  async function doExport() {
    setExporting(true);
    try {
      const res = await api.post<{ path: string }>("/notegen/export", { colors, profileName });
      toast.success("Colors exported", res.path);
      if (profileName && profileName !== DEFAULT_PROFILE && !profiles.some((p) => p.name === profileName)) {
        setProfiles((p) => [...p, { name: profileName, colors: structuredClone(colors) }]);
      }
    } catch (e) {
      toast.error("Export failed", (e as ApiError).message);
    } finally {
      setExporting(false);
    }
  }

  if (!data) {
    return (
      <Page title="CHNoteGen" subtitle="Design custom note colors" icon={<Palette size={20} />}>
        <Card className="flex items-center justify-center gap-3 py-10"><Spinner /> <span style={{ color: "var(--text-mid)" }}>Loading color palette…</span></Card>
      </Page>
    );
  }

  const previewColors = (section === "other" ? colors.guitar : colors[section]) || {};

  return (
    <Page
      title="CHNoteGen"
      subtitle="Design custom note colors and export a color profile"
      icon={<Palette size={20} />}
      actions={
        <>
          <button className="btn btn-ghost" onClick={reset}><RotateCcw size={15} /> Reset</button>
          <button className="btn btn-primary" onClick={doExport} disabled={exporting}>
            {exporting ? <Spinner size={15} /> : <Download size={15} />} Export
          </button>
        </>
      }
    >
      <div ref={rowRef} className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <Card className="mb-4">
            <SectionLabel>Profile</SectionLabel>
            {creatingProfile ? (
              <div className="flex gap-2.5">
                <input
                  autoFocus
                  className="input flex-1"
                  value={newProfileName}
                  onChange={(e) => setNewProfileName(e.target.value)}
                  placeholder="New profile name"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") confirmNewProfile();
                    if (e.key === "Escape") setCreatingProfile(false);
                  }}
                />
                <button className="btn btn-ghost flex-none" onClick={() => setCreatingProfile(false)}>Cancel</button>
                <button className="btn btn-primary flex-none" onClick={confirmNewProfile}>Save</button>
              </div>
            ) : (
              <select className="select" value={profileName} onChange={(e) => loadProfile(e.target.value)}>
                <option value={DEFAULT_PROFILE}>{DEFAULT_PROFILE}</option>
                {profiles.map((p) => (
                  <option key={p.name} value={p.name}>{p.name}</option>
                ))}
                {profileName !== DEFAULT_PROFILE && !profiles.some((p) => p.name === profileName) && (
                  <option value={profileName}>{profileName} (unsaved)</option>
                )}
                <option value={NEW_PROFILE_OPTION}>+ New profile…</option>
              </select>
            )}
            <div className="mt-1 text-[11px]" style={{ color: "var(--text-dim)" }}>
              Exports to {profileName || "colors"}.ini in your Clone Hero folder.
              {profilesLoading ? " Detecting profiles…" : profiles.length > 0 ? ` ${profiles.length} profile${profiles.length === 1 ? "" : "s"} detected.` : ""}
            </div>
          </Card>

          {/* Section tabs + search */}
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="inline-flex rounded-[12px] p-1" style={{ background: "var(--card2)", border: "1px solid var(--border)" }}>
              {sections.map((s) => (
                <button
                  key={s}
                  onClick={() => setSection(s)}
                  className="rounded-[9px] px-4 py-1.5 text-[13px] font-semibold transition-colors"
                  style={{ background: section === s ? "var(--accent)" : "transparent", color: section === s ? "#fff" : "var(--text-mid)" }}
                >
                  {SECTION_LABELS[s] || s}
                </button>
              ))}
            </div>
            <div className="relative w-64">
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-dim)" }} />
              <input className="input" style={{ paddingLeft: 36 }} value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter colors…" />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2">
            {keys.map((key) => {
              const val = colors[section][key];
              return (
                <div key={key} className="flex items-center gap-2.5 rounded-[10px] px-2.5 py-1.5" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12px] font-medium">{data._NG_FRIENDLY[key] || key}</div>
                    <div className="truncate text-[10px]" style={{ color: "var(--text-dim)", fontFamily: "ui-monospace, Consolas, monospace" }}>{key}</div>
                  </div>
                  <div className="flex flex-none items-center gap-1.5">
                    <ColorPicker value={val} onChange={(hex) => setColor(section, key, hex)} />
                    <input
                      className="input flex-none font-mono text-[11px]"
                      style={{ width: 92, height: 30, padding: "0 8px" }}
                      value={val}
                      onChange={(e) => setColor(section, key, e.target.value.toUpperCase())}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="sticky top-0 w-[360px] flex-none" style={{ height: previewHeight ?? 560 }}>
          <Card pad={false} className="flex h-full flex-col overflow-hidden">
            <div className="flex-none px-4 pt-4 pb-2">
              <SectionLabel>Live preview</SectionLabel>
            </div>
            <div className="min-h-0 flex-1 px-4 pb-4">
              <div
                className="h-full w-full overflow-hidden rounded-xl"
                style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
              >
                <HighwayPreview section={section === "other" ? "guitar" : section} colors={previewColors} />
              </div>
            </div>
          </Card>
        </div>
      </div>
    </Page>
  );
}
