import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { api, ApiError } from "./api";
import { useConfig } from "./config-context";
import { UpdateModal } from "../components/UpdateModal";

export interface UpdateResult {
  current: string;
  latest: string;
  updateAvailable: boolean;
  url: string;
  publishedAt: string;
  notes: string;
  installerUrl: string;
  installerName: string;
}

export interface InstallJob {
  status: "running" | "done" | "error";
  downloaded: number;
  total: number;
  message?: string;
  error?: string;
}

export type ModalState = "hidden" | "checking" | "current" | "available" | "downloading" | "error";

interface UpdateApi {
  result: UpdateResult | null;
  checking: boolean;
  openModal: () => void;
}

const Ctx = createContext<UpdateApi | null>(null);

export function useUpdateCheck(): UpdateApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useUpdateCheck must be used inside <UpdateProvider>");
  return ctx;
}

const POLL_MS = 300;

export function UpdateProvider({ children }: { children: ReactNode }) {
  const { config, update } = useConfig();
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<UpdateResult | null>(null);
  const [modalState, setModalState] = useState<ModalState>("hidden");
  const [modalError, setModalError] = useState("");
  const [installJob, setInstallJob] = useState<InstallJob | null>(null);

  const checkedOnLaunch = useRef(false);
  const installPollRef = useRef<number | null>(null);
  const configRef = useRef(config);
  configRef.current = config;

  useEffect(() => {
    return () => {
      if (installPollRef.current) window.clearInterval(installPollRef.current);
    };
  }, []);

  const runCheck = useCallback(async (manual: boolean) => {
    setChecking(true);
    if (manual) setModalState("checking");
    try {
      const res = await api.get<UpdateResult>("/updater/check");
      setResult(res);
      if (res.updateAvailable) {
        const skipped = configRef.current?.skipped_update_version === res.latest;
        if (manual || !skipped) setModalState("available");
      } else if (manual) {
        setModalState("current");
      }
    } catch (e) {
      if (manual) {
        setModalState("error");
        setModalError((e as ApiError).message);
      }
    } finally {
      setChecking(false);
    }
  }, []);

  // Check once automatically at launch. Silent unless there's an update the
  // user hasn't already dismissed, in which case the modal opens on its own.
  useEffect(() => {
    if (checkedOnLaunch.current) return;
    checkedOnLaunch.current = true;
    runCheck(false);
  }, [runCheck]);

  function openModal() {
    runCheck(true);
  }

  function closeModal(opts: { dismiss?: boolean } = {}) {
    if (opts.dismiss && result?.updateAvailable && result.latest) {
      // Remember this version so the launch auto-check doesn't reopen the
      // modal every time - the sidebar/Settings buttons still work normally.
      update({ skipped_update_version: result.latest });
    }
    setModalState("hidden");
    setInstallJob(null);
  }

  function pollInstall(jobId: string) {
    if (installPollRef.current) window.clearInterval(installPollRef.current);
    installPollRef.current = window.setInterval(async () => {
      try {
        const job = await api.post<InstallJob>("/updater/install/status", { jobId });
        setInstallJob(job);
        if (job.status === "done") {
          window.clearInterval(installPollRef.current!);
          installPollRef.current = null;
          setInstallJob({ ...job, message: "Installer launched. Closing CHSuite…" });
          setTimeout(() => {
            getCurrentWindow().close();
          }, 900);
        } else if (job.status === "error") {
          window.clearInterval(installPollRef.current!);
          installPollRef.current = null;
          setModalState("error");
          setModalError(job.error || "Install failed.");
        }
      } catch (e) {
        window.clearInterval(installPollRef.current!);
        installPollRef.current = null;
        setModalState("error");
        setModalError((e as ApiError).message);
      }
    }, POLL_MS);
  }

  async function startInstall() {
    if (!result?.installerUrl || !result?.installerName) return;
    setModalState("downloading");
    setInstallJob({ status: "running", downloaded: 0, total: 0, message: "Starting download…" });
    try {
      const res = await api.post<{ jobId: string }>("/updater/install", {
        url: result.installerUrl,
        name: result.installerName,
      });
      pollInstall(res.jobId);
    } catch (e) {
      setModalState("error");
      setModalError((e as ApiError).message);
    }
  }

  return (
    <Ctx.Provider value={{ result, checking, openModal }}>
      {children}
      <UpdateModal
        state={modalState}
        result={result}
        error={modalError}
        installJob={installJob}
        onInstall={startInstall}
        onClose={closeModal}
      />
    </Ctx.Provider>
  );
}
