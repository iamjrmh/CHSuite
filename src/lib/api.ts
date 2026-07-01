// Sidecar HTTP client.
//
// The Tauri Rust shell launches the Python sidecar and exposes the ephemeral
// port it bound to via the `sidecar_port` command. We resolve that once, build
// the base URL, then talk plain JSON/HTTP to the localhost API.

import { invoke } from "@tauri-apps/api/core";
import type { ApiEnvelope } from "./types";

let basePromise: Promise<string> | null = null;

async function resolveBase(): Promise<string> {
  // Poll the Rust command for a short while - the sidecar may still be booting
  // when the window first paints.
  for (let attempt = 0; attempt < 40; attempt++) {
    let port: number | null = null;
    try {
      port = await invoke<number | null>("sidecar_port");
    } catch {
      port = null;
    }
    if (port) return `http://127.0.0.1:${port}`;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new ApiError(
    "The CHSuite backend did not start. Make sure Python and the bundled sidecar are available.",
    "sidecar_unavailable",
  );
}

function base(): Promise<string> {
  if (!basePromise) basePromise = resolveBase();
  return basePromise;
}

export class ApiError extends Error {
  code: string;
  data: unknown;
  constructor(message: string, code = "error", data: unknown = null) {
    super(message);
    this.code = code;
    this.data = data;
  }
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): Promise<T> {
  const root = await base();
  let res: Response;
  try {
    res = await fetch(root + path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(
      `Could not reach the backend (${path}).`,
      "network",
      e,
    );
  }
  let json: ApiEnvelope<T>;
  try {
    json = (await res.json()) as ApiEnvelope<T>;
  } catch {
    throw new ApiError(`Bad response from backend (${path}).`, "bad_json");
  }
  if (!res.ok || json.error) {
    throw new ApiError(
      json.message || json.error || `Request failed (${res.status})`,
      json.error || "error",
      json.data,
    );
  }
  return json.data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  /** Warm the connection / surface a clear failure early. */
  health: () => request<{ service: string; version: string }>("GET", "/health"),
};

/** Fetch a binary resource from the sidecar and hand back a blob: URL (caller must revoke it). */
export async function fetchBlobUrl(path: string): Promise<string> {
  const root = await base();
  let res: Response;
  try {
    res = await fetch(root + path);
  } catch (e) {
    throw new ApiError(`Could not reach the backend (${path}).`, "network", e);
  }
  if (!res.ok) throw new ApiError(`Could not load image (${path}).`, "image");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
