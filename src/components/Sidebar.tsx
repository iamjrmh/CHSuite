import { Github, MessageCircle, RefreshCw, Download } from "lucide-react";
import { TOOLS } from "../lib/registry";
import type { ToolId } from "../lib/types";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useUpdateCheck } from "../lib/update-context";
import { Spinner } from "./ui";

const PRIMARY = TOOLS.filter((t) => t.id !== "settings");
const SETTINGS = TOOLS.find((t) => t.id === "settings")!;

export function Sidebar({
  active,
  onSelect,
}: {
  active: ToolId;
  onSelect: (id: ToolId) => void;
}) {
  const { checking, result, openModal } = useUpdateCheck();
  const hasUpdate = !!result?.updateAvailable;

  return (
    <nav
      className="flex flex-col"
      style={{
        width: "var(--sidebar-w)",
        background: "var(--sidebar)",
        borderRight: "1px solid var(--border)",
      }}
    >
      {/* Brand */}
      <div className="flex items-center justify-between gap-2 px-5 pb-4 pt-5">
        <div className="flex min-w-0 items-center gap-3">
          <img
            src="/assets/images/logo.png"
            alt="CHSuite"
            className="h-9 w-9 flex-none rounded-[10px]"
            draggable={false}
            style={{ boxShadow: "0 4px 18px -6px color-mix(in srgb, var(--accent) 80%, transparent)" }}
          />
          <div className="min-w-0 leading-tight">
            <div className="truncate text-[15px] font-extrabold tracking-tight glow">
              CHSuite
            </div>
            <div className="truncate text-[10.5px]" style={{ color: "var(--text-dim)" }}>
              Clone Hero toolkit
            </div>
          </div>
        </div>
        <button
          onClick={openModal}
          disabled={checking}
          aria-label={hasUpdate ? `Update available: v${result?.latest}` : "Check for updates"}
          title={hasUpdate ? `Update available: v${result?.latest} - click to view` : "Check for updates"}
          className="relative grid h-7 w-7 flex-none place-items-center rounded-lg transition-colors"
          style={{ color: hasUpdate ? "var(--accent)" : "var(--text-dim)" }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--hover)"; if (!hasUpdate) e.currentTarget.style.color = "var(--text)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; if (!hasUpdate) e.currentTarget.style.color = "var(--text-dim)"; }}
        >
          {checking ? <Spinner size={14} /> : hasUpdate ? <Download size={15} /> : <RefreshCw size={14} />}
          {hasUpdate && (
            <span
              className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full"
              style={{ background: "var(--accent)", boxShadow: "0 0 6px var(--accent)" }}
            />
          )}
        </button>
      </div>

      <div className="px-3.5">
        <div className="section-label px-2.5 pb-2 pt-1">Tools</div>
      </div>

      <div className="flex-1 overflow-y-auto px-3.5">
        <div className="flex flex-col gap-0.5">
          {PRIMARY.map((tool) => (
            <NavItem
              key={tool.id}
              tool={tool}
              active={active === tool.id}
              onSelect={onSelect}
            />
          ))}
        </div>
      </div>

      <div className="px-3.5 pb-3">
        <div className="hairline mb-2.5" />
        <NavItem
          tool={SETTINGS}
          active={active === "settings"}
          onSelect={onSelect}
        />
        <div className="mt-2.5 flex items-center justify-between px-2.5">
          <span className="text-[10.5px]" style={{ color: "var(--text-dim)" }}>
            v8.0.0
          </span>
          <div className="flex gap-1">
            <IconLink
              label="GitHub"
              onClick={() => openUrl("https://github.com/iamjrmh/CHSuite")}
            >
              <Github size={15} />
            </IconLink>
            <IconLink
              label="Discord"
              onClick={() => openUrl("https://discord.gg/PtVqaCWFHa")}
            >
              <MessageCircle size={15} />
            </IconLink>
          </div>
        </div>
      </div>
    </nav>
  );
}

function NavItem({
  tool,
  active,
  onSelect,
}: {
  tool: (typeof TOOLS)[number];
  active: boolean;
  onSelect: (id: ToolId) => void;
}) {
  const Icon = tool.icon;
  return (
    <button
      onClick={() => onSelect(tool.id)}
      aria-current={active ? "page" : undefined}
      className="group relative flex items-center gap-3 rounded-[11px] px-2.5 py-2 text-left transition-colors"
      style={{
        background: active ? "var(--selected)" : "transparent",
        color: active ? "var(--text)" : "var(--text-mid)",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = "var(--nav-hover)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.background = "transparent";
      }}
    >
      {active && (
        <span
          className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full"
          style={{
            background: "var(--accent)",
            boxShadow: "0 0 10px 0 var(--accent)",
          }}
        />
      )}
      <span
        className="grid h-7 w-7 flex-none place-items-center rounded-lg transition-colors"
        style={{
          background: active ? "color-mix(in srgb, var(--accent) 22%, transparent)" : "transparent",
          color: active ? "var(--accent)" : "var(--text-mid)",
        }}
      >
        <Icon size={16} />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-[13px] font-semibold leading-tight">
          {tool.label}
        </span>
        <span
          className="block truncate text-[10.5px] leading-tight"
          style={{ color: "var(--text-dim)" }}
        >
          {tool.tagline}
        </span>
      </span>
    </button>
  );
}

function IconLink({
  children,
  label,
  onClick,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="grid h-7 w-7 place-items-center rounded-lg transition-colors"
      style={{ color: "var(--text-dim)" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = "var(--text)";
        e.currentTarget.style.background = "var(--hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = "var(--text-dim)";
        e.currentTarget.style.background = "transparent";
      }}
    >
      {children}
    </button>
  );
}
