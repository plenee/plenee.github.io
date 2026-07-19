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

Scope: handles the `# Chapter N.M -- Title` boundary onward, plus the
top-level Academy landing page (academy/index.html, per
ACADEMY_PUBLISHING_INSTRUCTIONS.md §6 -- one section per track, grouped by
Volume, in academy_curriculum.md's reading order, which is discovered at
generation time, never hardcoded). Covers every track in both volumes
(Volume 1's plain `N.M` chapter ids and Volume 2's `PMN.M` ids, the latter
displayed to readers with the "PM" shorthand stripped per
ACADEMY_PUBLISHING_INSTRUCTIONS.md §7).

Usage:
    python3 generate_academy_pages.py track2_visibility_expanded.md
        Regenerates one track's chapter pages + its own index.html, from the
        CURRENT source file. Fast, but that index.html's search box will only
        cover this track's chapters until --all is next run, and the landing
        page (academy/index.html) is untouched.

    python3 generate_academy_pages.py --all
        Regenerates every track from current source, embeds one shared,
        cross-track search index on every track's index.html AND the landing
        page, and rebuilds the landing page itself. Run this after any
        content change so "Search Academy" stays corpus-wide accurate.

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
    PLENEE_ROOT,
    WEBSITE_DIR,
    build_index,
    dedupe_leading_article,
    slugify_title,
    smart_title,
    track_slug_and_num_from_filename,
    resolve_token,
)

CURRICULUM_PATH = PLENEE_ROOT / "plenee_app" / "docs" / "academy_curriculum.md"
TRACK_HEADER_RE = re.compile(r"^TRACK\s+(\d+)\s*—", re.MULTILINE)
VOLUME2_MARKER_RE = re.compile(r"^VOLUME 2\s*—", re.MULTILINE)

# Hand-authored, one sentence per track -- not mechanically extracted (per
# ACADEMY_PUBLISHING_INSTRUCTIONS.md §5's "write a new sentence, don't lift
# verbatim" spirit), but informed by each track's own subtitle in
# academy_curriculum.md. Keyed by track_slug so re-running --all never
# silently drops a teaser if a track gets renumbered -- only renamed/removed.
TRACK_TEASERS = {
    "track1-language-of-money": "The vocabulary everything else builds on — FLOW, NET, and NEST, in plain English.",
    "track2-visibility": "Map every account, transaction, and recurring charge before you try to change anything.",
    "track4-extraction-economy": "How banks, funds, and insurers profit from your inattention — and how to stop paying for it.",
    "track5-the-debt-trap": "A century of marketing and easy credit conditioned Americans into debt — see the strings before you feel them.",
    "track6-stop-the-bleeding": "Flywheel Stage 1 — eliminate the fees and cash leaks that don't require earning a dollar more.",
    "track7-free-up-cash-flow": "Flywheel Stage 2 — free up the cash flow that's already yours.",
    "track8-build-wealth": "Flywheel Stage 3 — put compounding to work, on purpose.",
    "track9-earn-dont-pay": "Flywheel Stage 4 — flip the equation from paying interest to earning it.",
    "track3-credit-mastery": "How credit scores actually work, and how to build or rebuild yours.",
    "track10-taxes-efficiency": "Keep more of what you earn — bracket mechanics, account sequencing, and withholding done right.",
    "track11-life-events": "Applied efficiency for the big transitions — cars, homes, marriage, kids, job changes.",
    "track12-retirement-decumulation": "Spending your NEST well — decumulation without the guilt.",
    "track13-protection": "Insurance, estate basics, fraud, and data privacy — insure catastrophes, not inconveniences.",
    "track14-high-wealth-efficiency": "The invisible fleecing at high net worth — fees, incentives, and what you're really paying for.",
    "track15-when-preparation-isnt-enough": "What preparation doesn't cover — sizing real exposure, and navigating the system after a shock.",
    "volume2-track1-your-built-in-wiring": "Why the mind misfires on money — the wiring behind every financial mistake, not a character flaw.",
    "volume2-track2-what-money-is-for": "What money is actually for — meaning, identity, and knowing when enough is enough.",
}

# Two-paragraph overviews for the landing page and each track's own index
# page. Hand-written per Rob's direction (2026-07-18): consumer voice, not
# academic/textbook framing -- avoid "teach"/"taught"/"curriculum"/"lesson".
ACADEMY_OVERVIEW = (
    "Most people never got a straight explanation of how money actually works — why a credit score moves the way it does, what a 1% fee really costs over 30 years, or who benefits when a bank waives one fee and not another. Plenee Academy fills that in: plain-English explanations of the systems, incentives, and numbers behind everyday financial decisions, written the way a sharp, financially literate friend would explain it — not the way a disclosure page does.",
    "It's organized in two parts. Volume 1 is something you dip into as decisions come up — reading a credit report, sizing an emergency fund, deciding whether refinancing helps or hurts — read whatever's relevant today and ignore the rest until you need it. Volume 2 turns the lens inward, on the mental shortcuts that make smart people mishandle money anyway, and why seeing them changes what happens next. Neither one tells you what to do with your specific numbers — that's what the rest of Plenee is for — but both make the decision in front of you easier to see clearly.",
)

