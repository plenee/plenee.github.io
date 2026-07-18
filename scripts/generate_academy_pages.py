#!/usr/bin/env python3
"""
Academy chapter page generator — Plenee Academy publishing pipeline.

Converts a single plenee_app/docs/academy/*_expanded.md source file into the
per-chapter HTML pages (plus a track index/TOC page) described in
website/ACADEMY_PUBLISHING_INSTRUCTIONS.md §2-6, reusing the exact template
already established by the hand-built website/academy/track2-visibility/
pages (CSS lifted verbatim from those pages; slug rule verified byte-for-byte
against them by resolve_academy_refs.py).

What this does, per chapter:
  - Strips the file's own Status/Grounding header block (never reader-facing).
  - Renders `## Subheading` sections as <h2> with anchor ids, listed in an
    in-page "In this chapter" jump list (excluding "The takeaway" and
    "Sources", which get their own distinct treatment below).
  - Renders inline **bold**/*italic* markdown.
  - Resolves every `{{ref:ID}}` token into a real relative <a href> link via
    resolve_academy_refs.py (same index, same slug rule) -- this is a real
    improvement over the original hand-built pages, which stripped tokens to
    plain, unlinked text.
  - Renders "## The takeaway" as the distinct teal-callout box the site's
    CSS already defines (`.takeaway`), matching every existing page.
  - Renders a chapter's "## Sources" section (if present) as a numbered
    footnote list at the bottom, with superscript in-text markers and
    back-links -- new CSS for this is added to the shared <style> block
    since no chapter in the original 8 pages had footnotes yet.
  - Emits Prev/Next chapter nav; the track's own index.html for "Next" on
    the last chapter and "Prev" on the first (that index.html is generated
    too, since every existing chapter page's breadcrumb already links to it
    and it doesn't exist on disk yet).

Scope: only handles the `# Chapter N.M -- Title` boundary onward -- it does
not (yet) generate the top-level Academy landing page. Covers every track in
both volumes (Volume 1's plain `N.M` chapter ids and Volume 2's `PMN.M` ids,
the latter displayed to readers with the "PM" shorthand stripped per
ACADEMY_PUBLISHING_INSTRUCTIONS.md §7).

Usage:
    python3 generate_academy_pages.py track2_visibility_expanded.md
        Regenerates one track's chapter pages + its own index.html, from the
        CURRENT source file. Fast, but that index.html's search box will only
        cover this track's chapters until --all is next run.

    python3 generate_academy_pages.py --all
        Regenerates every track from current source and embeds one shared,
        cross-track search index on every track's index.html. Run this after
        any content change so "Search Academy" stays corpus-wide accurate.

No third-party dependencies -- stdlib only.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_academy_refs import (  # noqa: E402
    ACADEMY_SRC,
    WEBSITE_DIR,
    build_index,
    slugify_title,
    track_slug_and_num_from_filename,
    resolve_token,
)

CHAPTER_SPLIT_RE = re.compile(r"^#\s*Chapter\s+(\S+)\s*—\s*(.+)$", re.MULTILINE)
SUBHEAD_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
TOKEN_RE = re.compile(r"\{\{ref:([A-Za-z0-9.]+)\}\}")
FOOTNOTE_MARKER_RE = re.compile(r"\[\^([A-Za-z0-9.\-]+)\]")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([A-Za-z0-9.\-]+)\]:\s*(.+)$", re.MULTILINE)

DISCLAIMER = "This is financial information and education, not personalized financial advice."

# ---------------------------------------------------------------------------
# Shared template pieces, lifted verbatim from the hand-built track2 pages
# (see website/academy/track2-visibility/*.html) plus new footnote CSS.
# ---------------------------------------------------------------------------

STYLE_BLOCK = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --navy:    #0C1929;
  --navy2:   #152236;
  --teal:    #0FA8BC;
  --teal-d:  #0A8A9E;
  --teal-l:  #E6F7FA;
  --orange:  #E87722;
  --orange-l:#FFF4EC;
  --white:   #FFFFFF;
  --off:     #F6F9FB;
  --text:    #0C1929;
  --muted:   #4E6175;
  --light:   #8A9EB0;
  --border:  #DDE8F0;
  --green:   #1E9E5E;
  --green-l: #E8FAF2;
}
html { scroll-behavior: smooth; }
body { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, system-ui, sans-serif; color: var(--text); background: var(--white); overflow-x: hidden; }

nav {
  position: sticky; top: 0; z-index: 300;
  background: #0C1929;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  height: 72px; display: flex; align-items: center; justify-content: space-between;
  padding: 0 48px;
}
.nav-logo { display: flex; align-items: center; height: 100%; line-height: 0; }
.nav-logo img { height: 100%; display: block; }
.nav-links { display: flex; gap: 32px; align-items: center; }
.nav-links a { color: #B6C6D6; text-decoration: none; font-size: 15px; font-weight: 500; transition: color .2s; }
.nav-links a:hover { color: var(--teal); }
.nav-links a.active { color: var(--teal); }

footer { background: var(--navy); border-top: 1px solid rgba(255,255,255,.07); padding: 32px 48px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
footer p { color: #2E4A60; font-size: 13px; }
.fl a { color: #2E4A60; font-size: 13px; text-decoration: none; margin-left: 24px; transition: color .2s; }
.fl a:hover { color: var(--teal); }

#disclaimer-strip { background: var(--off); border-top: 1px solid var(--border); padding: 16px 48px; text-align: center; }
#disclaimer-strip p { font-size: 12px; color: var(--light); line-height: 1.6; max-width: 900px; margin: 0 auto; }

@media (max-width: 768px) {
  nav { padding: 0 20px; height: 56px; }
  .nav-links { display: none; }
  footer { padding: 24px 20px; flex-direction: column; align-items: flex-start; gap: 12px; }
  .fl a { margin-left: 0; margin-right: 20px; }
}


/* ─── PAGE HEADER ─── */
.page-header { background: var(--navy); padding: 64px 48px 52px; text-align: center; }
.page-kicker { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--teal); background: rgba(15,168,188,.12); border: 1px solid rgba(15,168,188,.3); border-radius: 100px; padding: 6px 16px; margin-bottom: 18px; }
.page-header h1 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(32px,4vw,52px); font-weight: 700; color: #fff; letter-spacing: -1px; line-height: 1.15; margin-bottom: 14px; }
.page-header p { font-size: 16px; color: #7A9AB5; max-width: 640px; margin: 0 auto; line-height: 1.65; }

/* ─── BREADCRUMB ─── */
.crumb { max-width: 760px; margin: 28px auto 0; padding: 0 48px; display: flex; gap: 8px; align-items: center; font-size: 13px; color: var(--light); }
.crumb a { color: var(--muted); text-decoration: none; }
.crumb a:hover { color: var(--teal); }

/* ─── CHAPTER PAGE ─── */
.chapter-wrap { max-width: 760px; margin: 0 auto; padding: 44px 48px 24px; }
.chapter-eyebrow { font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--teal); margin-bottom: 12px; }
.chapter-wrap h1 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(28px,4vw,42px); font-weight: 700; color: var(--navy); letter-spacing: -.8px; line-height: 1.2; margin-bottom: 28px; }
.chapter-disclaimer { font-size: 12px; color: var(--light); line-height: 1.6; margin-bottom: 36px; padding-bottom: 28px; border-bottom: 1px solid var(--border); }

.jump-list { background: var(--off); border: 1.5px solid var(--border); border-radius: 14px; padding: 22px 26px; margin-bottom: 44px; }
.jump-list .jl-title { font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--teal); margin-bottom: 12px; }
.jump-list ol { padding-left: 18px; }
.jump-list li { margin-bottom: 6px; }
.jump-list a { color: var(--muted); text-decoration: none; font-size: 14px; transition: color .2s; }
.jump-list a:hover { color: var(--teal); }

.chapter-body h2 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(20px,2.5vw,26px); font-weight: 700; color: var(--navy); letter-spacing: -.3px; line-height: 1.3; margin: 44px 0 18px; }
.chapter-body p { font-size: 16px; color: var(--muted); line-height: 1.85; margin-bottom: 20px; }
.chapter-body p strong { color: var(--text); font-weight: 700; }
.chapter-body p em { color: var(--text); font-style: italic; }
.chapter-body sup { font-size: 11px; margin-left: 1px; }
.chapter-body sup a { color: var(--teal-d); text-decoration: none; font-weight: 700; }
.chapter-body sup a:hover { text-decoration: underline; }

.takeaway { background: var(--teal-l); border-left: 4px solid var(--teal); border-radius: 0 14px 14px 0; padding: 26px 30px; margin: 44px 0 8px; }
.takeaway .tk-label { font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--teal-d); margin-bottom: 10px; }
.takeaway p { color: var(--text); font-size: 16px; line-height: 1.75; margin-bottom: 0; font-weight: 500; }

.sources { margin: 36px 0 8px; padding-top: 24px; border-top: 1px solid var(--border); }
.sources .src-title { font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--teal-d); margin-bottom: 14px; }
.sources ol { padding-left: 20px; }
.sources li { font-size: 13px; color: var(--muted); line-height: 1.65; margin-bottom: 10px; }
.sources li a { color: var(--teal-d); text-decoration: none; margin-left: 4px; }
.sources li a:hover { text-decoration: underline; }

.chapter-nav { max-width: 760px; margin: 0 auto; padding: 8px 48px 64px; display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.cn-link { display: block; border: 1.5px solid var(--border); border-radius: 14px; padding: 20px 22px; text-decoration: none; transition: border-color .2s, transform .2s; }
.cn-link:hover { border-color: var(--teal); transform: translateY(-2px); }
.cn-link.next { text-align: right; }
.cn-dir { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--light); margin-bottom: 6px; }
.cn-title { font-size: 15px; font-weight: 700; color: var(--navy); line-height: 1.4; }
.cn-empty { visibility: hidden; }

/* ─── TRACK INDEX ─── */
.track-wrap { max-width: 900px; margin: 0 auto; padding: 56px 48px 88px; }
.chapter-grid { display: flex; flex-direction: column; gap: 14px; }
.chap-card { display: flex; gap: 20px; align-items: flex-start; border: 1.5px solid var(--border); border-radius: 16px; padding: 24px 26px; text-decoration: none; transition: border-color .2s, transform .2s, box-shadow .2s; }
.chap-card:hover { border-color: var(--teal); transform: translateY(-2px); box-shadow: 0 10px 30px rgba(12,25,41,.07); }
.chap-num { flex-shrink: 0; width: 44px; height: 44px; border-radius: 12px; background: var(--teal-l); color: var(--teal-d); display: flex; align-items: center; justify-content: center; font-family: Georgia, serif; font-weight: 700; font-size: 15px; }
.chap-info h3 { font-size: 17px; color: var(--navy); font-weight: 700; margin-bottom: 6px; line-height: 1.35; }
.chap-info p { font-size: 14px; color: var(--muted); line-height: 1.55; }

/* ─── ACADEMY SEARCH ─── */
/* Grafted verbatim from docs/academy/academy_search_feature_snippet.md
   (built + verified 2026-07-18 by a concurrent session). Listing pages only
   (Academy index + each track index) -- never on individual chapter pages. */
.academy-search-wrap { max-width: 620px; margin: 0 auto; padding: 0 48px; position: relative; }
.academy-search-box { position: relative; }
.academy-search-box svg { position: absolute; left: 18px; top: 50%; transform: translateY(-50%); color: var(--light); pointer-events: none; }
.academy-search-input { width: 100%; font-family: inherit; font-size: 16px; color: var(--text); background: #fff; border: 1.5px solid var(--border); border-radius: 12px; padding: 15px 18px 15px 48px; outline: none; transition: border-color .2s, box-shadow .2s; }
.academy-search-input:focus { border-color: var(--teal); box-shadow: 0 0 0 3px rgba(15,168,188,0.12); }
.search-results { margin-top: 14px; display: none; flex-direction: column; gap: 10px; }
.search-results.open { display: flex; }
.search-hit { display: block; border: 1.5px solid var(--border); border-radius: 12px; padding: 16px 18px; text-decoration: none; transition: border-color .2s, transform .2s; }
.search-hit:hover { border-color: var(--teal); transform: translateY(-1px); }
.search-hit .sh-track { font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: var(--teal-d); margin-bottom: 5px; }
.search-hit .sh-title { font-size: 15px; font-weight: 700; color: var(--navy); margin-bottom: 4px; line-height: 1.4; }
.search-hit .sh-snippet { font-size: 13px; color: var(--muted); line-height: 1.5; }
.search-hit mark { background: var(--teal-l); color: var(--teal-d); border-radius: 3px; padding: 0 2px; font-weight: 700; }
.search-empty { font-size: 14px; color: var(--light); text-align: center; padding: 18px 0; display: none; }
.search-empty.open { display: block; }
.search-count { font-size: 12px; color: var(--light); margin-top: 12px; text-align: center; display: none; }
.search-count.open { display: block; }
.track-search-wrap { max-width: 900px; margin: 32px auto 0; padding: 0 48px; }
.track-search-wrap .academy-search-wrap { padding: 0; max-width: none; }

@media (max-width: 768px) {
  .page-header { padding: 44px 20px 36px; }
  .crumb { padding: 0 20px; }
  .chapter-wrap { padding: 32px 20px 16px; }
  .chapter-nav { grid-template-columns: 1fr; padding: 8px 20px 48px; }
  .cn-link.next { text-align: left; }
  .track-wrap { padding: 40px 20px 64px; }
  .academy-search-wrap { padding: 0 20px; }
  .track-search-wrap { padding: 0 20px; }
}
"""

