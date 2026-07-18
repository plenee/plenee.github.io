#!/usr/bin/env python3
"""
Academy {{ref:ID}} resolver — Plenee Academy publishing pipeline.

Converts the `{{ref:ID}}` placeholder tokens used throughout
plenee_app/docs/academy/*_expanded.md into real relative links, using the
corpus's own current chapter/track structure as the source of truth. This is
the "resolution script" ACADEMY_PUBLISHING_INSTRUCTIONS.md (§1, §7) describes:
it reads a token, looks up the target chapter's current title, generates its
slug per that document's §3 rule, and emits a real relative URL.

Scope, deliberately narrow: this script ONLY resolves `{{ref:ID}}` tokens. It
does not do the rest of the markdown->HTML conversion (stripping Status
headers, h1/h2 conversion, "The takeaway" callout styling, etc.) described in
ACADEMY_PUBLISHING_INSTRUCTIONS.md §2-6 — that's a separate, larger piece of
work this script is meant to be composed with, not a replacement for it.

Token shapes handled (confirmed exhaustive by corpus scan, 2026-07-18):
    {{ref:4.1}}      -> Volume 1 chapter reference
    {{ref:PM1.2}}     -> Volume 2 chapter reference
    {{ref:track4}}    -> Volume 1 track-level reference (links to that
                          track's index page)
    (No Volume-2 track-level token shape exists in the corpus today — Volume
    2 chapters are always referenced individually.)

Assumes the fixed sibling directory layout this repo actually has:
    Plenee/
      plenee_app/docs/academy/*_expanded.md       <- source of truth
      website/academy/<track-slug>/<chapter>.html <- published pages
      website/scripts/resolve_academy_refs.py     <- this file

Usage:
    python3 resolve_academy_refs.py --check
        Build the index, resolve every {{ref:ID}} token in every source
        file, and report any that fail to resolve. Exits non-zero if any
        broken references are found. Run this before every publish.

    python3 resolve_academy_refs.py --render track4_extraction_economy_expanded.md
        Print the given source file's body with every {{ref:ID}} token
        replaced by a real `<a href="...">` link (relative to that file's
        own track folder). Everything else in the file is left untouched.

    python3 resolve_academy_refs.py --render-all OUTDIR/
        Run --render across every *_expanded.md file, writing ref-resolved
        copies into OUTDIR/ under the same filenames, for a future page-
        generation step to consume.

    python3 resolve_academy_refs.py --index
        Print the built chapter/track index as JSON (id -> track slug,
        chapter slug, titles) — useful for debugging or for a different
        pipeline that wants the lookup table without the substitution logic.

No third-party dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WEBSITE_DIR = SCRIPT_DIR.parent
PLENEE_ROOT = WEBSITE_DIR.parent
ACADEMY_SRC = PLENEE_ROOT / "plenee_app" / "docs" / "academy"

TOKEN_RE = re.compile(r"\{\{ref:([A-Za-z0-9.]+)\}\}")
TRACK_TITLE_RE = re.compile(
    r"^#\s*Plenee Academy\s*—\s*(?:Volume\s+\d+,\s*)?Track\s+\S+:\s*(.+?)\s*—\s*EXPANDED EDITION",
    re.MULTILINE,
)
CHAPTER_RE = re.compile(r"^#\s*Chapter\s+(\S+)\s*—\s*(.+)$", re.MULTILINE)


@dataclass
class ChapterInfo:
    chapter_id: str        # e.g. "4.1" or "PM1.2", exactly as it appears in tokens
    title: str
    track_slug: str
    chapter_slug: str       # without ".html"


@dataclass
class TrackInfo:
    track_num: str          # e.g. "4" — Volume 1 only (no Volume 2 track-level tokens exist)
    title: str
    track_slug: str


@dataclass
class AcademyIndex:
    chapters: dict[str, ChapterInfo] = field(default_factory=dict)
    tracks: dict[str, TrackInfo] = field(default_factory=dict)
    source_files: dict[str, Path] = field(default_factory=dict)  # track_slug -> source path


def slugify_title(title: str) -> str:
    """Matches the convention already observed in the published
    website/academy/track2-visibility/*.html filenames: lowercase, drop
    apostrophes (don't -> dont), turn every other non-alphanumeric run into a
    single hyphen, collapse repeats, strip leading/trailing hyphens."""
    s = title.lower()
    s = s.replace("'", "").replace("’", "")  # straight + curly apostrophe
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def track_slug_and_num_from_filename(stem: str) -> tuple[str, str | None]:
    """stem = filename with `_expanded.md` already stripped.
    Returns (track_slug, track_num_or_None). track_num is None for the two
    Volume 2 files, which have no track-level {{ref:...}} token shape."""
    if stem.startswith("pm_track1_"):
        rest = stem[len("pm_track1_"):]
        return f"volume2-track1-{rest.replace('_', '-')}", None
    if stem.startswith("pm_track2_"):
        rest = stem[len("pm_track2_"):]
        return f"volume2-track2-{rest.replace('_', '-')}", None
    m = re.match(r"track(\d+)_", stem)
    track_num = m.group(1) if m else None
    return stem.replace("_", "-"), track_num


def chapter_slug(chapter_id: str, title: str) -> str:
    """'4.10' + 'The ...' -> '4-10-the-...' ; 'PM1.2' + 'Loss ...' -> '1-2-loss-...'
    (the leading 'PM' is dropped from the slug's number portion — the file
    already lives inside the volume2-trackN folder, so repeating "PM" in the
    chapter filename would be redundant. This is a deliberate design choice,
    not an inference from an existing published example — Volume 2 has no
    published pages yet to confirm against.)"""
    num = chapter_id[2:] if chapter_id.startswith("PM") else chapter_id
    num_slug = num.replace(".", "-")
    return f"{num_slug}-{slugify_title(title)}"


def build_index(academy_src: Path = ACADEMY_SRC) -> AcademyIndex:
    idx = AcademyIndex()
    files = sorted(academy_src.glob("*_expanded.md"))
    if not files:
        raise FileNotFoundError(f"No *_expanded.md files found under {academy_src}")

    for path in files:
        text = path.read_text(encoding="utf-8")
        stem = path.name.removesuffix("_expanded.md")
        t_slug, t_num = track_slug_and_num_from_filename(stem)
        idx.source_files[t_slug] = path

        m = TRACK_TITLE_RE.search(text)
        track_title = m.group(1).strip() if m else stem

        if t_num is not None:
            idx.tracks[t_num] = TrackInfo(track_num=t_num, title=track_title, track_slug=t_slug)

        for cm in CHAPTER_RE.finditer(text):
            cid, ctitle = cm.group(1), cm.group(2).strip()
            idx.chapters[cid] = ChapterInfo(
                chapter_id=cid,
                title=ctitle,
                track_slug=t_slug,
                chapter_slug=chapter_slug(cid, ctitle),
            )

    return idx


def resolve_token(token_id: str, current_track_slug: str, idx: AcademyIndex) -> tuple[str, str] | None:
    """Returns (relative_url, default_display_text) or None if unresolvable."""
    if token_id.startswith("track") and token_id[len("track"):].isdigit():
        num = token_id[len("track"):]
        info = idx.tracks.get(num)
        if info is None:
            return None
        target = "index.html" if info.track_slug == current_track_slug else f"../{info.track_slug}/index.html"
        return target, f"Track {num}"

    info = idx.chapters.get(token_id)
    if info is None:
        return None
    fname = f"{info.chapter_slug}.html"
    target = fname if info.track_slug == current_track_slug else f"../{info.track_slug}/{fname}"
    return target, f"Chapter {token_id}"


def render(text: str, current_track_slug: str, idx: AcademyIndex) -> tuple[str, list[str]]:
    """Replace every {{ref:ID}} token in `text` with a real <a href> link.
    Returns (new_text, list_of_unresolved_ids)."""
    unresolved: list[str] = []

    def _sub(m: re.Match) -> str:
        token_id = m.group(1)
        resolved = resolve_token(token_id, current_track_slug, idx)
        if resolved is None:
            unresolved.append(token_id)
            return m.group(0)  # leave the raw token in place — never guess wrong

        url, default_text = resolved
        preceding = text[: m.start()].rstrip()
        # avoid "Chapter Chapter 4.1" / "Chapters Chapter 4.1" when the prose
        # already wrote the word "Chapter(s)" immediately before the token
        if preceding.endswith("Chapter") or preceding.endswith("Chapters"):
            link_text = token_id
        else:
            link_text = default_text
        return f'<a href="{url}">{link_text}</a>'

    new_text = TOKEN_RE.sub(_sub, text)
    return new_text, unresolved


def cmd_check(idx: AcademyIndex) -> int:
    total_tokens = 0
    all_unresolved: dict[str, list[str]] = {}
    for path in sorted(ACADEMY_SRC.glob("*_expanded.md")):
        text = path.read_text(encoding="utf-8")
        stem = path.name.removesuffix("_expanded.md")
        t_slug, _ = track_slug_and_num_from_filename(stem)
        tokens = TOKEN_RE.findall(text)
        total_tokens += len(tokens)
        _, unresolved = render(text, t_slug, idx)
        if unresolved:
            all_unresolved[path.name] = unresolved

    print(f"Indexed {len(idx.chapters)} chapters across {len(idx.source_files)} tracks "
          f"({len(idx.tracks)} Volume-1 track-level targets).")
    print(f"Checked {total_tokens} {{{{ref:ID}}}} tokens across {len(idx.source_files)} files.")

    if not all_unresolved:
        print("All references resolve cleanly. Nothing broken.")
        return 0

    print("\nBROKEN REFERENCES:")
    for fname, ids in all_unresolved.items():
        print(f"  {fname}: {', '.join(sorted(set(ids)))}")
    return 1


def cmd_render(source_arg: str) -> int:
    path = Path(source_arg)
    if not path.is_absolute():
        path = ACADEMY_SRC / source_arg
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        return 1

    idx = build_index()
    stem = path.name.removesuffix("_expanded.md")
    t_slug, _ = track_slug_and_num_from_filename(stem)
    text = path.read_text(encoding="utf-8")
    new_text, unresolved = render(text, t_slug, idx)
    print(new_text)
    if unresolved:
        print(f"\n[warning: {len(unresolved)} unresolved token(s): "
              f"{', '.join(sorted(set(unresolved)))}]", file=sys.stderr)
    return 0


def cmd_render_all(outdir_arg: str) -> int:
    idx = build_index()
    outdir = Path(outdir_arg)
    outdir.mkdir(parents=True, exist_ok=True)
    any_unresolved = False

    for path in sorted(ACADEMY_SRC.glob("*_expanded.md")):
        stem = path.name.removesuffix("_expanded.md")
        t_slug, _ = track_slug_and_num_from_filename(stem)
        text = path.read_text(encoding="utf-8")
        new_text, unresolved = render(text, t_slug, idx)
        (outdir / path.name).write_text(new_text, encoding="utf-8")
        if unresolved:
            any_unresolved = True
            print(f"  {path.name}: {len(unresolved)} unresolved -> "
                  f"{', '.join(sorted(set(unresolved)))}", file=sys.stderr)

    print(f"Wrote {len(list(ACADEMY_SRC.glob('*_expanded.md')))} ref-resolved files to {outdir}")
    return 1 if any_unresolved else 0


def cmd_index() -> int:
    idx = build_index()
    payload = {
        "tracks": {
            num: {"title": t.title, "track_slug": t.track_slug}
            for num, t in idx.tracks.items()
        },
        "chapters": {
            cid: {"title": c.title, "track_slug": c.track_slug, "chapter_slug": c.chapter_slug}
            for cid, c in idx.chapters.items()
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Validate every {{ref:ID}} token resolves.")
    group.add_argument("--render", metavar="SOURCE.md", help="Print one source file with refs resolved.")
    group.add_argument("--render-all", metavar="OUTDIR", help="Resolve refs across every source file into OUTDIR.")
    group.add_argument("--index", action="store_true", help="Print the built id->slug index as JSON.")
    args = parser.parse_args()

    if args.check:
        return cmd_check(build_index())
    if args.render:
        return cmd_render(args.render)
    if args.render_all:
        return cmd_render_all(args.render_all)
    if args.index:
        return cmd_index()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