TRACK_OVERVIEWS = {
    "track1-language-of-money": (
        "Most financial confusion isn't about math — it's about vocabulary. Terms like “net income,” “cash flow,” and “net worth” get thrown around constantly, but few people could define them precisely enough to use them, and fewer still were ever shown how the concepts connect. This track builds that vocabulary from the ground up, using Plenee's own plain-English versions of the ideas — FLOW, NET, and NEST — instead of the jargon that usually gets in the way.",
        "It covers what money actually moving through your life looks like (FLOW), whether you're coming out ahead over any given stretch of time (NET), and what you actually own once everything's netted out (NEST) — plus the more useful distinctions hiding underneath those three ideas, like the difference between debt that changes your financial position and debt that just pays for spending, or between money you're obligated to spend and money you're choosing to. It closes on a distinction that reframes a lot of what follows: being rich is what other people see; being wealthy is what they don't.",
    ),
    "track2-visibility": (
        "You can't fix what you can't see, and most people's financial picture is scattered across four or five logins, a stack of statements they don't read closely, and a credit report they've never actually opened. This track is about closing that gap — not about telling you what to change yet, just making sure you actually know where things stand before you try.",
        "It walks through mapping every account you hold, actually reading a transaction history instead of skimming it, understanding what's really in a credit report and how VantageScore and FICO differ, and finding the recurring charges that quietly outlive their usefulness. It also names something rarely said out loud: not having visibility costs real time and creates its own kind of stress — a “stress tax” that compounds the original problem. Everything after this track assumes the picture this one builds.",
    ),
    "track4-extraction-economy": (
        "A meaningful share of what flows out of the average household's accounts every year isn't the cost of a product or service — it's the cost of not looking closely. Overdraft fees, idle cash earning nothing, a 1% advisory fee compounding away decades of returns, whole life insurance sold instead of bought: none of it is illegal, and all of it depends on inattention to work.",
        "This track names the mechanisms one at a time — how credit card interest actually compounds, what a “free” app is really monetizing, how BNPL and payday lending price the true cost of easy payments, and where advisor incentives quietly diverge from client interest. It ends with a genuinely useful reframe: the people whose spending seems designed to impress others are, more often than not, impressing nobody in particular — the accumulation everyone assumes is happening usually isn't.",
    ),
    "track5-the-debt-trap": (
        "A century ago, financing a purchase on credit was considered shameful. Today it's the default. That shift wasn't an accident of changing values — it was manufactured, deliberately, by companies solving their own sales problem, from the first mass-mailed credit card to the advertising industry's discovery that manufactured desire sells better than need.",
        "This track traces that history: the marketing campaigns that made debt normal, the built-in obsolescence that keeps replacing what still works, and how buy-now-pay-later and influencer culture are simply the latest version of a very old playbook. It also corrects a few widely-repeated myths along the way — about who actually owns homes, and what's really behind housing-wealth concentration — before landing on the point underneath all of it: the real cost of carrying debt you don't need isn't just the interest, it's the freedom it quietly takes off the table.",
    ),
    "track6-stop-the-bleeding": (
        "Before anything else — before investing, before optimizing, before earning more — there's a simpler question: is money leaking out through fees, missed payments, and small recurring costs that don't need to exist? This track is entirely about closing those leaks, the fastest and least glamorous way to improve a financial position.",
        "It covers paying credit cards in full without triggering late fees or losing idle cash to prepayment, a smarter alternative to the usual “highest interest rate first” payoff advice, how big an emergency buffer actually needs to be before more savings stops helping, and the mechanics of credit utilization that most people get slightly wrong. None of it requires earning another dollar — it's just stopping the ones already earned from quietly disappearing.",
    ),
    "track7-free-up-cash-flow": (
        "Once the leaks are closed, the next question is where the money that's already coming in should actually go — not a rigid percentage-based budget copied from somewhere else, but targets built from your own real spending history.",
        "This track covers building a budget around what's a true obligation versus what's a real choice, timing cash against paycheck cycles and due dates so nothing arrives late by accident, right-sizing how much sits in checking versus savings versus investments, and the genuinely useful (and commonly misused) cases for debt consolidation, refinancing, and a HELOC held in reserve rather than spent down. The theme underneath: cash flow that's actually managed on purpose, instead of just reacting to whatever hits the account first.",
    ),
    "track8-build-wealth": (
        "Building wealth has very little to do with picking the right stock and almost everything to do with consistency held over a long enough stretch of time. That's a less exciting story than the one usually sold, but it's the one that's actually true.",
        "This track covers the mechanics that make consistency pay off: automating savings so it happens before spending gets the chance to compete, the order investment accounts should actually be funded in, why an employer 401k match is the one guaranteed high return most people leave unclaimed, and the real evidence on index funds versus active management. It also draws a distinction that matters more than it sounds like it should: getting wealthy and staying wealthy call for almost opposite instincts — optimism to build it, a healthy dose of paranoia to keep it.",
    ),
    "track9-earn-dont-pay": (
        "There's a specific moment worth naming in anyone's financial life: the day the interest, dividends, and rent coming in start to matter more than the interest going out. Everything before that day is about survival and stability; everything after it is about the equation flipping in your favor.",
        "This track covers what it actually looks like once lending starts beating borrowing — high-yield savings, T-bills, and money markets explained without the jargon — plus the assets that pay you directly (dividends, interest, rent) and a simple baseline for credit card rewards that beats chasing points and category bonuses for most people. The underlying move is the same throughout: stop paying to borrow and start getting paid to lend.",
    ),
    "track3-credit-mastery": (
        "A credit score is one of the most consequential numbers in anyone's financial life, and one of the least explained. Most people know roughly what raises or lowers it, but not the actual weighting behind the five factors, or why the common advice — “carry a small balance, it helps your score” — is simply wrong.",
        "This track breaks down exactly how a score is built, the difference between per-card and overall utilization (and why statement timing matters more than most people realize), how to build credit from nothing or rebuild it after damage, and when closing a card actually helps versus quietly hurts. It ends with the specific runway a mortgage application deserves — the twelve months before applying where small, avoidable mistakes do the most damage.",
    ),
    "track10-taxes-efficiency": (
        "Taxes are one of the largest recurring costs in anyone's financial life, and one of the most within a person's own control to reduce — not through anything aggressive, just through sequencing and placement decisions that are easy to get right once someone explains them clearly.",
        "This track covers the difference between the tax bracket a person thinks they're in and the one they're actually paying, which account a given dollar should go into first, how account placement and turnover quietly drag on investment returns, and why a large tax refund is closer to an interest-free loan to the government than a windfall. It closes on the withdrawal order that preserves the most value once money starts coming back out in retirement.",
    ),
    "track11-life-events": (
        "Most of the biggest financial decisions in a person's life don't happen on a schedule — they happen around specific events: a car purchase, a home, a marriage, a new job, a loss. Each one comes with its own traps, most of them well-documented but rarely explained at the moment they'd actually help.",
        "This track walks through the real total cost of owning a car versus what a monthly payment implies, the gap between what a lender approves and what a household can actually afford in a home, merging finances (and visibility) after marriage, what 529s and other education costs actually require, the rollover sales machine that targets a 401k the moment someone changes jobs, and the six-month rule worth following before acting on a windfall or inheritance. The common denominator: these decisions are big enough that a small amount of preparation changes the outcome substantially.",
    ),
    "track12-retirement-decumulation": (
        "Retirement flips the entire financial mindset that got someone there — for decades, the goal was accumulating and staying net-positive; in retirement, spending down is the plan working as intended, not a sign something's gone wrong.",
        "This track covers what that shift actually looks like: thinking in time-buckets rather than a single number, the real cost of over-saving (money that bought no freedom because it was never used), how sequence-of-returns risk changes withdrawal strategy, and the genuinely non-obvious math behind Social Security claiming age. It ends on the highest-return spending decade most people underrate — using both time and money deliberately once there's finally enough of both.",
    ),
    "track13-protection": (
        "Protection is the least exciting part of a financial plan and the part most likely to matter enormously exactly once. The right approach isn't insuring against every possible inconvenience — it's covering the handful of outcomes large enough to actually be catastrophic.",
        "This track covers what's worth insuring against versus what isn't, why the commission structure behind whole life insurance tells you most of what you need to know about who it's really designed for, the fraud and identity threats that have gotten more sophisticated as more of daily life moved online, and the estate basics — beneficiaries, wills, the paperwork nobody enjoys filling out — that determine what actually happens to everything else once it's no longer a person's to manage directly.",
    ),
    "track14-high-wealth-efficiency": (
        "Fees that look small as a percentage stop looking small once there's real money behind them — 1% a year on three million dollars is thirty thousand dollars, every year, and the question worth asking is simple: what, exactly, is being bought for that.",
        "This track covers the actual difference between fee-only, AUM-based, and commission-based advisors and how their incentives diverge, the activity bias that leads some advisors to trade more than a portfolio needs, the layered fees hidden inside structured products, and the tax cost of sitting on a concentrated position out of inertia rather than a decision. It closes on something easy to skip past at this level of wealth: passing on not just money to the next generation, but the visibility and habits that kept it intact.",
    ),
    "track15-when-preparation-isnt-enough": (
        "Job loss, a medical crisis, divorce, disability — by the actual numbers, these are common events, not rare ones, and “it won't happen to me” isn't a plan so much as a bet most people eventually lose at least once. This track exists for what happens after preparation runs out.",
        "It covers sizing a true worst-case gap rather than an optimistic one, the real difference between Chapter 7 and Chapter 13 bankruptcy (and a documented disparity in how filers are steered and treated), negotiating medical debt before it becomes a collections problem, the first ninety days after a job loss, and the early-warning window where acting in week one beats waiting until month six on a foreclosure or eviction. It ends where recovery does — rebuilding credit and re-establishing the visibility habits that make the next crisis, if there is one, easier to see coming.",
    ),
    "volume2-track1-your-built-in-wiring": (
        "Nobody makes money decisions on a blank slate — every one is filtered through wiring built for scarcity and survival, not for managing a 401k across four decades. That wiring isn't a flaw to be ashamed of; it's standard equipment, present in essentially everyone, and it's exploitable mostly by people who've studied it more carefully than their customers have.",
        "This track maps the specific patterns that do most of the damage — loss aversion, present bias, mental accounting, anchoring, the stories that move money faster than statistics do, and the scarcity mindset that narrows decision-making under real pressure rather than reflecting a lack of discipline. It ends with something practical: concrete ways to route around each pattern instead of just knowing it's there.",
    ),
    "volume2-track2-what-money-is-for": (
        "After the mechanics of how money moves and the wiring behind why it gets mismanaged, there's a more personal question left: what any of it is actually for. Spending is rarely just a transaction — it's usually a small statement about identity, whether or not that's ever said out loud.",
        "This track covers what a spending pattern reveals about self-image, the case for spending to satisfy a person's own sense of joy rather than someone else's formula for what's worth having, why time consistently outperforms luxury as a return on money spent, and “enough” — arguably the hardest concept in personal finance to define, and the one that determines when the rest of it stops being about accumulation and starts being about living.",
    ),
}