SEARCH_JS = r"""(function() {
  var wrap = document.getElementById('academy-search-wrap');
  if (!wrap) return;
  var input = document.getElementById('academy-search-input');
  var results = document.getElementById('search-results');
  var empty = document.getElementById('search-empty');
  var count = document.getElementById('search-count');
  var dataEl = document.getElementById('academy-search-data');
  var base = wrap.getAttribute('data-base') || '';
  var index = [];
  try { index = JSON.parse(dataEl.textContent); } catch (e) { index = []; }

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function highlight(text, q) {
    var i = text.toLowerCase().indexOf(q.toLowerCase());
    if (i === -1) return escapeHtml(text.slice(0, 140));
    var start = Math.max(0, i - 60);
    var end = Math.min(text.length, i + q.length + 80);
    var snippet = (start > 0 ? '…' : '') + text.slice(start, end) + (end < text.length ? '…' : '');
    var re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
    return escapeHtml(snippet).replace(re, '<mark>$1</mark>');
  }

  function render(q) {
    q = q.trim();
    if (!q) {
      results.classList.remove('open');
      empty.classList.remove('open');
      count.classList.remove('open');
      results.innerHTML = '';
      return;
    }
    var ql = q.toLowerCase();
    var scored = [];
    for (var i = 0; i < index.length; i++) {
      var item = index[i];
      var titleHit = item.t.toLowerCase().indexOf(ql) !== -1;
      var trackHit = item.trk.toLowerCase().indexOf(ql) !== -1;
      var textHit = item.x.toLowerCase().indexOf(ql) !== -1;
      if (!titleHit && !trackHit && !textHit) continue;
      var score = (titleHit ? 10 : 0) + (trackHit ? 3 : 0) + (textHit ? 1 : 0);
      scored.push({ item: item, score: score });
    }
    scored.sort(function(a, b) { return b.score - a.score; });
    var top = scored.slice(0, 8);

    if (top.length === 0) {
      results.classList.remove('open');
      results.innerHTML = '';
      empty.classList.add('open');
      count.classList.remove('open');
      return;
    }

    empty.classList.remove('open');
    count.textContent = scored.length + (scored.length === 1 ? ' result' : ' results');
    count.classList.add('open');

    results.innerHTML = top.map(function(s) {
      var item = s.item;
      var snippetSource = item.x;
      return '<a class="search-hit" href="' + base + item.u + '">' +
        '<div class="sh-track">' + escapeHtml(item.trk) + ' · ' + escapeHtml(item.n) + '</div>' +
        '<div class="sh-title">' + highlight(item.t, q) + '</div>' +
        '<div class="sh-snippet">' + highlight(snippetSource, q) + '</div>' +
        '</a>';
    }).join('');
    results.classList.add('open');
  }

  input.addEventListener('input', function() { render(input.value); });

  if (window.location.hash === '#search') {
    input.focus();
  }
})();"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title} — Plenee Academy</title>
<link href="https://fonts.googleapis.com/css2?family=Varela+Round&display=swap" rel="stylesheet">
<style>
{style}
</style>
</head>
<body>

<nav>
  <a href="../../index.html" class="nav-logo">
    <img src="../../Logo%20-%20Plenee_Navigator_v2.svg" alt="Plenee Navigator">
  </a>
  <div class="nav-links">
    <a href="../../index.html#how">How it works</a>
    <a href="../../index.html#features-start">Features</a>
    <a href="../index.html" class="active">Academy</a>
    <a href="../../index.html#fid">Our Promise</a>
  </div>
</nav>

{body}

<div id="disclaimer-strip">
  <p>Plenee Academy provides financial information and education, not personalized financial advice. Plenee Co. is not a registered investment adviser, broker-dealer, or financial planner. <a href="../../plenee_legal.html">Legal Disclosures &amp; Notices →</a></p>
</div>

<footer>
  <a href="../../index.html" style="display:block;line-height:0">
    <img src="../../Logo%20-%20Plenee_Navigator_v2.svg" height="44" alt="Plenee Navigator">
  </a>
  <p>© 2026 Plenee Co. All rights reserved.</p>
  <div class="fl"><a href="../../privacy.html">Privacy</a><a href="../../terms.html">Terms</a><a href="../../plenee_legal.html" style="color:var(--teal)">Legal</a><a href="../../contact.html">Contact</a></div>
</footer>

</body>
</html>
"""


