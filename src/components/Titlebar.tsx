import { useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Minus, Square, X, Play } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useToast } from "./Toast";
import { Spinner } from "./ui";

const appWindow = getCurrentWindow();

export function Titlebar() {
  const toast = useToast();
  const [launching, setLaunching] = useState(false);

  async function launch() {
    setLaunching(true);
    try {
      await api.post<{ launched: string }>("/manager/launch", {});
      toast.success("Launching Clone Hero");
    } catch (e) {
      const err = e as ApiError;
      toast.error(
        err.code === "no_exe" ? "No Clone Hero install found" : "Launch failed",
        err.code === "no_exe" ? "Set a default install in CHManager." : err.message,
      );
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div
      data-tauri-drag-region
      className="glass flex items-center justify-between select-none"
      style={{
        height: "var(--titlebar-h)",
        borderBottom: "1px solid var(--border)",
        paddingLeft: 14,
      }}
    >
      <div
        data-tauri-drag-region
        className="flex items-center gap-2.5 pointer-events-none"
      >
        <img
          src="/assets/images/logo.png"
          alt=""
          className="h-[18px] w-[18px] rounded"
          draggable={false}
        />
        <span
          className="text-[12.5px] font-semibold tracking-wide"
          style={{ color: "var(--text-mid)" }}
        >
          CHSuite
          <span style={{ color: "var(--text-dim)" }}> · by JURMR</span>
        </span>
      </div>

      <div className="flex h-full items-center">
        <button
          onClick={launch}
          disabled={launching}
          aria-label="Launch Clone Hero"
          title="Launch Clone Hero"
          className="mr-2 flex items-center gap-1.5 rounded-[8px] px-3 py-1 text-[12px] font-semibold transition-colors"
          style={{ background: "var(--accent)", color: "#fff", opacity: launching ? 0.7 : 1 }}
        >
          {launching ? <Spinner size={13} /> : <Play size={13} />} Play
        </button>
        <TitlebarButton onClick={() => appWindow.minimize()} label="Minimize">
          <Minus size={15} />
        </TitlebarButton>
        <TitlebarButton
          onClick={() => appWindow.toggleMaximize()}
          label="Maximize"
        >
          <Square size={12} />
        </TitlebarButton>
        <TitlebarButton
          onClick={() => appWindow.close()}
          label="Close"
          danger
        >
          <X size={16} />
        </TitlebarButton>
      </div>
    </div>
  );
}

function TitlebarButton({
  children,
  onClick,
  label,
  danger,
}: {
  children: React.ReactNode;
  onClick: () => void;
  label: string;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      className="grid w-[46px] place-items-center transition-colors"
      style={{ color: "var(--text-mid)" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = danger
          ? "var(--error)"
          : "var(--hover)";
        e.currentTarget.style.color = danger ? "#fff" : "var(--text)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.color = "var(--text-mid)";
      }}
    >
      {children}
    </button>
  );
}