# One simple line-icon per track (24x24 viewBox, stroke-only, inherits color
# via `currentColor` -- no per-track color, just a per-track silhouette).
# Shown at ~16px in the chapter-card badge on each track's index page, so
# each is a single recognizable shape, not a detailed illustration.
TRACK_ICON_PATHS: dict[str, str] = {
    "track1-language-of-money": '<rect x="4" y="5" width="16" height="12" rx="2"/><path d="M9 17l-2 3v-3"/>',
    "track2-visibility": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    "track3-credit-mastery": '<rect x="3" y="6" width="18" height="12" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/>',
    "track4-extraction-economy": '<path d="M12 3c-3 4-5 7-5 10a5 5 0 0010 0c0-3-2-6-5-10z"/>',
    "track5-the-debt-trap": '<rect x="2" y="7" width="11" height="10" rx="5"/><rect x="11" y="7" width="11" height="10" rx="5"/>',
    "track6-stop-the-bleeding": '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
    "track7-free-up-cash-flow": '<path d="M2 13c2-3 4-3 6 0s4 3 6 0 4-3 6 0"/>',
    "track8-build-wealth": '<line x1="5" y1="20" x2="5" y2="14"/><line x1="12" y1="20" x2="12" y2="9"/><line x1="19" y1="20" x2="19" y2="4"/>',
    "track9-earn-dont-pay": '<circle cx="12" cy="12" r="9"/><path d="M12 7v10M9.5 9.7c0-1.5 1.1-2.7 2.5-2.7s2.5 1 2.5 2.1-1 1.9-2.5 1.9-2.5 1-2.5 2.1 1.1 2.1 2.5 2.1 2.5-1.2 2.5-2.7"/>',
    "track10-taxes-efficiency": '<circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/><line x1="5" y1="19" x2="19" y2="5"/>',
    "track11-life-events": '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/>',
    "track12-retirement-decumulation": '<path d="M6 3h12M6 21h12M7 3c0 5 5 7 5 9s-5 4-5 9M17 3c0 5-5 7-5 9s5 4 5 9"/>',
    "track13-protection": '<path d="M12 3l7 3v6c0 5-3 8-7 9-4-1-7-4-7-9V6l7-3z"/>',
    "track14-high-wealth-efficiency": '<path d="M6 9l6-6 6 6-6 12z"/><path d="M6 9h12M9 9l3 12M15 9l-3 12"/>',
    "track15-when-preparation-isnt-enough": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><line x1="12" y1="3" x2="12" y2="8"/><line x1="12" y1="16" x2="12" y2="21"/><line x1="3" y1="12" x2="8" y2="12"/><line x1="16" y1="12" x2="21" y2="12"/>',
    "volume2-track1-your-built-in-wiring": '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M6 8v3c0 2 2 3 6 3M18 8v3c0 2-2 3-6 3"/>',
    "volume2-track2-what-money-is-for": '<circle cx="12" cy="12" r="9"/><path d="M14.5 9.5l-1.2 4.3-4.3 1.2 1.2-4.3z"/>',
}


def render_track_icon(track_slug: str, size: int = 16) -> str:
    inner = TRACK_ICON_PATHS.get(track_slug)
    if inner is None:
        return ""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{inner}</svg>'
    )