SEARCH_SNIPPET_CAP = 30000  # chars of plain text indexed per chapter -- see
                             # academy_search_feature_snippet.md's "lesson learned"
                             # before lowering this; a 2,200-char cap previously
                             # missed 3 of 4 genuine matches in this same track.


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def strip_tags(rendered_html: str) -> str:
    """Plain text from a block of generated <p>/<h2> HTML, for search indexing."""
    text = re.sub(r"<[^>]+>", " ", rendered_html)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


def display_chapter_id(chapter_id: str) -> str:
    """'PM' is internal shorthand only -- never show "Chapter PM1.2" to a
    reader, just "Chapter 1.2" (ACADEMY_PUBLISHING_INSTRUCTIONS.md §7)."""
    return chapter_id[2:] if chapter_id.startswith("PM") else chapter_id


def search_html(placement: str) -> str:
    """placement: 'academy' (root academy/index.html) or 'track' (a track's own
    index.html, one level deeper -- links need a '../' prefix)."""
    base = "" if placement == "academy" else "../"
    return f"""<div class="academy-search-wrap" id="academy-search-wrap" data-base="{base}">
      <div class="academy-search-box">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <input type="text" class="academy-search-input" id="academy-search-input" placeholder="Search Plenee Academy — try &quot;overdraft&quot; or &quot;idle cash&quot;" autocomplete="off">
      </div>
      <div class="search-results" id="search-results"></div>
      <p class="search-empty" id="search-empty">No chapters found. Try a different word.</p>
      <p class="search-count" id="search-count"></p>
    </div>"""


