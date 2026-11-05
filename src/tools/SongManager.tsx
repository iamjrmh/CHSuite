import { useEffect, useMemo, useRef, useState } from "react";
import { Music2, Search, Download, FolderInput, Video, VideoOff, FileArchive, FolderOutput, CheckSquare, Square, HardDrive, RefreshCw, Trash2, StopCircle, SkipForward, X } from "lucide-react";
import { Page, Card, EmptyState, Spinner, pickFolder } from "../components/ui";
import { useToast } from "../components/Toast";
import { api, ApiError, fetchBlobUrl } from "../lib/api";
import { useConfig } from "../lib/config-context";
import { renderRichText } from "../lib/richtext";
import type { Song, BulkStatus } from "../lib/types";

const INSTRUMENTS = ["", "guitar", "bass", "drums", "keys", "rhythm", "vocals"];
const DIFFICULTIES = ["", "expert", "hard", "medium", "easy"];
const POLL_MS = 350;
const BULK_POLL_MS = 1000;

interface LibrarySong {
  path: string;
  name: string;
  artist: string;
  charter: string;
  type: "sng" | "folder";
  size: number;
  art: string;
}

interface ScanJob {
  status: "running" | "done" | "error";
  count: number;
  dir: string;
  songs?: LibrarySong[];
  totalSize?: number;
  error?: string;
}

interface DownloadQueueItem {
  md5: string;
  name: string;
  artist: string;
  status: "pending" | "downloading" | "done" | "skipped" | "failed";
  error?: string;
  path?: string;
}

interface DownloadJob {
  status: "collecting" | "running" | "done";
  dir: string;
  total: number;
  done: number;
  queue: DownloadQueueItem[];
  error?: string;
}

interface ConvertQueueItem {
  path: string;
  status: "pending" | "converting" | "done" | "skipped" | "failed";
  newPath?: string;
  error?: string;
}

interface ConvertJob {
  status: "running" | "done";
  total: number;
  done: number;
  queue: ConvertQueueItem[];
}