CHAPTER_SPLIT_RE = re.compile(r"^#\s*Chapter\s+(\S+)\s*—\s*(.+)$", re.MULTILINE)
SUBHEAD_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
TOKEN_RE = re.compile(r"\{\{ref:([A-Za-z0-9.]+)\}\}")
FOOTNOTE_MARKER_RE = re.compile(r"\[\^([A-Za-z0-9.\-]+)\]")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([A-Za-z0-9.\-]+)\]:\s*(.+)$", re.MULTILINE)

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
.nav-toggle { display: none; background: none; border: none; color: #fff; cursor: pointer; padding: 8px; align-items: center; justify-content: center; }

footer { background: var(--navy); border-top: 1px solid rgba(255,255,255,.07); padding: 32px 48px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
footer p { color: #2E4A60; font-size: 13px; }
.fl a { color: #2E4A60; font-size: 13px; text-decoration: none; margin-left: 24px; transition: color .2s; }
.fl a:hover { color: var(--teal); }

#disclaimer-strip { background: var(--off); border-top: 1px solid var(--border); padding: 16px 48px; text-align: center; }
#disclaimer-strip p { font-size: 12px; color: var(--light); line-height: 1.6; max-width: 900px; margin: 0 auto; }

@media (max-width: 768px) {
  nav { padding: 0 20px; height: 56px; }
  .nav-toggle { display: flex; }
  .nav-links { display: none; position: absolute; top: 100%; left: 0; right: 0; flex-direction: column; align-items: stretch; gap: 0; background: #0C1929; border-bottom: 1px solid rgba(255,255,255,.08); padding: 4px 20px 10px; }
  .nav-links.open { display: flex; }
  .nav-links a { padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,.06); font-size: 12px; white-space: nowrap; }
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
.chapter-wrap h1 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(28px,4vw,42px); font-weight: 700; color: var(--navy); letter-spacing: -.8px; line-height: 1.2; margin-bottom: 14px; }
.chapter-title-subtitle { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(16px,2vw,20px); font-weight: 400; color: var(--muted); line-height: 1.35; margin-bottom: 14px; }
.chapter-accent { width: 56px; height: 3px; border-radius: 2px; background: var(--teal); margin-bottom: 28px; }

.jump-list { background: var(--off); border: 1.5px solid var(--border); border-radius: 14px; padding: 22px 26px; margin-bottom: 44px; }
.jump-list .jl-title { font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--teal); margin-bottom: 12px; }
.jump-list ol { padding-left: 18px; }
.jump-list li { margin-bottom: 6px; }
.jump-list a { color: var(--muted); text-decoration: none; font-size: 14px; transition: color .2s; }
.jump-list a:hover { color: var(--teal); }

.chapter-body h2 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(20px,2.5vw,26px); font-weight: 700; color: var(--navy); letter-spacing: -.3px; line-height: 1.3; margin: 44px 0 6px; }
.subhead-accent { width: 200px; height: 1px; background: var(--orange); margin-bottom: 20px; }
.chapter-body p { font-size: 16px; color: var(--muted); line-height: 1.85; margin-bottom: 20px; }
.chapter-body p strong { color: var(--text); font-weight: 700; }
.chapter-body p em { color: var(--text); font-style: italic; }
.chapter-body sup { font-size: 11px; margin-left: 1px; }
.chapter-body sup a { color: var(--teal-d); text-decoration: none; font-weight: 700; }
.chapter-body sup a:hover { text-decoration: underline; }
a.ref-link { color: var(--teal-d); font-weight: 400; text-decoration: none; }
a.ref-link:hover { text-decoration: underline; }

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
.track-wrap { max-width: 720px; margin: 0 auto; padding: 56px 48px 88px; }
.chapter-grid { display: flex; flex-direction: column; gap: 14px; }
.chap-card { display: flex; gap: 20px; align-items: flex-start; border: 1.5px solid var(--border); border-radius: 16px; padding: 24px 26px; text-decoration: none; transition: border-color .2s, transform .2s, box-shadow .2s; }
.chap-card:hover { border-color: var(--teal); transform: translateY(-2px); box-shadow: 0 10px 30px rgba(12,25,41,.07); }
.chap-num { flex-shrink: 0; width: 48px; height: 52px; border-radius: 12px; background: var(--teal-l); color: var(--teal-d); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; }
.chap-num .cn-icon { line-height: 0; }
.chap-num .cn-digits { font-family: Georgia, serif; font-weight: 700; font-size: 13px; }
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
.track-search-wrap { max-width: 720px; margin: 32px auto 0; padding: 0 48px; }
.track-search-wrap .academy-search-wrap { padding: 0; max-width: none; }

/* ─── OVERVIEW (landing page + track index pages) ─── */
.overview-wrap { max-width: 720px; margin: 0 auto; padding: 32px 48px 8px; }
.overview-wrap p { font-size: 16px; color: var(--muted); line-height: 1.75; margin-bottom: 18px; }
.overview-wrap p:last-child { margin-bottom: 0; }

/* ─── DATA CHART (ACADEMY_PUBLISHING_INSTRUCTIONS.md §8a) ─── */
.data-chart { max-width: 720px; margin: 40px auto; padding: 0 48px; }
.dc-headline { font-family: Georgia, 'Times New Roman', serif; font-size: 36px; font-weight: 700; color: var(--navy); letter-spacing: -.5px; }
.dc-subtitle { font-size: 13px; color: var(--muted); margin-top: 4px; margin-bottom: 20px; }
.dc-divider { border-top: 1px solid var(--border); margin: 16px 0; }
.dc-rows { display: flex; flex-direction: column; gap: 16px; }
.dc-row-top { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 2px 12px; margin-bottom: 6px; }
.dc-row-label { font-size: 14px; color: var(--navy); }
.dc-row-value { font-size: 14px; font-weight: 700; color: var(--navy); font-variant-numeric: tabular-nums; white-space: nowrap; }
.dc-bar-track { height: 10px; border-radius: 5px; overflow: hidden; }
.dc-bar-track.teal { background: var(--teal-l); }
.dc-bar-track.orange { background: var(--orange-l); }
.dc-bar-fill { height: 100%; border-radius: 5px; }
.dc-bar-fill.teal { background: var(--teal); }
.dc-bar-fill.orange { background: var(--orange); }
.dc-legend { display: flex; flex-wrap: wrap; gap: 10px 20px; margin-top: 4px; }
.dc-legend-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); }
.dc-swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
.dc-swatch.teal { background: var(--teal); }
.dc-swatch.orange { background: var(--orange); }
.dc-caption { font-size: 12px; color: var(--light); margin-top: 18px; line-height: 1.6; }

/* ─── SHARED CONCEPT DIAGRAM (ACADEMY_PUBLISHING_INSTRUCTIONS.md §8b) ─── */
.concept-diagram { max-width: 720px; margin: 32px auto; padding: 0 48px; }
.concept-diagram svg { width: 100%; height: auto; display: block; }
.cd-caption { font-size: 12px; color: var(--light); text-align: center; margin-top: 12px; }

/* ─── ACADEMY LANDING PAGE ─── */
.academy-pullquote { text-align: center; font-family: Georgia, 'Times New Roman', serif; font-style: italic; font-size: 19px; color: var(--navy); max-width: 560px; margin: 28px auto 0; padding: 0 48px; line-height: 1.5; }
.volume-section { margin-top: 56px; }
.volume-h2 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(22px,3vw,30px); font-weight: 700; color: var(--navy); letter-spacing: -.4px; margin-bottom: 8px; }
.volume-sub { color: var(--muted); font-size: 15px; margin-bottom: 24px; max-width: 640px; }
.track-grid { display: flex; flex-direction: column; gap: 14px; }
.track-card { display: flex; gap: 20px; align-items: flex-start; border: 1.5px solid var(--border); border-radius: 16px; padding: 24px 26px; text-decoration: none; transition: border-color .2s, transform .2s, box-shadow .2s; }
.track-card:hover { border-color: var(--teal); transform: translateY(-2px); box-shadow: 0 10px 30px rgba(12,25,41,.07); }
.track-num { flex-shrink: 0; width: 56px; height: 56px; border-radius: 12px; background: var(--teal-l); color: var(--teal-d); display: flex; align-items: center; justify-content: center; font-family: Georgia, serif; font-weight: 700; font-size: 17px; }
.track-info h3 { font-size: 18px; color: var(--navy); font-weight: 700; margin-bottom: 6px; line-height: 1.35; }
.track-info p { font-size: 14px; color: var(--muted); line-height: 1.55; }

