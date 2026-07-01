import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";

type ToastKind = "success" | "error" | "warn" | "info";
interface Toast {
  id: number;
  kind: ToastKind;
  title: string;
  detail?: string;
  leaving?: boolean;
}

interface ToastApi {
  push: (kind: ToastKind, title: string, detail?: string) => void;
  success: (title: string, detail?: string) => void;
  error: (title: string, detail?: string) => void;
  warn: (title: string, detail?: string) => void;
  info: (title: string, detail?: string) => void;
}

const Ctx = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  warn: AlertTriangle,
  info: Info,
} as const;

const COLORS = {
  success: "var(--success)",
  error: "var(--error)",
  warn: "var(--warn)",
  info: "var(--accent)",
} as const;

// Matches .toast-item's transition duration in styles.css - the exit
// transition has to finish playing before the toast actually leaves the DOM.
const EXIT_MS = 220;

let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((t) => t.map((x) => (x.id === id ? { ...x, leaving: true } : x)));
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, EXIT_MS);
  }, []);

  const push = useCallback(
    (kind: ToastKind, title: string, detail?: string) => {
      const id = ++counter;
      setToasts((t) => [...t, { id, kind, title, detail }]);
      setTimeout(() => remove(id), kind === "error" ? 6500 : 4200);
    },
    [remove],
  );

  const api: ToastApi = {
    push,
    success: (t, d) => push("success", t, d),
    error: (t, d) => push("error", t, d),
    warn: (t, d) => push("warn", t, d),
    info: (t, d) => push("info", t, d),
  };

  return (
    <Ctx.Provider value={api}>
      {children}
      <div
        className="fixed bottom-5 right-5 z-[1000] flex flex-col gap-2.5"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => remove(t.id)} />
        ))}
      </div>
    </Ctx.Provider>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    // Double rAF: guarantees the browser paints the initial (hidden) style
    // at least once before flipping the class, so the transition actually
    // runs instead of snapping straight to its end state.
    const raf1 = requestAnimationFrame(() => {
      const raf2 = requestAnimationFrame(() => setEntered(true));
      return () => cancelAnimationFrame(raf2);
    });
    return () => cancelAnimationFrame(raf1);
  }, []);

  const Icon = ICONS[toast.kind];
  const visible = entered && !toast.leaving;

  return (
    <div
      className={`toast-item glass flex items-start gap-3 rounded-[14px] border px-4 py-3 shadow-2xl ${visible ? "toast-visible" : ""}`}
      style={{
        borderColor: "var(--border2)",
        minWidth: 280,
        maxWidth: 420,
      }}
      role="alert"
    >
      <Icon
        size={18}
        style={{ color: COLORS[toast.kind], marginTop: 1, flex: "none" }}
      />
      <div className="min-w-0 flex-1">
        <div className="text-[13.5px] font-semibold leading-snug">
          {toast.title}
        </div>
        {toast.detail && (
          <div
            className="mt-0.5 text-[12px] leading-snug break-words"
            style={{ color: "var(--text-mid)" }}
          >
            {toast.detail}
          </div>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="rounded p-0.5 transition-colors"
        style={{ color: "var(--text-dim)" }}
        aria-label="Dismiss"
      >
        <X size={15} />
      </button>
    </div>
  );
}