export function SongManager() {
  const toast = useToast();
  const { config, update } = useConfig();
  const [tab, setTab] = useState<"search" | "library">("search");

  const [query, setQuery] = useState("");
  const [instrument, setInstrument] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [songs, setSongs] = useState<Song[]>([]);
  const [found, setFound] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(false);
  const [downloadJob, setDownloadJob] = useState<DownloadJob | null>(null);

  const [libSongs, setLibSongs] = useState<LibrarySong[]>([]);
  const [libLoading, setLibLoading] = useState(false);
  const [libLoaded, setLibLoaded] = useState(false);
  const [libSelected, setLibSelected] = useState<Set<string>>(new Set());
  const [libDeleting, setLibDeleting] = useState(false);
  const [scanCount, setScanCount] = useState(0);
  const [convertJob, setConvertJob] = useState<ConvertJob | null>(null);

  const [bulkStatus, setBulkStatus] = useState<BulkStatus | null>(null);
  const [bulkStarting, setBulkStarting] = useState(false);

  const songsDir = config?.sm_songs_dir || "";
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<(reset?: boolean) => void>(() => {});
  const scanPollRef = useRef<number | null>(null);
  const downloadPollRef = useRef<number | null>(null);
  const convertPollRef = useRef<number | null>(null);
  const bulkPollRef = useRef<number | null>(null);

  const downloadingMd5s = useMemo(() => {
    if (!downloadJob || downloadJob.status === "done") return new Set<string>();
    return new Set(downloadJob.queue.filter((q) => q.status === "pending" || q.status === "downloading").map((q) => q.md5));
  }, [downloadJob]);

  const converting = !!convertJob && convertJob.status !== "done";
  const libSelectedHasFolder = useMemo(
    () => libSongs.some((s) => libSelected.has(s.path) && s.type === "folder"),
    [libSongs, libSelected],
  );
  const libSelectedHasSng = useMemo(
    () => libSongs.some((s) => libSelected.has(s.path) && s.type === "sng"),
    [libSongs, libSelected],
  );

  // Stop any in-flight polling when the tool unmounts.
  useEffect(() => {
    return () => {
      if (scanPollRef.current) window.clearInterval(scanPollRef.current);
      if (downloadPollRef.current) window.clearInterval(downloadPollRef.current);
      if (convertPollRef.current) window.clearInterval(convertPollRef.current);
      if (bulkPollRef.current) window.clearInterval(bulkPollRef.current);
    };
  }, []);

  // Pre-fill with the latest charts on load, same as the original CHSuite.
  useEffect(() => {
    search(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Check on open whether a bulk "download all" is already running (survives
  // switching tabs/tools) or was left interrupted/stopped from a previous
  // session - the checkpoint on disk means that state outlives the app
  // closing, so this can offer to resume right where it left off.
  useEffect(() => {
    refreshBulkStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (bulkStatus?.status === "running") {
      if (!bulkPollRef.current) bulkPollRef.current = window.setInterval(refreshBulkStatus, BULK_POLL_MS);
    } else if (bulkPollRef.current) {
      window.clearInterval(bulkPollRef.current);
      bulkPollRef.current = null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bulkStatus?.status]);

  // "Select all" stays active as more results load in, so newly-appended
  // songs keep getting picked up automatically while scrolling.
  useEffect(() => {
    if (selectAll) setSelected(new Set(songs.map((s) => s.md5)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [songs, selectAll]);

  // Only scan once per app session - switching tabs re-shows the cached
  // list instead of rescanning. Refresh (or a full app restart) is what
  // triggers a fresh scan. The on-disk cache (from the last scan) is painted
  // instantly while that fresh scan runs in the background, so restarting
  // the app doesn't mean staring at a scanning spinner every time.
  useEffect(() => {
    if (tab === "library" && !libLoaded) {
      primeFromCache();
      loadLibrary();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // A different songs folder invalidates the cached scan.
  useEffect(() => {
    setLibLoaded(false);
    setLibSongs([]);
    if (tab === "library") {
      primeFromCache();
      loadLibrary();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [songsDir]);

  // Keep a live pointer to the latest `search` closure so the scroll
  // observer below always fires the current query/page/filters.
  useEffect(() => {
    searchRef.current = search;
  });

  // Auto-load more results as the sentinel scrolls into view, replacing
  // the old "Load more" button.
  useEffect(() => {
    if (tab !== "search" || !hasMore) return;
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) searchRef.current(false);
      },
      { rootMargin: "600px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [tab, hasMore, songs.length]);

  function toggleSelectAll() {
    if (selectAll) {
      setSelectAll(false);
      setSelected(new Set());
    } else {
      setSelectAll(true);
    }
  }

  async function search(reset = true) {
    if (!reset && (loading || !hasMore)) return;
    const nextPage = reset ? 1 : page + 1;
    setLoading(true);
    try {
      const res = await api.post<{ found: number; songs: Song[]; hasMore: boolean }>("/songs/search", {
        query,
        page: nextPage,
        instrument: instrument || null,
        difficulty: difficulty || null,
      });
      setFound(res.found);
      setHasMore(res.hasMore);
      setPage(nextPage);
      setSongs((prev) => (reset ? res.songs : [...prev, ...res.songs]));
      setSearched(true);
    } catch (e) {
      toast.error("Search failed", (e as ApiError).message);
    } finally {
      setLoading(false);
    }
  }

  // Best-effort instant paint from the sidecar's on-disk scan cache - no
  // filesystem walk, so it resolves almost immediately. Only ever adds data;
  // never blanks the list, so it's safe to fire alongside loadLibrary().
  async function primeFromCache() {
    const dir = songsDir;
    try {
      const res = await api.post<{ songs: LibrarySong[] }>("/songs/library/cached", { dir: dir || undefined });
      // The songs folder may have changed while this was in flight - a stale
      // cache read for the old folder must not paint over the new one.
      if (dir !== songsDir) return;
      if (res.songs && res.songs.length) {
        setLibSongs(res.songs);
        setLibLoaded(true);
      }
    } catch {
      // Real scan below is the source of truth either way.
    }
  }

  async function loadLibrary() {
    setLibLoading(true);
    setScanCount(0);
    try {
      const res = await api.post<{ jobId: string }>("/songs/library/scan", { dir: songsDir || undefined });
      pollScan(res.jobId);
    } catch (e) {
      toast.error("Could not read songs folder", (e as ApiError).message);
      setLibLoading(false);
    }
  }

  function pollScan(jobId: string) {
    if (scanPollRef.current) window.clearInterval(scanPollRef.current);
    scanPollRef.current = window.setInterval(async () => {
      try {
        const job = await api.post<ScanJob>("/songs/library/scan/status", { jobId });
        setScanCount(job.count);
        if (job.status === "done") {
          window.clearInterval(scanPollRef.current!);
          scanPollRef.current = null;
          const next = job.songs || [];
          setLibSongs(next);
          setLibLoaded(true);
          setLibLoading(false);
          setLibSelected((prev) => {
            if (prev.size === 0) return prev;
            const validPaths = new Set(next.map((s) => s.path));
            const filtered = new Set([...prev].filter((p) => validPaths.has(p)));
            return filtered.size === prev.size ? prev : filtered;
          });
        } else if (job.status === "error") {
          window.clearInterval(scanPollRef.current!);
          scanPollRef.current = null;
          toast.error("Could not read songs folder", job.error || "Unknown error");
          setLibLoading(false);
        }
      } catch (e) {
        window.clearInterval(scanPollRef.current!);
        scanPollRef.current = null;
        toast.error("Could not read songs folder", (e as ApiError).message);
        setLibLoading(false);
      }
    }, POLL_MS);
  }

  async function deleteLibraryPaths(paths: string[]) {
    if (!paths.length) return;
    setLibDeleting(true);
    try {
      const res = await api.post<{ deleted: string[]; failed: { path: string; error: string }[] }>("/songs/library/delete", { paths });
      toast.success(
        `Deleted ${res.deleted.length} song${res.deleted.length === 1 ? "" : "s"}`,
        res.failed.length ? `${res.failed.length} could not be removed.` : undefined,
      );
      setLibSongs((prev) => prev.filter((s) => !res.deleted.includes(s.path)));
      setLibSelected((prev) => {
        const n = new Set(prev);
        res.deleted.forEach((p) => n.delete(p));
        return n;
      });
    } catch (e) {
      toast.error("Deletion failed", (e as ApiError).message);
    } finally {
      setLibDeleting(false);
    }
  }

  async function convertSelected(target: "sng" | "folder" | "keep", stripVideo: boolean) {
    const paths = [...libSelected];
    if (!paths.length) return;
    try {
      const res = await api.post<{ jobId: string }>("/songs/library/convert", {
        paths,
        target,
        stripVideo,
        dir: songsDir || undefined,
      });
      pollConvert(res.jobId);
    } catch (e) {
      toast.error("Conversion failed", (e as ApiError).message);
    }
  }

  function pollConvert(jobId: string) {
    if (convertPollRef.current) window.clearInterval(convertPollRef.current);
    convertPollRef.current = window.setInterval(async () => {
      try {
        const job = await api.post<ConvertJob>("/songs/library/convert/status", { jobId });
        setConvertJob(job);
        if (job.status === "done") {
          window.clearInterval(convertPollRef.current!);
          convertPollRef.current = null;
          const ok = job.queue.filter((q) => q.status === "done").length;
          const skipped = job.queue.filter((q) => q.status === "skipped").length;
          const failed = job.queue.filter((q) => q.status === "failed").length;
          const detail = [
            skipped ? `${skipped} unchanged` : null,
            failed ? `${failed} failed` : null,
          ].filter(Boolean).join(" · ") || undefined;
          toast.success(`Converted ${ok}/${job.total}`, detail);
          setLibSelected(new Set());
          setTimeout(() => setConvertJob(null), 2500);
          loadLibrary();
        }
      } catch (e) {
        window.clearInterval(convertPollRef.current!);
        convertPollRef.current = null;
        toast.error("Conversion failed", (e as ApiError).message);
        setConvertJob(null);
      }
    }, POLL_MS);
  }

  function toggleLibSelectAll() {
    if (libSelected.size === libSongs.length && libSongs.length > 0) {
      setLibSelected(new Set());
    } else {
      setLibSelected(new Set(libSongs.map((s) => s.path)));
    }
  }

  async function setDir() {
    const d = await pickFolder("Select your Clone Hero songs folder");
    if (d) {
      await update({ sm_songs_dir: d });
      toast.success("Songs folder set", d);
    }
  }

  async function download(list: Song[]) {
    if (!list.length) return;
    try {
      const res = await api.post<{ jobId: string }>("/songs/download", {
        songs: list.map((s) => ({ md5: s.md5, name: s.name, artist: s.artist })),
        dir: songsDir || undefined,
      });
      pollDownload(res.jobId);
    } catch (e) {
      toast.error("Download failed", (e as ApiError).message);
    }
  }

  // An unfiltered "download all" is the whole-catalog case, handled by the
  // resumable bulk subsystem below (checkpointed to disk, survives an app
  // restart). A filtered one (a typed query or instrument/difficulty set) is
  // a one-off batch scoped to those filters, so it stays on the simpler
  // fire-and-forget job used for an explicit multi-select download.
  async function downloadAll() {
    if (!found) return;
    if (!query && !instrument && !difficulty) {
      startBulk(false);
      return;
    }
    try {
      const res = await api.post<{ jobId: string }>("/songs/download-all", {
        query,
        instrument: instrument || undefined,
        difficulty: difficulty || undefined,
        dir: songsDir || undefined,
      });
      pollDownload(res.jobId);
    } catch (e) {
      toast.error("Download failed", (e as ApiError).message);
    }
  }

  async function refreshBulkStatus() {
    try {
      const st = await api.post<BulkStatus>("/songs/bulk/status", {});
      setBulkStatus(st.status === "none" ? null : st);
    } catch {
      // Best-effort - the next poll (or the next time this tool opens) tries again.
    }
  }

  async function startBulk(resume: boolean) {
    setBulkStarting(true);
    try {
      const st = await api.post<BulkStatus>("/songs/bulk/start", { dir: songsDir || undefined, resume });
      setBulkStatus(st);
    } catch (e) {
      toast.error("Couldn't start downloading", (e as ApiError).message);
    } finally {
      setBulkStarting(false);
    }
  }

  async function stopBulk() {
    try {
      const st = await api.post<BulkStatus>("/songs/bulk/stop", {});
      setBulkStatus(st);
    } catch (e) {
      toast.error("Couldn't stop", (e as ApiError).message);
    }
  }

  async function skipCurrentBulk() {
    try {
      const st = await api.post<BulkStatus>("/songs/bulk/skip", {});
      setBulkStatus(st);
    } catch {
      // Nothing to skip (job already finished/stopped) - safe to ignore.
    }
  }

  async function discardBulk() {
    try {
      await api.post("/songs/bulk/discard", {});
    } catch (e) {
      toast.error("Couldn't dismiss", (e as ApiError).message);
      return;
    }
    setBulkStatus(null);
  }

  function pollDownload(jobId: string) {
    if (downloadPollRef.current) window.clearInterval(downloadPollRef.current);
    downloadPollRef.current = window.setInterval(async () => {
      try {
        const job = await api.post<DownloadJob>("/songs/download/status", { jobId });
        setDownloadJob(job);
        if (job.status === "done") {
          window.clearInterval(downloadPollRef.current!);
          downloadPollRef.current = null;
          if (job.error) {
            toast.error("Download failed", job.error);
            setDownloadJob(null);
            return;
          }
          const ok = job.queue.filter((q) => q.status === "done").length;
          const skipped = job.queue.filter((q) => q.status === "skipped").length;
          const failed = job.queue.filter((q) => q.status === "failed").length;
          const detail = [
            skipped ? `${skipped} already downloaded, skipped` : null,
            failed ? `${failed} failed` : null,
          ].filter(Boolean).join(" · ") || job.dir;
          toast.success(`Downloaded ${ok}/${job.total}`, detail);
          const finishedMd5s = new Set(job.queue.filter((q) => q.status === "done" || q.status === "skipped").map((q) => q.md5));
          setSongs((prev) => prev.map((s) => (finishedMd5s.has(s.md5) ? { ...s, alreadyDownloaded: true } : s)));
          setSelectAll(false);
          setSelected(new Set());
          setTimeout(() => setDownloadJob(null), 2500);
        }
      } catch (e) {
        window.clearInterval(downloadPollRef.current!);
        downloadPollRef.current = null;
        toast.error("Download failed", (e as ApiError).message);
        setDownloadJob(null);
      }
    }, POLL_MS);
  }

  return (
    <Page
      title="CHSongManager"
      subtitle="Search ChorusEncore and manage your downloaded charts"
      icon={<Music2 size={20} />}
      actions={
        tab === "search" ? (
          <>
            {selected.size > 0 && (
              <button className="btn btn-primary" onClick={() => download(songs.filter((s) => selected.has(s.md5)))}>
                <Download size={15} /> Download {selected.size}
              </button>
            )}
            {searched && found > 0 && !downloadJob && (query || instrument || difficulty) && (
              <button className="btn btn-primary" onClick={downloadAll}>
                <Download size={15} /> Download all {found.toLocaleString()} results
              </button>
            )}
            <button className="btn btn-ghost" onClick={setDir}>
              <FolderInput size={15} /> {songsDir ? "Songs folder" : "Set folder"}
            </button>
          </>
        ) : (
          <>
            {libSelected.size > 0 && (
              <>
                <button className="btn btn-ghost" onClick={() => convertSelected("keep", true)} disabled={converting}>
                  {converting ? <Spinner size={15} /> : <VideoOff size={15} />} Remove video
                </button>
                {libSelectedHasSng && (
                  <button className="btn btn-ghost" onClick={() => convertSelected("folder", false)} disabled={converting}>
                    <FolderOutput size={15} /> To folder
                  </button>
                )}
                {libSelectedHasFolder && (
                  <button className="btn btn-ghost" onClick={() => convertSelected("sng", false)} disabled={converting}>
                    <FileArchive size={15} /> To .sng
                  </button>
                )}
                <button className="btn btn-danger" onClick={() => deleteLibraryPaths([...libSelected])} disabled={libDeleting}>
                  {libDeleting ? <Spinner size={15} /> : <Trash2 size={15} />} Delete {libSelected.size}
                </button>
              </>
            )}
            <button className="btn btn-ghost" onClick={setDir}>
              <FolderInput size={15} /> {songsDir ? "Songs folder" : "Set folder"}
            </button>
          </>
        )
      }
    >
      <div className="mb-4 inline-flex rounded-[12px] p-1" style={{ background: "var(--card2)", border: "1px solid var(--border)" }}>
        <button
          onClick={() => setTab("search")}
          className="flex items-center rounded-[9px] px-4 py-1.5 text-[13px] font-semibold transition-colors"
          style={{ background: tab === "search" ? "var(--accent)" : "transparent", color: tab === "search" ? "#fff" : "var(--text-mid)" }}
        >
          <Search size={13} className="mr-1.5" /> Search
        </button>
        <button
          onClick={() => setTab("library")}
          className="flex items-center rounded-[9px] px-4 py-1.5 text-[13px] font-semibold transition-colors"
          style={{ background: tab === "library" ? "var(--accent)" : "transparent", color: tab === "library" ? "#fff" : "var(--text-mid)" }}
        >
          <HardDrive size={13} className="mr-1.5" /> Library{libLoaded && libSongs.length > 0 ? ` (${libSongs.length})` : ""}
        </button>
      </div>

      {tab === "search" ? (
        <>
          {!bulkStatus ? (
            <Card className="mb-4 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[13px] font-semibold">Download every song on ChorusEncore</div>
                <div className="text-[12px]" style={{ color: "var(--text-mid)" }}>
                  One click, runs in the background, resumes automatically if interrupted.
                </div>
              </div>
              <button className="btn btn-primary flex-none" onClick={() => startBulk(false)} disabled={bulkStarting}>
                {bulkStarting ? <Spinner size={15} /> : <Download size={15} />} Download All Songs
              </button>
            </Card>
          ) : bulkStatus.status === "running" ? (
            <Card className="mb-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="truncate text-[13px] font-semibold">
                  {bulkStatus.phase === "deferred"
                    ? `Retrying ${bulkStatus.deferredCount ?? 0} slow download${bulkStatus.deferredCount === 1 ? "" : "s"}…`
                    : `Downloading every song… ${((bulkStatus.done ?? 0) + (bulkStatus.skipped ?? 0)).toLocaleString()}/${(bulkStatus.found ?? 0).toLocaleString()}`}
                </span>
                <div className="flex flex-none items-center gap-2">
                  <button className="btn btn-ghost btn-sm" onClick={skipCurrentBulk}>
                    <SkipForward size={13} /> Skip
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={stopBulk}>
                    <StopCircle size={13} /> Stop
                  </button>
                </div>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--card2)" }}>
                <div
                  className="h-full rounded-full transition-[width]"
                  style={{
                    width: `${bulkStatus.found ? (((bulkStatus.done ?? 0) + (bulkStatus.skipped ?? 0)) / bulkStatus.found) * 100 : 0}%`,
                    background: "var(--accent)",
                  }}
                />
              </div>
              <div className="mt-2 flex items-center justify-between gap-3 text-[12px]" style={{ color: "var(--text-mid)" }}>
                <span className="min-w-0 truncate">
                  {bulkStatus.currentName || "Preparing…"}
                  {bulkStatus.currentTotal ? ` · ${fmtSize(bulkStatus.currentBytes || 0)}/${fmtSize(bulkStatus.currentTotal)}` : ""}
                </span>
                <span className="flex-none">
                  {(bulkStatus.skipped ?? 0).toLocaleString()} already owned
                  {bulkStatus.failedCount ? ` · ${bulkStatus.failedCount.toLocaleString()} failed` : ""}
                </span>
              </div>
            </Card>
          ) : bulkStatus.status === "done" ? (
            <Card className="mb-4 flex items-center justify-between gap-3">
              <span className="text-[13px] font-semibold">
                Downloaded everything - {(bulkStatus.done ?? 0).toLocaleString()} new,{" "}
                {(bulkStatus.skipped ?? 0).toLocaleString()} already owned
                {bulkStatus.failedCount ? `, ${bulkStatus.failedCount.toLocaleString()} failed` : ""}
              </span>
              <button className="btn btn-ghost btn-sm flex-none" onClick={discardBulk} title="Dismiss">
                <X size={13} />
              </button>
            </Card>
          ) : (
            <Card className="mb-4 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[13px] font-semibold">
                  {bulkStatus.status === "interrupted" ? "Download all was interrupted" : "Download all paused"} -{" "}
                  {((bulkStatus.done ?? 0) + (bulkStatus.skipped ?? 0)).toLocaleString()}/{(bulkStatus.found ?? 0).toLocaleString()} songs
                </div>
                {bulkStatus.stopReason && (
                  <div className="truncate text-[12px]" style={{ color: "var(--text-mid)" }}>{bulkStatus.stopReason}</div>
                )}
              </div>
              <div className="flex flex-none items-center gap-2">
                <button className="btn btn-primary btn-sm" onClick={() => startBulk(true)} disabled={bulkStarting}>
                  {bulkStarting ? <Spinner size={13} /> : <Download size={13} />} Resume
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => startBulk(false)} disabled={bulkStarting}>Start over</button>
                <button className="btn btn-ghost btn-sm" onClick={discardBulk} title="Dismiss">
                  <X size={13} />
                </button>
              </div>
            </Card>
          )}

          <Card className="mb-4">
            <form onSubmit={(e) => { e.preventDefault(); search(true); }} className="flex gap-2.5">
              <div className="relative flex-1">
                <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: "var(--text-dim)" }} />
                <input className="input pl-10" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search songs, artists, charters…" />
              </div>
              <select className="select w-32 flex-none" value={instrument} onChange={(e) => setInstrument(e.target.value)}>
                {INSTRUMENTS.map((i) => <option key={i} value={i}>{i ? cap(i) : "Instrument"}</option>)}
              </select>
              <select className="select w-32 flex-none" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                {DIFFICULTIES.map((d) => <option key={d} value={d}>{d ? cap(d) : "Difficulty"}</option>)}
              </select>
              <button type="submit" className="btn btn-primary flex-none" disabled={loading}>
                {loading && page === 1 ? <Spinner size={15} /> : <Search size={15} />} Search
              </button>
            </form>
          </Card>

          {downloadJob && (
            <Card className="mb-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[13px] font-semibold">
                  {downloadJob.status === "collecting"
                    ? `Finding songs… ${downloadJob.total.toLocaleString()} queued`
                    : downloadJob.status === "done"
                      ? "Download complete"
                      : `Downloading… ${downloadJob.done}/${downloadJob.total}`}
                </span>
                {downloadJob.status !== "done" && <Spinner size={14} />}
              </div>
              <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--card2)" }}>
                <div
                  className="h-full rounded-full transition-[width]"
                  style={{ width: `${downloadJob.status !== "collecting" && downloadJob.total ? (downloadJob.done / downloadJob.total) * 100 : 0}%`, background: "var(--accent)" }}
                />
              </div>
              {downloadJob.status === "running" && (
                <div className="mt-2 truncate text-[12px]" style={{ color: "var(--text-mid)" }}>
                  {downloadJob.queue.find((q) => q.status === "downloading")?.name || "Preparing…"}
                </div>
              )}
            </Card>
          )}

          {loading && !searched ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-[76px]" />)}
            </div>
          ) : !searched ? (
            <EmptyState icon={<Music2 size={26} />} title="Find your next chart" hint="Search the ChorusEncore library by song, artist, album or charter, then download straight to your songs folder." />
          ) : songs.length === 0 ? (
            <EmptyState icon={<Search size={26} />} title="No results" hint={`Nothing matched "${query}". Try a different search.`} />
          ) : (
            <>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-[13px]" style={{ color: "var(--text-mid)" }}>{found.toLocaleString()} results · showing {songs.length}</span>
                <button className="btn btn-ghost btn-sm" onClick={toggleSelectAll}>
                  {selectAll ? <CheckSquare size={14} /> : <Square size={14} />} {selectAll ? "Deselect all" : "Select all"}
                </button>
              </div>
              <div className="flex flex-col gap-2">
                {songs.map((s) => {
                  const isDl = downloadingMd5s.has(s.md5);
                  const isSel = selected.has(s.md5);
                  const already = s.alreadyDownloaded;
                  return (
                    <Card key={s.md5 + s.name} className="flex items-center gap-3.5" pad={false}>
                      <div className="flex items-center gap-3.5 py-2.5 pl-3">
                        <input type="checkbox" className="check" checked={isSel} onChange={() => setSelected((p) => { const n = new Set(p); n.has(s.md5) ? n.delete(s.md5) : n.add(s.md5); return n; })} />
                        <Art md5={s.albumArtMd5} />
                      </div>
                      <div className="min-w-0 flex-1 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-[14px] font-bold">{renderRichText(s.name) || "Untitled"}</span>
                          {s.hasVideoBackground && <Video size={13} style={{ color: "var(--text-dim)" }} />}
                          {already && <span className="badge badge-ok">Downloaded</span>}
                        </div>
                        <div className="truncate text-[12px]" style={{ color: "var(--text-mid)" }}>
                          {renderRichText(s.artist)}{s.album ? ` · ${s.album}` : ""}{s.year ? ` · ${s.year}` : ""}
                        </div>
                        <div className="truncate text-[11px]" style={{ color: "var(--text-dim)" }}>
                          {s.charter ? <>Charted by {renderRichText(s.charter)}</> : ""}{s.length ? ` · ${fmtLen(s.length)}` : ""}
                        </div>
                      </div>
                      <div className="pr-3">
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => download([s])}
                          disabled={isDl || already}
                          title={already ? "Already in your songs folder" : ""}
                        >
                          {isDl ? <Spinner size={14} /> : <Download size={14} />} {isDl ? "" : already ? "Downloaded" : "Get"}
                        </button>
                      </div>
                    </Card>
                  );
                })}
              </div>
              {hasMore && (
                <div ref={sentinelRef} className="mt-2 flex justify-center py-4">
                  {loading && <Spinner size={16} />}
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <>
          {convertJob && (
            <Card className="mb-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[13px] font-semibold">
                  {convertJob.status === "done" ? "Conversion complete" : "Converting…"} {convertJob.done}/{convertJob.total}
                </span>
                {convertJob.status !== "done" && <Spinner size={14} />}
              </div>
              <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--card2)" }}>
                <div
                  className="h-full rounded-full transition-[width]"
                  style={{ width: `${convertJob.total ? (convertJob.done / convertJob.total) * 100 : 0}%`, background: "var(--accent)" }}
                />
              </div>
            </Card>
          )}
          {libLoading && !libLoaded ? (
            <Card className="flex flex-col items-center justify-center gap-3 py-12">
              <Spinner />
              <span style={{ color: "var(--text-mid)" }}>
                Scanning your songs folder…{scanCount > 0 ? ` ${scanCount.toLocaleString()} found` : ""}
              </span>
            </Card>
          ) : libSongs.length === 0 ? (
            <EmptyState
              icon={<HardDrive size={26} />}
              title="No downloaded songs found"
              hint={songsDir ? `Nothing found in ${songsDir}.` : "Set your Clone Hero songs folder to see what's downloaded."}
            />
          ) : (
            <>
              <div className="mb-3 flex items-center justify-between">
                <span className="text-[13px]" style={{ color: "var(--text-mid)" }}>
                  {libSongs.length} song{libSongs.length === 1 ? "" : "s"} · {fmtSize(libSongs.reduce((a, s) => a + s.size, 0))}
                </span>
                <div className="flex items-center gap-2">
                  <button className="btn btn-ghost btn-sm" onClick={loadLibrary} disabled={libLoading}>
                    {libLoading ? <Spinner size={14} /> : <RefreshCw size={14} />} Refresh
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={toggleLibSelectAll}>
                    {libSelected.size === libSongs.length && libSongs.length > 0 ? <CheckSquare size={14} /> : <Square size={14} />}{" "}
                    {libSelected.size === libSongs.length && libSongs.length > 0 ? "Deselect all" : "Select all"}
                  </button>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                {libSongs.map((s) => {
                  const isSel = libSelected.has(s.path);
                  return (
                    <Card key={s.path} className="flex items-center gap-3.5" pad={false}>
                      <div className="flex items-center gap-3.5 py-2.5 pl-3">
                        <input type="checkbox" className="check" checked={isSel} onChange={() => setLibSelected((p) => { const n = new Set(p); n.has(s.path) ? n.delete(s.path) : n.add(s.path); return n; })} />
                        <LibraryArt art={s.art} />
                      </div>
                      <div className="min-w-0 flex-1 py-2.5">
                        <div className="truncate text-[14px] font-bold">{renderRichText(s.name) || "Untitled"}</div>
                        <div className="truncate text-[12px]" style={{ color: "var(--text-mid)" }}>
                          {renderRichText(s.artist)}{s.charter ? <> · Charted by {renderRichText(s.charter)}</> : ""}
                        </div>
                        <div className="truncate text-[11px]" style={{ color: "var(--text-dim)" }}>
                          {fmtSize(s.size)} · {s.type === "sng" ? ".sng" : "folder"}
                        </div>
                      </div>
                      <div className="pr-3">
                        <button className="btn btn-ghost btn-sm" onClick={() => deleteLibraryPaths([s.path])} disabled={libDeleting}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </Page>
  );
}

function Art({ md5 }: { md5: string }) {
  const [err, setErr] = useState(false);
  if (!md5 || err)
    return <div className="grid h-12 w-12 flex-none place-items-center rounded-lg" style={{ background: "var(--card2)", border: "1px solid var(--border)", color: "var(--text-dim)" }}><Music2 size={18} /></div>;
  return <img src={`https://files.enchor.us/${md5}.jpg`} alt="" onError={() => setErr(true)} className="h-12 w-12 flex-none rounded-lg object-cover" style={{ border: "1px solid var(--border)" }} draggable={false} />;
}

function LibraryArt({ art }: { art: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    if (!art) return;
    let blobUrl: string | null = null;
    let cancelled = false;
    fetchBlobUrl(`/songs/library/art?path=${encodeURIComponent(art)}`)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u);
          return;
        }
        blobUrl = u;
        setUrl(u);
      })
      .catch(() => setErr(true));
    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [art]);

  if (!art || err)
    return <div className="grid h-12 w-12 flex-none place-items-center rounded-lg" style={{ background: "var(--card2)", border: "1px solid var(--border)", color: "var(--text-dim)" }}><Music2 size={18} /></div>;
  if (!url) return <div className="h-12 w-12 flex-none rounded-lg skeleton" />;
  return <img src={url} alt="" className="h-12 w-12 flex-none rounded-lg object-cover" style={{ border: "1px solid var(--border)" }} draggable={false} />;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
function fmtLen(ms: number) {
  const sec = Math.round((ms > 100000 ? ms / 1000 : ms));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
