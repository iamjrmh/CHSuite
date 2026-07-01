import { useState } from "react";
import { Titlebar } from "./components/Titlebar";
import { Sidebar } from "./components/Sidebar";
import { Spinner } from "./components/ui";
import { useConfig } from "./lib/config-context";
import type { ToolId } from "./lib/types";

import { About } from "./tools/About";
import { MenuChanger } from "./tools/MenuChanger";
import { NameGen } from "./tools/NameGen";
import { NoteGen } from "./tools/NoteGen";
import { Cleaner } from "./tools/Cleaner";
import { Patcher } from "./tools/Patcher";
import { SongManager } from "./tools/SongManager";
import { Manager } from "./tools/Manager";
import { SettingsView } from "./tools/Settings";

export function App() {
  const [active, setActive] = useState<ToolId>("about");
  const { ready, offline } = useConfig();

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden">
      <Titlebar />
      <div className="flex min-h-0 flex-1">
        <Sidebar active={active} onSelect={setActive} />
        <main
          className="relative min-w-0 flex-1"
          style={{ background: "var(--bg)" }}
        >
          {/* Soft accent glow in the corner for depth */}
          <div
            className="pointer-events-none absolute -right-40 -top-40 h-96 w-96 rounded-full opacity-[0.13]"
            style={{
              background:
                "radial-gradient(circle, var(--accent), transparent 70%)",
            }}
          />
          {!ready ? (
            <div className="flex h-full items-center justify-center gap-3">
              <Spinner size={20} />
              <span style={{ color: "var(--text-mid)" }}>
                Starting CHSuite…
              </span>
            </div>
          ) : (
            <View id={active} offline={offline} onNavigate={setActive} />
          )}
        </main>
      </div>
    </div>
  );
}

function View({
  id,
  offline,
  onNavigate,
}: {
  id: ToolId;
  offline: boolean;
  onNavigate: (id: ToolId) => void;
}) {
  switch (id) {
    case "about":
      return <About onNavigate={onNavigate} offline={offline} />;
    case "menuchanger":
      return <MenuChanger />;
    case "namegen":
      return <NameGen />;
    case "notegen":
      return <NoteGen />;
    case "cleaner":
      return <Cleaner />;
    case "patcher":
      return <Patcher />;
    case "songmanager":
      return <SongManager />;
    case "manager":
      return <Manager />;
    case "settings":
      return <SettingsView />;
  }
}
