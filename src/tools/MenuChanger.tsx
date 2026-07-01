import { useEffect, useState } from "react";
import {
  Image as ImageIcon,
  Save,
  RotateCcw,
  ImagePlus,
  X,
  Check,
  AlertCircle,
} from "lucide-react";
import { Page, Card, PathPicker, EmptyState, Spinner, pickFolder, pickFile } from "../components/ui";
import { useToast } from "../components/Toast";
import { api, ApiError } from "../lib/api";
import { useConfig } from "../lib/config-context";
import type { Background } from "../lib/types";

export function MenuChanger() {
  const toast = useToast();
  const { config, update } = useConfig();
  const [dataDir, setDataDir] = useState("");
  const [backgrounds, setBackgrounds] = useState<Background[]>([]);
  const [hasBackup, setHasBackup] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [applying, setApplying] = useState(false);
  const [restoring, setRestoring] = useState(false);
  // background name -> chosen replacement image path
  const [replacements, setReplacements] = useState<Record<string, string>>({});

  useEffect(() => {
    if (config?.default_data_path) setDataDir(config.default_data_path);
  }, [config?.default_data_path]);

  async function pickDir() {
    const d = await pickFolder("Select your Clone Hero_Data folder");
    if (d) {
      setDataDir(d);
      update({ default_data_path: d });
    }
  }

  async function scan() {
    if (!dataDir) return;
    setScanning(true);
    try {
      const res = await api.post<{ backgrounds: Background[]; hasBackup: boolean; backupsCreated: number }>(
        "/menu/scan",
        { dataDir, previews: true },
      );
      setBackgrounds(res.backgrounds);
      setHasBackup(res.hasBackup);
      setScanned(true);
      const matched = res.backgrounds.filter((b) => b.matched).length;
      toast.success(`Scanned ${matched} backgrounds`, res.backupsCreated ? `${res.backupsCreated} files backed up` : "Backups already present");
    } catch (e) {
      toast.error("Scan failed", (e as ApiError).message);
    } finally {
      setScanning(false);
    }
  }

  useEffect(() => {
    if (dataDir) scan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataDir]);

  async function chooseReplacement(bg: Background) {
    const f = await pickFile(`Replacement for ${bg.name}`, [
      { name: "Images", extensions: ["png", "jpg", "jpeg", "webp", "bmp"] },
    ]);
    if (f) setReplacements((p) => ({ ...p, [bg.name]: f }));
  }

  async function apply() {
    const reps = Object.entries(replacements).map(([background, imagePath]) => ({ background, imagePath }));
    if (reps.length === 0) {
      toast.warn("Nothing to apply", "Choose at least one replacement image.");
      return;
    }
    setApplying(true);
    try {
      const res = await api.post<{ applied: string[]; saved: number; errors: { background: string; error: string }[] }>(
        "/menu/apply",
        { dataDir, replacements: reps },
      );
      if (res.applied.length) {
        toast.success(`Applied ${res.applied.length} background${res.applied.length === 1 ? "" : "s"}`, "Open Clone Hero to see the result.");
        setReplacements({});
        await scan();
      }
      res.errors.forEach((er) => toast.error(`${er.background}`, er.error));
    } catch (e) {
      toast.error("Apply failed", (e as ApiError).message);
    } finally {
      setApplying(false);
    }
  }

  async function restore() {
    setRestoring(true);
    try {
      const res = await api.post<{ restored: number }>("/menu/restore", { dataDir });
      toast.success(`Restored ${res.restored} file${res.restored === 1 ? "" : "s"}`, "Originals are back in place.");
      setReplacements({});
      await scan();
    } catch (e) {
      toast.error("Restore failed", (e as ApiError).message);
    } finally {
      setRestoring(false);
    }
  }

  const repCount = Object.keys(replacements).length;

  return (
    <Page
      title="CHMenuChanger"
      subtitle="Swap Clone Hero's menu background textures"
      icon={<ImageIcon size={20} />}
      actions={
        scanned ? (
          <>
            <button className="btn btn-ghost" onClick={restore} disabled={restoring || !hasBackup}>
              {restoring ? <Spinner size={15} /> : <RotateCcw size={15} />} Restore originals
            </button>
            <button className="btn btn-primary" onClick={apply} disabled={applying || repCount === 0}>
              {applying ? <Spinner size={15} /> : <Save size={15} />} Apply {repCount > 0 ? `(${repCount})` : ""}
            </button>
          </>
        ) : null
      }
    >
      <Card className="mb-4">
        <PathPicker label="Clone Hero_Data folder" value={dataDir} placeholder="e.g. …\Clone Hero\Clone Hero_Data" onPick={pickDir} />
      </Card>

      {scanning ? (
        <div className="grid grid-cols-3 gap-3.5">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-48" />)}
        </div>
      ) : !scanned ? (
        <EmptyState
          icon={<ImageIcon size={26} />}
          title="No assets scanned yet"
          hint="Select your Clone Hero_Data folder to get started. Originals are automatically backed up the first time."
        />
      ) : (
        <div className="grid grid-cols-3 gap-3.5">
          {backgrounds.map((bg) => (
            <BackgroundCard
              key={bg.name}
              bg={bg}
              replacement={replacements[bg.name]}
              onChoose={() => chooseReplacement(bg)}
              onClear={() => setReplacements((p) => { const n = { ...p }; delete n[bg.name]; return n; })}
            />
          ))}
        </div>
      )}
    </Page>
  );
}

