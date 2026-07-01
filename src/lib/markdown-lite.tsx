// Minimal Markdown renderer for GitHub release notes inside the update
// modal: headers, **bold**, `code`, [links](url), "-"/"*" bullets, and "---"
// rules. Raw HTML tags (release.md uses a few for centered images) are
// stripped rather than rendered, since this is a small popup summary, not a
// full replica of the GitHub release page.

import type { ReactNode } from "react";

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /(\*\*(.+?)\*\*)|(`(.+?)`)|(\[([^\]]+)\]\(([^)]+)\))/g;
  let key = 0;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1]) {
      nodes.push(<strong key={`${keyPrefix}-${key++}`}>{m[2]}</strong>);
    } else if (m[3]) {
      nodes.push(
        <code key={`${keyPrefix}-${key++}`} className="rounded px-1 py-0.5 text-[11px]" style={{ background: "var(--card2)" }}>
          {m[4]}
        </code>,
      );
    } else if (m[5]) {
      nodes.push(
        <a key={`${keyPrefix}-${key++}`} href={m[7]} target="_blank" rel="noreferrer" className="underline" style={{ color: "var(--accent)" }}>
          {m[6]}
        </a>,
      );
    }
    last = re.lastIndex;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function renderReleaseNotes(markdown: string): ReactNode {
  const clean = markdown.replace(/<[^>]+>/g, "").trim();
  if (!clean) return null;

  const blocks: ReactNode[] = [];
  let listBuf: string[] = [];
  let bkey = 0;

  const flushList = () => {
    if (!listBuf.length) return;
    const items = listBuf;
    blocks.push(
      <ul key={`ul-${bkey++}`} className="ml-4 list-disc space-y-1">
        {items.map((item, i) => (
          <li key={i}>{renderInline(item, `li-${bkey}-${i}`)}</li>
        ))}
      </ul>,
    );
    listBuf = [];
  };

  for (const raw of clean.split("\n")) {
    const line = raw.trim();
    if (!line) {
      flushList();
      continue;
    }
    if (/^-{3,}$/.test(line)) {
      flushList();
      blocks.push(<hr key={`hr-${bkey++}`} className="my-2" style={{ borderColor: "var(--border)" }} />);
      continue;
    }
    const header = line.match(/^(#{1,6})\s+(.*)$/);
    if (header) {
      flushList();
      const level = header[1].length;
      blocks.push(
        <div
          key={`h-${bkey++}`}
          className={level <= 2 ? "mt-2 text-[13px] font-bold" : "mt-2 text-[12.5px] font-semibold"}
        >
          {renderInline(header[2], `h-${bkey}`)}
        </div>,
      );
      continue;
    }
    const bullet = line.match(/^[-*]\s+(.*)$/);
    if (bullet) {
      listBuf.push(bullet[1]);
      continue;
    }
    flushList();
    blocks.push(
      <p key={`p-${bkey++}`} className="leading-relaxed">
        {renderInline(line, `p-${bkey}`)}
      </p>,
    );
  }
  flushList();

  return <>{blocks}</>;
}
