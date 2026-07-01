// Renders the TextMesh Pro-style rich text tags Clone Hero uses in song.ini
// name/artist/charter fields (the same <color=#RRGGBB> markup CHNameGen
// produces - see lib/namegen.ts) as styled React nodes instead of raw tags.

import type { CSSProperties, ReactNode } from "react";

interface TagState {
  color?: string;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strike?: boolean;
}

const TAG_RE = /<(\/?)(color|b|i|u|s|size|cspace)(?:=[^>]*)?>/gi;

export function renderRichText(text: string): ReactNode {
  if (!text || !text.includes("<")) return text;

  const stack: TagState[] = [{}];
  const nodes: ReactNode[] = [];
  let key = 0;
  let lastIndex = 0;
  TAG_RE.lastIndex = 0;

  const flush = (chunk: string) => {
    if (!chunk) return;
    const state = stack[stack.length - 1];
    if (!state.color && !state.bold && !state.italic && !state.underline && !state.strike) {
      nodes.push(chunk);
      return;
    }
    const style: CSSProperties = {};
    if (state.color) style.color = state.color;
    if (state.bold) style.fontWeight = 700;
    if (state.italic) style.fontStyle = "italic";
    const deco = [state.underline && "underline", state.strike && "line-through"].filter(Boolean).join(" ");
    if (deco) style.textDecoration = deco;
    nodes.push(
      <span key={key++} style={style}>
        {chunk}
      </span>,
    );
  };

  let match: RegExpExecArray | null;
  while ((match = TAG_RE.exec(text))) {
    flush(text.slice(lastIndex, match.index));
    lastIndex = TAG_RE.lastIndex;
    const [full, closing, tag] = match;
    if (closing) {
      if (stack.length > 1) stack.pop();
      continue;
    }
    const next: TagState = { ...stack[stack.length - 1] };
    const lower = tag.toLowerCase();
    if (lower === "color") {
      const eq = full.indexOf("=");
      next.color = eq >= 0 ? full.slice(eq + 1, -1).replace(/"/g, "") : next.color;
    } else if (lower === "b") next.bold = true;
    else if (lower === "i") next.italic = true;
    else if (lower === "u") next.underline = true;
    else if (lower === "s") next.strike = true;
    // size/cspace are consumed (so the raw tag doesn't leak into the text)
    // but not visually applied here - this is a list row, not the game HUD.
    stack.push(next);
  }
  flush(text.slice(lastIndex));

  return nodes.length ? <>{nodes}</> : text;
}