function BackgroundCard({
  bg,
  replacement,
  onChoose,
  onClear,
}: {
  bg: Background;
  replacement?: string;
  onChoose: () => void;
  onClear: () => void;
}) {
  return (
    <Card pad={false} className="overflow-hidden">
      <div className="relative aspect-video w-full overflow-hidden" style={{ background: "var(--bg)" }}>
        {replacement ? (
          <div
            className="grid h-full w-full place-items-center px-3 text-center"
            style={{
              background:
                "linear-gradient(135deg, color-mix(in srgb, var(--accent) 26%, var(--card)), var(--card))",
            }}
          >
            <div>
              <ImagePlus size={22} style={{ color: "var(--accent)", margin: "0 auto 6px" }} />
              <div className="truncate text-[11px] font-semibold" style={{ maxWidth: 180 }}>
                {replacement.split(/[\\/]/).pop()}
              </div>
              <div className="mt-0.5 text-[10px]" style={{ color: "var(--text-mid)" }}>ready to apply</div>
            </div>
          </div>
        ) : bg.preview ? (
          <img src={bg.preview} alt={bg.name} className="h-full w-full object-cover" draggable={false} />
        ) : (
          <div className="grid h-full w-full place-items-center" style={{ color: "var(--text-dim)" }}>
            {bg.matched ? <Spinner /> : <div className="flex flex-col items-center gap-1.5 text-[11px]"><AlertCircle size={20} /> No texture matched</div>}
          </div>
        )}
        {replacement && (
          <div className="absolute right-2 top-2 flex items-center gap-1 rounded-full px-2 py-1 text-[10.5px] font-semibold" style={{ background: "var(--accent)", color: "#fff" }}>
            <Check size={11} /> New
          </div>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 px-3 py-2.5">
        <div className="min-w-0">
          <div className="truncate text-[13px] font-bold">{bg.name}</div>
          <div className="text-[10.5px]" style={{ color: "var(--text-dim)" }}>
            {bg.requiredSize[0]}×{bg.requiredSize[1]}
          </div>
        </div>
        {replacement ? (
          <button className="grid h-8 w-8 flex-none place-items-center rounded-lg" style={{ background: "var(--card2)", border: "1px solid var(--border)", color: "var(--text-dim)" }} onClick={onClear} aria-label="Clear replacement">
            <X size={15} />
          </button>
        ) : (
          <button className="btn btn-ghost btn-sm flex-none" onClick={onChoose} disabled={!bg.matched}>
            <ImagePlus size={14} /> Replace
          </button>
        )}
      </div>
    </Card>
  );
}
