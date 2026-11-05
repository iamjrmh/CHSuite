import { useEffect, useState, useCallback } from "react";
import { Wrench, RefreshCw, ShieldCheck, RotateCcw, Cog, Zap, ZapOff } from "lucide-react";
import { Page, Card, EmptyState, Spinner } from "../components/ui";
import { useToast } from "../components/Toast";
import { api, ApiError } from "../lib/api";
import type { Install } from "../lib/types";

export function Patcher() {
  const toast = useToast();
  const [installs, setInstalls] = useState<Install[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [fastAuto, setFastAuto] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ installs: Install[]; fastBootAuto: boolean }>("/patcher/installs");
      setInstalls(res.installs);
      setFastAuto(res.fastBootAuto);
    } catch (e) {
      toast.error("Could not read installs", (e as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function act(install: Install, manual: boolean) {
    setBusy(install.path);
    try {
      const res = await api.post<{ message: string }>(
        manual ? "/patcher/patch" : "/patcher/unpatch",
        { path: install.path },
      );
      toast.success(manual ? "Patched" : "Unpatched", res.message);
      await refresh();
    } catch (e) {
      toast.error("Action failed", (e as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  async function toggleFastBoot(install: Install, enable: boolean) {
    setBusy(`${install.path}#fast`);
    try {
      const res = await api.post<{ message: string }>(
        enable ? "/patcher/fastboot/enable" : "/patcher/fastboot/disable",
        { path: install.path },
      );
      toast.success(enable ? "Fast boot on" : "Fast boot off", res.message);
      await refresh();
    } catch (e) {
      toast.error("Fast boot failed", (e as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  async function setAuto(enabled: boolean) {
    setFastAuto(enabled);
    try {
      await api.post("/patcher/fastboot/auto", { enabled });
      if (enabled) setTimeout(refresh, 1500);
    } catch (e) {
      setFastAuto(!enabled);
      toast.error("Could not save setting", (e as ApiError).message);
    }
  }

  const patchedCount = installs.filter((i) => !i.fromLauncher).length;
  const fastCount = installs.filter((i) => i.fastBoot?.state === "on").length;

  return (
    <Page
      title="CHPatcher"
      subtitle="Stop the launcher from resetting your game files"
      icon={<Wrench size={20} />}
      actions={
        <button className="btn btn-ghost" onClick={refresh} disabled={loading}>
          {loading ? <Spinner size={15} /> : <RefreshCw size={15} />}
          Refresh
        </button>
      }
    >
      {loading ? (
        <Card className="flex items-center justify-center gap-3 py-10"><Spinner /> <span style={{ color: "var(--text-mid)" }}>Reading game_installs.json…</span></Card>
      ) : installs.length === 0 ? (
        <EmptyState
          icon={<Cog size={26} />}
          title="No installs registered"
          hint="No installs were found in game_installs.json. Add one through the Clone Hero Launcher or CHManager, then refresh."
        />
      ) : (
        <>
          <div className="mb-4 flex gap-3">
            <Stat label="Installs" value={installs.length} />
            <Stat label="Patched (Manual)" value={patchedCount} accent />
            <Stat label="Launcher-managed" value={installs.length - patchedCount} />
            <Stat label="Fast boot" value={fastCount} accent />
          </div>
          <Card className="mb-4 flex items-center gap-4">
            <div
              className="grid h-11 w-11 flex-none place-items-center rounded-[12px]"
              style={{ background: "var(--card2)", border: "1px solid var(--border2)", color: "var(--accent)" }}
            >
              <Zap size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[14px] font-bold">Fast boot</div>
              <div className="text-[12px]" style={{ color: "var(--text-mid)" }}>
                Clone Hero opens every .sng file on startup just to check it loads, which takes 30+ minutes for a big
                library on a hard drive. Fast boot skips that check; songs still load normally when you play them.
              </div>
            </div>
            <label className="flex flex-none cursor-pointer items-center gap-2 text-[12.5px] font-semibold">
              <input type="checkbox" checked={fastAuto} onChange={(e) => setAuto(e.target.checked)} />
              Keep on after updates
            </label>
          </Card>
          <div className="flex flex-col gap-2.5">
            {installs.map((inst) => {
              const patched = !inst.fromLauncher;
              const isBusy = busy === inst.path;
              return (
                <Card key={inst.path} className="flex items-center gap-4">
                  <div
                    className="grid h-11 w-11 flex-none place-items-center rounded-[12px]"
                    style={{
                      background: patched ? "color-mix(in srgb, var(--success) 16%, var(--card2))" : "var(--card2)",
                      border: "1px solid var(--border2)",
                      color: patched ? "var(--success)" : "var(--text-mid)",
                    }}
                  >
                    {patched ? <ShieldCheck size={20} /> : <Cog size={20} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] font-bold">Clone Hero {inst.version}</span>
                      <span className={patched ? "badge badge-ok" : "badge"}>
                        {patched ? "✓ Manual" : "⚙ Launcher"}
                      </span>
                      {!inst.exists && <span className="badge badge-warn">exe missing</span>}
                      <FastBootBadge state={inst.fastBoot?.state} reason={inst.fastBoot?.reason} />
                    </div>
                    <div className="truncate text-[11.5px]" style={{ color: "var(--text-dim)", fontFamily: "ui-monospace, Consolas, monospace" }}>{inst.path}</div>
                  </div>
                  {(inst.fastBoot?.state === "on" || inst.fastBoot?.state === "off") && (
                    <button
                      className="btn btn-ghost"
                      onClick={() => toggleFastBoot(inst, inst.fastBoot?.state !== "on")}
                      disabled={busy === `${inst.path}#fast`}
                    >
                      {busy === `${inst.path}#fast` ? (
                        <Spinner size={15} />
                      ) : inst.fastBoot?.state === "on" ? (
                        <ZapOff size={15} />
                      ) : (
                        <Zap size={15} />
                      )}
                      {inst.fastBoot?.state === "on" ? "Fast boot off" : "Fast boot on"}
                    </button>
                  )}
                  {patched ? (
                    <button className="btn btn-ghost" onClick={() => act(inst, false)} disabled={isBusy}>
                      {isBusy ? <Spinner size={15} /> : <RotateCcw size={15} />} Unpatch
                    </button>
                  ) : (
                    <button className="btn btn-primary" onClick={() => act(inst, true)} disabled={isBusy}>
                      {isBusy ? <Spinner size={15} /> : <ShieldCheck size={15} />} Patch
                    </button>
                  )}
                </Card>
              );
            })}
          </div>
        </>
      )}
    </Page>
  );
}

function FastBootBadge({ state, reason }: { state?: string; reason?: string }) {
  if (state === "on") return <span className="badge badge-ok">⚡ Fast boot</span>;
  if (state === "off") return <span className="badge">Fast boot off</span>;
  if (state === "unsupported")
    return (
      <span className="badge badge-warn" title={reason}>
        Fast boot n/a
      </span>
    );
  return null;
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <Card className="flex-1" pad={false}>
      <div className="px-4 py-3">
        <div className="text-[22px] font-extrabold leading-none" style={{ color: accent ? "var(--accent)" : "var(--text)" }}>{value}</div>
        <div className="mt-1 section-label">{label}</div>
      </div>
    </Card>
  );
}
