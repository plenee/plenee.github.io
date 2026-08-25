"""Builds the Academy v2 site from plenee_app/docs/academy_v2/.

PARALLEL BUILD. Writes only to website/academy2/. It does not read, modify or overwrite
anything under website/academy/, and generate_academy_pages.py is imported read-only for
its shared CSS and page shell so the two sites cannot drift apart visually.

The v2 model, from docs/academy_v2/navigation.md:

  chapters/<slug>.md   one chapter, ONE canonical URL, /academy2/<slug>/
  tracks/<slug>.md     an ordered list of chapter slugs — a view, not a container
  contents.md          the general index: every chapter exactly once, by subject

A chapter belongs to as many tracks as it serves and moves nowhere. Track context rides in
a ?via= query parameter and never creates a second URL, because five copies of one chapter
at five addresses splits whatever retrieval authority the page earns five ways.

Run from the website/ directory:  python3 scripts/generate_academy_v2.py
"""
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_academy_pages import (  # noqa: E402
    ART_FILTER_DEFS, PAGE_TEMPLATE, STYLE_BLOCK, TRACK_HUES, render_chapter_art,
)

WEBSITE = Path(__file__).resolve().parents[1]
def _find_src() -> Path:
    """Locate the v2 source tree.

    It does not always sit in the main checkout. When the branch holding it is checked out
    as a git worktree, plenee_app/docs/academy_v2 is left behind as an empty directory and
    the build fails with a bare FileNotFoundError three frames deep. Ask git where the
    branch actually is rather than assuming.
    """
    import os, subprocess
    # An explicit override, because the resolver below picks a tree on the machine's
    # behalf. When two checkouts of this branch exist, editing one and building from the
    # other looks exactly like a build that did nothing.
    env = os.environ.get("PLENEE_ACADEMY_SRC")
    if env:
        cand = Path(env).expanduser().resolve()
        if not (cand / "contents.md").exists():
            raise SystemExit(f"PLENEE_ACADEMY_SRC={cand} has no contents.md")
        print(f"  source: {cand}  (PLENEE_ACADEMY_SRC)")
        return cand
    default = WEBSITE.parent / "plenee_app" / "docs" / "academy_v2"
    if (default / "contents.md").exists():
        # Announce it. This path was empty while the branch lived only in a worktree, so
        # the resolver fell through to the worktree and said so. Once the branch merged to
        # main the path filled in, the resolver silently switched trees, and a build could
        # take a stale copy without anything in the output saying which tree it read.
        print(f"  source: {default}  (main checkout)")
        return default
    repo = WEBSITE.parent / "plenee_app"
    try:
        out = subprocess.run(["git", "-C", str(repo), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        out = ""
    for line in out.splitlines():
        if line.startswith("worktree "):
            cand = Path(line.split(" ", 1)[1]) / "docs" / "academy_v2"
            if (cand / "contents.md").exists():
                print(f"  source: {cand}  (branch is checked out as a worktree)")
                return cand
    raise SystemExit(
        f"BUILD FAILED: no academy_v2 source found.\n"
        f"  looked in {default}\n"
        f"  and in every worktree of {repo}\n"
        f"The branch holding docs/academy_v2/ is not checked out anywhere.")


def _check_trees_agree(chosen: Path) -> None:
    """Refuse to build from a tree that is missing another tree's work.

    The source can live in the main checkout or in a worktree, and _find_src prefers the
    main checkout. That is fine while the two agree. When they do not, the build silently
    drops whatever the chosen tree lacks: on 2026-08-24 a build from main produced no
    quizzes because the 37 quiz sources existed only on the branch, and it deleted 38
    published pages without a word. The page count in the summary line was the only
    symptom, and only because someone happened to remember the previous number.

    Presence is what is checked, not content. Trees that hold the same files but differ
    inside are reported as a count, not a failure — that is ordinary while a branch is in
    flight, and failing on it would make the build unusable.
    """
    import subprocess
    repo = WEBSITE.parent / "plenee_app"
    try:
        out = subprocess.run(["git", "-C", str(repo), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return
    others = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            c = Path(line.split(" ", 1)[1]) / "docs" / "academy_v2"
            if c != chosen and (c / "contents.md").exists():
                others.append(c)
    rel = lambda root: {f.relative_to(root).as_posix()
                        for f in root.rglob("*.md") if ".no-autofix" not in f.parts}
    mine = rel(chosen)
    for o in others:
        theirs = rel(o)
        missing = sorted(theirs - mine)
        if missing:
            shown = "\n    ".join(missing[:12])
            more = f"\n    ... and {len(missing) - 12} more" if len(missing) > 12 else ""
            raise SystemExit(
                f"BUILD FAILED: {o} holds {len(missing)} source files this tree does not.\n"
                f"  Building from {chosen} would publish without them, and would DELETE any\n"
                f"  pages they produced. Merge the trees first.\n    {shown}{more}")
        differing = sum(1 for f in sorted(mine & theirs)
                        if (chosen / f).read_bytes() != (o / f).read_bytes())
        if differing:
            print(f"  note: {differing} file(s) differ from {o} — building this tree's version")


SRC = _find_src()
_check_trees_agree(SRC)
OUT = Path(os.environ["PLENEE_ACADEMY_OUT"]).expanduser().resolve() \
    if os.environ.get("PLENEE_ACADEMY_OUT") else WEBSITE / "academy2"

V2_STYLE = """
/* The two non-personalized ways into the corpus. Quiet by intent: the track cards are the
   page's argument, and these are for a reader who already knows what they are after. */
.ways{margin:3.25rem auto 0;padding-top:2rem;border-top:1px solid var(--border);text-align:center}
.ways .chapters-heading{margin-bottom:1.15rem}
.ways-row{display:flex;flex-wrap:wrap;justify-content:center;gap:1rem 3.5rem}
.way{display:inline-flex;flex-direction:column;gap:.15rem;text-decoration:none;
  padding:.35rem .5rem;border-radius:6px}
.way-t{font-weight:700;color:var(--teal-d)}
.way-t::after{content:" \2192";display:inline-block;transition:transform .15s ease}
.way:hover .way-t::after,.way:focus-visible .way-t::after{transform:translateX(3px)}
.way:hover,.way:focus-visible{background:var(--teal-l)}
.way-m{font-size:.82rem;color:var(--light);font-weight:400}
@media (prefers-reduced-motion:reduce){.way-t::after{transition:none}}
@media (max-width:640px){.ways-row{gap:1.4rem}}

/* The chapter heading breaks after the colon: subject on one line, what the chapter says
   about it on the next. The second line is set lighter so the pair reads as one heading
   rather than two. */
.chapter-wrap h1 .h1-rest{color:var(--muted);font-weight:600}

/* Quizzes. The score is not the point — the reveal under each answer is, because a number
   out of ten teaches nothing and the cost of the miss does. Built from the Academy's own
   variables so a quiz reads as a chapter that happens to ask questions. */
.qz-q{margin:0 0 2.6rem;padding:0 0 2.2rem;border-bottom:1px solid var(--border)}
.qz-q:last-of-type{border-bottom:0}
.qz-qtext{font-weight:700;color:var(--navy);margin:0 0 1rem;line-height:1.45}
.qz-num{display:inline-block;min-width:1.6rem;color:var(--teal-d);font-variant-numeric:tabular-nums}
.qz-opts{display:flex;flex-direction:column;gap:.5rem}
.qz-opt{text-align:left;font:inherit;font-size:.97rem;color:var(--navy);background:var(--off);
  border:1px solid var(--border);border-radius:7px;padding:.68rem .9rem;cursor:pointer;
  transition:border-color .12s ease,background .12s ease}
.qz-opt:hover:enabled,.qz-opt:focus-visible:enabled{border-color:var(--teal);background:var(--teal-l)}
.qz-opt:disabled{cursor:default;opacity:1}
.qz-opt.correct{border-color:var(--green);background:var(--green-l);font-weight:600}
.qz-opt.wrong{border-color:#D98A8A;background:#FDF0F0}
.qz-why{margin:1rem 0 0;padding:.85rem 1rem;border-left:3px solid var(--border);
  color:var(--muted);line-height:1.6;background:var(--off);border-radius:0 6px 6px 0}
.qz-why.ok{border-left-color:var(--green)}
.qz-why.no{border-left-color:#D98A8A}
.quiz-result{margin:2.5rem 0 0;padding:1.6rem;border:1px solid var(--border);
  border-radius:10px;background:var(--off)}
.quiz-score{font-size:1.5rem;font-weight:700;color:var(--navy);margin:.4rem 0 .6rem}
.quiz-bench{color:var(--muted);margin:0 0 1rem}
.qz-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.2rem}
.qz-card{display:flex;flex-direction:column;padding:1.6rem;border:1px solid var(--border);
  border-radius:10px;background:#fff;text-decoration:none;
  transition:border-color .15s ease,transform .15s ease}
/* the blurbs differ in length, so the call to action is pushed to the foot of the card and
   the two line up regardless */
.qz-card p{flex:1}
.qz-card:hover,.qz-card:focus-visible{border-color:var(--teal);transform:translateY(-2px)}
.qz-kicker{font-size:.72rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
  color:var(--teal-d);margin-bottom:.5rem}
.qz-card h3{margin:0 0 .5rem;color:var(--navy);font-size:1.2rem}
.qz-card p{margin:0 0 1.1rem;color:var(--muted);line-height:1.6}
.qz-go{font-weight:700;color:var(--teal-d)}
.qz-note{color:var(--muted);margin:0 0 1.3rem;max-width:60ch}
.qz-grid{margin:0 0 3.2rem}
.qz-card{position:relative}
.qz-lvl{position:absolute;top:1.1rem;right:1.1rem;width:1.9rem;height:1.9rem;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:.82rem;font-weight:700;
  color:var(--teal-d);background:var(--teal-l);border:1px solid var(--border)}

@media (prefers-reduced-motion:reduce){.qz-card{transition:none}.qz-card:hover{transform:none}}

/* Glossary. A reference page, not prose: the reader is looking something up, so the term
   is the scannable unit and the definition follows it. Uses the chapter shell unchanged. */
.gl-jump{display:flex;flex-wrap:wrap;gap:.45rem;margin:0 0 2.2rem;padding:0;list-style:none}
.gl-jump a{display:inline-block;padding:.32rem .7rem;border:1px solid var(--border);
  border-radius:999px;font-size:.85rem;color:var(--muted);text-decoration:none;background:var(--off)}
.gl-jump a:hover,.gl-jump a:focus-visible{border-color:var(--teal);color:var(--teal-d);background:var(--teal-l)}
.gl{margin:0 0 2.4rem}
.gl dt{font-weight:700;color:var(--navy);margin:1.5rem 0 .3rem;scroll-margin-top:5rem}
.gl dt:first-of-type{margin-top:.6rem}
.gl dd{margin:0;color:var(--muted);line-height:1.65}
.gl dd + dt{border-top:1px solid var(--border);padding-top:1.5rem}
/* Plenee's own vocabulary has fixed casing that must never be "corrected" — mark it so a
   reader can see at a glance which words are ours and which are the industry's. */
.gl dt.own::after{content:"Plenee term";margin-left:.6rem;font-size:.7rem;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;color:var(--teal-d);
  background:var(--teal-l);padding:.13rem .45rem;border-radius:3px;vertical-align:.13em}
@media (max-width:640px){.gl dt{margin-top:1.3rem}}

/* v1's stylesheet covers every component here once the markup matches it. Two things are
   genuinely new in v2 and are built from v1's own variables rather than invented: the
   track-membership block (which reuses .takeaway so it reads as the same family) and
   tables, which v1 has no rules for because v1 chapters contain none. */
.alsoin ol{margin:.5rem 0 0;padding-left:1.15rem}
.alsoin li{margin:.4rem 0;color:var(--muted)}
.alsoin li a{color:var(--teal-d);font-weight:600;text-decoration:none}
.alsoin li a:hover{text-decoration:underline}
.ctx{display:flex;gap:.7rem;align-items:baseline;flex-wrap:wrap}
.ctx .pos{color:var(--light);font-variant-numeric:tabular-nums}
.v2-scroll{overflow-x:auto;margin:1.6rem 0;-webkit-overflow-scrolling:touch}
table.v2{border-collapse:collapse;width:100%;font-size:.94rem;color:var(--text)}
table.v2 th,table.v2 td{border-bottom:1px solid var(--border);padding:.6rem .7rem;
  text-align:left;vertical-align:top}
table.v2 thead th{background:var(--off);color:var(--navy);font-weight:600;
  border-bottom:2px solid var(--border);white-space:nowrap}
table.v2 tbody tr:last-child td{border-bottom:none}
.chap-card .cc-tile{position:relative}
.chap-card .cc-title{position:absolute;left:0;right:0;bottom:0;margin:0;padding:2.2rem 1.15rem .9rem;
  font-family:Georgia,'Times New Roman',serif;font-size:1.12rem;line-height:1.25;color:#fff;
  text-shadow:0 1px 14px rgba(0,0,0,.55);
  background:linear-gradient(to top,rgba(12,25,41,.88) 0%,rgba(12,25,41,.62) 45%,rgba(12,25,41,0) 100%)}
.chap-card .cc-body p{margin:0 0 1rem}
sup.fnref a{color:var(--teal-d);text-decoration:none;font-weight:600;padding:0 .1em}
sup.fnref a:hover{text-decoration:underline}
"""

# Six palettes, borrowed from v1 so the two sites cannot diverge. Assigned by what the
# situation is about rather than alphabetically: teal for beginnings, slate for irregular
# work, rose for the protection-heavy household, orange where extraction concentrates,
# gold for accumulation, deep teal for late life and for method.
HUES = list(dict.fromkeys(TRACK_HUES.values()))
TEAL, ORANGE, GOLD, SLATE, ROSE, DEEP = HUES[0], HUES[1], HUES[2], HUES[3], HUES[4], HUES[5]
TRACK_HUE = {
    "still-studying": TEAL, "first-job-renting": TEAL,
    "no-payslip": SLATE, "looking-after-everyone": SLATE,
    "just-bought-a-house": ROSE,
    "one-income-no-buffer": ORANGE, "two-countries": ORANGE,
    "earning-well": GOLD, "five-years-out": GOLD,
    "policies-you-already-own": DEEP, "flooded-with-offers": DEEP,
}


def hue_of(tslug: str) -> tuple[str, str, str]:
    return TRACK_HUE.get(tslug, TEAL)


def hue_style(tslug: str) -> str:
    h, l, d = hue_of(tslug)
    return f'style="--hue:{h};--hue-l:{l};--hue-d:{d};"'


def art_for(slug: str) -> str:
    return render_chapter_art(sum(ord(c) for c in slug) % 6 + 1, slug)


def anchor(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:60]


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def parse_front(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.index("\n---", 3)
    meta: dict = {}
    for line in text[3:end].strip().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            meta[k.strip()] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        else:
            # a title containing a colon has to be quoted in YAML; strip the quotes or they
            # render literally on the card
            if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            meta[k.strip()] = v
    return meta, text[end + 4:]


def load() -> tuple[dict, dict, str]:
    chapters = {}
    for f in sorted((SRC / "chapters").glob("*.md")):
        meta, body = parse_front(f.read_text())
        meta["body"] = body
        chapters[meta.get("slug", f.stem)] = meta
    tracks = {}
    for f in sorted((SRC / "tracks").glob("*.md")):
        meta, body = parse_front(f.read_text())
        overview, _, listing = body.partition("## Chapters")
        entries = []
        for m in re.finditer(r'^\d+\. \*\*\{\{ref:([\w-]+)\}\}\*\* — (.+)$', listing, re.M):
            entries.append({"slug": m.group(1), "why": m.group(2).strip()})
        meta["overview"] = overview
        meta["entries"] = entries
        tracks[meta.get("slug", f.stem)] = meta
    return chapters, tracks, (SRC / "contents.md").read_text()


# --------------------------------------------------------------------------- markdown

def refs(text: str, titles: dict, depth: str) -> str:
    def sub(m):
        slug = m.group(1)
        if slug not in titles:
            raise SystemExit(f"BUILD FAILED: {{{{ref:{slug}}}}} has no chapter. "
                             "A dangling reference must break the build, not render as text.")
        return f'<a class="ref-link" href="{depth}{slug}.html">{esc(titles[slug])}</a>'
    return re.sub(r'\{\{ref:([\w-]+)\}\}', sub, text)


def is_block(ln: str) -> bool:
    """True if the line opens a block that is not a paragraph.

    The bug this replaces: excluding any line starting with "-" or "*" also excluded
    "**Bold lead-in.**", which is how most paragraphs in this corpus open. Those lines
    matched no branch and were silently dropped — 16 of 17 in one chapter. A list marker
    is an asterisk or hyphen FOLLOWED BY A SPACE; bold is not.
    """
    s = ln.lstrip()
    return (s.startswith(("#", "|", ">"))
            or s.rstrip() == "---"
            or bool(re.match(r'^([-*+] |\d+\. )', s)))


def inline(s: str, seen: set | None = None) -> str:
    """seen tracks footnote numbers already given an anchor id. A note cited twice must not
    emit the same id twice — that is invalid HTML and sends the back-link to the wrong
    occurrence. Only the first citation carries the id; later ones are plain links."""
    s = esc(s)

    def fn(m):
        n = m.group(1)
        first = seen is None or n not in seen
        if seen is not None:
            seen.add(n)
        idattr = f' id="r{n}"' if first else ""
        return f'<sup class="fnref"{idattr}><a href="#fn{n}">{n}</a></sup>'

    s = re.sub(r'\[\^(\d+)\]', fn, s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2">\1</a>', s)
    return s


def render_body(md: str) -> tuple[str, str]:
    """Returns (body_html, sources_html). Footnote definitions are pulled out first."""
    body, _, srcblock = md.partition("\n## Sources\n")
    notes = re.findall(r'^\[\^(\d+)\]: (.*?)(?=\n\[\^|\Z)', srcblock, re.S | re.M)
    seen: set = set()
    heads: list = []
    out, i = [], 0
    lines = body.split("\n")
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            i += 1
            continue  # the H1 is rendered from frontmatter
        if ln.startswith("## "):
            raw = ln[3:].strip()
            a = anchor(re.sub(r'[*`]', '', raw))
            heads.append((a, re.sub(r'[*`]', '', raw)))
            out.append(f'<h2 id="{a}">{inline(raw, seen)}</h2>'
                       f'<div class="subhead-accent"></div>')
            i += 1
        elif ln.startswith("### "):
            out.append(f"<h3>{inline(ln[4:].strip(), seen)}</h3>")
            i += 1
        elif ln.startswith("|"):
            tbl = []
            while i < len(lines) and lines[i].startswith("|"):
                tbl.append(lines[i]); i += 1
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl]
            rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
            if rows:
                head = "".join(f"<th>{inline(c, seen)}</th>" for c in rows[0])
                trs = "".join("<tr>" + "".join(f"<td>{inline(c, seen)}</td>" for c in r) + "</tr>"
                              for r in rows[1:])
                out.append(f'<div class="v2-scroll"><table class="v2"><thead><tr>{head}'
                           f'</tr></thead><tbody>{trs}</tbody></table></div>')
        elif re.match(r'^\s*[-*] ', ln) or re.match(r'^\s*\d+\. ', ln):
            ordered = bool(re.match(r'^\s*\d+\. ', ln))
            items = []
            while i < len(lines) and (re.match(r'^\s*[-*] ', lines[i]) or re.match(r'^\s*\d+\. ', lines[i])
                                      or (items and lines[i].startswith("   ") and lines[i].strip())):
                if re.match(r'^\s*([-*]|\d+\.) ', lines[i]):
                    items.append(re.sub(r'^\s*([-*]|\d+\.) ', '', lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x, seen)}</li>" for x in items) + f"</{tag}>")
        elif ln.startswith(">"):
            q = []
            while i < len(lines) and lines[i].startswith(">"):
                q.append(lines[i].lstrip("> ").rstrip()); i += 1
            out.append(f"<blockquote><p>{inline(' '.join(q), seen)}</p></blockquote>")
        elif ln.strip() == "---":
            out.append("<hr>"); i += 1
        elif ln.strip():
            para = []
            while i < len(lines) and lines[i].strip() and not is_block(lines[i]):
                para.append(lines[i].strip()); i += 1
            if para:
                out.append(f"<p>{inline(' '.join(para), seen)}</p>")
            else:
                i += 1
        else:
            i += 1

    src_html = ""
    if notes:
        lis = "".join(f'<li id="fn{n}">{inline(" ".join(t.split()), seen)} '
                      f'<a href="#r{n}">&#8617;</a></li>' for n, t in notes)
        src_html = ('<div class="sources"><div class="src-title">Sources</div>'
                    f"<ol>{lis}</ol></div>")
    return "\n".join(out), src_html, heads


# --------------------------------------------------------------------------- pages

BASE = "https://plenee.com/academy2/"

# Flat .html files, not directories. Directory-style URLs need a server to resolve "/" to
# index.html, so they break when the site is opened from disk — and v1 emits flat files, so
# this matches it. One canonical URL per chapter either way.


BASE = "https://plenee.com/academy2/"


def shell(title: str, body: str, depth_root: str, ac_root: str, canonical: str = "") -> str:
    # v2 pages mark Academy2 as the active section, never Academy — the highlight was
    # previously hardcoded onto Academy and so lit up on v2 pages too.
    page = PAGE_TEMPLATE.format(page_title=esc(title), style=STYLE_BLOCK + V2_STYLE,
                                body=body, root=depth_root, ac_root=ac_root,
                                ac_active="", ac2_active=' class="active"')
    # Every page declares its canonical URL without the ?via= parameter. Track context is a
    # query string precisely so a chapter never gets a second address; without this tag a
    # crawler can still index /slug/?via=a and /slug/?via=b as separate pages and split
    # whatever authority the chapter earns.
    tag = f'<link rel="canonical" href="{BASE}{canonical}">'
    return page.replace("</title>", "</title>\n" + tag, 1)


def crumb(here: str, depth: str, mid: tuple | None = None,
          right: tuple | None = None) -> str:
    parts = [f'<a href="{depth}index.html">Academy</a><span>&rsaquo;</span>']
    if mid:
        parts.append(f'<a href="{mid[1]}">{esc(mid[0])}</a><span>&rsaquo;</span>')
    parts.append(f"<span>{esc(here)}</span>")
    parts.append('<span style="margin-left:auto"></span>')
    # a crumb that links to the page you are already on is dead weight; the contents page
    # points at the picker instead
    label, href = right or ("Everything by subject", f"{depth}contents.html")
    parts.append(f'<a href="{href}">{esc(label)}</a>')
    return '<div class="crumb">' + "".join(parts) + "</div>"


NAV_JS = """
<script>
(function(){
  var el=document.getElementById('v2-nav'); if(!el) return;
  var d=JSON.parse(el.textContent);
  var p=new URLSearchParams(location.search).get('via');
  if(!p){try{p=localStorage.getItem('plenee_track')||''}catch(e){}}
  if(p&&!d.tracks[p]){p=''}
  if(!p) return;                      /* no track context: the server-rendered nav stands */
  try{localStorage.setItem('plenee_track',p)}catch(e){}
  var t=d.tracks[p],s=document.getElementById('v2-ctx');
  /* the crumb above already carries the 'everything by subject' link; repeating it here
     put the same destination twice on one screen */
  s.innerHTML='<span>In <a href="tracks/'+p+'.html">'+t.title+'</a></span>'
    +'<span class="pos">'+t.pos+' of '+t.len+'</span>';
  var n=document.getElementById('v2-pager'),h='';
  if(t.prev){h+='<a class="cn-link prev" href="'+t.prev.slug+'.html?via='+p+'">'
    +'<div class="cn-dir">Previous</div><div class="cn-title">'+t.prev.title+'</div></a>'}
  else{h+='<a class="cn-link prev" href="tracks/'+p+'.html">'
    +'<div class="cn-dir">Previous</div><div class="cn-title">Back to '+t.title+'</div></a>'}
  if(t.next){h+='<a class="cn-link next" href="'+t.next.slug+'.html?via='+p+'">'
    +'<div class="cn-dir">Next</div><div class="cn-title">'+t.next.title+'</div></a>'}
  n.innerHTML=h;
})();
</script>
"""


def pager(prev, nxt, depth="") -> str:
    h = ""
    if prev:
        h += (f'<a class="cn-link prev" href="{depth}{prev["slug"]}.html">'
              f'<div class="cn-dir">Previous</div>'
              f'<div class="cn-title">{esc(prev["title"])}</div></a>')
    if nxt:
        h += (f'<a class="cn-link next" href="{depth}{nxt["slug"]}.html">'
              f'<div class="cn-dir">Next</div>'
              f'<div class="cn-title">{esc(nxt["title"])}</div></a>')
    return f'<div class="chapter-nav" id="v2-pager">{h}</div>'


def h1_title(t: str) -> str:
    """The chapter H1, broken onto a second line after the colon.

    Titles are two parts — the subject, then what the chapter says about it. Running them
    together makes the reader parse the whole string to find where the claim starts. The
    break is display only: the title stays one string everywhere it is not a heading, so
    the browser tab, the breadcrumb and the next/previous links are unaffected."""
    m = re.match(r'^(.*?:)\s+(.+)$', t)
    if not m:
        return esc(t)
    return f'{esc(m.group(1))}<br><span class="h1-rest">{esc(m.group(2))}</span>'


def chapter_page(slug, ch, tracks, titles, subject_nbrs, subject_name) -> str:
    if slug == GLOSSARY_SLUG:
        body_html, src_html, heads = glossary_body(ch["body"]), "", []
    else:
        body_html, src_html, heads = render_body(ch["body"])
    # Footnote definitions can carry {{ref:}} too — one chapter cites another's sourcing
    # from inside a note. Resolving only the body left the marker printed in the Sources
    # list, which is the same class of bug as the contents page had.
    body_html = refs(body_html, titles, "")
    src_html = refs(src_html, titles, "")

    memberships, navmap = [], {}
    for tslug, tr in tracks.items():
        slugs = [e["slug"] for e in tr["entries"]]
        if slug not in slugs:
            continue
        idx = slugs.index(slug)
        memberships.append((tslug, tr.get("title", tslug), tr["entries"][idx]["why"]))
        navmap[tslug] = {
            "title": tr.get("title", tslug), "pos": idx + 1, "len": len(slugs),
            "prev": ({"slug": slugs[idx-1], "title": titles[slugs[idx-1]]} if idx else None),
            "next": ({"slug": slugs[idx+1], "title": titles[slugs[idx+1]]}
                     if idx + 1 < len(slugs) else None),
        }

    # Reuses the .takeaway box rather than inventing a component. This is the block a cold
    # arrival from search depends on: the general index is the whole corpus and a poor next
    # step, but a list of situations lets someone recognise their own and pick up a path.
    also = ""
    if memberships:
        lis = "".join(
            f'<li><a href="tracks/{ts}.html">{esc(tt)}</a> — <span class="why">{inline(why)}</span></li>'
            for ts, tt, why in sorted(memberships, key=lambda x: x[1]))
        also = ('<div class="takeaway alsoin"><div class="tk-label">Also in these situations</div>'
                f'<div class="subhead-accent"></div><ol>{lis}</ol></div>')

    jump = ""
    if len(heads) > 2:
        lis = "".join(f'<li><a href="#{a}">{esc(txt)}</a></li>' for a, txt in heads)
        jump = ('<div class="jump-list"><div class="jl-title">In this chapter</div>'
                f"<ol>{lis}</ol></div>")

    payload = json.dumps({"tracks": navmap})
    body = (
        crumb(ch.get("title", slug), "")
        + '<div class="chapter-wrap">'
        + f'<div class="chapter-eyebrow ctx" id="v2-ctx">{esc(subject_name)}</div>'
        + f'<h1>{h1_title(ch.get("title", slug))}</h1>'
        + '<div class="chapter-accent"></div>'
        + jump
        + f'<div class="chapter-body">{body_html}{also}{src_html}</div>'
        + pager((subject_nbrs or {}).get("prev"), (subject_nbrs or {}).get("next"))
        + "</div>"
        + f'<script type="application/json" id="v2-nav">{payload}</script>{NAV_JS}'
    )
    return shell(ch.get("title", slug), body, "../", "", f"{slug}.html")


CHAPTER_TITLES: dict = {}


def blurb(md: str, limit: int = 260) -> str:
    """The card description. Prefers the chapter's own "short version", which is written to
    summarise it — the opening paragraph is unreliable because many chapters open on an
    example, which reads as a non-sequitur on a card."""
    body = md.split("\n## Sources\n")[0]
    # v2 chapters close with "The short version"; the 133 ported from v1 close with
    # "The takeaway". Looking for only the first meant every ported chapter fell back to
    # its raw opening paragraph — a chapter opening, not a summary, and often far longer.
    m = re.search(r'^## (?:The short version|The takeaway)\s*\n(.+?)(?=\n##|\Z)',
                  body, re.S | re.M)
    src = m.group(1) if m else body

    def clean(s):
        s = re.sub(r'\[\^\d+\]', '', " ".join(s.split()))
        # Card blurbs are lifted from chapter bodies, which carry {{ref:slug}} markers.
        # The ref substitution never reaches them, so they were rendering literally on
        # published track pages. Replace with the chapter's title where known.
        # Cross-references belong in a chapter, not on a card. Resolving them to full
        # titles is right for body text and wrong here — a short-version paragraph citing
        # three chapters becomes 200 characters of other chapters' titles and pushes the
        # actual description past the limit. Drop parenthetical and trailing citations
        # outright, and shorten a bare one to the part before its colon so the sentence
        # still parses.
        s = re.sub(r'\s*[;,]?\s*\(\s*(?:\{\{ref:[\w-]+\}\}[;,\s]*)+\)', '', s)
        s = re.sub(r'\s*[;,]\s*(?:\{\{ref:[\w-]+\}\}[;,\s]*)+(?=[.!?]|$)', '', s)
        s = re.sub(r'\{\{ref:([\w-]+)\}\}',
                   lambda m: CHAPTER_TITLES.get(m.group(1), m.group(1).replace("-", " ")).split(":")[0],
                   s)
        s = re.sub(r'\s+([.,;:)])', r'\1', re.sub(r'\s{2,}', ' ', s)).strip()
        return re.sub(r'[*`]', '', s)

    for para in re.split(r'\n\s*\n', src):
        s = clean(para)
        if s.startswith(("#", "|", ">", "-", "*", "1.")) or len(s) < 60:
            continue
        if len(s) <= limit:
            return s
        # End on a sentence. A card cut mid-clause reads as broken text, and the
        # trailing ellipsis was appearing on 76 published cards. Prefer the last
        # complete sentence that fits; only fall back to a word cut when even the
        # first sentence is longer than the limit.
        sentences = re.findall(r'.+?[.!?](?=\s|$)', s[:limit + 1])
        if sentences:
            kept = "".join(sentences).strip()
            if len(kept) >= 60:
                return kept
        cut = s[:limit].rsplit(" ", 1)[0]
        return cut.rstrip(",;:—- ") + "…"
    return ""


def cards(entries, titles, href, hue_slug) -> str:
    out = []
    for e in entries:
        out.append(
            f'<a class="chap-card" href="{href(e)}" {hue_style(hue_slug(e))}>'
            f'<div class="cc-tile">{art_for(e["slug"])}'
            f'<h3 class="cc-title">{esc(titles[e["slug"]])}</h3></div>'
            f'<div class="cc-body"><p>{inline(e.get("blurb") or e["why"])}</p>'
            f'<span class="cc-cta">Read &rarr;</span></div></a>')
    return f'<div class="chapter-grid">{"".join(out)}</div>'


def track_page(tslug, tr, titles) -> str:
    ov, _, _ = render_body(tr["overview"])
    for e in tr["entries"]:
        e["blurb"] = CHAPTER_BLURB.get(e["slug"], "")
    grid = cards(tr["entries"], titles,
                 href=lambda e: f'../{e["slug"]}.html?via={tslug}',
                 hue_slug=lambda e: tslug)
    body = (
        ART_FILTER_DEFS
        + '<div class="page-header">'
        + '<div class="page-kicker">A situation</div>'
        + f'<h1>{esc(tr.get("title", tslug))}</h1>'
        + f'<p class="header-subtitle">{esc(tr.get("profile", ""))}</p></div>'
        + crumb(tr.get("title", tslug), "../")
        + f'<div class="overview-wrap">{ov}</div>'
        + '<div class="track-wrap">'
        + f'<div class="chapters-heading">{len(tr["entries"])} chapters, in this order</div>'
        + grid + "</div>")
    return shell(tr.get("title", tslug), body, "../../", "../", f"tracks/{tslug}.html")


GLOSSARY_SLUG = "money-words-defined"
_GL_TERM = re.compile(r'^\*\*(?P<term>[^*]+)\*\*\s+—\s+(?P<def>.+)$')


def _paras(lines: list) -> list:
    """Join wrapped lines into paragraphs, splitting on blank lines."""
    out, cur = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def glossary_body(md: str) -> str:
    """Render **term** — definition lines as a real <dl>, with a jump bar for the groups.

    A glossary is looked up, not read through, so the term has to be the scannable unit
    and each one needs a stable anchor other chapters can link to.

    Prose is kept as well. The lead-in before the first group, and any group that is prose
    rather than terms (Sources), are content. Discarding them is how this chapter's two
    opening paragraphs and its entire sourcing note came to be written, committed and
    never rendered."""
    groups, cur, lead = [], None, []
    for ln in md.split("\n"):
        s = ln.strip()
        if ln.startswith("## "):
            cur = {"title": s[3:].strip(), "id": anchor(s[3:].strip()),
                   "items": [], "intro": []}
            groups.append(cur)
            continue
        if cur is None:
            # The H1 is emitted by the page header; the paragraphs under it are not.
            if not ln.startswith("#"):
                lead.append(ln)
            continue
        m = _GL_TERM.match(s)
        if m:
            cur["items"].append((m.group("term").strip(), m.group("def").strip()))
        elif ln.startswith("#"):
            continue
        elif cur["items"] and s:
            t, d = cur["items"][-1]
            cur["items"][-1] = (t, d + " " + s)
        elif not cur["items"]:
            cur["intro"].append(ln)
    groups = [g for g in groups if g["items"] or _paras(g["intro"])]
    own = {g["id"] for g in groups if "plenee uses" in g["title"].lower()}
    out = [f"<p>{inline(t)}</p>" for t in _paras(lead)]
    out.append('<ul class="gl-jump">' + "".join(
        f'<li><a href="#{g["id"]}">{esc(g["title"])}</a></li>'
        for g in groups if g["items"]) + "</ul>")
    for g in groups:
        out.append(f'<h2 id="{g["id"]}">{esc(g["title"])}</h2><div class="subhead-accent"></div>')
        for para in _paras(g["intro"]):
            out.append(f"<p>{inline(para)}</p>")
        if not g["items"]:
            continue
        cls = " class=\"own\"" if g["id"] in own else ""
        rows = "".join(
            f'<dt id="term-{anchor(t)}"{cls}>{inline(t)}</dt><dd>{inline(d)}</dd>'
            for t, d in g["items"])
        out.append(f'<dl class="gl">{rows}</dl>')
    return "".join(out)


def contents_page(md, titles) -> str:
    # refs resolve AFTER render_body, not before. inline() escapes its input, so an
    # anchor produced up front arrives as visible &lt;a ...&gt; text — which is exactly
    # what shipped to /academy2/contents.html. A {{ref:slug}} marker carries no HTML
    # characters, so it passes through escaping untouched and resolves cleanly here.
    body_html, _, _ = render_body(md.split("---\n", 2)[-1])
    body_html = refs(body_html, titles, "")
    body = (
        '<div class="page-header"><div class="page-kicker">The whole Academy</div>'
        '<h1>Everything, by Subject</h1>'
        '<p class="header-subtitle">Every chapter, once, grouped by what it is about</p></div>'
        + crumb("Everything by subject", "", right=("Choose a situation", "index.html"))
        + f'<div class="chapter-wrap"><div class="chapter-body">{body_html}</div>'
        + '<div class="chapter-nav"><a class="cn-link next" href="index.html">'
        + '<div class="cn-dir">Or</div><div class="cn-title">Choose a situation instead</div>'
        + "</a></div></div>")
    return shell("Everything, by Subject", body, "../", "", "contents.html")


def ways_in(titles, chapters) -> str:
    """The two entry points that are not the track cards.

    The cards above ask the reader to recognize their own situation. These do not: one is
    ordered by subject, one by word. They are peers of each other and subordinate to the
    cards, so they share a rule and a label rather than sitting loose under the grid.
    Counts are read from the corpus, never typed, because a number that drifts is worse
    than no number.
    """
    gl = chapters.get(GLOSSARY_SLUG, {}).get("body", "")
    terms = len(re.findall(r'^\*\*([^*]+)\*\*\s+—', gl, re.M))
    nq = len(list((SRC / "quizzes").glob("*.md"))) if (SRC / "quizzes").exists() else 0
    ways = [("contents.html", "Everything by subject", f"{len(titles)} chapters"),
            (f"{GLOSSARY_SLUG}.html", "Glossary", f"{terms} terms")]
    if nq:
        ways.append(("quizzes.html", "Quizzes", f"{nq} to try"))
    return ('<div class="ways"><div class="chapters-heading">Or find it another way</div>'
            '<div class="ways-row">' + "".join(
                f'<a class="way" href="{h}"><span class="way-t">{esc(t)}</span>'
                f'<span class="way-m">{esc(m)}</span></a>' for h, t, m in ways)
            + "</div></div>")


QUIZ_JS = """
<script>
(function(){
  var el=document.getElementById('quiz-data'); if(!el) return;
  var D=JSON.parse(el.textContent), wrap=document.getElementById('quiz'), answered=0, right=0;
  D.items.forEach(function(it,i){
    var q=document.createElement('div'); q.className='qz-q';
    var h=document.createElement('div'); h.className='qz-qtext';
    h.innerHTML='<span class="qz-num">'+(i+1)+'</span>'+it.q; q.appendChild(h);
    var list=document.createElement('div'); list.className='qz-opts';
    it.options.forEach(function(o,j){
      var b=document.createElement('button'); b.type='button'; b.className='qz-opt';
      b.innerHTML=o;
      b.addEventListener('click',function(){
        if(q.dataset.done) return;
        q.dataset.done='1'; answered++;
        var ok=(j===it.answer); if(ok) right++;
        Array.prototype.forEach.call(list.children,function(c,k){
          c.disabled=true;
          if(k===it.answer) c.classList.add('correct');
          else if(k===j) c.classList.add('wrong');
        });
        var why=document.createElement('div');
        why.className='qz-why '+(ok?'ok':'no');
        why.innerHTML='<strong>'+(ok?'Correct.':'Not quite.')+'</strong> '+it.why;
        q.appendChild(why);
        if(answered===D.n){
          var r=document.getElementById('quiz-result');
          document.getElementById('quiz-score').textContent=right+' out of '+D.n+'.';
          r.hidden=false; r.scrollIntoView({behavior:'smooth',block:'nearest'});
        }
      });
      list.appendChild(b);
    });
    q.appendChild(list); wrap.appendChild(q);
  });
})();
</script>
"""

def load_quizzes() -> list:
    """Parse quizzes/*.md into question data.

    One `### Q:` per question, options as list items with `*` marking the correct one, and
    a `>` block for what the reader is told after answering. The asterisk is stripped before
    anything reaches the page — the answer key lives in the generator, not in the markup a
    reader can read."""
    out = []
    for f in sorted((SRC / "quizzes").glob("*.md")):
        meta, body = parse_front(f.read_text())
        intro, qs = [], []
        cur = None
        for ln in body.split("\n"):
            if ln.startswith("### Q:"):
                cur = {"q": ln[6:].strip(), "options": [], "answer": 0, "why": []}
                qs.append(cur)
            elif cur is None:
                if ln.strip() and not ln.startswith("#"):
                    intro.append(ln.strip())
            elif ln.startswith("- "):
                o = ln[2:].strip()
                if o.endswith(" *"):
                    cur["answer"] = len(cur["options"])
                    o = o[:-2].strip()
                cur["options"].append(o)
            elif ln.startswith("> "):
                cur["why"].append(ln[2:].strip())
        meta["intro"] = " ".join(intro)
        meta["questions"] = [{**q, "why": " ".join(q["why"])} for q in qs]
        out.append(meta)
    return out


def quiz_page(qz: dict, titles: dict) -> str:
    """One quiz. Answering is client-side; the page holds every question at once.

    The signature is the reveal rather than the score. A number out of ten teaches nothing,
    so each answer opens into what it costs and the chapter that shows the working — which
    is the only thing here the other financial literacy quizzes cannot do."""
    data = []
    for q in qz["questions"]:
        data.append({
            "q": esc(q["q"]),
            "options": [esc(o) for o in q["options"]],
            "answer": q["answer"],
            "why": refs(inline(q["why"]), titles, ""),
        })
    n = len(data)
    bench = qz.get("benchmark", "")
    body = (
        '<div class="page-header"><div class="page-kicker">' + esc(qz.get("kicker", "Quiz"))
        + '</div><h1>' + esc(qz.get("title", qz["slug"])) + '</h1>'
        + '<p class="header-subtitle">' + esc(qz.get("blurb", "")) + '</p></div>'
        + crumb(qz.get("title", ""), "", right=("All quizzes", "quizzes.html"))
        + '<div class="chapter-wrap"><div class="chapter-body">'
        + (f'<p>{inline(qz["intro"])}</p>' if qz.get("intro") else "")
        + '<div id="quiz"></div>'
        + '<div class="quiz-result" id="quiz-result" hidden>'
        + '<div class="tk-label">Your score</div><div class="subhead-accent"></div>'
        + '<p class="quiz-score" id="quiz-score"></p>'
        + (f'<p class="quiz-bench">{inline(bench)}</p>' if bench else "")
        + '<p><a class="ref-link" href="quizzes.html">Take another &rarr;</a></p>'
        + "</div></div></div>"
        + '<script type="application/json" id="quiz-data">'
        + json.dumps({"n": n, "items": data}) + "</script>"
        + QUIZ_JS)
    return shell(qz.get("title", qz["slug"]), body, "../", "", f'{qz["slug"]}.html')


def quizzes_index(quizzes: list) -> str:
    """Grouped by family, ordered by level within it.

    Families and their ordering come from the quiz files themselves. Hardcoding the list
    here meant every new family needed a generator edit, which is how a family gets written
    and then silently left off the page."""
    fams = {}
    for q in quizzes:
        key = q.get("family", "other")
        fams.setdefault(key, {"title": q.get("family_title", key),
                              "note": q.get("family_note", ""),
                              "order": int(q.get("family_order", 99)), "items": []})
        fams[key]["items"].append(q)
    out = []
    for key, fam in sorted(fams.items(), key=lambda kv: (kv[1]["order"], kv[0])):
        group = sorted(fam["items"], key=lambda q: int(q.get("level", 99)))
        rows = "".join(
            f'<a class="qz-card" href="{q["slug"]}.html">'
            + (f'<div class="qz-lvl">{esc(str(q["level"]))}</div>' if q.get("level") else "")
            + f'<div class="qz-kicker">{esc(q.get("kicker", ""))}</div>'
            f'<h3>{esc(q.get("title", q["slug"]))}</h3>'
            f'<p>{esc(q.get("blurb", ""))}</p>'
            f'<span class="qz-go">Start &rarr;</span></a>' for q in group)
        out.append(f'<div class="chapters-heading">{esc(fam["title"])}</div>'
                   + (f'<p class="qz-note">{esc(fam["note"])}</p>' if fam["note"] else "")
                   + f'<div class="qz-grid">{rows}</div>')
    n = sum(len(f["items"]) for f in fams.values())
    body = (
        '<div class="page-header"><div class="page-kicker">Plenee Academy</div>'
        '<h1>Test what you actually know</h1>'
        f'<p class="header-subtitle">{n} quizzes, graded, so a beginner is not asked an '
        'expert question and an expert is not asked a trivial one.</p></div>'
        + crumb("Quizzes", "", right=("Everything by subject", "contents.html"))
        + '<div class="track-wrap">' + "".join(out) + "</div>")
    return shell("Quizzes", body, "../", "", "quizzes.html")


def landing_page(tracks, titles, chapters) -> str:
    entries = [{"slug": ts, "why": tr.get("profile", ""), "blurb": blurb(tr["overview"])}
               for ts, tr in sorted(tracks.items(), key=lambda x: x[1].get("title", x[0]))]
    tl = {ts: tr.get("title", ts) for ts, tr in tracks.items()}
    grid = cards(entries, tl, href=lambda e: f'tracks/{e["slug"]}.html', hue_slug=lambda e: e["slug"])
    body = (
        ART_FILTER_DEFS
        + '<div class="page-header"><div class="page-kicker">Plenee Academy</div>'
        + "<h1>Start where you are</h1>"
        + '<p class="header-subtitle">What you get sold, what it costs, and what comes back</p></div>'
        + '<div class="track-wrap">'
        + '<div class="chapters-heading">Pick the situation closest to yours</div>'
        + grid
        + ways_in(titles, chapters) + "</div>")
    return shell("Plenee Academy", body, "../", "", "")


CHAPTER_BLURB: dict = {}


def main() -> int:
    chapters, tracks, contents_md = load()
    # Populate titles BEFORE blurbs — blurb() resolves {{ref:}} markers against them.
    CHAPTER_TITLES.update({s: c.get("title", s) for s, c in chapters.items()})
    CHAPTER_BLURB.update({s: (c.get("blurb") or blurb(c["body"]))
                          for s, c in chapters.items()})
    titles = {s: c.get("title", s) for s, c in chapters.items()}

    # subject-order neighbours, for readers with no track context
    order = re.findall(r'\{\{ref:([\w-]+)\}\}', contents_md)
    # the eyebrow carries the chapter's subject from the general index. v1 puts a chapter
    # number there; v2 has no numbers by design, so it carries something true instead.
    subject_of, cur = {}, "Academy"
    for line in contents_md.split("\n"):
        if line.startswith("## "):
            cur = line[3:].strip()
        for m in re.finditer(r'\{\{ref:([\w-]+)\}\}', line):
            subject_of[m.group(1)] = cur
    subj = {}
    for i, s in enumerate(order):
        subj[s] = {
            "prev": ({"slug": order[i-1], "title": titles[order[i-1]]} if i else None),
            "next": ({"slug": order[i+1], "title": titles[order[i+1]]} if i+1 < len(order) else None),
        }

    missing = [s for s in chapters if s not in order]
    if missing:
        raise SystemExit(f"BUILD FAILED: chapters missing from contents.md: {missing}. "
                         "The general index is the canonical listing; a chapter absent from it "
                         "would generate a page nothing links to.")

    # Footnotes fail silently, and that is the worst kind of failure in this corpus. The
    # renderer matches [^<digits>] only and takes definitions from a "## Sources" section.
    # A marker like [^cs6-1], or a definition sitting loose at the foot of the file, is not
    # an error — it simply vanishes, and the page publishes looking entirely normal with
    # its citations gone. Twenty chapters nearly shipped that way. In an Academy whose whole
    # method is that every claim carries its source, silence is the wrong response.
    fn_problems = []
    for slug, ch in chapters.items():
        raw = ch["body"]
        body = raw.split("\n## Sources")[0]
        nonnum = sorted({m.group(1) for m in re.finditer(r'\[\^([^\]]+)\]', body)
                         if not m.group(1).isdigit()})
        used = {m.group(1) for m in re.finditer(r'\[\^(\d+)\]', body)}
        defined = {m.group(1) for m in re.finditer(r'^\[\^(\d+)\]:', raw, re.M)}
        outside = "## Sources" not in raw and defined
        if nonnum:
            fn_problems.append(f"{slug}: non-numeric footnote markers {nonnum} — the "
                               f"renderer matches [^1] style only, so these would be dropped")
        if used - defined:
            fn_problems.append(f"{slug}: markers {sorted(used - defined)} have no definition")
        if outside:
            fn_problems.append(f"{slug}: footnote definitions exist but there is no "
                               f"'## Sources' heading, so none of them would render")
    if fn_problems:
        raise SystemExit("BUILD FAILED: footnotes would be silently dropped.\n  "
                         + "\n  ".join(fn_problems))

    # Every check below is here because the failure it catches is SILENT. A build that
    # errors is cheap; a build that publishes something subtly wrong is not, because
    # nothing downstream will notice and the page looks entirely normal.

    # A slug collision does not error — the second file simply replaces the first in the
    # dict and one chapter stops existing, with the page count still looking plausible.
    files = list((SRC / "chapters").glob("*.md"))
    if len(files) != len(chapters):
        seen = {}
        for f in files:
            m = re.search(r'^slug:\s*(\S+)', f.read_text(), re.M)
            s = m.group(1) if m else f.stem
            seen.setdefault(s, []).append(f.name)
        clashes = {s: v for s, v in seen.items() if len(v) > 1}
        raise SystemExit(f"BUILD FAILED: {len(files)} chapter files produced "
                         f"{len(chapters)} chapters. Slug collisions: {clashes}")

    # A {{ref:}} pointing at nothing renders as a dead link or survives as raw markup,
    # depending where it sits. Neither stops the build.
    known = set(chapters)
    dangling = []
    for name, md in ([(f"chapters/{s}", c["body"]) for s, c in chapters.items()]
                     + [(f"tracks/{s}", t.get("overview", "") + "".join(
                         e["why"] for e in t["entries"])) for s, t in tracks.items()]
                     + [("contents.md", contents_md)]):
        for r in sorted({m.group(1) for m in re.finditer(r'\{\{ref:([\w-]+)\}\}', md)}):
            if r not in known:
                dangling.append(f"{name} -> {{{{ref:{r}}}}}")
    if dangling:
        raise SystemExit("BUILD FAILED: references to chapters that do not exist.\n  "
                         + "\n  ".join(dangling))

    # A source listed under ## Sources that nothing cites renders as an orphan entry in
    # the Sources block, usually because a citation was edited out of the prose and its
    # definition left behind.
    orphan_notes = []
    for slug, ch in chapters.items():
        raw = ch["body"]
        used = {m.group(1) for m in re.finditer(r'\[\^(\d+)\]', raw.split("\n## Sources")[0])}
        defs = re.findall(r'^\[\^(\d+)\]:', raw, re.M)
        if set(defs) - used:
            orphan_notes.append(f"{slug}: sources {sorted(set(defs) - used)} defined but never cited")
        dup = sorted({d for d in defs if defs.count(d) > 1})
        if dup:
            orphan_notes.append(f"{slug}: footnote {dup} defined more than once")
    if orphan_notes:
        raise SystemExit("BUILD FAILED: footnote definitions do not match their citations.\n  "
                         + "\n  ".join(orphan_notes))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    (OUT / "index.html").write_text(landing_page(tracks, titles, chapters))
    (OUT / "contents.html").write_text(contents_page(contents_md, titles))

    quizzes = load_quizzes()
    if quizzes:
        (OUT / "quizzes.html").write_text(quizzes_index(quizzes))
        for qz in quizzes:
            (OUT / f'{qz["slug"]}.html').write_text(quiz_page(qz, titles))
    (OUT / "tracks").mkdir()
    for tslug, t in tracks.items():
        (OUT / "tracks" / f"{tslug}.html").write_text(track_page(tslug, t, titles))
    for slug, ch in chapters.items():
        (OUT / f"{slug}.html").write_text(
            chapter_page(slug, ch, tracks, titles, subj.get(slug), subject_of.get(slug, "Academy")))

    # Everything above checks the SOURCES. This checks the OUTPUT, and it is the only one
    # that catches a bug in the renderer itself. {{ref:}} markers once shipped to live
    # pages inside card blurbs, because every source file was correct and nothing looked
    # at what was actually written.
    raw_markers = sorted(f.relative_to(OUT).as_posix()
                         for f in OUT.rglob("*.html") if "{{ref:" in f.read_text())
    if raw_markers:
        raise SystemExit(
            "BUILD FAILED: unrendered {{ref:}} markers in the output — "
            "the pages are written but MUST NOT be published.\n  "
            + "\n  ".join(raw_markers))

    n = len(list(OUT.rglob("*.html")))
    print(f"academy2/: {len(chapters)} chapters, {len(tracks)} tracks, {n} pages")
    untracked = [s for s in chapters
                 if not any(s in [e["slug"] for e in t["entries"]] for t in tracks.values())]
    if untracked:
        print(f"  WARNING: in no track, reachable only from the general index: {untracked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