def inline_markdown(text: str) -> str:
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def parse_chapters(source_text: str) -> list[dict]:
    """Split the file into chapters at `# Chapter N.M -- Title` boundaries."""
    matches = list(CHAPTER_SPLIT_RE.finditer(source_text))
    chapters = []
    for i, m in enumerate(matches):
        cid, ctitle = m.group(1), m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(source_text)
        raw = source_text[start:end]
        raw = raw.split("\n---\n")[0]  # stop at the trailing chapter separator
        chapters.append({"id": cid, "title": ctitle, "raw": raw.strip("\n")})
    return chapters


def split_sections(raw: str) -> tuple[list[tuple[str, str]], str | None, dict[str, str]]:
    """Returns (sections, takeaway_text, footnote_defs) where sections is an
    ordered list of (heading, body_markdown) excluding 'The takeaway' and
    'Sources', which are pulled out separately."""
    heads = list(SUBHEAD_RE.finditer(raw))
    sections: list[tuple[str, str]] = []
    takeaway: str | None = None
    footnote_defs: dict[str, str] = {}

    for i, m in enumerate(heads):
        heading = m.group(1).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(raw)
        body = raw[start:end].strip("\n")

        if heading.lower() == "sources":
            for fm in FOOTNOTE_DEF_RE.finditer(body):
                footnote_defs[fm.group(1)] = fm.group(2).strip()
        elif heading.lower() == "the takeaway":
            takeaway = body.strip()
        else:
            sections.append((heading, body))

    return sections, takeaway, footnote_defs


