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
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_academy_pages import PAGE_TEMPLATE, STYLE_BLOCK  # noqa: E402

WEBSITE = Path(__file__).resolve().parents[1]
SRC = WEBSITE.parent / "plenee_app" / "docs" / "academy_v2"
OUT = WEBSITE / "academy2"

V2_STYLE = """
.v2-strip{display:flex;gap:.75rem;align-items:center;flex-wrap:wrap;font-size:.85rem;
  padding:.6rem .9rem;border-radius:8px;background:rgba(0,0,0,.04);margin:0 0 1.6rem}
.v2-strip a{text-decoration:none;border-bottom:1px solid rgba(0,0,0,.2)}
.v2-strip .v2-pos{opacity:.65}
.v2-alsoin{margin:2.6rem 0 0;padding:1.1rem 1.2rem;border-radius:10px;background:rgba(0,0,0,.03)}
.v2-alsoin h3{margin:0 0 .7rem;font-size:.95rem;letter-spacing:.02em;text-transform:uppercase;opacity:.7}
.v2-alsoin ul{margin:0;padding:0;list-style:none}
.v2-alsoin li{margin:.45rem 0;font-size:.94rem}
.v2-alsoin .v2-why{opacity:.7}
.v2-pager{display:flex;justify-content:space-between;gap:1rem;margin:2.2rem 0 0}
.v2-pager a{max-width:46%;text-decoration:none;font-size:.94rem}
.v2-pager .v2-next{text-align:right;margin-left:auto}
.v2-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1rem;margin:1.6rem 0}
.v2-card{display:block;padding:1.1rem 1.2rem;border-radius:10px;background:rgba(0,0,0,.03);
  text-decoration:none;transition:transform .12s ease}
.v2-card:hover{transform:translateY(-2px)}
.v2-card b{display:block;margin-bottom:.35rem}
.v2-card span{font-size:.9rem;opacity:.75}
.v2-sub{opacity:.75;margin:.2rem 0 1.6rem}
.v2-fn{font-size:.88rem;opacity:.85}
.v2-fn li{margin:.5rem 0}
table.v2{border-collapse:collapse;width:100%;margin:1.4rem 0;font-size:.93rem}
table.v2 th,table.v2 td{border-bottom:1px solid rgba(0,0,0,.12);padding:.5rem .6rem;text-align:left;vertical-align:top}
table.v2 th{font-weight:600}
.v2-scroll{overflow-x:auto}
sup.fnref a{text-decoration:none;padding:0 .1em}
"""


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
        return f'<a href="{depth}{slug}/">{esc(titles[slug])}</a>'
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
    out, i = [], 0
    lines = body.split("\n")
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            i += 1
            continue  # the H1 is rendered from frontmatter
        if ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:].strip(), seen)}</h2>")
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
                      f'<a href="#r{n}" aria-label="back to text">&#8617;</a></li>' for n, t in notes)
        src_html = f'<h2>Sources</h2><ol class="v2-fn">{lis}</ol>'
    return "\n".join(out), src_html


# --------------------------------------------------------------------------- pages

BASE = "https://plenee.com/academy2/"


def shell(title: str, body: str, depth_root: str, ac_root: str, canonical: str = "") -> str:
    page = PAGE_TEMPLATE.format(page_title=esc(title), style=STYLE_BLOCK + V2_STYLE,
                                body=body, root=depth_root, ac_root=ac_root)
    # Every page declares its canonical URL without the ?via= parameter. Track context is a
    # query string precisely so a chapter never gets a second address; without this tag a
    # crawler can still index /slug/?via=a and /slug/?via=b as separate pages and split
    # whatever authority the chapter earns.
    tag = f'<link rel="canonical" href="{BASE}{canonical}">'
    return page.replace("</title>", "</title>\n" + tag, 1)


NAV_JS = """
<script>
(function(){
  var d=JSON.parse(document.getElementById('v2-nav').textContent);
  var p=new URLSearchParams(location.search).get('via');
  if(!p){try{p=localStorage.getItem('plenee_track')||''}catch(e){}}
  if(p&&!d.tracks[p]){p=''}
  if(p){try{localStorage.setItem('plenee_track',p)}catch(e){}}
  var strip=document.getElementById('v2-strip'),pager=document.getElementById('v2-pager');
  if(p){
    var t=d.tracks[p];
    strip.innerHTML='<span>In <a href="'+d.depth+'tracks/'+p+'/">'+t.title+'</a></span>'
      +'<span class="v2-pos">'+t.pos+' of '+t.len+'</span>'
      +'<a href="'+d.depth+'contents/">See everything by subject instead</a>';
    strip.style.display='';
    var h='';
    if(t.prev){h+='<a class="v2-prev" href="'+d.depth+t.prev.slug+'/?via='+p+'">&#8592; '+t.prev.title+'</a>'}
    if(t.next){h+='<a class="v2-next" href="'+d.depth+t.next.slug+'/?via='+p+'">'+t.next.title+' &#8594;</a>'}
    if(!t.prev&&!t.next){h='<a href="'+d.depth+'tracks/'+p+'/">Back to '+t.title+'</a>'}
    pager.innerHTML=h;
  }else if(d.subject){
    var h='';
    if(d.subject.prev){h+='<a class="v2-prev" href="'+d.depth+d.subject.prev.slug+'/">&#8592; '+d.subject.prev.title+'</a>'}
    if(d.subject.next){h+='<a class="v2-next" href="'+d.depth+d.subject.next.slug+'/">'+d.subject.next.title+' &#8594;</a>'}
    pager.innerHTML=h;
  }
})();
</script>
"""


