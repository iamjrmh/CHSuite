import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";
import { setTheme } from "./theme";
import type { AppConfig } from "./types";

interface ConfigApi {
  config: AppConfig | null;
  ready: boolean;
  offline: boolean;
  update: (patch: Partial<AppConfig>) => Promise<void>;
  changeTheme: (name: string) => Promise<void>;
}

const Ctx = createContext<ConfigApi | null>(null);

export function useConfig(): ConfigApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useConfig must be used inside <ConfigProvider>");
  return ctx;
}

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [ready, setReady] = useState(false);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await api.get<AppConfig>("/config");
        setConfig(cfg);
        await setTheme(cfg.theme || "Default");
      } catch {
        setOffline(true);
        await setTheme("Default");
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const update = async (patch: Partial<AppConfig>) => {
    try {
      const cfg = await api.post<AppConfig>("/config", patch);
      setConfig(cfg);
    } catch {
      // Optimistic local update if the backend is unreachable.
      setConfig((c) => (c ? { ...c, ...patch } : c));
    }
  };

  const changeTheme = async (name: string) => {
    await setTheme(name);
    await update({ theme: name });
  };

  return (
    <Ctx.Provider value={{ config, ready, offline, update, changeTheme }}>
      {children}
    </Ctx.Provider>
  );
}
