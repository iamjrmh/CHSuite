import { useState } from "react";
import { Trash2, FileSearch, FolderX, ShieldAlert } from "lucide-react";
import { Page, Card, PathPicker, EmptyState, Spinner, pickFile } from "../components/ui";
import { useToast } from "../components/Toast";
import { api, ApiError } from "../lib/api";

interface BadSong {
  path: string;
  name: string;
  exists: boolean;
}

export function Cleaner() {
  const toast = useToast();
  const [file, setFile] = useState("");
  const [songs, setSongs] = useState<BadSong[]>([]);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [scanned, setScanned] = useState(false);

  async function pick() {
    const f = await pickFile("Select badsongs.txt", [
      { name: "Text", extensions: ["txt"] },
    ]);
    if (!f) return;
    setFile(f);
    await parse(f);
  }

  async function parse(path: string) {
    setLoading(true);
    try {
      const res = await api.post<{ count: number; songs: BadSong[] }>(
        "/cleaner/parse",
        { path },
      );
      setSongs(res.songs);
      setChecked(new Set(res.songs.filter((s) => s.exists).map((s) => s.path)));
      setScanned(true);
      if (res.count === 0) toast.info("Nothing to clean", "No ERROR folders found in that file.");
    } catch (e) {
      toast.error("Could not read file", (e as ApiError).message);
    } finally {
      setLoading(false);
    }
  }

  function toggle(path: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }

  async function remove() {
    const paths = [...checked];
    if (paths.length === 0) return;
    setDeleting(true);
    try {
      const res = await api.post<{ deleted: string[]; failed: { path: string }[]; missing: string[] }>(
        "/cleaner/delete",
        { paths },
      );
      toast.success(
        `Deleted ${res.deleted.length} song${res.deleted.length === 1 ? "" : "s"}`,
        res.failed.length ? `${res.failed.length} could not be removed.` : "Logged to deletedsongs.log",
      );
      setSongs((prev) => prev.filter((s) => !res.deleted.includes(s.path)));
      setChecked(new Set());
    } catch (e) {
      toast.error("Deletion failed", (e as ApiError).message);
    } finally {
      setDeleting(false);
    }
  }

  const selectedCount = checked.size;

  return (
    <Page
      title="CHCleaner"
      subtitle="Parse badsongs.txt and bulk-delete the ERROR folders"
      icon={<Trash2 size={20} />}
      actions={
        scanned && songs.length > 0 ? (
          <button className="btn btn-danger" onClick={remove} disabled={deleting || selectedCount === 0}>
            {deleting ? <Spinner size={15} /> : <FolderX size={15} />}
            Delete {selectedCount > 0 ? `(${selectedCount})` : ""}
          </button>
        ) : null
      }
    >
      <Card className="mb-4">
        <PathPicker label="badsongs.txt" value={file} placeholder="Usually in Documents\Clone Hero" onPick={pick} />
      </Card>

      <div
        className="mb-4 flex items-start gap-3 rounded-[12px] border px-4 py-2.5"
        style={{ borderColor: "var(--border)", background: "var(--card2)" }}
      >
        <ShieldAlert size={16} style={{ color: "var(--warn)", marginTop: 2, flex: "none" }} />
        <p className="text-[12.5px]" style={{ color: "var(--text-mid)" }}>
          Only folders under <b>ERROR:</b> sections are listed. Songs under{" "}
          <b>Warning:</b> are intentionally left alone. Deletions are permanent
          but logged.
        </p>
      </div>

      {loading ? (
        <Card className="flex items-center justify-center gap-3 py-10">
          <Spinner /> <span style={{ color: "var(--text-mid)" }}>Parsing…</span>
        </Card>
      ) : !scanned ? (
        <EmptyState
          icon={<FileSearch size={26} />}
          title="No file loaded yet"
          hint="Pick your badsongs.txt to see which broken song folders can be cleaned up."
        />
      ) : songs.length === 0 ? (
        <EmptyState icon={<Trash2 size={26} />} title="Nothing to clean" hint="No ERROR folders were found - your library is healthy." />
      ) : (
        <Card pad={false}>
          <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
            <span className="text-[13px] font-semibold">
              {songs.length} folder{songs.length === 1 ? "" : "s"} marked for deletion
            </span>
            <div className="flex gap-2">
              <button className="btn btn-ghost btn-sm" onClick={() => setChecked(new Set(songs.filter((s) => s.exists).map((s) => s.path)))}>Select all</button>
              <button className="btn btn-ghost btn-sm" onClick={() => setChecked(new Set())}>None</button>
            </div>
          </div>
          <div className="max-h-[42vh] overflow-y-auto">
            {songs.map((s) => (
              <label
                key={s.path}
                className="flex cursor-pointer items-center gap-3 px-4 py-2.5 transition-colors"
                style={{ borderBottom: "1px solid var(--border)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <input type="checkbox" className="check" checked={checked.has(s.path)} onChange={() => toggle(s.path)} disabled={!s.exists} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px] font-medium">{s.name}</div>
                  <div className="truncate text-[11px]" style={{ color: "var(--text-dim)", fontFamily: "ui-monospace, Consolas, monospace" }}>{s.path}</div>
                </div>
                {!s.exists && <span className="badge">missing</span>}
              </label>
            ))}
          </div>
        </Card>
      )}
    </Page>
  );
}
