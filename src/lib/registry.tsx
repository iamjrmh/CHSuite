import {
  Info,
  Image,
  Type,
  Palette,
  Trash2,
  Wrench,
  Music2,
  Boxes,
  Settings,
  type LucideIcon,
} from "lucide-react";
import type { ToolId } from "./types";

export interface ToolMeta {
  id: ToolId;
  label: string;
  icon: LucideIcon;
  tagline: string;
  description: string;
}

export const TOOLS: ToolMeta[] = [
  {
    id: "about",
    label: "About",
    icon: Info,
    tagline: "Overview & quick launch",
    description:
      "Your home base. Read what each tool does and jump straight into it.",
  },
  {
    id: "menuchanger",
    label: "CHMenuChanger",
    icon: Image,
    tagline: "Swap menu backgrounds",
    description:
      "Replace Clone Hero's menu background textures directly in the Unity asset files, with live previews and automatic backups.",
  },
  {
    id: "namegen",
    label: "CHNameGen",
    icon: Type,
    tagline: "Colored player names",
    description:
      "Build gradient or per-letter colored player names with styling, then export straight to profiles.ini.",
  },
  {
    id: "notegen",
    label: "CHNoteGen",
    icon: Palette,
    tagline: "Custom note colors",
    description:
      "Design your own note colors across guitar, drums and 6-fret, then export a ready-to-use color profile.",
  },
  {
    id: "cleaner",
    label: "CHCleaner",
    icon: Trash2,
    tagline: "Purge broken songs",
    description:
      "Parse badsongs.txt and bulk-delete the ERROR folders cluttering your library - with a full deletion log.",
  },
  {
    id: "patcher",
    label: "CHPatcher",
    icon: Wrench,
    tagline: "Stop launcher resets",
    description:
      "Patch any registered install so the launcher stops resetting your game files. One click to patch or revert.",
  },
  {
    id: "songmanager",
    label: "CHSongManager",
    icon: Music2,
    tagline: "Download charts",
    description:
      "Search the ChorusEncore library and download charts straight into your songs folder, individually or in bulk.",
  },
  {
    id: "manager",
    label: "CHManager",
    icon: Boxes,
    tagline: "Manage installs",
    description:
      "See every Clone Hero install at a glance, launch or patch them, and download any release or PTB build from GitHub.",
  },
  {
    id: "settings",
    label: "Settings",
    icon: Settings,
    tagline: "Themes & preferences",
    description: "Switch between 25 themes and tweak how CHSuite behaves.",
  },
];

export const TOOL_MAP: Record<ToolId, ToolMeta> = Object.fromEntries(
  TOOLS.map((t) => [t.id, t]),
) as Record<ToolId, ToolMeta>;
