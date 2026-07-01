import { CheckCircle2, Download, AlertTriangle, ExternalLink, ArrowRight } from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { Spinner } from "./ui";
import { renderReleaseNotes } from "../lib/markdown-lite";
import type { ModalState, UpdateResult, InstallJob } from "../lib/update-context";

export function UpdateModal({
  state,
  result,
  error,
  installJob,
  onInstall,
  onClose,
}: {
  state: ModalState;
  result: UpdateResult | null;
  error: string;
  installJob: InstallJob | null;
  onInstall: () => void;
  onClose: (opts?: { dismiss?: boolean }) => void;
}) {
  if (state === "hidden") return null;

  const showLater = state === "checking" || state === "available" || state === "downloading";
  const showClose = state === "current" || state === "error";
  const showView = state === "available" && !!result?.url;
  const showInstall = state === "available";
  const canInstall = !!result?.installerUrl;

  const pct =
    installJob && installJob.total
      ? Math.min(100, Math.round((installJob.downloaded / installJob.total) * 100))
      : 0;

  return (
    <div className="fixed inset-0 z-[1100] grid place-items-center" role="dialog" aria-modal="true">
      <div
        className="absolute inset-0"
        style={{ background: "rgba(6,7,11,0.65)" }}
        onClick={() => {
          if (state === "downloading") return;
          onClose({ dismiss: state === "available" });
        }}
      />
      <div
        className="pop-in glass relative flex flex-col rounded-[20px] border p-6"
        style={{ borderColor: "var(--border2)", width: 420, boxShadow: "0 30px 70px -15px rgba(0,0,0,0.6)" }}
      >
        <div className="mb-4 flex items-center gap-3">
          <div
            className="grid h-11 w-11 flex-none place-items-center rounded-[13px]"
            style={{
              background: "linear-gradient(140deg, color-mix(in srgb, var(--accent) 26%, var(--card)), var(--card))",
              border: "1px solid var(--border2)",
              color: state === "current" ? "var(--success)" : state === "error" ? "var(--error)" : "var(--accent)",
            }}
          >
            {state === "checking" || state === "downloading" ? (
              <Spinner size={18} />
            ) : state === "current" ? (
              <CheckCircle2 size={20} />
            ) : state === "error" ? (
              <AlertTriangle size={20} />
            ) : (
              <Download size={20} />
            )}
          </div>
          <div className="min-w-0">
            <div className="text-[10.5px] font-bold uppercase tracking-wide" style={{ color: "var(--text-dim)" }}>
              {state === "checking" && "Checking GitHub…"}
              {state === "current" && "All caught up"}
              {state === "available" && "Update available"}
              {state === "downloading" && "Installing update"}
              {state === "error" && "Couldn't check for updates"}
            </div>
            <div className="text-[15px] font-bold leading-tight">
              {state === "checking" && "Looking for updates"}
              {state === "current" && "You're up to date"}
              {state === "available" && `CHSuite v${result?.latest}`}
              {state === "downloading" && "Downloading installer"}
              {state === "error" && "Update check failed"}
            </div>
          </div>
        </div>

        <p className="text-[12.5px] leading-relaxed" style={{ color: "var(--text-mid)" }}>
          {state === "checking" && "Just a moment, reaching out to the release server."}
          {state === "current" && `You're running CHSuite v${result?.current}, the latest release.`}
          {state === "available" &&
            (result?.publishedAt
              ? `Released ${new Date(result.publishedAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}.`
              : "A newer version is ready to install.")}
          {state === "downloading" && (installJob?.message || "Fetching the installer from GitHub.")}
          {state === "error" && "We couldn't talk to the release server. Check your connection and try again."}
        </p>

        {state === "available" && result && (
          <div className="mt-3 flex items-center gap-2">
            <span className="badge">v{result.current}</span>
            <ArrowRight size={13} style={{ color: "var(--text-dim)" }} />
            <span className="badge badge-ok">v{result.latest}</span>
          </div>
        )}

        {state === "available" && result?.notes && (
          <div
            className="mt-3 max-h-[220px] overflow-y-auto rounded-[12px] border p-3 text-[12px]"
            style={{ borderColor: "var(--border)", background: "var(--card2)" }}
          >
            {renderReleaseNotes(result.notes)}
          </div>
        )}

        {state === "downloading" && (
          <div className="mt-3">
            <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--card2)" }}>
              <div
                className="h-full rounded-full transition-[width]"
                style={{ width: `${pct}%`, background: "var(--accent)" }}
              />
            </div>
          </div>
        )}

        {state === "error" && (
          <div
            className="mt-3 rounded-[12px] border px-3 py-2.5 text-[12px]"
            style={{ borderColor: "color-mix(in srgb, var(--error) 40%, var(--border))", background: "color-mix(in srgb, var(--error) 12%, var(--card))", color: "color-mix(in srgb, var(--error) 88%, white)" }}
          >
            {error}
          </div>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          {showLater && (
            <button
              className="btn btn-ghost btn-sm"
              disabled={state === "downloading"}
              onClick={() => onClose({ dismiss: state === "available" })}
            >
              Later
            </button>
          )}
          {showClose && (
            <button className="btn btn-ghost btn-sm" onClick={() => onClose()}>
              Close
            </button>
          )}
          {showView && (
            <button className="btn btn-ghost btn-sm" onClick={() => openUrl(result!.url)}>
              View release <ExternalLink size={13} />
            </button>
          )}
          {showInstall && (
            <button className="btn btn-primary btn-sm" disabled={!canInstall} title={canInstall ? "" : "This release has no installer attached."} onClick={onInstall}>
              <Download size={14} /> Install update
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
