import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError } from "./api";
import { useToast } from "../components/Toast";

export interface UpdateResult {
  current: string;
  latest: string;
  updateAvailable: boolean;
  url: string;
  publishedAt: string;
  notes: string;
}

interface UpdateApi {
  checking: boolean;
  result: UpdateResult | null;
  checkNow: (announce?: boolean) => Promise<void>;
}

const Ctx = createContext<UpdateApi | null>(null);

export function useUpdateCheck(): UpdateApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useUpdateCheck must be used inside <UpdateProvider>");
  return ctx;
}

export function UpdateProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<UpdateResult | null>(null);
  const checkedOnLaunch = useRef(false);

  const checkNow = useCallback(
    async (announce = false) => {
      setChecking(true);
      try {
        const res = await api.get<UpdateResult>("/updater/check");
        setResult(res);
        if (res.updateAvailable) {
          toast.info(`Update available: v${res.latest}`, `You're on v${res.current}.`);
        } else if (announce) {
          toast.success("You're up to date", `v${res.current}`);
        }
      } catch (e) {
        if (announce) toast.error("Could not check for updates", (e as ApiError).message);
      } finally {
        setChecking(false);
      }
    },
    [toast],
  );

  // Check once automatically at launch - silent if already up to date,
  // so it doesn't nag every time the app opens.
  useEffect(() => {
    if (checkedOnLaunch.current) return;
    checkedOnLaunch.current = true;
    checkNow(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <Ctx.Provider value={{ checking, result, checkNow }}>{children}</Ctx.Provider>;
}
