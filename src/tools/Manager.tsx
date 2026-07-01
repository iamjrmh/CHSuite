import { useEffect, useRef, useState, useCallback } from "react";
import {
  Boxes,
  Play,
  FolderOpen,
  Star,
  ShieldCheck,
  RotateCcw,
  Trash2,
  RefreshCw,
  Download,
  Plus,
  Pencil,
} from "lucide-react";
import { Page, Card, EmptyState, Spinner, pickFolder } from "../components/ui";
import { useToast } from "../components/Toast";
import { api, ApiError } from "../lib/api";
import type { Install } from "../lib/types";

interface Release {
  tag: string;
  name: string;
  prerelease: boolean;
  publishedAt: string;
  asset: { name: string; url: string; size: number };
}

interface InstallJob {
  status: "running" | "done" | "error";
  phase: string;
  downloaded: number;
  total: number;
  dest: string;
  message?: string;
  error?: string;
  copiedUserData?: string[];
  copiedBackgrounds?: string[];
}

type TabId = "installs" | "release" | "ptb";
const POLL_MS = 350;

export function Manager() {
  const toast = useToast();
  const [tab, setTab] = useState<TabId>("installs");
  const [installs, setInstalls] = useState<Install[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const [releases, setReleases] = useState<Release[] | null>(null);
  const [ptb, setPtb] = useState<Release[] | null>(null);
  const [relLoading, setRelLoading] = useState(false);

  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const [installingTag, setInstallingTag] = useState<string | null>(null);
  const [installJob, setInstallJob] = useState<InstallJob | null>(null);
  const installPollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (installPollRef.current) window.clearInterval(installPollRef.current);
    };
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ installs: Install[] }>("/manager/installs");
      setInstalls(res.installs);
    } catch (e) {
      toast.error("Could not read installs", (e as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function loadReleases() {
    if (releases) return;
    setRelLoading(true);
    try {
      const res = await api.get<{ releases: Release[]; ptb: Release[] }>("/manager/releases");
      setReleases(res.releases);
      setPtb(res.ptb);
    } catch (e) {
      toast.error("Could not fetch releases", (e as ApiError).message);
    } finally {
      setRelLoading(false);
    }
  }

  useEffect(() => {
    if (tab === "release" || tab === "ptb") loadReleases();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function action(path: string, endpoint: string, label: string, body?: object) {
    setBusy(path + endpoint);
    try {
      await api.post(endpoint, { path, ...body });
      toast.success(label);
      await refresh();
    } catch (e) {
      toast.error("Action failed", (e as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  function startRename(inst: Install) {
    setRenaming(inst.path);
    setRenameValue(inst.name || "");
  }

  async function confirmRename(path: string) {
    const name = renameValue.trim();
    try {
      await api.post("/manager/rename", { path, name });
      setRenaming(null);
      await refresh();
    } catch (e) {
      toast.error("Rename failed", (e as ApiError).message);
    }
  }

  async function startInstall(release: Release, dest?: string) {
    setInstallingTag(release.tag);
    try {
      const res = await api.post<{ jobId: string }>("/manager/install", {
        tag: release.tag,
        name: release.asset.name,
        url: release.asset.url,
        size: release.asset.size,
        dest,
      });
      pollInstall(res.jobId);
    } catch (e) {
      const err = e as ApiError;
      if (err.code === "no_dest") {
        const folder = await pickFolder(`Choose where to install ${release.name || release.tag}`);
        if (folder) {
          startInstall(release, folder);
          return;
        }
      } else {
        toast.error("Install failed", err.message);
      }
      setInstallingTag(null);
    }
  }

  function pollInstall(jobId: string) {
    if (installPollRef.current) window.clearInterval(installPollRef.current);
    installPollRef.current = window.setInterval(async () => {
      try {
        const job = await api.post<InstallJob>("/manager/install/status", { jobId });
        setInstallJob(job);
        if (job.status !== "running") {
          window.clearInterval(installPollRef.current!);
          installPollRef.current = null;
          setInstallingTag(null);
          if (job.status === "done") {
            const copied = job.copiedUserData?.length;
            const copiedBgs = job.copiedBackgrounds?.length;
            const extras = [
              copied ? `${copied} save item${copied === 1 ? "" : "s"}` : null,
              copiedBgs ? `${copiedBgs} menu background${copiedBgs === 1 ? "" : "s"}` : null,
            ].filter(Boolean);
            toast.success("Install complete", extras.length ? `${job.dest} · carried over ${extras.join(" & ")}` : job.dest);
            await refresh();
            setTab("installs");
            setTimeout(() => setInstallJob(null), 3000);
          } else {
            toast.error("Install failed", job.error || "Unknown error");
            setInstallJob(null);
          }
        }
      } catch (e) {
        window.clearInterval(installPollRef.current!);
        installPollRef.current = null;
        setInstallingTag(null);
        toast.error("Install failed", (e as ApiError).message);
        setInstallJob(null);
      }
    }, POLL_MS);
  }

  async function addExisting() {
    const folder = await pickFolder("Select a Clone Hero install folder");
    if (!folder) return;
    try {
      const res = await api.post<{ message: string; added: boolean }>("/manager/add", { path: folder });
      toast[res.added ? "success" : "info"]("Add install", res.message);
      await refresh();
    } catch (e) {
      toast.error("Could not add install", (e as ApiError).message);
    }
  }

  return (
    <Page
      title="CHManager"
      subtitle="Manage installs and download builds from GitHub"
      icon={<Boxes size={20} />}
      actions={
        tab === "installs" ? (
          <>
            <button className="btn btn-ghost" onClick={addExisting}><Plus size={15} /> Add existing</button>
            <button className="btn btn-ghost" onClick={refresh} disabled={loading}>{loading ? <Spinner size={15} /> : <RefreshCw size={15} />} Refresh</button>
          </>
        ) : (
          <button className="btn btn-ghost" onClick={() => { setReleases(null); setPtb(null); loadReleases(); }} disabled={relLoading}>
            {relLoading ? <Spinner size={15} /> : <RefreshCw size={15} />} Refresh
          </button>
        )
      }
    >
      <div className="mb-4 inline-flex rounded-[12px] p-1" style={{ background: "var(--card2)", border: "1px solid var(--border)" }}>
        <Tab active={tab === "installs"} onClick={() => setTab("installs")}>Local installs</Tab>
        <Tab active={tab === "release"} onClick={() => setTab("release")}>Releases</Tab>
        <Tab active={tab === "ptb"} onClick={() => setTab("ptb")}>PTB</Tab>
      </div>

      {tab === "installs" ? (
        loading ? (
          <Card className="flex items-center justify-center gap-3 py-10"><Spinner /> <span style={{ color: "var(--text-mid)" }}>Loading installs…</span></Card>
        ) : installs.length === 0 ? (
          <EmptyState icon={<Boxes size={26} />} title="No installs found" hint="Register an existing install, or download a fresh build from the Releases tab." action={<button className="btn btn-primary" onClick={addExisting}><Plus size={15} /> Add existing install</button>} />
        ) : (
          <div className="flex flex-col gap-2.5">
            {installs.map((inst) => {
              const patched = !inst.fromLauncher;
              return (
                <Card key={inst.path} className="flex items-center gap-3">
                  <div className="grid h-11 w-11 flex-none place-items-center rounded-[12px]" style={{ background: "var(--card2)", border: "1px solid var(--border2)", color: inst.isDefault ? "var(--accent)" : "var(--text-mid)" }}>
                    {inst.isDefault ? <Star size={20} fill="var(--accent)" /> : <Boxes size={20} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    {renaming === inst.path ? (
                      <form
                        className="mb-1 flex items-center gap-1.5"
                        onSubmit={(e) => { e.preventDefault(); confirmRename(inst.path); }}
                      >
                        <input
                          autoFocus
                          className="input flex-none"
                          style={{ height: 30, padding: "0 8px", width: 220 }}
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          placeholder={`Clone Hero ${inst.version}`}
                        />
                        <button type="submit" className="btn btn-primary btn-sm">Save</button>
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRenaming(null)}>Cancel</button>
                      </form>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-[14px] font-bold">{inst.name || `Clone Hero ${inst.version}`}</span>
                        {inst.name && <span className="text-[12px]" style={{ color: "var(--text-dim)" }}>v{inst.version}</span>}
                        {inst.isDefault && <span className="badge badge-ok">★ default</span>}
                        <span className={patched ? "badge badge-ok" : "badge"}>{patched ? "Manual" : "Launcher"}</span>
                        {!inst.exists && <span className="badge badge-warn">exe missing</span>}
                      </div>
                    )}
                    <div className="truncate text-[11.5px]" style={{ color: "var(--text-dim)", fontFamily: "ui-monospace, Consolas, monospace" }}>{inst.path}</div>
                  </div>
                  <div className="flex flex-none gap-1.5">
                    <IconBtn label="Launch" onClick={() => action(inst.path, "/manager/launch", "Launching Clone Hero")} disabled={!inst.exists || !!busy}><Play size={16} /></IconBtn>
                    <IconBtn label="Rename" onClick={() => startRename(inst)}><Pencil size={16} /></IconBtn>
                    <IconBtn label="Open folder" onClick={() => action(inst.path, "/manager/open-folder", "Opened folder")}><FolderOpen size={16} /></IconBtn>
                    {!inst.isDefault && <IconBtn label="Set default" onClick={() => action(inst.path, "/manager/set-default", "Set as default")}><Star size={16} /></IconBtn>}
                    {patched ? (
                      <IconBtn label="Unpatch" onClick={() => action(inst.path, "/patcher/unpatch", "Unpatched")}><RotateCcw size={16} /></IconBtn>
                    ) : (
                      <IconBtn label="Patch" onClick={() => action(inst.path, "/patcher/patch", "Patched")}><ShieldCheck size={16} /></IconBtn>
                    )}
                    <IconBtn label="Delete install" danger onClick={() => action(inst.path, "/manager/delete", "Deleted install")}><Trash2 size={16} /></IconBtn>
                  </div>
                </Card>
              );
            })}
          </div>
        )
      ) : (
        <ReleaseList
          loading={relLoading}
          releases={(tab === "release" ? releases : ptb) || []}
          installingTag={installingTag}
          installJob={installJob}
          onInstall={startInstall}
        />
      )}
    </Page>
  );
}

function ReleaseList({
  loading,
  releases,
  installingTag,
  installJob,
  onInstall,
}: {
  loading: boolean;
  releases: Release[];
  installingTag: string | null;
  installJob: InstallJob | null;
  onInstall: (r: Release) => void;
}) {
  if (loading) return <Card className="flex items-center justify-center gap-3 py-10"><Spinner /> <span style={{ color: "var(--text-mid)" }}>Fetching from GitHub…</span></Card>;
  if (releases.length === 0) return <EmptyState icon={<Download size={26} />} title="No builds found" hint="Couldn't find matching builds for your system architecture." />;
  return (
    <div className="flex flex-col gap-2.5">
      {releases.slice(0, 30).map((r) => {
        const isThis = installingTag === r.tag;
        const blocked = installingTag !== null && !isThis;
        return (
          <Card key={r.tag} className="flex flex-col gap-2.5">
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[14px] font-bold">{r.name || r.tag}</span>
                  {r.prerelease && <span className="badge badge-warn">PTB</span>}
                </div>
                <div className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
                  {r.publishedAt?.slice(0, 10)} · {(r.asset.size / 1_048_576).toFixed(1)} MB · {r.asset.name}
                </div>
              </div>
              <button className="btn btn-primary" onClick={() => onInstall(r)} disabled={isThis || blocked}>
                {isThis ? <Spinner size={15} /> : <Download size={15} />} {isThis ? "Installing…" : "Install"}
              </button>
            </div>
            {isThis && installJob && (
              <div>
                <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--card2)" }}>
                  <div
                    className="h-full rounded-full transition-[width]"
                    style={{
                      width: `${installJob.total ? Math.min(100, (installJob.downloaded / installJob.total) * 100) : installJob.phase === "downloading" ? 0 : 100}%`,
                      background: "var(--accent)",
                    }}
                  />
                </div>
                <div className="mt-1.5 truncate text-[11.5px]" style={{ color: "var(--text-mid)" }}>{installJob.message}</div>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function IconBtn({ children, label, onClick, danger, disabled }: { children: React.ReactNode; label: string; onClick: () => void; danger?: boolean; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      disabled={disabled}
      className="grid h-9 w-9 place-items-center rounded-lg transition-colors disabled:opacity-40"
      style={{ background: "var(--card2)", border: "1px solid var(--border)", color: danger ? "var(--error)" : "var(--text-mid)" }}
      onMouseEnter={(e) => { if (!disabled) { e.currentTarget.style.background = danger ? "color-mix(in srgb, var(--error) 20%, var(--card2))" : "var(--hover)"; e.currentTarget.style.color = danger ? "#fff" : "var(--text)"; } }}
      onMouseLeave={(e) => { e.currentTarget.style.background = "var(--card2)"; e.currentTarget.style.color = danger ? "var(--error)" : "var(--text-mid)"; }}
    >
      {children}
    </button>
  );
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className="rounded-[9px] px-5 py-1.5 text-[13px] font-semibold transition-colors" style={{ background: active ? "var(--accent)" : "transparent", color: active ? "#fff" : "var(--text-mid)" }}>
      {children}
    </button>
  );
}