def chapter_page(slug, ch, tracks, titles, subject_nbrs) -> str:
    body_html, src_html = render_body(refs(ch["body"], titles, "../"))
    memberships = []
    navmap = {}
    for tslug, t in tracks.items():
        slugs = [e["slug"] for e in t["entries"]]
        if slug not in slugs:
            continue
        idx = slugs.index(slug)
        why = t["entries"][idx]["why"]
        memberships.append((tslug, t.get("title", tslug), why))
        navmap[tslug] = {
            "title": t.get("title", tslug), "pos": idx + 1, "len": len(slugs),
            "prev": ({"slug": slugs[idx-1], "title": titles[slugs[idx-1]]} if idx else None),
            "next": ({"slug": slugs[idx+1], "title": titles[slugs[idx+1]]} if idx+1 < len(slugs) else None),
        }
    also = ""
    if memberships:
        lis = "".join(
            f'<li><a href="../tracks/{ts}/">{esc(tt)}</a> — <span class="v2-why">{inline(why)}</span></li>'
            for ts, tt, why in sorted(memberships, key=lambda x: x[1]))
        also = ('<div class="v2-alsoin"><h3>This chapter also appears in</h3>'
                f'<ul>{lis}</ul></div>')
    payload = json.dumps({"depth": "../", "tracks": navmap, "subject": subject_nbrs})
    body = (
        f'<article class="chapter">'
        f'<div class="v2-strip" id="v2-strip" style="display:none"></div>'
        f'<h1>{esc(ch.get("title", slug))}</h1>'
        f'{body_html}{src_html}{also}'
        f'<div class="v2-pager" id="v2-pager"></div>'
        f'</article>'
        f'<script type="application/json" id="v2-nav">{payload}</script>{NAV_JS}'
    )
    return shell(ch.get("title", slug), body, "../../", "../", f"{slug}/")


def track_page(tslug, t, titles) -> str:
    ov, _ = render_body(t["overview"])
    cards = "".join(
        f'<a class="v2-card" href="../../{e["slug"]}/?via={tslug}"><b>{esc(titles[e["slug"]])}</b>'
        f'<span>{inline(e["why"])}</span></a>' for e in t["entries"])
    body = (f'<article class="chapter"><h1>{esc(t.get("title", tslug))}</h1>'
            f'<p class="v2-sub">{esc(t.get("profile", ""))}</p>{ov}'
            f'<div class="v2-cards">{cards}</div>'
            f'<p><a href="../../contents/">See everything by subject instead</a></p></article>')
    return shell(t.get("title", tslug), body, "../../../", "../../", f"tracks/{tslug}/")


def contents_page(md, titles) -> str:
    body_html, _ = render_body(refs(md.split("---\n", 2)[-1], titles, "../"))
    body = (f'<article class="chapter">{body_html}'
            f'<p><a href="../">Choose a situation instead</a></p></article>')
    return shell("Everything, by Subject", body, "../../", "../", "contents/")


def landing_page(tracks, titles) -> str:
    cards = "".join(
        f'<a class="v2-card" href="tracks/{ts}/"><b>{esc(t.get("title", ts))}</b>'
        f'<span>{esc(t.get("profile",""))}</span></a>'
        for ts, t in sorted(tracks.items(), key=lambda x: x[1].get("title", x[0])))
    body = (
        '<article class="chapter"><h1>Plenee Academy</h1>'
        '<p>Every chapter is sourced, and every figure carries where it came from. '
        'Pick the situation closest to yours for a shorter path through it, or read '
        'everything by subject.</p>'
        f'<div class="v2-cards">{cards}</div>'
        '<p><a href="contents/">See everything by subject</a></p></article>')
    return shell("Plenee Academy", body, "../", "", "")


def main() -> int:
    chapters, tracks, contents_md = load()
    titles = {s: c.get("title", s) for s, c in chapters.items()}

    # subject-order neighbours, for readers with no track context
    order = re.findall(r'\{\{ref:([\w-]+)\}\}', contents_md)
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

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    (OUT / "index.html").write_text(landing_page(tracks, titles))
    (OUT / "contents").mkdir()
    (OUT / "contents" / "index.html").write_text(contents_page(contents_md, titles))
    for tslug, t in tracks.items():
        d = OUT / "tracks" / tslug
        d.mkdir(parents=True)
        (d / "index.html").write_text(track_page(tslug, t, titles))
    for slug, ch in chapters.items():
        d = OUT / slug
        d.mkdir(parents=True)
        (d / "index.html").write_text(chapter_page(slug, ch, tracks, titles, subj.get(slug)))

    n = len(list(OUT.rglob("index.html")))
    print(f"academy2/: {len(chapters)} chapters, {len(tracks)} tracks, {n} pages")
    untracked = [s for s in chapters
                 if not any(s in [e["slug"] for e in t["entries"]] for t in tracks.values())]
    if untracked:
        print(f"  WARNING: in no track, reachable only from the general index: {untracked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