def render_paragraphs(body: str, footnote_numbers: dict[str, int], track_slug: str, idx) -> str:
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    out = []
    for p in paras:
        p_html = inline_markdown(p)

        def _ref_sub(m: re.Match, _p=p) -> str:
            token_id = m.group(1)
            resolved = resolve_token(token_id, track_slug, idx)
            if resolved is None:
                return m.group(0)
            url, default_text = resolved
            preceding = _p[: m.start()].rstrip()
            link_text = token_id if (preceding.endswith("Chapter") or preceding.endswith("Chapters")) else default_text
            return f'<a href="{esc(url)}">{esc(link_text)}</a>'

        # ref tokens survive esc() unchanged (braces/colons aren't escaped by html.escape
        # with quote=False), so substitute after inline_markdown.
        p_html = TOKEN_RE.sub(_ref_sub, p_html)

        def _fn_sub(m: re.Match) -> str:
            label = m.group(1)
            num = footnote_numbers.get(label)
            if num is None:
                return m.group(0)
            return f'<sup id="fnref-{esc(label)}"><a href="#fn-{esc(label)}">{num}</a></sup>'

        p_html = FOOTNOTE_MARKER_RE.sub(_fn_sub, p_html)
        out.append(f"<p>{p_html}</p>")
    return "\n".join(out)


