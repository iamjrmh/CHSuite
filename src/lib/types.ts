export type ToolId =
  | "about"
  | "menuchanger"
  | "namegen"
  | "notegen"
  | "cleaner"
  | "patcher"
  | "songmanager"
  | "manager"
  | "settings";

export interface ApiEnvelope<T> {
  ok?: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface AppConfig {
  theme: string;
  default_data_path: string;
  ch_default_install: string;
  sm_songs_dir: string;
  discord_rpc: boolean;
  default_install_dir: string;
  skipped_update_version: string;
  [k: string]: unknown;
}

export interface Install {
  path: string;
  name?: string;
  version: string;
  fromLauncher: boolean;
  channel?: string;
  exists: boolean;
  exe?: string;
  isDefault?: boolean;
}

export interface Background {
  name: string;
  matched: boolean;
  asset: string;
  requiredSize: [number, number];
  preview: string;
}

export interface Song {
  md5: string;
  name: string;
  artist: string;
  album: string;
  genre: string;
  year: string | number;
  charter: string;
  length: number;
  albumArtMd5: string;
  hasVideoBackground: boolean;
  diffGuitar: number;
  diffDrums: number;
  alreadyDownloaded: boolean;
}
