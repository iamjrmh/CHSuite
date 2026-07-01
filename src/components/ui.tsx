import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { open } from "@tauri-apps/plugin-dialog";

/* --- Page scaffolding ---------------------------------------------------- */

export function Page({
  title,
  subtitle,
  icon,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-start justify-between gap-4 px-8 pt-7 pb-5">
        <div className="flex items-center gap-3.5">
          {icon && (
            <div
              className="grid h-11 w-11 place-items-center rounded-[13px]"
              style={{
                background:
                  "linear-gradient(140deg, color-mix(in srgb, var(--accent) 26%, var(--card)), var(--card))",
                border: "1px solid var(--border2)",
                color: "var(--accent)",
              }}
            >
              {icon}
            </div>
          )}
          <div>
            <h1 className="text-[22px] font-bold leading-tight tracking-tight">
              {title}
            </h1>
            {subtitle && (
              <p
                className="mt-0.5 text-[13px]"
                style={{ color: "var(--text-dim)" }}
              >
                {subtitle}
              </p>
            )}
          </div>
        </div>
        {actions && <div className="flex items-center gap-2.5">{actions}</div>}
      </header>
      <div className="allow-select min-h-0 flex-1 overflow-y-auto px-8 pb-8">
        <div className="fade-up">{children}</div>
      </div>
    </div>
  );
}

export function Card({
  children,
  className = "",
  pad = true,
  style,
}: {
  children: ReactNode;
  className?: string;
  pad?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <div className={`card ${pad ? "p-5" : ""} ${className}`} style={style}>
      {children}
    </div>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="section-label mb-2.5">{children}</div>;
}

export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="spin" style={{ flex: "none" }} />;
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      {icon && (
        <div
          className="mb-4 grid h-16 w-16 place-items-center rounded-2xl"
          style={{
            background: "var(--card2)",
            border: "1px solid var(--border)",
            color: "var(--text-dim)",
          }}
        >
          {icon}
        </div>
      )}
      <div className="text-[15px] font-semibold">{title}</div>
      {hint && (
        <div
          className="mt-1.5 max-w-md text-[13px] leading-relaxed"
          style={{ color: "var(--text-dim)" }}
        >
          {hint}
        </div>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* --- Native pickers (Tauri dialog) -------------------------------------- */

export async function pickFolder(title = "Select a folder"): Promise<string | null> {
  const res = await open({ directory: true, multiple: false, title });
  return typeof res === "string" ? res : null;
}

export async function pickFile(
  title = "Select a file",
  filters?: { name: string; extensions: string[] }[],
): Promise<string | null> {
  const res = await open({ directory: false, multiple: false, title, filters });
  return typeof res === "string" ? res : null;
}

export async function pickFiles(
  title = "Select files",
  filters?: { name: string; extensions: string[] }[],
): Promise<string[]> {
  const res = await open({ directory: false, multiple: true, title, filters });
  return Array.isArray(res) ? res : [];
}

/** Path input + Browse button row. */
export function PathPicker({
  label,
  value,
  placeholder,
  onPick,
  mono = true,
}: {
  label?: string;
  value: string;
  placeholder?: string;
  onPick: () => void;
  mono?: boolean;
}) {
  return (
    <div>
      {label && <SectionLabel>{label}</SectionLabel>}
      <div className="flex gap-2.5">
        <div
          className="input flex min-w-0 items-center"
          style={{
            color: value ? "var(--text)" : "var(--text-dim)",
            fontFamily: mono
              ? "ui-monospace, 'Cascadia Code', Consolas, monospace"
              : "inherit",
            fontSize: mono ? 12.5 : 13.5,
          }}
        >
          <span className="truncate">{value || placeholder || "No path selected"}</span>
        </div>
        <button className="btn btn-ghost flex-none" onClick={onPick}>
          Browse…
        </button>
      </div>
    </div>
  );
}