def render_chapter_page(chapter: dict, chapter_index: int, all_chapters: list[dict],
                         track_info, track_title: str, track_slug: str, idx) -> tuple[str, dict]:
    sections, takeaway, footnote_defs = split_sections(chapter["raw"])

    footnote_order = list(footnote_defs.keys())  # dict preserves insertion order (definition order)
    footnote_numbers = {label: i + 1 for i, label in enumerate(footnote_order)}

    jump_items = []
    body_html_parts = []
    search_text_parts = []
    for heading, body in sections:
        hid = slugify_title(heading)
        jump_items.append(f'<li><a href="#{hid}">{esc(heading)}</a></li>')
        body_html_parts.append(f'<h2 id="{hid}">{esc(heading)}</h2>')
        section_html = render_paragraphs(body, footnote_numbers, track_slug, idx)
        body_html_parts.append(section_html)
        search_text_parts.append(strip_tags(section_html))

    chapter_body_html = "\n".join(body_html_parts)

    takeaway_html = ""
    if takeaway:
        takeaway_body_html = render_paragraphs(takeaway, footnote_numbers, track_slug, idx)
        search_text_parts.append(strip_tags(takeaway_body_html))
        takeaway_html = (
            '\n  <div class="takeaway">\n'
            '      <div class="tk-label">The takeaway</div>\n'
            f"      {takeaway_body_html}\n"
            "    </div>"
        )

    sources_html = ""
    if footnote_defs:
        items = []
        for label in footnote_order:
            num = footnote_numbers[label]
            def_html = inline_markdown(footnote_defs[label])
            def_html = TOKEN_RE.sub(
                lambda m: (lambda r: f'<a href="{esc(r[0])}">{esc(r[1])}</a>' if r else m.group(0))(
                    resolve_token(m.group(1), track_slug, idx)
                ),
                def_html,
            )
            items.append(
                f'<li id="fn-{esc(label)}">{def_html} '
                f'<a href="#fnref-{esc(label)}">↩</a></li>'
            )
        sources_html = (
            '\n  <div class="sources">\n'
            '      <div class="src-title">Sources</div>\n'
            f'      <ol>\n{chr(10).join(items)}\n      </ol>\n'
            "    </div>"
        )

    jump_list_html = ""
    if jump_items:
        jump_list_html = (
            '\n  <div class="jump-list">\n'
            '      <div class="jl-title">In this chapter</div>\n'
            f'      <ol>\n{chr(10).join(jump_items)}\n      </ol>\n'
            "    </div>\n"
        )

    prev_chap = all_chapters[chapter_index - 1] if chapter_index > 0 else None
    next_chap = all_chapters[chapter_index + 1] if chapter_index + 1 < len(all_chapters) else None

    if prev_chap:
        prev_html = (
            f'<a class="cn-link prev" href="{prev_chap["slug"]}.html">\n'
            '      <div class="cn-dir">Previous</div>\n'
            f'      <div class="cn-title">{esc(prev_chap["title"])}</div>\n'
            "    </a>"
        )
    else:
        prev_html = (
            '<a class="cn-link prev" href="index.html">\n'
            '      <div class="cn-dir">Previous</div>\n'
            f'      <div class="cn-title">Back to {esc(track_title)}</div>\n'
            "    </a>"
        )

    if next_chap:
        next_html = (
            f'<a class="cn-link next" href="{next_chap["slug"]}.html">\n'
            '      <div class="cn-dir">Next</div>\n'
            f'      <div class="cn-title">{esc(next_chap["title"])}</div>\n'
            "    </a>"
        )
    else:
        next_html = (
            '<a class="cn-link next" href="index.html">\n'
            '      <div class="cn-dir">Next</div>\n'
            f'      <div class="cn-title">Back to {esc(track_title)}</div>\n'
            "    </a>"
        )

    body = f"""<div class="crumb">
  <a href="../index.html">Academy</a>
  <span>›</span>
  <a href="index.html">{esc(track_title)}</a>
  <span>›</span>
  <span>{esc(display_chapter_id(chapter["id"]))}</span>
  <span style="margin-left:auto"></span>
  <a href="../index.html#search">🔍 Search Academy</a>
</div>

<div class="chapter-wrap">
  <div class="chapter-eyebrow">Volume {track_info.volume} · Track {track_info.display_num} · Chapter {esc(display_chapter_id(chapter["id"]))}</div>
  <h1>{esc(chapter["title"])}</h1>
  <p class="chapter-disclaimer">{DISCLAIMER}</p>
{jump_list_html}
  <div class="chapter-body">
{chapter_body_html}
  </div>
{takeaway_html}{sources_html}
</div>

<div class="chapter-nav">
  {prev_html}
  {next_html}
</div>"""

    page_html = PAGE_TEMPLATE.format(page_title=esc(chapter["title"]), style=STYLE_BLOCK, body=body)

    search_entry = {
        "t": chapter["title"],
        "trk": f"Volume {track_info.volume} · {track_title}",
        "n": f'Chapter {display_chapter_id(chapter["id"])}',
        "u": f'{track_slug}/{chapter["slug"]}.html',
        "x": " ".join(search_text_parts).strip()[:SEARCH_SNIPPET_CAP],
    }
    return page_html, search_entry


