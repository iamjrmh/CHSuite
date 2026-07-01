import { ArrowRight, Guitar, AlertCircle } from "lucide-react";
import { Page } from "../components/ui";
import { TOOLS } from "../lib/registry";
import type { ToolId } from "../lib/types";

export function About({
  onNavigate,
  offline,
}: {
  onNavigate: (id: ToolId) => void;
  offline: boolean;
}) {
  const tools = TOOLS.filter((t) => t.id !== "about" && t.id !== "settings");

  return (
    <Page title="Welcome to CHSuite" subtitle="The all-in-one Clone Hero toolkit, by JURMR" icon={<Guitar size={20} />}>
      {offline && (
        <div
          className="mb-5 flex items-start gap-3 rounded-[14px] border px-4 py-3"
          style={{
            background: "color-mix(in srgb, var(--warn) 12%, var(--card))",
            borderColor: "color-mix(in srgb, var(--warn) 40%, var(--border))",
          }}
        >
          <AlertCircle size={18} style={{ color: "var(--warn)", marginTop: 1 }} />
          <div className="text-[13px]">
            <div className="font-semibold">Backend not connected</div>
            <div style={{ color: "var(--text-mid)" }}>
              The Python sidecar isn't responding. Tools that touch files or the
              network will be unavailable, but you can still browse and theme the
              app.
            </div>
          </div>
        </div>
      )}

      {/* Hero */}
      <div
        className="relative mb-6 overflow-hidden rounded-[20px] border p-7"
        style={{
          borderColor: "var(--border2)",
          background:
            "linear-gradient(135deg, color-mix(in srgb, var(--accent) 20%, var(--card)), var(--card) 55%, color-mix(in srgb, var(--accent2) 14%, var(--card)))",
        }}
      >
        <div className="relative z-10 max-w-2xl">
          <h2 className="text-[26px] font-extrabold leading-tight tracking-tight">
            Everything for Clone Hero, in one place.
          </h2>
          <p className="mt-2 text-[14px] leading-relaxed" style={{ color: "var(--text-mid)" }}>
            Swap menu backgrounds, craft colored names and note colors, clean up
            broken songs, download charts, and manage every install - without
            ever leaving the app.
          </p>
          <button
            className="btn btn-primary mt-5"
            onClick={() => onNavigate("menuchanger")}
          >
            Get started <ArrowRight size={16} />
          </button>
        </div>
        <img
          src="/assets/images/clonehero-logo.png"
          alt=""
          draggable={false}
          className="pointer-events-none absolute -right-6 -bottom-10 h-56 w-56 object-contain opacity-25"
          style={{ filter: "drop-shadow(0 0 40px var(--accent))" }}
        />
      </div>

      {/* Tool grid */}
      <div className="grid grid-cols-2 gap-3.5">
        {tools.map((tool) => {
          const Icon = tool.icon;
          return (
            <button
              key={tool.id}
              onClick={() => onNavigate(tool.id)}
              className="card group flex items-start gap-4 p-5 text-left transition-[transform,border-color]"
              style={{ transitionDuration: "180ms" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--accent)";
                e.currentTarget.style.transform = "translateY(-2px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.transform = "translateY(0)";
              }}
            >
              <div
                className="grid h-12 w-12 flex-none place-items-center rounded-[14px] transition-colors"
                style={{
                  background:
                    "linear-gradient(140deg, color-mix(in srgb, var(--accent) 24%, var(--card2)), var(--card2))",
                  border: "1px solid var(--border2)",
                  color: "var(--accent)",
                }}
              >
                <Icon size={22} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[15px] font-bold">{tool.label}</span>
                  <ArrowRight
                    size={15}
                    className="opacity-0 transition-[opacity,transform] group-hover:translate-x-0.5 group-hover:opacity-100"
                    style={{ color: "var(--accent)" }}
                  />
                </div>
                <p
                  className="mt-1 text-[12.5px] leading-relaxed"
                  style={{ color: "var(--text-dim)" }}
                >
                  {tool.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </Page>
  );
}