@media (max-width: 768px) {
  .academy-pullquote { padding: 0 20px; }
  .page-header { padding: 44px 20px 36px; }
  .crumb { padding: 0 20px; }
  .chapter-wrap { padding: 32px 20px 16px; }
  .chapter-nav { grid-template-columns: 1fr; padding: 8px 20px 48px; }
  .cn-link.next { text-align: left; }
  .track-wrap { padding: 40px 20px 64px; }
  .academy-search-wrap { padding: 0 20px; }
  .track-search-wrap { padding: 0 20px; }
  .overview-wrap { padding: 24px 20px 8px; }
  .data-chart { padding: 0 20px; }
  .concept-diagram { padding: 0 20px; }
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
  <a href="{root}index.html" class="nav-logo">
    <img src="{root}Logo%20-%20Plenee_Navigator_v2.svg" alt="Plenee Navigator">
  </a>
  <div class="nav-links" id="nav-links">
    <a href="{root}index.html#how">How it works</a>
    <a href="{root}index.html#features-start">Features</a>
    <a href="{ac_root}index.html" class="active">Academy</a>
    <a href="{root}index.html#fid">Our Promise</a>
  </div>
  <button class="nav-toggle" id="nav-toggle" aria-label="Menu" aria-expanded="false" aria-controls="nav-links">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  </button>
</nav>
<script>
(function(){{
  var toggle = document.getElementById('nav-toggle');
  var links = document.getElementById('nav-links');
  if (!toggle || !links) return;
  toggle.addEventListener('click', function(){{
    var open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }});
  links.querySelectorAll('a').forEach(function(a){{
    a.addEventListener('click', function(){{
      links.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }});
  }});
}})();
</script>

{body}

<div id="disclaimer-strip">
  <p>Plenee Academy provides financial information and education, not personalized financial advice. Plenee Co. is not a registered investment adviser, broker-dealer, or financial planner. <a href="{root}plenee_legal.html">Legal Disclosures &amp; Notices →</a></p>
</div>

<footer>
  <a href="{root}index.html" style="display:block;line-height:0">
    <img src="{root}Logo%20-%20Plenee_Navigator_v2.svg" height="44" alt="Plenee Navigator">
  </a>
  <p>© 2026 Plenee Co. All rights reserved.</p>
  <div class="fl"><a href="{root}privacy.html">Privacy</a><a href="{root}terms.html">Terms</a><a href="{root}plenee_legal.html" style="color:var(--teal)">Legal</a><a href="{root}contact.html">Contact</a></div>
</footer>

</body>
</html>
"""

# Nesting-depth prefixes for PAGE_TEMPLATE's {root}/{ac_root}: chapter and track
# pages live 2 levels under the site root (academy/<track>/*.html); the Academy
# landing page lives 1 level under it (academy/index.html).
DEPTH_CHAPTER_OR_TRACK = {"root": "../../", "ac_root": "../"}
DEPTH_LANDING = {"root": "../", "ac_root": ""}


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

        def _ref_sub(m: re.Match, _text=p_html) -> str:
            token_id = m.group(1)
            resolved = resolve_token(token_id, track_slug, idx)
            if resolved is None:
                return m.group(0)
            url, default_text = resolved
            link_text = dedupe_leading_article(_text[: m.start()], default_text)
            return f'<a class="ref-link" href="{esc(url)}">{esc(link_text)}</a>'

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


def render_data_chart(headline: str, subtitle: str, rows: list[dict],
                       legend: list[tuple[str, str]], caption: str) -> str:
    """Reusable "data chart" component per ACADEMY_PUBLISHING_INSTRUCTIONS.md §8a:
    a big headline figure, horizontal label/value rows over slim bars (largest
    bar = 100% of track width), and a <=2-color legend where color encodes
    meaning (teal = avoidable through behavior, orange = predatory/structural),
    never sequence. Pure HTML/CSS -- no chart library, no JS. `rows` is a list
    of {"label", "value", "fraction" (0-1, relative to the largest row),
    "color": "teal"|"orange"}. `caption` is the accessible text alternative."""
    row_html = "\n".join(
        '    <div class="dc-row">\n'
        f'      <div class="dc-row-top"><span class="dc-row-label">{esc(r["label"])}</span>'
        f'<span class="dc-row-value">{esc(r["value"])}</span></div>\n'
        f'      <div class="dc-bar-track {r["color"]}"><div class="dc-bar-fill {r["color"]}" '
        f'style="width:{r["fraction"] * 100:.0f}%"></div></div>\n'
        "    </div>"
        for r in rows
    )
    legend_html = "\n".join(
        f'    <div class="dc-legend-item"><span class="dc-swatch {color}"></span>{esc(text)}</div>'
        for color, text in legend
    )
    return (
        '<figure class="data-chart">\n'
        f"  <div class=\"dc-headline\">{esc(headline)}</div>\n"
        f'  <div class="dc-subtitle">{esc(subtitle)}</div>\n'
        '  <div class="dc-divider"></div>\n'
        f'  <div class="dc-rows">\n{row_html}\n  </div>\n'
        '  <div class="dc-divider"></div>\n'
        f'  <div class="dc-legend">\n{legend_html}\n  </div>\n'
        f'  <figcaption class="dc-caption">{esc(caption)}</figcaption>\n'
        "</figure>"
    )


# Pilot chart -- Chapter 4.1's own verified figures (see that chapter's Sources:
# [^4.1-1] thru [^4.1-5]). $160B/$17B/$12B are independently sourced; the $41B
# "remainder" is arithmetic (230 - 160 - 17 - 12), not a separately-cited total --
# labeled honestly as an estimate per ACADEMY_PUBLISHING_INSTRUCTIONS.md §8a.
EXTRACTION_CHART_HTML = render_data_chart(
    headline="~$230B",
    subtitle="a year, extracted through inattention — not honest interest",
    rows=[
        {"label": "Revolving credit-card interest", "value": "$160B · 70%", "fraction": 160 / 160, "color": "teal"},
        {"label": "Other predatory lending & fees (remainder, est.)", "value": "$41B · 18%", "fraction": 41 / 160, "color": "orange"},
        {"label": "Card late fees", "value": "$17B · 7%", "fraction": 17 / 160, "color": "teal"},
        {"label": "Overdraft fees", "value": "$12B · 5%", "fraction": 12 / 160, "color": "teal"},
    ],
    legend=[
        ("teal", "avoidable through behavior — pay in full, on time, keep a buffer"),
        ("orange", "predatory/structural — priced beyond any honest cost of risk"),
    ],
    caption="Of the roughly $230 billion a year in extraction: $160B is avoidable "
            "credit-card interest, an estimated $41B is predatory lending and account "
            "fees not separately itemized here, $17B is late fees, and $12B is overdraft fees.",
)

# Chapter 5.7's own verified figures (see footnotes 5.7-6, 5.7-7): no
# avoidable/predatory distinction applies here (it's a trend, not a
# decomposition), so both rows use teal per §8a's "no distinction -> teal
# alone" fallback.
NEGATIVE_EQUITY_CHART_HTML = render_data_chart(
    headline="31%",
    subtitle="of vehicle trade-ins now carry negative equity into a new loan — near an all-time high",
    rows=[
        {"label": "2018–2022 average (CFPB, trade-in basis)", "value": "~27%", "fraction": 27 / 31, "color": "teal"},
        {"label": "Most recent data (Edmunds, Q1 2026)", "value": "31%", "fraction": 31 / 31, "color": "teal"},
    ],
    legend=[("teal", "share of vehicle trade-ins carrying negative equity into the next loan")],
    caption="Negative equity on vehicle trade-ins has climbed from roughly 27% in "
            "2018–2022 (CFPB, recalculated to a comparable trade-in basis) to about "
            "31% in the most recent data (Edmunds, Q1 2026) — averaging $7,183 per "
            "affected loan, with roughly double the two-year repossession risk of a "
            "positive-equity trade-in.",
)

# Chapter 5.8's own verified figures (footnote 5.8-1). Single color again --
# this is a recovery trend, not an avoidable/predatory split.
OWNERS_EQUITY_CHART_HTML = render_data_chart(
    headline="71.6%",
    subtitle="of home value is now owner equity — the highest sustained share in over a decade",
    rows=[
        {"label": "2026 (current)", "value": "71.6%", "fraction": 71.6 / 71.6, "color": "teal"},
        {"label": "2009 (post-crash trough)", "value": "~37%", "fraction": 37 / 71.6, "color": "teal"},
    ],
    legend=[("teal", "owners' equity as a share of total home value")],
    caption="Homeowners' equity share of total home value collapsed to roughly 37% "
            "at the bottom of the 2008 crash and has since recovered to 71.6% as of "
            "early 2026 — the highest sustained level in over a decade.",
)

# Chapter 8.5's own verified figures (footnotes 8.5-1, 8.5-2). Two independent
# SPIVA/Persistence Scorecard stats, not parts of one total -- still teal
# alone, no avoidable/predatory distinction applies.
SPIVA_CHART_HTML = render_data_chart(
    headline="85–95%",
    subtitle="of actively managed US equity funds trailed their benchmark over 10–20 years",
    rows=[
        {"label": "Active funds underperforming their benchmark (10–20yr)", "value": "85–95%", "fraction": 1.0, "color": "teal"},
        {"label": "Top-quartile funds still top-quartile 5 years later", "value": "0%", "fraction": 0.0, "color": "teal"},
    ],
    legend=[("teal", "S&P Dow Jones Indices — SPIVA / Persistence Scorecard")],
    caption="S&P's SPIVA scorecards find 85–95% of actively managed US equity funds "
            "underperformed their benchmark over 10, 15, and 20-year periods; "
            "separately, its Persistence Scorecard found 0% of large-cap funds "
            "ranking top-quartile in 2021 stayed top-quartile five years later — "
            "worse than random chance would produce.",
)

# Maps a chapter id to (heading to insert after, lowercased; graphic html). The
# heading match is case-insensitive against the chapter's own "## Heading" text.
CHAPTER_GRAPHICS: dict[str, tuple[str, str]] = {
    "4.1": ("the avoidable layer", EXTRACTION_CHART_HTML),
    "5.7": ("the car version: rolling backward before you've moved forward", NEGATIVE_EQUITY_CHART_HTML),
    "5.8": ("the claim, and the honest version of it", OWNERS_EQUITY_CHART_HTML),
    "8.5": ("why the pros lose to the average", SPIVA_CHART_HTML),
}

# Pilot diagram -- ACADEMY_PUBLISHING_INSTRUCTIONS.md §8b's "The Flywheel": the
# 4-stage arc Tracks 6-9 walk through, in a reusable inline SVG (brand palette,
# flat fills, no gradients). Single color ramp (teal) + navy + gray per the
# "<=2 color ramps" rule -- sequence is shown by the numbered badges, not color.
FLYWHEEL_DIAGRAM_HTML = """<figure class="concept-diagram">
<svg viewBox="0 0 520 400" role="img" aria-label="The Flywheel: four stages in sequence -- Stop the Bleeding, Free Up Cash Flow, Build Wealth, and Earn, Don't Pay -- then back to Stop the Bleeding.">
  <defs>
    <marker id="fw-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--teal)"/>
    </marker>
  </defs>
  <path d="M 220 55 Q 260 40 300 55" fill="none" stroke="var(--teal)" stroke-width="3" marker-end="url(#fw-arrow)"/>
  <path d="M 400 90 Q 415 200 400 310" fill="none" stroke="var(--teal)" stroke-width="3" marker-end="url(#fw-arrow)"/>
  <path d="M 300 345 Q 260 360 220 345" fill="none" stroke="var(--teal)" stroke-width="3" marker-end="url(#fw-arrow)"/>
  <path d="M 120 310 Q 105 200 120 90" fill="none" stroke="var(--teal)" stroke-width="3" marker-end="url(#fw-arrow)"/>

  <rect x="20" y="20" width="200" height="70" rx="14" fill="var(--teal-l)"/>
  <circle cx="34" cy="34" r="14" fill="var(--navy)"/>
  <text x="34" y="39" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="14" fill="var(--white)">1</text>
  <text x="120" y="60" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="16" fill="var(--teal-d)">Stop the</text>
  <text x="120" y="80" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="16" fill="var(--teal-d)">Bleeding</text>

  <rect x="300" y="20" width="200" height="70" rx="14" fill="var(--teal-l)"/>
  <circle cx="314" cy="34" r="14" fill="var(--navy)"/>
  <text x="314" y="39" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="14" fill="var(--white)">2</text>
  <text x="400" y="55" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="15" fill="var(--teal-d)">Free Up</text>
  <text x="400" y="75" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="15" fill="var(--teal-d)">Cash Flow</text>

  <rect x="300" y="310" width="200" height="70" rx="14" fill="var(--teal-l)"/>
  <circle cx="314" cy="324" r="14" fill="var(--navy)"/>
  <text x="314" y="329" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="14" fill="var(--white)">3</text>
  <text x="400" y="352" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="16" fill="var(--teal-d)">Build Wealth</text>

  <rect x="20" y="310" width="200" height="70" rx="14" fill="var(--teal-l)"/>
  <circle cx="34" cy="324" r="14" fill="var(--navy)"/>
  <text x="34" y="329" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="14" fill="var(--white)">4</text>
  <text x="120" y="345" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="15" fill="var(--teal-d)">Earn,</text>
  <text x="120" y="365" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="15" fill="var(--teal-d)">Don't Pay</text>
</svg>
<figcaption class="cd-caption">Four stages, in order — stop the bleeding, free up cash flow, build wealth, earn instead of pay — then the cycle repeats.</figcaption>
</figure>"""

# Maps a track_slug to a diagram shown on that track's own index page --
# every track in the 4-stage Flywheel arc gets the same shared diagram.
TRACK_GRAPHICS: dict[str, str] = {
    "track6-stop-the-bleeding": FLYWHEEL_DIAGRAM_HTML,
    "track7-free-up-cash-flow": FLYWHEEL_DIAGRAM_HTML,
    "track8-build-wealth": FLYWHEEL_DIAGRAM_HTML,
    "track9-earn-dont-pay": FLYWHEEL_DIAGRAM_HTML,
}

# Shared diagram #2 -- the statement-cycle timeline (closing date -> statement
# balance -> grace period -> due date), used by every chapter that discusses
# grace periods or statement timing.
STATEMENT_CYCLE_DIAGRAM_HTML = """<figure class="concept-diagram">
<svg viewBox="0 0 600 170" role="img" aria-label="Statement-cycle timeline: the statement closes and sets your balance, then a grace period runs until the payment due date -- pay in full by then and no interest accrues.">
  <defs>
    <marker id="sc-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--border)"/>
    </marker>
  </defs>
  <line x1="30" y1="85" x2="570" y2="85" stroke="var(--border)" stroke-width="2" marker-end="url(#sc-arrow)"/>
  <rect x="130" y="75" width="340" height="20" rx="10" fill="var(--teal-l)"/>
  <circle cx="130" cy="85" r="8" fill="var(--teal)"/>
  <circle cx="470" cy="85" r="8" fill="var(--navy)"/>
  <text x="130" y="55" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="14" fill="var(--navy)">Statement Closes</text>
  <text x="130" y="128" text-anchor="middle" font-size="12" fill="var(--muted)">Balance is set</text>
  <text x="300" y="70" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="13" fill="var(--teal-d)">Grace Period</text>
  <text x="300" y="128" text-anchor="middle" font-size="12" fill="var(--muted)">No interest if paid in full</text>
  <text x="470" y="55" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="14" fill="var(--navy)">Payment Due</text>
  <text x="470" y="128" text-anchor="middle" font-size="12" fill="var(--muted)">Pay in full here</text>
</svg>
<figcaption class="cd-caption">The statement-cycle timeline: closing date sets the balance, a grace period follows, and paying in full by the due date is what keeps interest at zero.</figcaption>
</figure>"""

# Shared diagram #3 -- how FLOW, NET, and NEST connect (Track 1's own
# vocabulary): FLOW is money moving in a period, NET is whether that period
# came out ahead, NEST is the cumulative total across every period.
FLOW_NET_NEST_DIAGRAM_HTML = """<figure class="concept-diagram">
<svg viewBox="0 0 600 190" role="img" aria-label="How FLOW, NET, and NEST connect: FLOW is money moving in a period, NET is whether that period ended positive or negative, and NEST is the cumulative total across every period.">
  <defs>
    <marker id="fnn-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--teal)"/>
    </marker>
  </defs>
  <path d="M185 95 L223 95" fill="none" stroke="var(--teal)" stroke-width="3" marker-end="url(#fnn-arrow)"/>
  <path d="M395 95 L433 95" fill="none" stroke="var(--teal)" stroke-width="3" marker-end="url(#fnn-arrow)"/>
  <rect x="20" y="60" width="165" height="70" rx="14" fill="var(--teal-l)"/>
  <text x="102" y="103" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="20" fill="var(--teal-d)">FLOW</text>
  <rect x="230" y="60" width="165" height="70" rx="14" fill="var(--teal-l)"/>
  <text x="312" y="103" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="20" fill="var(--teal-d)">NET</text>
  <rect x="440" y="60" width="140" height="70" rx="14" fill="var(--teal-l)"/>
  <text x="510" y="103" text-anchor="middle" font-family="Georgia, serif" font-weight="700" font-size="20" fill="var(--teal-d)">NEST</text>
  <text x="102" y="150" text-anchor="middle" font-size="13" fill="var(--muted)">Money moving in</text>
  <text x="102" y="167" text-anchor="middle" font-size="13" fill="var(--muted)">a given period</text>
  <text x="312" y="150" text-anchor="middle" font-size="13" fill="var(--muted)">Did that period end</text>
  <text x="312" y="167" text-anchor="middle" font-size="13" fill="var(--muted)">positive or negative?</text>
  <text x="510" y="150" text-anchor="middle" font-size="13" fill="var(--muted)">The cumulative total,</text>
  <text x="510" y="167" text-anchor="middle" font-size="13" fill="var(--muted)">every period combined</text>
</svg>
<figcaption class="cd-caption">FLOW is money moving in a period; NET is whether that period came out ahead; NEST is the running total every period builds toward.</figcaption>
</figure>"""

# Shared diagram #4 -- credit utilization mechanics: balance divided by
# limit, snapshotted at the moment the statement closes.
UTILIZATION_DIAGRAM_HTML = """<figure class="concept-diagram">
<svg viewBox="0 0 600 175" role="img" aria-label="Credit utilization: your balance divided by your limit, snapshotted at the moment your statement closes. Example: a $3,000 balance against a $10,000 limit is 30% utilization.">
  <text x="20" y="28" font-family="Georgia, serif" font-weight="700" font-size="15" fill="var(--navy)">Credit Limit: $10,000</text>
  <rect x="20" y="42" width="560" height="22" rx="11" fill="var(--border)"/>
  <rect x="20" y="42" width="168" height="22" rx="11" fill="var(--teal)"/>
  <text x="20" y="92" font-family="Georgia, serif" font-weight="700" font-size="15" fill="var(--navy)">Balance at Statement Close: $3,000</text>
  <text x="20" y="124" font-size="14" fill="var(--muted)">Utilization = $3,000 ÷ $10,000 =</text>
  <text x="255" y="124" font-family="Georgia, serif" font-weight="700" font-size="16" fill="var(--teal-d)">30%</text>
  <text x="20" y="155" font-size="12" fill="var(--light)">This snapshot -- not what you pay off later -- is what gets reported to the bureaus.</text>
</svg>
<figcaption class="cd-caption">Utilization is balance divided by limit, measured at the moment your statement closes -- paying down the balance the next day doesn't change what already got reported.</figcaption>
</figure>"""

# Extends CHAPTER_GRAPHICS with the 3 diagrams above, placed in the chapters
# that actually discuss each concept (checked against each chapter's own
# content, not assumed from stale pre-reorg numbering).
CHAPTER_GRAPHICS_DIAGRAMS: dict[str, tuple[str, str]] = {
    "4.3": ("second mechanic: the grace period is conditional", STATEMENT_CYCLE_DIAGRAM_HTML),
    "6.1": ("why \"on the due date\" — the float you're donating", STATEMENT_CYCLE_DIAGRAM_HTML),
    "1.4": ("one number, built from the whole map", FLOW_NET_NEST_DIAGRAM_HTML),
    "3.2": ("dial two: the snapshot, and when the camera clicks", UTILIZATION_DIAGRAM_HTML),
    "6.7": ("mechanic three: the denominator", UTILIZATION_DIAGRAM_HTML),
}
CHAPTER_GRAPHICS.update(CHAPTER_GRAPHICS_DIAGRAMS)


def render_chapter_page(chapter: dict, chapter_index: int, all_chapters: list[dict],
                         track_info, track_title: str, track_slug: str, idx) -> tuple[str, dict]:
    sections, takeaway, footnote_defs = split_sections(chapter["raw"])

    footnote_order = list(footnote_defs.keys())  # dict preserves insertion order (definition order)
    footnote_numbers = {label: i + 1 for i, label in enumerate(footnote_order)}

    title_parts = chapter["title"].split(":", 1)
    title_headline = esc(title_parts[0].strip())
    title_subtitle_html = (
        f'\n  <p class="chapter-title-subtitle">{esc(title_parts[1].strip())}</p>'
        if len(title_parts) > 1 else ""
    )

    jump_items = []
    body_html_parts = []
    search_text_parts = []
    for heading, body in sections:
        hid = slugify_title(heading)
        jump_items.append(f'<li><a href="#{hid}">{esc(heading)}</a></li>')
        body_html_parts.append(f'<h2 id="{hid}">{esc(heading)}</h2>')
        body_html_parts.append('<div class="subhead-accent"></div>')
        section_html = render_paragraphs(body, footnote_numbers, track_slug, idx)
        body_html_parts.append(section_html)
        search_text_parts.append(strip_tags(section_html))

        graphic = CHAPTER_GRAPHICS.get(chapter["id"])
        if graphic and graphic[0] == heading.strip().lower():
            body_html_parts.append(graphic[1])

    chapter_body_html = "\n".join(body_html_parts)

    takeaway_html = ""
    if takeaway:
        takeaway_body_html = render_paragraphs(takeaway, footnote_numbers, track_slug, idx)
        search_text_parts.append(strip_tags(takeaway_body_html))
        takeaway_html = (
            '\n  <div class="takeaway">\n'
            '      <div class="tk-label">The takeaway</div>\n'
            '      <div class="subhead-accent"></div>\n'
            f"      {takeaway_body_html}\n"
            "    </div>"
        )

    sources_html = ""
    if footnote_defs:
        items = []
        for label in footnote_order:
            num = footnote_numbers[label]
            def_html = inline_markdown(footnote_defs[label])

            def _def_ref_sub(m: re.Match, _text=def_html) -> str:
                resolved = resolve_token(m.group(1), track_slug, idx)
                if resolved is None:
                    return m.group(0)
                url, default_text = resolved
                link_text = dedupe_leading_article(_text[: m.start()], default_text)
                return f'<a class="ref-link" href="{esc(url)}">{esc(link_text)}</a>'

            def_html = TOKEN_RE.sub(_def_ref_sub, def_html)
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
  <div class="chapter-eyebrow">Volume {track_info.volume} · T.{track_info.display_num} · Chapter {esc(display_chapter_id(chapter["id"]))}</div>
  <h1>{title_headline}</h1>{title_subtitle_html}
  <div class="chapter-accent"></div>
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

    page_html = PAGE_TEMPLATE.format(page_title=esc(chapter["title"]), style=STYLE_BLOCK, body=body,
                                      **DEPTH_CHAPTER_OR_TRACK)

    search_entry = {
        "t": chapter["title"],
        "trk": f"Volume {track_info.volume} · {track_title}",
        "n": f'Chapter {display_chapter_id(chapter["id"])}',
        "u": f'{track_slug}/{chapter["slug"]}.html',
        "x": " ".join(search_text_parts).strip()[:SEARCH_SNIPPET_CAP],
    }
    return page_html, search_entry


def overview_html(paragraphs: tuple[str, str]) -> str:
    paras = "\n".join(f"  <p>{esc(p)}</p>" for p in paragraphs)
    return f'<div class="overview-wrap">\n{paras}\n</div>'


def render_index_page(track_info, track_title: str, chapters: list[dict], search_index: list[dict]) -> str:
    cards = []
    for c in chapters:
        title_parts = c["title"].split(":", 1)
        headline = esc(title_parts[0].strip())
        subtitle_html = (
            f'\n      <p class="chap-subtitle">{esc(title_parts[1].strip())}</p>'
            if len(title_parts) > 1 else ""
        )
        cards.append(
            f'  <a class="chap-card" href="{c["slug"]}.html">\n'
            '    <div class="chap-num">'
            f'<span class="cn-icon">{render_track_icon(track_info.track_slug)}</span>'
            f'<span class="cn-digits">{esc(display_chapter_id(c["id"]))}</span></div>\n'
            '    <div class="chap-info">\n'
            f'      <h3>{headline}</h3>{subtitle_html}\n'
            "    </div>\n"
            "  </a>"
        )

    search_json = json.dumps(search_index, ensure_ascii=False).replace("</script", "<\\/script")

    body = f"""<div class="page-header">
  <div class="page-kicker">Volume {track_info.volume} · T.{track_info.display_num}</div>
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

{overview_html(TRACK_OVERVIEWS[track_info.track_slug])}

{TRACK_GRAPHICS.get(track_info.track_slug, "")}

<div class="track-wrap">
  <div class="chapter-grid">
{chr(10).join(cards)}
  </div>
</div>

<script type="application/json" id="academy-search-data">{search_json}</script>
<script>{SEARCH_JS}</script>"""

    return PAGE_TEMPLATE.format(page_title=esc(track_title), style=STYLE_BLOCK, body=body,
                                 **DEPTH_CHAPTER_OR_TRACK)


def parse_curriculum_track_order(idx) -> list:
    """Reading order + volume grouping, discovered from academy_curriculum.md
    at generation time (never hardcoded here -- ACADEMY_PUBLISHING_INSTRUCTIONS.md
    §6 explicitly warns this order has changed twice in one day already).
    Returns a list of TrackInfo in reading order (Volume 1 tracks, then Volume 2)."""
    text = CURRICULUM_PATH.read_text(encoding="utf-8")
    v2_marker = VOLUME2_MARKER_RE.search(text)
    v1_text, v2_text = (text[: v2_marker.start()], text[v2_marker.start():]) if v2_marker else (text, "")

    v1_nums = TRACK_HEADER_RE.findall(v1_text)
    v2_nums = TRACK_HEADER_RE.findall(v2_text)

    by_volume2_num = {t.display_num: t for t in idx.tracks_by_slug.values() if t.volume == 2}

    order = [idx.tracks[num] for num in v1_nums]
    order += [by_volume2_num[num] for num in v2_nums]
    return order


def render_landing_page(track_order: list, search_index: list[dict]) -> str:
    def cards_html(tracks: list) -> str:
        parts = []
        for t in tracks:
            teaser = TRACK_TEASERS.get(t.track_slug, "")
            parts.append(
                f'  <a class="track-card" href="{t.track_slug}/index.html">\n'
                f'    <div class="track-num">T.{esc(t.display_num)}</div>\n'
                '    <div class="track-info">\n'
                f'      <h3>{esc(smart_title(t.title))}</h3>\n'
                f'      <p>{esc(teaser)}</p>\n'
                "    </div>\n"
                "  </a>"
            )
        return "\n".join(parts)

    v1_tracks = [t for t in track_order if t.volume == 1]
    v2_tracks = [t for t in track_order if t.volume == 2]

    search_json = json.dumps(search_index, ensure_ascii=False).replace("</script", "<\\/script")

    body = f"""<div class="page-header">
  <div class="page-kicker">Plenee Academy</div>
  <h1>A Guide for Wealth</h1>
  <p>Free financial education grounded in real research, not sales pitches — a reference library for every decision, and a psychology track for the biases quietly running your money. Education, never personalized advice.</p>
</div>

<p class="academy-pullquote">&ldquo;Rich is what people see. Wealth is what they don't.&rdquo;</p>

<div class="track-search-wrap">
{search_html('academy')}
</div>

{overview_html(ACADEMY_OVERVIEW)}

<div class="track-wrap">
  <div class="volume-section">
    <h2 class="volume-h2">Volume 1 — A Guide for Wealth</h2>
    <p class="volume-sub">Reference material — read any track, in any order, whenever a decision comes up.</p>
    <div class="track-grid">
{cards_html(v1_tracks)}
    </div>
  </div>

  <div class="volume-section">
    <h2 class="volume-h2">Volume 2 — The Psychology of Money</h2>
    <p class="volume-sub">A cumulative, narrative read on the mental wiring behind every money decision.</p>
    <div class="track-grid">
{cards_html(v2_tracks)}
    </div>
  </div>
</div>

<script type="application/json" id="academy-search-data">{search_json}</script>
<script>{SEARCH_JS}</script>"""

    return PAGE_TEMPLATE.format(page_title="Plenee Academy", style=STYLE_BLOCK, body=body, **DEPTH_LANDING)


def generate_landing_page(idx, global_search_index: list[dict]) -> None:
    track_order = parse_curriculum_track_order(idx)
    html_out = render_landing_page(track_order, global_search_index)
    outfile = WEBSITE_DIR / "academy" / "index.html"
    outfile.write_text(html_out, encoding="utf-8")
    print(f"  wrote {outfile.relative_to(WEBSITE_DIR)}")


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
    track_title = smart_title(track_info.title)

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
    """Regenerate every track from current source, embed one shared cross-track
    search index on every track's index.html, and rebuild the Academy landing
    page (its reading order/grouping comes from academy_curriculum.md, not from
    file-discovery order)."""
    idx = build_index()
    files = sorted(ACADEMY_SRC.glob("*_expanded.md"))
    results = [generate_track_pages(str(f), idx) for f in files]
    global_search_index = [e for r in results for e in r["search_entries"]]
    write_index_pages(results, global_search_index)
    generate_landing_page(idx, global_search_index)
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