def render_index_page(track_info, track_title: str, chapters: list[dict], search_index: list[dict]) -> str:
    cards = []
    for c in chapters:
        cards.append(
            f'  <a class="chap-card" href="{c["slug"]}.html">\n'
            f'    <div class="chap-num">{esc(display_chapter_id(c["id"]))}</div>\n'
            '    <div class="chap-info">\n'
            f'      <h3>{esc(c["title"])}</h3>\n'
            "    </div>\n"
            "  </a>"
        )

    search_json = json.dumps(search_index, ensure_ascii=False).replace("</script", "<\\/script")

    body = f"""<div class="page-header">
  <div class="page-kicker">Volume {track_info.volume} · Track {track_info.display_num}</div>
  <h1>{esc(track_title)}</h1>
</div>

<div class="crumb">
  <a href="../index.html">Academy</a>
  <span>›</span>
  <span>{esc(track_title)}</span>
</div>

<div class="track-search-wrap">
{search_html('track')}
</div>

<div class="track-wrap">
  <div class="chapter-grid">
{chr(10).join(cards)}
  </div>
</div>

<script type="application/json" id="academy-search-data">{search_json}</script>
<script>{SEARCH_JS}</script>"""

    return PAGE_TEMPLATE.format(page_title=esc(track_title), style=STYLE_BLOCK, body=body)


