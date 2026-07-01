import { useEffect, useState } from "react";
import { Settings as SettingsIcon, Check, Wand2, RefreshCw, ExternalLink } from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { Page, Card, SectionLabel, PathPicker, Spinner, pickFolder } from "../components/ui";
import { useToast } from "../components/Toast";
import { useConfig } from "../lib/config-context";
import { useUpdateCheck } from "../lib/update-context";
import { listThemes, themeSwatch } from "../lib/theme";
import { api, ApiError } from "../lib/api";

export function SettingsView() {
  const toast = useToast();
  const { config, changeTheme, update } = useConfig();
  const { checking, result, checkNow } = useUpdateCheck();
  const [themes, setThemes] = useState<string[]>([]);
  const [swatches, setSwatches] = useState<Record<string, { accent: string; accent2: string; bg: string; card: string }>>({});
  const [detecting, setDetecting] = useState(false);

  useEffect(() => {
    (async () => {
      const names = await listThemes();
      setThemes(names);
      const sw: typeof swatches = {};
      await Promise.all(
        names.map(async (n) => {
          const s = await themeSwatch(n);
          if (s) sw[n] = s;
        }),
      );
      setSwatches(sw);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const current = config?.theme || "Default";

  async function detect() {
    setDetecting(true);
    try {
      const res = await api.post<{ documents: string; installs: { path: string }[] }>("/config/detect", {});
      const found: string[] = [];
      if (res.documents) found.push("Documents folder");
      if (res.installs.length) found.push(`${res.installs.length} install(s)`);
      toast.success("Detection complete", found.length ? found.join(" · ") : "Nothing auto-detected");
    } catch (e) {
      toast.error("Detection failed", (e as ApiError).message);
    } finally {
      setDetecting(false);
    }
  }

  return (
    <Page
      title="Settings"
      subtitle="Themes and Clone Hero preferences"
      icon={<SettingsIcon size={20} />}
      actions={
        <button className="btn btn-ghost" onClick={detect} disabled={detecting}>
          {detecting ? <Spinner size={15} /> : <Wand2 size={15} />} Auto-detect
        </button>
      }
    >
      <Card className="mb-4">
        <div className="mb-3 flex items-center justify-between">
          <SectionLabel>Theme</SectionLabel>
          <span className="text-[12px]" style={{ color: "var(--text-dim)" }}>{themes.length} themes · {current}</span>
        </div>
        <div className="grid grid-cols-4 gap-2.5">
          {themes.map((name) => {
            const sw = swatches[name];
            const active = name === current;
            return (
              <button
                key={name}
                onClick={() => changeTheme(name)}
                className="group relative overflow-hidden rounded-[12px] p-0 text-left transition-colors"
                style={{ border: `1.5px solid ${active ? "var(--accent)" : "var(--border)"}` }}
              >
                <div className="flex h-14 w-full" style={{ background: sw?.bg || "var(--card)" }}>
                  <div className="m-auto flex gap-1.5">
                    <span className="h-6 w-6 rounded-full" style={{ background: sw?.accent || "#6c3bff" }} />
                    <span className="h-6 w-6 rounded-full" style={{ background: sw?.accent2 || "#ff3b8a" }} />
                    <span className="h-6 w-6 rounded-full" style={{ background: sw?.card || "#181c28", border: "1px solid rgba(255,255,255,0.1)" }} />
                  </div>
                </div>
                <div className="flex items-center justify-between px-2.5 py-2" style={{ background: "var(--card)" }}>
                  <span className="truncate text-[11.5px] font-semibold">{name}</span>
                  {active && <Check size={14} style={{ color: "var(--accent)", flex: "none" }} />}
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      <Card className="mb-4">
        <SectionLabel>Clone Hero paths</SectionLabel>
        <div className="mt-2 flex flex-col gap-4">
          <PathPicker
            label="Default Clone Hero_Data folder"
            value={config?.default_data_path || ""}
            placeholder="Used by CHMenuChanger"
            onPick={async () => { const d = await pickFolder("Select Clone Hero_Data"); if (d) update({ default_data_path: d }); }}
          />
          <PathPicker
            label="Default install folder"
            value={config?.ch_default_install || ""}
            placeholder="Used by CHManager / Launch"
            onPick={async () => { const d = await pickFolder("Select Clone Hero install"); if (d) update({ ch_default_install: d }); }}
          />
          <PathPicker
            label="Songs folder"
            value={config?.sm_songs_dir || ""}
            placeholder="Where CHSongManager saves charts"
            onPick={async () => { const d = await pickFolder("Select songs folder"); if (d) update({ sm_songs_dir: d }); }}
          />
          <PathPicker
            label="Auto-install location"
            value={config?.default_install_dir || ""}
            placeholder="Where CHManager installs new releases/PTB builds - each version gets its own subfolder"
            onPick={async () => { const d = await pickFolder("Select where new Clone Hero versions should be installed"); if (d) update({ default_install_dir: d }); }}
          />
        </div>
      </Card>

      <Card>
        <SectionLabel>About</SectionLabel>
        <div className="mt-1 flex items-center gap-3">
          <img src="/assets/images/logo.png" alt="" className="h-12 w-12 flex-none rounded-xl" draggable={false} />
          <div className="min-w-0 flex-1 text-[13px]">
            <div className="font-bold">CHSuite v8.0.0</div>
            <div style={{ color: "var(--text-dim)" }}>Rebuilt with Tauri · React · a Python sidecar. Made with 🎸 by JURMR.</div>
            {result && (
              <div className="mt-1 flex items-center gap-1.5" style={{ color: result.updateAvailable ? "var(--accent)" : "var(--text-dim)" }}>
                <span>{result.updateAvailable ? `Update available: v${result.latest}` : `You're up to date (v${result.current})`}</span>
                {result.updateAvailable && (
                  <button className="inline-flex items-center gap-1 underline" onClick={() => openUrl(result.url)}>
                    View release <ExternalLink size={11} />
                  </button>
                )}
              </div>
            )}
          </div>
          <button className="btn btn-ghost btn-sm flex-none" onClick={() => checkNow(true)} disabled={checking}>
            {checking ? <Spinner size={14} /> : <RefreshCw size={14} />} Check for updates
          </button>
        </div>
      </Card>
    </Page>
  );
}