def generate_track_pages(source_filename: str, idx) -> dict:
    """Writes one track's chapter HTML pages (not its index.html -- that needs
    the full cross-track search index, assembled by the caller after every
    track has run). Returns the metadata write_index_pages() needs."""
    path = Path(source_filename)
    if not path.is_absolute():
        path = ACADEMY_SRC / source_filename
    if not path.exists():
        raise FileNotFoundError(path)

    stem = path.name.removesuffix("_expanded.md")
    track_slug, _ = track_slug_and_num_from_filename(stem)
    track_info = idx.tracks_by_slug[track_slug]
    track_title = track_info.title.title()

    text = path.read_text(encoding="utf-8")
    raw_chapters = parse_chapters(text)
    chapters = []
    for c in raw_chapters:
        info = idx.chapters[c["id"]]
        chapters.append({**c, "slug": info.chapter_slug})

    outdir = WEBSITE_DIR / "academy" / track_slug
    outdir.mkdir(parents=True, exist_ok=True)

    search_entries = []
    for i, chapter in enumerate(chapters):
        html_out, search_entry = render_chapter_page(chapter, i, chapters, track_info, track_title, track_slug, idx)
        search_entries.append(search_entry)
        outfile = outdir / f"{chapter['slug']}.html"
        outfile.write_text(html_out, encoding="utf-8")
        print(f"  wrote {outfile.relative_to(WEBSITE_DIR)}")

    return {
        "track_info": track_info,
        "track_title": track_title,
        "chapters": chapters,
        "search_entries": search_entries,
        "outdir": outdir,
    }


def write_index_pages(track_results: list[dict], global_search_index: list[dict]) -> None:
    for r in track_results:
        index_html = render_index_page(r["track_info"], r["track_title"], r["chapters"], global_search_index)
        index_path = r["outdir"] / "index.html"
        index_path.write_text(index_html, encoding="utf-8")
        print(f"  wrote {index_path.relative_to(WEBSITE_DIR)}")


def generate(source_filename: str) -> None:
    """Single-track regeneration -- fast for iterating on one file's content,
    but its index.html search box will only cover THIS track's chapters until
    --all is next run (which re-embeds the full cross-track index everywhere)."""
    idx = build_index()
    result = generate_track_pages(source_filename, idx)
    write_index_pages([result], result["search_entries"])


def generate_all() -> None:
    """Regenerate every track from current source and embed one shared,
    cross-track search index on every track's index.html."""
    idx = build_index()
    files = sorted(ACADEMY_SRC.glob("*_expanded.md"))
    results = [generate_track_pages(str(f), idx) for f in files]
    global_search_index = [e for r in results for e in r["search_entries"]]
    write_index_pages(results, global_search_index)
    print(f"\nDone: {len(results)} tracks, {len(global_search_index)} chapters indexed for search.")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    if sys.argv[1] == "--all":
        generate_all()
    else:
        generate(sys.argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
