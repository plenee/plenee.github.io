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

# Two-paragraph overviews for the landing page and each track's own index
# page. Hand-written per Rob's direction (2026-07-18): consumer voice, not
# academic/textbook framing -- avoid "teach"/"taught"/"curriculum"/"lesson".
ACADEMY_OVERVIEW = (
    "Most people never got a straight explanation of how money actually works — why a credit score moves the way it does, what a 1% fee really costs over 30 years, or who benefits when a bank waives one fee and not another. Plenee Academy fills that in: plain-English explanations of the systems, incentives, and numbers behind everyday financial decisions, written the way a sharp, financially literate friend would explain it — not the way a disclosure page does."
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

# Six thematic color groups for the landing page's track cards (extends
# Plenee's existing navy/teal/orange brand rather than an arbitrary rainbow;
# each is a (base, tint, dark) hex triple applied per-card via inline CSS
# custom properties --hue/--hue-l/--hue-d). Chosen 2026-07-20 during the
# academy_landing_mockup.html iteration.
TRACK_HUES: dict[str, tuple[str, str, str]] = {
    "track1-language-of-money": ("#0FA8BC", "#E6F7FA", "#0A8A9E"),
    "track2-visibility": ("#0FA8BC", "#E6F7FA", "#0A8A9E"),
    "track4-extraction-economy": ("#E87722", "#FFF4EC", "#C7630F"),
    "track5-the-debt-trap": ("#E87722", "#FFF4EC", "#C7630F"),
    "track6-stop-the-bleeding": ("#C9971F", "#FBF4E1", "#A67D15"),
    "track7-free-up-cash-flow": ("#C9971F", "#FBF4E1", "#A67D15"),
    "track8-build-wealth": ("#C9971F", "#FBF4E1", "#A67D15"),
    "track9-earn-dont-pay": ("#C9971F", "#FBF4E1", "#A67D15"),
    "track3-credit-mastery": ("#5B7A99", "#EAF1F6", "#46607A"),
    "track10-taxes-efficiency": ("#5B7A99", "#EAF1F6", "#46607A"),
    "track11-life-events": ("#5B7A99", "#EAF1F6", "#46607A"),
    "track12-retirement-decumulation": ("#5B7A99", "#EAF1F6", "#46607A"),
    "track13-protection": ("#A8506B", "#FAEBEF", "#8C3F54"),
    "track14-high-wealth-efficiency": ("#A8506B", "#FAEBEF", "#8C3F54"),
    "track15-when-preparation-isnt-enough": ("#A8506B", "#FAEBEF", "#8C3F54"),
    "volume2-track1-your-built-in-wiring": ("#1F5A6B", "#E7F3F5", "#17434F"),
    "volume2-track2-what-money-is-for": ("#1F5A6B", "#E7F3F5", "#17434F"),
}

# Per-chapter overview paragraph + finance-themed abstract-art style id
# (1=Candlestick Rhythm, 2=Ledger Rules+Trendline, 3=Coin Stacks,
# 4=Ticker Wave/Area Chart, 5=Banknote Guilloche Weave, 6=Ascending Growth
# Bars -- see academy_tile_art_finance_styles_mockup.html for the originals).
# Keyed by track_slug -> chapter_id (chapter_id matches the raw id captured
# by CHAPTER_SPLIT_RE, e.g. '2.1' or 'PM1.7').
CHAPTER_META: dict[str, dict[str, tuple[str, int]]] = {
    "track2-visibility": {
        "2.1": ("Nobody decides to pay $400 a year in fees or leave cash idle while a card racks up interest — these things just happen, quietly, off to the side. Most financial underperformance isn't a discipline problem; it's a visibility problem, and it comes before every other problem this curriculum covers.", 4),
        "2.2": ("A blank-sheet test — write down every account you own, from memory — reveals how incomplete most people's mental map really is. The accounts that get forgotten are exactly the ones quietly losing money: old 401ks in high-fee default funds, a store card nobody remembers opening.", 3),
        "2.3": ("A mortgage or car payment isn't fully an expense — part of it is principal, quietly building your net worth. This chapter covers the four reading skills that keep a spending analysis honest: transfers aren't spending, categories tell the real story, one purchase can be several things, and some spending is seasonal.", 2),
        "2.4": ("Two credit scores for the same person, forty points apart, are both correct — they're just different formulas reading the same underlying file. This chapter separates the report (the raw history) from the score (a formula applied to it), and shows why checking your own file never hurts it.", 5),
        "2.5": ("Subscription spending is chronically underestimated, and not by accident — free trials, annual renewals, and slow price creep are all engineered to be forgettable. The fix isn't vigilance, it's a periodic sweep: annualize every charge and decide, on purpose, what's actually worth keeping.", 1),
        "2.6": ("Financial stress rarely tracks the size of the number — it tracks the gap between what your finances demand and what you can bring to them: skills nobody taught you, time nobody has, and surprises nobody saw coming. Left alone, that stress narrows attention and drives worse decisions, compounding the very problem it came from.", 6),
        "2.7": ("Manual money management has a real cost that never appears on a statement: the hours, priced at whatever your time is worth. Worse, those hours usually buy stale, incomplete information — a bad trade at any income level.", 2),
        "2.8": ("A credit card statement is built around four numbers — statement balance, due date, current balance, minimum payment — and confusing them is what turns an interest-free card into an expensive one. This chapter also covers the federally required payoff-disclosure box, arguably the most honest sentence any card issuer prints.", 5),
    },
    "track1-language-of-money": {
        "1.1": ("Ask why cash flow, net income, and net worth actually differ and most people shrug — including successful ones. That shrug isn't stupidity; it's a translation failure, because the ideas are simple but the vocabulary was built by and for accountants. Every profession that manages complexity names it first; households manage the most consequential numbers in their lives with no working language at all.", 2),
        "1.2": ("Money's basic fact is that it moves — in as paychecks, out as rent and groceries — and FLOW is the plain word for that motion, split into inFLOW, outFLOW, and three honest states: Positive, Negative, and Equal. Negative Flow isn't automatically a failure; it depends on whether the drawdown was planned. Naming the motion is the first step toward actually watching it.", 4),
        "1.3": ("FLOW watches money move; NET scores what the movement amounted to — did the period leave you ahead, behind, or even. The subtle trap: FLOW and NET aren't the same question, since a mortgage payment can be mostly principal, moving cash out without counting as an expense. Learning to hold both numbers at once is the single biggest upgrade in this vocabulary.", 2),
        "1.4": ("After the motion and the verdict comes the real question: what do you actually have? NEST is assets minus liabilities, the running total every Net Plus period feeds and every Net Minus period draws down. It moves for reasons FLOW and NET can't see — market gains, loan principal, depreciation — which makes it the one number that measures the wealth nobody else can see.", 3),
        "1.5": ("Not all outflow is spending — paying down a loan or funding savings changes your position, it doesn't consume it, so those dollars get their own dials. loanFLOW tracks whether debt is growing or shrinking; saveFLOW tracks whether your savings and investments are building or draining. Carved cleanly out of the ordinary totals, the two dials finally let two households with identical spending look completely different underneath.", 4),
        "1.6": ("Ordinary spending still hides one more split: the outflow that happens whether or not you decide anything, versus the outflow you actually choose. coreFLOW is the mandatory floor — rent, taxes, minimum debt payments — and lifeFLOW is everything above it. Knowing your coreFLOW number answers the scariest question in personal finance: what does your life cost if everything goes wrong?", 2),
        "1.7": ("Rich is what people see — the car, the renovation, money already spent. Wealth is what they don't — the assets quietly compounding, unseen by anyone driving past. The two aren't different amounts of the same thing; they're competitors for the same dollar, and the culture's imagery of 'having money' is built almost entirely from evidence of not having it.", 3),
        "1.8": ("Every business runs on two documents — an income statement and a balance sheet — reviewed on schedule, because operating without them would be reckless. A household is economically identical, yet almost none keeps either one. This chapter shows they already do, in translated form: NET is the income statement, NEST is the balance sheet, and FLOW is the cash flow statement running underneath both.", 2),
        "1.9": ("Personal finance splits into two different jobs: Money Management, the daily operating pillars of Cash, Debt, and Investment; and Financial Planning, the overlay work of risk, tax, retirement, and estate design that sits on top of them. Most financial products live in one box while pricing themselves like the other. Knowing which box a service — or your own need — belongs in is half of shopping for help wisely.", 5),
    },
    "track3-credit-mastery": {
        "3.1": ("Your credit score doesn't know your income, your savings, or your job title — it measures exactly one thing: how you handle borrowed money. Two behaviors, paying on time and keeping balances low against limits, make up two-thirds of the formula, and both are things you control this month, not circumstances you're stuck with. A narrow formula turns out to be a steerable one.", 5),
        "3.2": ("Two people can owe the identical $3,000 and score completely differently, because scoring reads utilization by distribution and timing, not just total debt. A single near-maxed card hurts even when your overall ratio looks fine, and issuers report balances at statement closing, not the due date — so a card paid in full every month can still show as maxed. Pay down before the close, not just before you owe it.", 5),
        "3.3": ("Building credit from zero has real, boring, mostly-free exits: a secured card, a credit-builder loan, or authorized-user status on someone else's clean old account — followed by small balances, perfect payments, and time. Rebuilding after damage runs the same road, helped by a fact most people don't know: negative marks age off, and scoring forgives faster than the file does. The shortcut industry sells what patience gives away for free.", 5),
        "3.4": ("People avoid rate-shopping a mortgage because they fear checking their credit — but checking your own score never costs a point, and even applying only costs about five, temporarily. Multiple applications for the same loan type within a couple of weeks count as a single inquiry, precisely so you can compare lenders freely. Skipping that comparison to protect five points can cost tens of thousands over a loan's life.", 5),
        "3.5": ("Closing a paid-off card feels tidy, but your score reads it as two losses on two clocks: an instant utilization hit, since that limit disappears from your available credit, and a slow-motion history hit years later when the account ages off. The default is keep old cards open, especially the oldest, with one small recurring charge on autopay — an unused card is one of the few assets that pays you for doing nothing.", 5),
        "3.6": ("Carrying a small balance does not help your score — it only helps your bank, at roughly 24% a year, for zero scoring benefit. The bureaus see your statement balance whether you pay it off or not, so the full payer and the balance carrier look identical on the file; only one of them pays interest. This chapter also retires the score's other favorite myths, from checking your own credit to a raise moving the number.", 5),
        "3.7": ("A mortgage rate gets decided, in part, by what your credit file looks like on one schedulable day — so treat the year before applying like a campaign: clean errors and quiet new applications early, drive utilization down deliberately in the months before, then freeze the story completely near the end. Half a point of rate tier is worth tens of thousands over a loan's life, for preparation that costs nothing but attention.", 5),
    },
    "track4-extraction-economy": {
        "4.1": ("American households pay a trillion dollars a year in interest, and most of it is honest — the fair price of a mortgage or an auto loan. The real fleecing is the roughly $230 billion that isn't: predatory lending priced far beyond any real risk, plus avoidable fees and interest that exist only where attention lapses. It doesn't spread evenly either — it stacks on the same tens of millions of households, year after year.", 5),
        "4.2": ("A $35 overdraft fee on a $6 purchase is nearly six times the price of the thing you bought, and these fees are stunningly concentrated: roughly 9% of accounts generate almost 80% of all overdraft revenue, disproportionately among working households with thin margins, not the very poorest. They aren't character failures — they're timing failures, caused by rent and payday landing on the wrong days, and timing is exactly the kind of problem visibility solves.", 5),
        "4.3": ("Credit cards have a switch almost nobody's told about: pay your statement in full and purchases are interest-free for weeks; carry even one dollar and interest starts at the register, on everything, immediately. Carrying and paying in full aren't two prices for one product — they're two entirely different products, one free and one running around 24%. Even paying off a balance mid-cycle can leave a trailing-interest charge waiting on the next statement.", 4),
        "4.4": ("'Four easy payments of $25' is engineered to not sound like $100, and buy-now-pay-later industrialized that trick. Used perfectly, it's genuinely free credit — the damage lives in the imperfections: late fees on tiny balances, deferred-interest deadlines that retroactively charge the entire original amount, and installments spread across providers that never see each other's plans, so the real monthly total exists nowhere until you add it up yourself.", 5),
        "4.5": ("There's a fee nobody bills you for: money sitting idle in checking, earning nothing, while a high-yield savings account down the street pays real interest for zero extra risk. It gets brutal when idle cash coexists with high-interest debt — a 24-point spread running against you, silently, every single day. Unlike almost everything else in this track, fixing it requires no discipline at all, just twenty minutes and a login.", 4),
        "4.6": ("'Just one percent' is the most expensive phrase in wealth management, because an annual asset-under-management fee is paid from your strongest compounding dollars, year after year, for decades. Run the math on $500,000 over 25 years and that one percent can cost more than the original principal. Reframe the fee against your actual returns, not your assets, and the true cost — often a sizable share of your entire gain — comes into focus.", 5),
        "4.7": ("The single most useful question to ask anyone managing your money is simply how they're paid, because compensation shapes advice even through decent, well-meaning people. Commission structures reward transactions; asset-based fees quietly discourage anything that shrinks the fee base, like paying off a mortgage. The advisors worth keeping are the ones who sometimes recommend doing nothing — advice against their own interest is the single most reliable signal that exists.", 5),
        "4.8": ("Whole life insurance gets sold hard at kitchen tables while term insurance gets bought quietly on comparison sites, and the gap explains the entire pattern: permanent policies carry large upfront commissions that term doesn't. Term answers the actual need — replacing income if people depend on you — directly and cheaply; whole life bundles that need with an expensive savings vehicle whose economics favor the seller most in exactly the years most buyers quit.", 5),
        "4.9": ("Some fees you pay once and see; the expensive ones you pay forever and never see at all — fund expense ratios, 401k plan layers, mortgage closing costs, all quietly skimmed as percentages before a number ever reaches your statement. Every one of them dies to the same weapon: rate times balance equals dollars per year. '0.85%' sounds like nothing; '$3,400 a year from your retirement account' does not.", 5),
        "4.10": ("A free finance app with a hundred million users and no subscription fee still makes billions — from somewhere, and that somewhere is you. Referral bounties reward the app when you take on more credit, not when your finances improve; your transaction data becomes a targeting asset; 'free' dashboards exist to funnel you toward paid products past a balance threshold. Ask of any tool: does it earn more when your finances improve, or when you transact?", 5),
        "4.11": ("Watch someone drive by in a stunning car and you rarely think they're impressive — you imagine yourself in the seat instead, and the driver vanishes from the thought entirely. That's the Man in the Car paradox: status spending buys a signal the audience never actually receives, because they're too busy daydreaming about themselves. Richness is what people see; wealth is what they don't, and the audience you're spending on isn't even watching.", 3),
    },
    "track5-the-debt-trap": {
        "5.1": ("Going into debt for anything beyond a home or business used to be shameful, and that taboo didn't erode on its own — it was dismantled on purpose by companies that needed to sell more than people could pay for in cash. GM built an entire financing company to move cars in 1919; Ford tried an alternative and lost market share for a decade. Knowing the taboo was manufactured makes it easier to ignore the pressure to carry debt you don't need.", 5),
        "5.2": ("The credit card most Americans carry was built from two ideas: a card usable across many merchants instead of one store, and the willingness to mail live, already-activated cards to strangers by the tens of thousands. The resulting delinquency and fraud spiraled badly enough that Congress finally banned unsolicited card mailings by law in 1970. The instinct behind it — distribution outrunning caution, with someone else absorbing the fallout — still shows up in credit offers today.", 5),
        "5.3": ("By the 1950s, advertisers had stopped guessing what people wanted and started studying it clinically — real research, though its most famous myth, hidden subliminal messages, turns out to be fabricated folklore the original book actually treated with skepticism. The older, better-evidenced mechanism is economist Thorstein Veblen's: status pursued through visible waste, with no natural stopping point, a dynamic so recognizable a cartoonist's own overspending became the phrase 'keeping up with the Joneses.'", 5),
        "5.4": ("'Planned obsolescence' actually covers two very different claims: a real, archivally-documented lightbulb cartel that fined manufacturers for making bulbs last too long, and Detroit's openly acknowledged strategy of annual styling changes designed to make last year's car feel outdated. Only one of them required secrecy to work. Both aimed at the same result — more frequent purchases — and both still shape the replacement-cycle arithmetic behind every category from cars to phones.", 5),
        "5.5": ("Nothing about modern marketing is conceptually new — what's changed is precision and friction. Social media targets individual insecurities instead of demographics, and buy-now-pay-later embeds financing directly at checkout, approved in seconds, skewing hardest toward younger, lower-income, and disproportionately Black and Hispanic users. The honest gap: nobody has a reliable, industry-wide measure of how risky BNPL actually is, because most lenders still don't report performance the way credit cards do.", 5),
        "5.6": ("A fair interest rate on more debt than you can safely carry does the same damage as a predatory rate on an amount you could handle — which means fair pricing and safe sizing are two different questions entirely. Card issuers, retailers, and platforms all profit from the volume, whether or not any single loan is predatory. And some of the debt isn't chasing a want at all — it's covering education, healthcare, and housing costs that grew far faster than income.", 5),
        "5.7": ("Your name on a title doesn't mean you own the asset — you own the equity, the gap between what it's worth and what you still owe, and decades of loan engineering have quietly shrunk that gap. Interest-only mortgages, negative-amortization loans, and vanishing down payments let buyers 'own' homes with little or no real stake, and the same trick now runs through car loans, where rolled-over negative equity roughly doubles the odds of repossession.", 5),
        "5.8": ("Existing homeowners aren't losing their equity — it's actually near a decade-long high. The real story is narrower: fewer first-time buyers are getting in the door at all, while a separate, much larger trend concentrates wealth at the top mostly through stocks and business ownership, not housing debt. The two trends are real but different stories, and what's still fully within a household's control is the structure of the loan used to get in.", 3),
        "5.9": ("Every chapter in this track named a piece of machinery — manufactured respectability, mass distribution, engineered desire, engineered replacement — and none of it has stopped running. What changes once you've seen it is that debt stops being a reflex and becomes a choice made with the manufacturing visible: a pre-decided pause before urgency purchases, an honest look at discretionary spending, a loan-to-value check before signing anything. What debt spends first is never just money — it's your freedom to choose differently later.", 5),
    },
    "track6-stop-the-bleeding": {
        "6.1": ("Autopay in full, on the due date, is arguably the single best-return setting change in ordinary finance — yet careful people skip it out of a completely rational fear: what if the money isn't there when it fires? That fear isn't an autopay problem, it's a visibility problem. See your cash coming weeks ahead, and the safest configuration stops being a gamble and becomes the obvious default.", 5),
        "6.2": ("Pure highest-APR-first payoff math is correct about interest and blind to something else: your credit score reads utilization per card, and a near-maxed card gets flagged no matter how cheap its rate is. The Intelligent Avalanche fixes this — triage the dangerously maxed cards first, price every deviation from pure math in real dollars, then weight it all by whether you're about to apply for a loan.", 5),
        "6.3": ("Avalanche saves the most interest, Snowball keeps you motivated with fast wins, and Intelligent Avalanche protects your credit score from mechanics neither classic method knows exists — and the decades-long argument over which is 'right' persists because all three are answering genuinely different questions. Price each against your actual balances and your actual temperament; the plan that finishes beats the one that's merely optimal on paper.", 2),
        "6.4": ("A financial plan that only works if nothing goes wrong isn't a plan, it's a bet — and something surprising you is a near-certainty over time, even if no specific emergency is. An unbuffered $500 shock doesn't cost $500, it cascades onto a 24% card. Start with the first $1,000 (it does the most work), size the rest to your real volatility, and park it somewhere boring and reachable.", 3),
        "6.5": ("Your internet provider has a whole department paid to discount your bill the moment you ask — and most people never call. Sort recurring bills into three buckets — directly negotiable, shoppable, and checkable for errors — run the short scripts, and annualize the wins: twenty bucks a month sounds trivial until it's $240 a year for a twenty-minute phone call.", 5),
        "6.6": ("A new car doesn't just cost money, it destroys it — roughly 20% of its value gone in year one alone — while most buyers finance the destruction and pay interest on top of it. Depreciation never shows up on a bill, so it goes unmanaged. Price it honestly per year of ownership, and the arbitrage falls out on its own: let someone else absorb the steep first years.", 4),
        "6.7": ("Utilization is the rare credit-score factor with total amnesia — pay a maxed card down and the penalty vanishes with the very next reporting cycle, no waiting period required. The trick is knowing the mechanics: it's judged per card, not just overall; the snapshot is taken at statement closing, not the due date; and raising limits or keeping old cards open quietly shrinks the ratio without touching a balance.", 5),
    },
    "track7-free-up-cash-flow": {
        "7.1": ("Most budgets fail because they treat every dollar as up for negotiation this month, when a big chunk of your money — the mortgage, the insurance, the minimum payments — was already decided years ago. Split spending into Core FLOW, the committed money you can only renegotiate structurally, and Extra FLOW, the genuinely decidable rest, and the budget stops feeling like a moral exam you keep failing.", 2),
        "7.2": ("\"$400 a month on groceries\" — says who? Not your own transaction history, which already knows exactly what you spend. Anchor every category target to your real trailing twelve months, adjust it as a deliberate small delta rather than a fantasy number, and give lumpy categories like gifts or utilities a shape that follows the calendar instead of a flat number that cries wolf every December.", 2),
        "7.3": ("Two households with identical income and spending can have wildly different financial lives, because money is a sequence, not a sum — a month can balance perfectly on paper and still hit a painful trough in its first week if bills cluster before payday. Map your calendar to find the low point, then either fund it or simply move a due date; the fix costs one free phone call.", 4),
        "7.4": ("Money sitting in the wrong account isn't lost, it's just underemployed — showing up every day to a job beneath its ability and earning nothing for the trouble. Give every dollar a home matched to when you'll actually need it: checking for this month's trough, high-yield savings for someday-soon money, CDs for known dates, and investing only for the long horizon — nothing risked, just money sorted.", 3),
        "7.5": ("Consolidation ads sell one number — the lower monthly payment — and stay very quiet about how it got lower, because there are two ways and they have opposite values. The only honest test is total lifetime cost: rate, fees, and time together. Take the genuine wins, but a stretched-out term that trims the payment while adding years of interest is the same debt, just combed differently.", 5),
        "7.6": ("A windfall behaves differently from a paycheck — your brain tags it 'extra,' and extra money has a habit of vanishing by Tuesday with nothing to show for it. The fix isn't discipline in the moment, it's a split decided before the money ever lands: buffer, high-rate debt, goals, and a deliberate guilt-free slice that protects the rest of the plan from resentment.", 3),
        "7.7": ("The best time to arrange emergency credit is exactly when you don't need it — which is also, predictably, when almost nobody bothers. A HELOC arranged in calm weather costs almost nothing sitting unused and beats every panic option people actually reach for in a crunch. The whole safety valve depends on two disciplines: open it early, and write down what counts as an emergency before temptation shows up.", 5),
    },
    "track8-build-wealth": {
        "8.1": ("Compounding is the one force in finance that earns the word miraculous, and its whole job description is unglamorous: earn a return, leave it alone, repeat for decades. Humans are wired to think linearly, so we chronically underrate what patient time does and overrate what clever timing might. Starting ten years earlier commonly beats contributing for thirty extra years — and protecting the streak from a big loss matters more than chasing a better one.", 4),
        "8.2": ("Most households save whatever's left after spending; households that actually build wealth invert the sentence and spend whatever's left after saving. Same income, opposite order of operations — and the order, not the amount, is usually what decides the outcome. Automate the transfer to fire on payday before anything else moves, and saving stops being a monthly test of willpower and becomes plumbing.", 3),
        "8.3": ("The alphabet soup of 401k, IRA, Roth, and HSA confuses people because they mistake the wrapper for the investment — an IRA isn't a holding, it's a tax rule with a name. Learn what each container actually does and the commonly taught order for filling them: capture the match, clear expensive debt, use the triple-advantaged HSA, then work outward. The wrapper you choose is one of the few genuinely free lunches in finance.", 5),
        "8.4": ("Somewhere in your employment paperwork is a sentence worth thousands of dollars a year: your employer will match your retirement contributions, dollar for dollar or better — a guaranteed, immediate 50-100% return that no casino would dare offer. And a remarkable share of employees leave part of it uncollected simply because nobody ever reads the plan document. Five minutes in the portal is the highest-paid five minutes in this whole track.", 6),
        "8.5": ("Few debates in finance have been studied this thoroughly, and the evidence is unusually one-sided: over long stretches, the large majority of actively managed funds have trailed their benchmark index after fees, and the one variable that predicts it in advance is cost. Choosing the index isn't cleverness, it's humility — accepting the market's return minus almost nothing, while nearly every incentive in investing tries to sell you the opposite.", 1),
        "8.6": ("Before any question about which investments to hold comes a bigger one: how is the money split between higher-risk and steadier assets? That split explains far more of a portfolio's ups and downs than the individual picks inside it. The real test isn't which mix maximizes expected return — it's which mix you can actually hold through a 30% crash without selling, because the best allocation on paper is worthless abandoned in a panic.", 1),
        "8.7": ("Getting wealthy and staying wealthy are nearly opposite skills — one rewards optimism, risk, and concentration, the other rewards humility, diversification, and a healthy paranoia about everything that can go wrong. Because losses are asymmetric — a 50% drop needs a 100% gain to recover — the people who lose fortunes almost always fail the transition, still playing the getting game after they've already won it.", 6),
        "8.8": ("Your net worth has an honest asterisk most people never see: a $400,000 traditional 401k isn't $400,000 of yours, because withdrawals get taxed as income and the government effectively holds a lien on part of it. Roth balances are fully yours; pre-tax balances deserve a real haircut in your head. Reading your net worth tax-adjusted, not at face value, is what keeps retirement-readiness numbers honest.", 2),
        "8.9": ("For most homeowners the house is the biggest number on the balance sheet and the strangest one — an asset that charges you rent in taxes and maintenance, wealth you can't spend without selling or borrowing, and a place to live whose value isn't financial at all. Untangling those three roles separately, rather than calling it simply 'an asset,' is how you see what homeownership is actually doing to your finances.", 4),
    },
    "track9-earn-dont-pay": {
        "9.1": ("Somewhere in a well-run financial life is a day nobody celebrates because nobody notices it: the day the interest you earn finally exceeds the interest you pay. Before that crossing you're renting money; after it, money starts renting itself out on your behalf. Most households live their whole lives on the paying side simply because nobody ever added the two numbers together on one page.", 4),
        "9.2": ("Interest is one machine with two seats — pay the rate in one, collect it in the other — and the only real difference is position. Write your household's actual paying and earning columns side by side, something almost nobody does, then flip the equation deliberately in rate order: idle cash against expensive debt first, then honest yields, then the long build everything else depends on.", 2),
        "9.3": ("An asset is anything of real value you own, whether or not it currently sends you a check — the popular 'assets pay you' reframe is a useful sorting trick, not an actual definition. Within everything you own, three families genuinely do pay their holder: interest, dividends, and rents, each trading a different mix of risk and effort for the income, and none of them as truly 'passive' as advertised.", 3),
        "9.4": ("You can't opt out of paying the swipe fee baked into every price tag — you can only decide whether to collect your share back. The boring baseline is a no-fee card paying roughly 2% cash on everything, cash beating points because it can't be devalued or expired. But the entire calculus only works in pay-in-full mode: one month of carrying a balance at 24% erases a whole year of collected rewards.", 5),
        "9.5": ("Every deposit account is really a loan you're making to a bank, dressed up in friendlier words like 'savings' and 'account.' High-yield savings, money markets, CDs, and Treasury bills are the plain-language instruments where that loan pays you back safely — no market risk, no skill required, just yield. This boring floor is where the buffer lives, and often where a household first feels the earning column actually working.", 3),
    },
    "track10-taxes-efficiency": {
        "10.1": ("Most people think their tax bracket is the rate the government takes from all their income — it isn't. Brackets are a staircase: only your last dollar hits the top rate, so your marginal rate (what the next dollar costs) and your effective rate (what you actually pay overall) are two very different numbers. Getting this straight kills the raise-will-cost-me-money myth for good.", 5),
        "10.2": ("Every dollar you save gets taxed now, later, or never, and the order you fill your accounts in is one of the few guaranteed efficiency wins in personal finance. Match the employer match first, then never-taxed space, then other advantaged accounts, then flexible taxable — with debt and your buffer still cutting the line ahead of all of it.", 2),
        "10.3": ("Fees aren't the only drag on your investments — taxes on dividends and realized gains quietly compound against you too. Three structural habits manage most of it: put tax-noisy holdings in sheltered accounts, let low turnover defer gains so they keep compounding, and know that losses on paper have real salvage value within the wash-sale rules.", 1),
        "10.4": ("That big spring tax refund people celebrate isn't a windfall — it's proof you gave the government an interest-free loan all year while your own credit card balance compounded at 24% in the meantime. The fix isn't minimizing withholding, it's accuracy: get your paycheck closer to right so your money works for you all year instead of showing up months late.", 5),
        "10.5": ("After decades of building your nest egg, the order you draw it down in changes how much of it survives taxes. Since brackets reset every year, spreading withdrawals across accounts and years thoughtfully — rather than dumping it all as taxable income at once — can be worth real money, and it's exactly the kind of plannable decision a professional should help execute.", 4),
    },
    "track11-life-events": {
        "11.1": ("A car lot is basically a building engineered to make you ignore arithmetic — the payment frame, the long loan, the underwater trade-in, and the finance-office upsell all work together against you at once. The fix is total cost of ownership calculated before you arrive, price and financing negotiated as two separate deals, and a hard refusal to ever finance negative equity.", 6),
        "11.2": ("Your mortgage approval letter isn't financial advice — it's just the largest amount a lender thinks you can repay without defaulting, indifferent to your savings goals or your actual life. The real number comes from your own full-cost cash projection, checked against your buffer and retirement contributions staying funded, not the ratio someone else calculated for you.", 5),
        "11.3": ("Marriage merges two money histories, two credit files, and two sets of unspoken beliefs about what money means — and couples routinely skip the diligence they'd never skip buying a used car. Real merger prep means surfacing those money meanings first, disclosing full financial maps to each other, then choosing an account structure — full joint, full separate, or hybrid — that fits the relationship rather than a template.", 2),
        "11.4": ("College savings gets priced to parental emotion, which is exactly why this chapter insists on cold arithmetic: 529 plans are a genuinely good tax-advantaged wrapper, but funding them ahead of retirement is a trade-off nobody says out loud. There are loans for college; there are none for retirement — so match, retirement savings, and buffer come first, education savings after.", 3),
        "11.5": ("The moment you change jobs, an entire industry starts calling about your old 401k, because a rollover is the single largest sum of money most people ever move at once. There are really only four honest options — leave it, roll to the new plan, roll to an IRA, or cash out — and the friendly caller pushing the IRA route is usually the one who profits most from your choice.", 5),
        "11.6": ("Divorce, widowhood, and other household dissolutions don't just adjust a financial life, they can shatter it — often while one partner never held the full picture to begin with. The sequence that keeps a crisis from compounding is visibility first: rebuild the complete account map, secure shared exposures like joint credit, and defer every irreversible decision until the emotional pressure has passed.", 5),
        "11.7": ("Sudden money — an inheritance, a settlement, an insurance payout — attracts urgency, salespeople, and every cognitive bias in the book, all at once. The professional consensus is refreshingly simple: park it somewhere boring, make no irreversible decisions for six months, and spend that time quietly figuring out the tax picture and what you actually want the money to do.", 3),
    },
    "track12-retirement-decumulation": {
        "12.1": ("Spending down your savings in retirement isn't failure, it's the whole point — decades of saving exist precisely so later decades can draw them down. Yet the psychology rarely cooperates: loss aversion and a lifelong saver identity make people chronically underspend what they worked decades to build, mistaking the plan working for the plan failing.", 4),
        "12.2": ("Money buys different amounts of life depending on your age, and Bill Perkins' Die With Zero framework asks the question accumulation-minded savers never do: what's the optimal amount to die with? The practical answer is time-bucketing your experiences to the age windows when they're actually usable, and giving to people while you're alive to watch it matter rather than leaving an accidental, poorly-timed bequest.", 3),
        "12.3": ("Running out of money in retirement gets all the warnings; the opposite failure — dying with your largest balance ever, having never taken delivery of the freedom you bought — gets none, despite being disturbingly common among disciplined savers. The fix is structural: a pre-authorized minimum spend, a written definition of enough, and a concrete list of experiences with closing age-windows.", 3),
        "12.4": ("Two retirees can have identical savings and identical average returns yet end up in completely different places, purely because of the order their returns arrived in — a bad market in year one of retirement does damage a bad market in year twenty never would. Safe withdrawal thinking, including the famous 4% rule, is really about planning for bad sequences and keeping spending flexible, not chasing an average.", 1),
        "12.5": ("Social Security is already the inflation-adjusted lifetime annuity people are told to go buy elsewhere, and the one decision left is when to claim it. Framed as a longevity bet it sounds like a race against your own life expectancy; framed correctly as insurance against outliving your money, delaying purchases a bigger guaranteed floor against the outcome that actually hurts.", 5),
        "12.6": ("Retirement is where financial advice is most genuinely valuable and most expensively priced, because the portfolio is at its peak right as sequence risk, tax-ordered withdrawals, and claiming decisions all land at once. The real question isn't whether advice is worth paying for, it's which jobs are worth paying for and whether a perpetual percentage fee actually matches work that's mostly one-time or annual.", 5),
        "12.7": ("Money converts into life at a falling rate as you age, which means the highest-return purchases left in retirement aren't more savings — they're time and memories. Buying capacity (help with chores and errands) and proximity (visits made now, while they're easy) beats hoarding, because objects depreciate but the memories they buy only appreciate.", 4),
    },
    "track13-protection": {
        "13.1": ("Insurance is a losing bet on average by design, which makes it rational for exactly one thing: covering losses big enough to break you, not ones you could easily absorb. Insure the catastrophes — liability, income, life, health, dwelling — and let your buffer self-insure the small stuff, raising deductibles as that buffer grows instead of paying retail for inconvenience coverage.", 5),
        "13.2": ("Life insurance exists for exactly one scenario: people depend on your income, and your death would turn grief into financial ruin. Term insurance fits that finite dependency window cheaply and honestly, while whole life gets pushed hard mainly because it pays a commission — if a permanent-insurance pitch shows up with a persuader attached, that's the whole story right there.", 5),
        "13.3": ("Fraud and scams run on the same fuel as legal financial extraction — inattention, urgency, and a good story — just without any disclosure rules to constrain them. The same visibility and structure that beats legitimate fee extraction beats most criminal schemes too: freeze your credit files, use two-factor everywhere, watch your transaction feed, and give every unsolicited urgent request 48 hours it can't survive.", 5),
        "13.4": ("Estate planning sounds like a wealthy person's luxury, so it gets endlessly deferred, but it's really just the paperwork that decides whether your savings reach the people you meant them for. The single highest-leverage fact nobody explains: beneficiary designations override your will entirely, so that stale form from twenty years ago can hand your account to an ex-spouse no matter what you wrote elsewhere.", 5),
        "13.5": ("Your financial data is an asset, and you're leaking a lot of it for free to bureaus, banks, brokers, and every app you've ever connected. Real privacy isn't achievable, but the discretionary leakage is containable in an afternoon: freeze your files, exercise your opt-outs, audit connected apps, and ask of every free tool the one question that never retires — who profits from this, and is it worth the price?", 5),
    },
    "track14-high-wealth-efficiency": {
        "14.1": ("A $3 million portfolio under a 1% AUM arrangement pays $30,000 a year, every year — a luxury car's worth of fee that gets a quarterly call instead of an annual invoice. The fix isn't outrage, it's itemization: price the management, the planning, the tax work, and the behavioral hand-holding separately, then decide if the bundle actually earns its gap over buying each piece alone.", 5),
        "14.2": ("Commission, AUM percentage, and flat-fee advisors aren't just different price tags — they're different incentive gradients, each quietly steering what gets recommended and what never comes up. AUM's particular trap: it tilts against any legitimate reason to move money out of the managed pool, from paying off a mortgage to funding retirement income. Ask exactly how you're paid, get \"fee-only fiduciary\" in writing, and re-run the math yearly.", 5),
        "14.3": ("Trading too much isn't just an activity bias, it's a second silent management fee — 1-2% annual turnover friction on $3 million runs $30,000-60,000 a year, for motion the evidence says actively subtracts value. The instinct that \"doing something\" beats sitting still is precisely backwards here. Audit turnover annually and demand a specific, client-driven reason for every major move — \"the market environment\" doesn't count.", 1),
        "14.4": ("Structured products — annuities, notes, private placements — sell complexity as a feature, stacking wrapper fees, guarantee costs, and rider charges into documents engineered so nobody reads them closely, often landing at 2-4% a year all-in. The test isn't whether something's complex; it's what the same job costs assembled from simple parts. Run that math before signing anything with a surrender schedule.", 5),
        "14.5": ("The biggest risk in a high-wealth portfolio is usually a good decision that kept working too long — the concentrated stock position nobody ever sells, because selling means a real tax bill today against a risk that only ever feels like \"not yet.\" No bad decision gets made; the exposure just compounds quietly. The way out is structural: a written, staged, pre-committed exit schedule that treats the risk as a price, not a hypothetical.", 1),
        "14.6": ("Fortunes and financial capability don't automatically travel together — the old \"gone by the third generation\" statistic is shakier than advertised, but the underlying risk is real. What actually transfers isn't the trust document, it's practice: money discussed as a system with shared vocabulary, efficiency modeled out loud, and real decisions handed to kids at survivable scale, long before any inheritance arrives.", 6),
    },
    "track15-when-preparation-isnt-enough": {
        "15.1": ("Job loss, disability, divorce, and medical crisis aren't rare misfortunes — they're base-rate ordinary events with real, documented odds, which makes \"it won't happen to me\" a statistical error rather than a plan. Insurers price these risks daily; households rarely plan for them the same way. The fix is sizing exposure honestly and learning the system's machinery before a crisis forces you to learn it underwater.", 5),
        "15.2": ("Everyone sizes a buffer for ordinary shocks; almost nobody computes the worst-case one — what a genuine income gap actually costs per month, for how many months, against what resources actually cover it. The number isn't meant to be funded entirely in cash. It's meant to be known, because a computed runway turns crisis dread into a plan with an actual shape.", 3),
        "15.3": ("Bankruptcy is designed machinery, not a moral verdict — Chapter 7 discharges debt fast for those who qualify, Chapter 13 repays over years and fails to reach discharge far more often than advertised. And the research shows a real, documented disparity: Black filers get steered toward the slower, costlier chapter at roughly double the rate of white filers. Every filer's defense is the same — interrogate the chapter recommendation, never accept it as a default.", 5),
        "15.4": ("The bankruptcy stereotype is wrong: filers look like the general population — same education, same jobs, same homeownership rates — knocked out of the middle class by job loss, medical bills, and divorce, not by recklessness. That finding kills the shame and redirects the real prevention toward margin and disability coverage, not spending lectures, since the deficit was never character to begin with.", 5),
        "15.5": ("Medical debt breaks every rule that applies to other balances: it's unchosen, unpriced upfront, and unusually negotiable, because the sticker price is fictional to a degree no other bill matches. Before paying anything, request the itemized bill, appeal the insurance denial, ask for the charity-care assistance nonprofit hospitals are required to offer, and take the interest-free payment plan over a credit card every time.", 5),
        "15.6": ("Job loss has a clear sequence, and it matters because the costliest decisions get made in the first days, under exactly the stress that makes good decisions hardest. File for unemployment immediately, compare COBRA against marketplace coverage instead of defaulting to either, cut to crisis spending fast, and let the pre-computed runway number — not panic — decide what happens next.", 4),
        "15.7": ("Housing crises run on a clock that inverts most people's instincts: the options are maximal in week one and evaporate by month six, yet the natural reflex is to avoid the lender while scraping together the payment. Loss-mitigation programs, modifications, and assistance all work best applied early and completely — the silence that feels protective is actually the most expensive thing you can do.", 4),
        "15.8": ("Recovery gets no press, which leaves people who've been through bankruptcy or foreclosure assuming the damage is permanent — it isn't. Credit files heal on a schedule faster than most expect, the legitimate rebuilding toolkit is boring and free, and the \"second chance\" market preying on this exact moment is worth watching for. The real asset coming out the other side is the crisis-forged habits themselves.", 6),
    },
    "volume2-track1-your-built-in-wiring": {
        "PM1.1": ("The envelope budgeter, the day-trader, the spouse who won't look at the retirement account during downturns — each pattern looks irrational from outside and felt sensible from inside, because it was, once, in the world where it got learned. Naming why a habit formed doesn't excuse it, but it does tell you exactly where to intervene, which is more than shame ever manages.", 2),
        "PM1.2": ("Four pieces of ancient mental wiring quietly run financial decisions: losses hurt twice as hard as gains feel good, today always outbids tomorrow, identical dollars get filed into imaginary buckets, and the first number seen reframes everything after it. None of it can be uninstalled — but naming the pattern in the moment weakens its pull, and automating the decisions it corrupts removes it from the negotiation entirely.", 2),
        "PM1.3": ("Satisfaction equals what you have minus what you expected, and a raise quietly inflates the second number as fast as the first — which is how a household can double its income and feel exactly as stretched as before. The real win was never the raise; it's the gap between what you could spend and what you do, and it only survives if something deliberately interrupts the upgrade.", 4),
        "PM1.4": ("Nobody ever refinanced a house because of a spreadsheet — they did it because of a story, and a vivid story beats a table of statistics almost every time, which is exactly why every extraction pitch in finance arrives dressed as one. The defense isn't cynicism, it's a habit: when a story pushes you toward a transaction, ask it for the total cost, the base rate, and who profits if you believe it.", 2),
        "PM1.5": ("The unused gym membership isn't costing willpower to keep — it's costing nothing to not cancel, and that's the whole trap. Status quo bias, salience bias, and denial all run on the same lever: the relevant number is effortful to see. Make it ambient instead — automatic, assembled, always current — and all three patterns lose the darkness they operate in.", 2),
        "PM1.6": ("\"I'll definitely be earning more by then\" and \"I can definitely stop whenever I want\" share the same bad track record. Optimism bias sizes debt against the best case, restraint bias treats a credit limit as harmless just because you intend not to use it, and exponential growth bias hides how long a minimum payment can lose to its own interest — sometimes for years before the balance visibly moves.", 4),
        "PM1.7": ("Five years into a job you've outgrown, the wiring asks \"haven't I already invested too much to leave?\" when the only useful question is \"would I take this today, knowing what I know now?\" Sunk cost keeps people stuck defending past years that can't be recovered anyway, while the ostrich effect keeps the market-rate comparison unchecked — together they can hold someone in place for a decade.", 6),
        "PM1.8": ("You don't beat these patterns by trying harder — you beat them with small structures that don't need willpower at all. Wait 48 hours before non-essential purchases, look at every account on one screen, calendar the subscription audit, price big purchases in hours of work instead of dollars, and bring another person into the numbers. None of it asks you to be better; it just changes what the moment contains.", 2),
        "PM1.9": ("A $40 tap and a $40 cash handover cost the same but feel nothing alike — the tap is weightless, and that missing friction is exactly why cashless spending runs higher on identical budgets. Framing plays the same trick from the other side: \"$1 a day\" and \"$365 a year\" are the same number wearing different clothes. The fix for both is the same habit — annualize the wording, and keep a running total visible.", 2),
        "PM1.10": ("Buying $15 shoes that fall apart in a month instead of a $60 pair that lasts five years isn't a math failure — it's what genuine scarcity does to anyone's attention, narrowing focus onto this week's number until everything else, including the cheaper long-run option, becomes hard to even see. More financial advice doesn't help a tunneled mind; fewer competing decisions and a bigger buffer do.", 4),
        "PM1.11": ("List your own car next to an identical stranger's car and you'll price yours higher — not from dishonesty, just ownership. The endowment effect quietly inflates the value of the home with the marks on the doorframe, the inherited stock, the position that once won, and it costs real money whenever an honest valuation actually matters. The antidote is simple to state: at decision time, price it like a stranger would.", 2),
    },
    "volume2-track2-what-money-is-for": {
        "PM2.1": ("If a stranger read your last ninety days of transactions with no explanation allowed, how close would their sketch of you land? A transaction history is the most honest autobiography anyone will produce — unedited and immune to good intentions — and sorting ninety days into aligned, habitual, and performative piles usually finds the biggest recoverable money in spending nobody actually chose or wanted.", 2),
        "PM2.2": ("There's no universal formula for good spending — every famous budgeting rule just smuggles in someone else's values dressed as arithmetic. The real discipline has two blades: spend lavishly, without apology, on what genuinely delivers for you, and cut mercilessly everything in the meh middle tier that's merely fine. Even-trimming everything equally feels fair and fails reliably, because it starves the joy that makes any plan survivable.", 2),
        "PM2.3": ("Ask wealthy people what they value most and they rarely describe an object — they describe unscheduled mornings. Money's highest dividend is control over your own time, and every dollar in a NEST is quietly a purchase of future autonomy. Priced in months-of-freedom instead of dollars, a $700-a-month status car stops competing with a cheaper car and starts competing with roughly a month of \"I don't have to\" a year.", 3),
        "PM2.4": ("The most dangerous people in finance aren't the ones who don't understand money — they're the ones who had everything and risked it for more, because no number ever triggered \"done.\" The goalposts move by default; hedonic adaptation works on ambition just as it works on lifestyle. Defining \"enough\" in advance, as an actual written number, is what turns an endless treadmill into a finish line that holds still.", 3),
    },
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


# ---------------------------------------------------------------------------
# Finance-themed abstract-art chapter-card tiles (replaces the old flat icon
# badge). Six motifs, chosen per chapter via CHAPTER_META's art_style id and
# tinted via the enclosing card's own --hue/--hue-d CSS custom properties, so
# a single static template works for every track's color. Ported verbatim
# from academy_tile_art_finance_styles_mockup.html (approved 2026-07-21).
# ---------------------------------------------------------------------------

ART_FILTER_DEFS = """<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <filter id="artBlur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>
    <filter id="softBlur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3"/></filter>
    <filter id="grainFilter" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" result="noise"/>
      <feColorMatrix in="noise" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.55 0"/>
    </filter>
  </defs>
</svg>"""

_ART_GRAIN_RECT = '<rect class="grain" x="0" y="0" width="400" height="132" filter="url(#grainFilter)"/>'

ART_TEMPLATES: dict[int, str] = {
    1: f"""<svg class="cc-art" viewBox="0 0 400 132" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <g filter="url(#softBlur)" opacity="0.6">
    <line x1="30" y1="30" x2="30" y2="95" style="stroke:var(--hue-d);" stroke-width="1.5"/>
    <rect x="22" y="45" width="16" height="35" style="fill:var(--hue-d);"/>
    <line x1="70" y1="20" x2="70" y2="70" style="stroke:var(--hue);" stroke-width="1.5"/>
    <rect x="62" y="35" width="16" height="25" style="fill:var(--hue);"/>
    <line x1="110" y1="50" x2="110" y2="110" style="stroke:var(--hue-d);" stroke-width="1.5"/>
    <rect x="102" y="60" width="16" height="40" style="fill:var(--hue-d);"/>
    <line x1="150" y1="15" x2="150" y2="60" style="stroke:var(--hue);" stroke-width="1.5"/>
    <rect x="142" y="25" width="16" height="25" style="fill:var(--hue);"/>
    <line x1="190" y1="40" x2="190" y2="100" style="stroke:var(--hue-d);" stroke-width="1.5"/>
    <rect x="182" y="55" width="16" height="35" style="fill:var(--hue-d);"/>
    <line x1="230" y1="10" x2="230" y2="55" style="stroke:var(--hue);" stroke-width="1.5"/>
    <rect x="222" y="18" width="16" height="28" style="fill:var(--hue);"/>
    <line x1="270" y1="35" x2="270" y2="90" style="stroke:var(--hue-d);" stroke-width="1.5"/>
    <rect x="262" y="45" width="16" height="32" style="fill:var(--hue-d);"/>
    <line x1="310" y1="5" x2="310" y2="45" style="stroke:var(--hue);" stroke-width="1.5"/>
    <rect x="302" y="12" width="16" height="22" style="fill:var(--hue);"/>
    <line x1="350" y1="25" x2="350" y2="80" style="stroke:var(--hue-d);" stroke-width="1.5"/>
    <rect x="342" y="35" width="16" height="30" style="fill:var(--hue-d);"/>
  </g>
  {_ART_GRAIN_RECT}
</svg>""",
    2: f"""<svg class="cc-art" viewBox="0 0 400 132" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <g style="stroke:var(--hue-d);" stroke-width="1" opacity="0.3">
    <line x1="0" y1="18" x2="400" y2="18"/>
    <line x1="0" y1="36" x2="400" y2="36"/>
    <line x1="0" y1="54" x2="400" y2="54"/>
    <line x1="0" y1="72" x2="400" y2="72"/>
    <line x1="0" y1="90" x2="400" y2="90"/>
    <line x1="0" y1="108" x2="400" y2="108"/>
  </g>
  <line x1="0" y1="120" x2="400" y2="120" style="stroke:var(--hue-d);" stroke-width="1" opacity="0.35"/>
  <line x1="80" y1="0" x2="80" y2="132" style="stroke:var(--hue-d);" stroke-width="1" opacity="0.2"/>
  <line x1="220" y1="0" x2="220" y2="132" style="stroke:var(--hue-d);" stroke-width="1" opacity="0.2"/>
  <line x1="340" y1="0" x2="340" y2="132" style="stroke:var(--hue-d);" stroke-width="1" opacity="0.2"/>
  <path d="M0,105 L60,95 L120,100 L180,70 L240,75 L300,45 L360,50 L400,25" fill="none" style="stroke:var(--hue);" stroke-width="3" opacity="0.75" filter="url(#softBlur)"/>
  {_ART_GRAIN_RECT}
</svg>""",
    3: f"""<svg class="cc-art" viewBox="0 0 400 132" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <g filter="url(#artBlur)" opacity="0.7">
    <ellipse cx="70" cy="110" rx="32" ry="9" style="fill:var(--hue-d);"/>
    <ellipse cx="70" cy="98" rx="32" ry="9" style="fill:var(--hue);"/>
    <ellipse cx="70" cy="86" rx="32" ry="9" style="fill:var(--hue-d);"/>
    <ellipse cx="70" cy="74" rx="32" ry="9" style="fill:var(--hue);"/>
    <ellipse cx="180" cy="115" rx="30" ry="8" style="fill:var(--hue);"/>
    <ellipse cx="180" cy="104" rx="30" ry="8" style="fill:var(--hue-d);"/>
    <ellipse cx="180" cy="93" rx="30" ry="8" style="fill:var(--hue);"/>
    <ellipse cx="300" cy="105" rx="34" ry="9" style="fill:var(--hue-d);"/>
    <ellipse cx="300" cy="92" rx="34" ry="9" style="fill:var(--hue);"/>
    <ellipse cx="300" cy="79" rx="34" ry="9" style="fill:var(--hue-d);"/>
    <ellipse cx="300" cy="66" rx="34" ry="9" style="fill:var(--hue);"/>
    <ellipse cx="300" cy="53" rx="34" ry="9" style="fill:var(--hue-d);"/>
  </g>
  {_ART_GRAIN_RECT}
</svg>""",
    5: f"""<svg class="cc-art" viewBox="0 0 400 132" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <g fill="none" opacity="0.55">
    <path d="M-20,20 C60,60 100,-20 180,20 S300,60 420,20" style="stroke:var(--hue-d);" stroke-width="1.2"/>
    <path d="M-20,40 C60,80 100,0 180,40 S300,80 420,40" style="stroke:var(--hue);" stroke-width="1.2"/>
    <path d="M-20,60 C60,100 100,20 180,60 S300,100 420,60" style="stroke:var(--hue-d);" stroke-width="1.2"/>
    <path d="M-20,80 C60,120 100,40 180,80 S300,120 420,80" style="stroke:var(--hue);" stroke-width="1.2"/>
    <path d="M-20,100 C60,140 100,60 180,100 S300,140 420,100" style="stroke:var(--hue-d);" stroke-width="1.2"/>
    <path d="M-20,30 C60,-10 100,70 180,30 S300,-10 420,30" style="stroke:var(--hue);" stroke-width="1"/>
    <path d="M-20,70 C60,30 100,110 180,70 S300,30 420,70" style="stroke:var(--hue-d);" stroke-width="1"/>
    <path d="M-20,110 C60,70 100,150 180,110 S300,70 420,110" style="stroke:var(--hue);" stroke-width="1"/>
  </g>
  {_ART_GRAIN_RECT}
</svg>""",
    6: f"""<svg class="cc-art" viewBox="0 0 400 132" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <g filter="url(#artBlur)" opacity="0.65">
    <rect x="20" y="105" width="34" height="27" style="fill:var(--hue-d);"/>
    <rect x="70" y="90" width="34" height="42" style="fill:var(--hue);"/>
    <rect x="120" y="95" width="34" height="37" style="fill:var(--hue-d);"/>
    <rect x="170" y="70" width="34" height="62" style="fill:var(--hue);"/>
    <rect x="220" y="55" width="34" height="77" style="fill:var(--hue-d);"/>
    <rect x="270" y="60" width="34" height="72" style="fill:var(--hue);"/>
    <rect x="320" y="30" width="34" height="102" style="fill:var(--hue-d);"/>
  </g>
  {_ART_GRAIN_RECT}
</svg>""",
}


def render_chapter_art(art_style: int, uid: str) -> str:
    """Style 4 (Ticker Wave) embeds its own local gradient, which needs a
    per-card-unique id -- with a static template, duplicate ids on one page
    would all resolve to the first card's --hue (a real bug on multi-card
    index pages, unlike the single-instance style-picker mockup)."""
    if art_style == 4:
        return f"""<svg class="cc-art" viewBox="0 0 400 132" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="tickerFade-{uid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" style="stop-color:var(--hue);stop-opacity:0.55"/>
      <stop offset="100%" style="stop-color:var(--hue);stop-opacity:0"/>
    </linearGradient>
  </defs>
  <path d="M0,90 Q40,60 80,75 T160,50 T240,70 T320,30 T400,45 L400,132 L0,132 Z" fill="url(#tickerFade-{uid})" filter="url(#softBlur)"/>
  <path d="M0,90 Q40,60 80,75 T160,50 T240,70 T320,30 T400,45" fill="none" style="stroke:var(--hue-d);" stroke-width="2.5" opacity="0.7" filter="url(#softBlur)"/>
  <circle cx="160" cy="50" r="4" style="fill:var(--hue-d);" opacity="0.6"/>
  <circle cx="320" cy="30" r="4" style="fill:var(--hue-d);" opacity="0.6"/>
  {_ART_GRAIN_RECT}
</svg>"""
    return ART_TEMPLATES[art_style]


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
/* Track-index-only: the parenthetical part of a track's title (e.g. "(The
   Systemic Conditioning of Americans)") shown as its own line under the h1,
   rather than crowding the h1 itself or every breadcrumb/nav mention. */
.header-subtitle { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(15px,2vw,19px); font-weight: 400; color: #7A9AB5; line-height: 1.4; margin-top: -6px; margin-bottom: 14px; }
/* Landing-page-only: "Plenee" set large (matching the h1 below), the
   "Academy" pill sitting underneath it rather than "Plenee Academy" both
   inside one small chip. */
.landing-brand { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(32px,4vw,52px); font-weight: 700; color: #fff; letter-spacing: -1px; line-height: 1.15; margin-bottom: 18px; }

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
.track-wrap { max-width: 1080px; margin: 0 auto; padding: 56px 48px 88px; }
.chapters-heading { font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--teal-d); margin-bottom: 18px; }
.chapter-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }
.chap-card {
  --hue: var(--teal); --hue-l: var(--teal-l); --hue-d: var(--teal-d);
  display: flex; flex-direction: column;
  border: 1.5px solid var(--border); border-radius: 18px; overflow: hidden;
  text-decoration: none; background: #fff;
  transition: border-color .2s, transform .2s, box-shadow .2s;
}
.chap-card:hover { border-color: var(--hue); transform: translateY(-3px); box-shadow: 0 14px 34px rgba(12,25,41,.09); }
.cc-tile { height: 132px; position: relative; overflow: hidden; background: var(--hue-l); }
.cc-art { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
.cc-art .grain { mix-blend-mode: multiply; opacity: .5; }
.cc-body { padding: 22px 24px 20px; display: flex; flex-direction: column; flex: 1; }
.cc-body h3 { font-family: Georgia, 'Times New Roman', serif; font-size: 18px; font-weight: 700; color: var(--navy); line-height: 1.3; margin-bottom: 10px; }
.cc-body p { font-size: 14px; color: var(--muted); line-height: 1.6; margin-bottom: 16px; flex: 1; }
.cc-cta { font-size: 13px; font-weight: 700; letter-spacing: .2px; display: inline-flex; align-items: center; gap: 6px; margin-top: auto; color: var(--hue-d); }
.cc-cta svg { width: 14px; height: 14px; transition: transform .2s; }
.chap-card:hover .cc-cta svg { transform: translateX(3px); }

@media (max-width: 860px) {
  .chapter-grid { grid-template-columns: 1fr; }
}

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

/* ─── OVERVIEW (track index pages) ─── */
/* Widened to match the chapter-card grid below it (.track-wrap, 1080px) and
   split its two paragraphs into side-by-side columns when there's room;
   collapses to a single stacked column at the same breakpoint the card grid
   itself collapses at, so the two never disagree about "narrow." */
.overview-wrap { max-width: 1080px; margin: 0 auto; padding: 32px 48px 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px 40px; }
.overview-wrap p { font-size: 16px; color: var(--muted); line-height: 1.75; margin-bottom: 18px; }
.overview-wrap p:last-child { margin-bottom: 0; }
@media (max-width: 860px) {
  .overview-wrap { grid-template-columns: 1fr; }
}

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

.landing-overview {
  max-width: 1080px; margin: 44px auto 0; padding: 0 48px;
  display: grid; grid-template-columns: 1fr 1fr; gap: 24px; align-items: center;
}
.landing-overview-logo { display: flex; align-items: center; justify-content: center; }
.landing-overview-logo svg { width: 100%; max-width: 224px; height: auto; display: block; }
/* #overview-needle's rotation is applied as a native SVG transform attribute
   (via JS), not a CSS transform -- that pivots reliably at SVG-space (0,0),
   the pivot/hub position, matching how the source logo's own static
   transform="rotate(43)" already worked. CSS transform-origin tricks on SVG
   (transform-box: view-box, etc.) proved inconsistent across browsers. */
.landing-overview p { font-size: 16px; color: var(--muted); line-height: 1.75; margin: 0; }

.volume-section { max-width: 1080px; margin: 0 auto; padding: 64px 48px 8px; }
.volume-section + .volume-section { padding-top: 12px; }
.volume-kicker { font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px; }
.volume-section.v1 .volume-kicker { color: var(--teal-d); }
.volume-section.v2 .volume-kicker { color: #17434F; }
.volume-h2 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(26px,3.2vw,36px); font-weight: 700; color: var(--navy); letter-spacing: -.5px; margin-bottom: 8px; }
.volume-sub { color: var(--muted); font-size: 16px; margin-bottom: 40px; max-width: 620px; }

/* Each card sets its own --hue/--hue-l/--hue-d inline (see TRACK_HUES: the 6
   thematic groups -- Foundations=teal, Know-your-opponent=orange,
   Flywheel=gold, Life admin=slate, Protection/crisis=rose, Psychology=indigo). */
.track-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; margin-bottom: 8px; }
.track-card {
  --hue: var(--teal); --hue-l: var(--teal-l); --hue-d: var(--teal-d);
  display: flex; flex-direction: column;
  border: 1.5px solid var(--border); border-radius: 18px; overflow: hidden;
  text-decoration: none; background: #fff;
  transition: border-color .2s, transform .2s, box-shadow .2s;
}
.track-card:hover { border-color: var(--hue); transform: translateY(-3px); box-shadow: 0 14px 34px rgba(12,25,41,.09); }

.tc-tile { height: 108px; display: flex; align-items: center; justify-content: center; position: relative; background: var(--hue-l); }
.tc-tile svg { width: 44px; height: 44px; color: var(--hue-d); }
.tc-num {
  position: absolute; top: 14px; right: 16px;
  font-family: Georgia, serif; font-weight: 700; font-size: 13px;
  padding: 3px 10px; border-radius: 100px; background: rgba(255,255,255,.6);
  color: var(--hue-d);
}

.tc-body { padding: 24px 26px 22px; display: flex; flex-direction: column; flex: 1; }
.tc-body h3 { font-family: Georgia, 'Times New Roman', serif; font-size: 19px; font-weight: 700; color: var(--navy); line-height: 1.3; margin-bottom: 2px; }
.tc-subtitle { font-family: Georgia, 'Times New Roman', serif; font-size: 13px; font-style: italic; color: var(--muted); margin-bottom: 10px; }
.tc-body p { font-size: 14.5px; color: var(--muted); line-height: 1.65; margin-bottom: 18px; flex: 1; }
.tc-cta { font-size: 13px; font-weight: 700; letter-spacing: .2px; display: inline-flex; align-items: center; gap: 6px; margin-top: auto; color: var(--hue-d); }
.tc-cta svg { width: 14px; height: 14px; transition: transform .2s; }
.track-card:hover .tc-cta svg { transform: translateX(3px); }

@media (max-width: 860px) {
  .track-grid { grid-template-columns: 1fr; }
}

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
  .landing-overview { padding: 0 20px; grid-template-columns: 1fr; text-align: center; }
  .landing-overview-logo svg { max-width: 96px; }
  .volume-section { padding: 48px 20px 8px; }
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


TRACK_PAREN_SUBTITLE_RE = re.compile(r"^(.*?)\s*\((.+)\)\s*$")


def split_paren_title(title: str) -> tuple[str, str | None]:
    """Track titles from the source header sometimes carry a parenthetical
    subtitle baked into the same string, e.g. 'The Debt Trap (The Systemic
    Conditioning of Americans)'. Splits that into a bare main title (used
    anywhere the full title would be too long -- breadcrumbs, nav links,
    search labels) and the subtitle on its own (shown as a second line under
    the title on cards and page headers, never inline)."""
    m = TRACK_PAREN_SUBTITLE_RE.match(title)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return title, None


def search_html() -> str:
    """The Academy landing page's own corpus-wide search box. Track index
    pages no longer embed one -- they link out to this one instead."""
    return """<div class="academy-search-wrap" id="academy-search-wrap" data-base="">
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
    track_title_bare, _track_subtitle = split_paren_title(track_title)
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
            f'      <div class="cn-title">Back to {esc(track_title_bare)}</div>\n'
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
            f'      <div class="cn-title">Back to {esc(track_title_bare)}</div>\n'
            "    </a>"
        )

    body = f"""<div class="crumb">
  <a href="../index.html">Academy</a>
  <span>›</span>
  <a href="index.html">{esc(track_title_bare)}</a>
  <span>›</span>
  <span>{esc(display_chapter_id(chapter["id"]))}</span>
  <span style="margin-left:auto"></span>
  <a href="../index.html#search">🔍 Search Academy</a>
</div>

<div class="chapter-wrap">
  <div class="chapter-eyebrow">T.{track_info.display_num} · Chapter {esc(display_chapter_id(chapter["id"]))}</div>
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
        "trk": track_title_bare,
        "n": f'Chapter {display_chapter_id(chapter["id"])}',
        "u": f'{track_slug}/{chapter["slug"]}.html',
        "x": " ".join(search_text_parts).strip()[:SEARCH_SNIPPET_CAP],
    }
    return page_html, search_entry


def overview_html(paragraphs: tuple[str, str]) -> str:
    paras = "\n".join(f"  <p>{esc(p)}</p>" for p in paragraphs)
    return f'<div class="overview-wrap">\n{paras}\n</div>'


# Landing-page-only overview: rotating compass/logo mark beside the single
# ACADEMY_OVERVIEW paragraph. Deliberately a separate renderer from
# overview_html() above -- that one's still used unchanged by every track
# index page with TRACK_OVERVIEWS's two-paragraph tuples.
LANDING_COMPASS_SVG = """<svg class="landing-overview-logo-mark" viewBox="-210 -210 420 420" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="needle-bright" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#FFD08A"/>
      <stop offset="100%" stop-color="#F9AE4C"/>
    </linearGradient>
  </defs>

  <!-- Compass face -- fixed, does not rotate -->
  <g class="compass-face">
    <circle cx="0" cy="0" r="192" fill="none" stroke="#DDE8F0" stroke-width="3"/>
    <line x1="0" y1="-192" x2="0" y2="-176" stroke="#DDE8F0" stroke-width="3"/>
    <line x1="0" y1="192" x2="0" y2="176" stroke="#DDE8F0" stroke-width="3"/>
    <line x1="-192" y1="0" x2="-176" y2="0" stroke="#DDE8F0" stroke-width="3"/>
    <line x1="192" y1="0" x2="176" y2="0" stroke="#DDE8F0" stroke-width="3"/>
    <g font-family="Georgia, 'Times New Roman', serif" font-weight="700" text-anchor="middle">
      <text x="0" y="-155" dominant-baseline="middle" font-size="34" fill="#0C1929">N</text>
      <text x="0" y="155" dominant-baseline="middle" font-size="28" fill="#8A9EB0">S</text>
      <text x="155" y="0" dominant-baseline="middle" font-size="28" fill="#8A9EB0">E</text>
      <text x="-155" y="0" dominant-baseline="middle" font-size="28" fill="#8A9EB0">W</text>
    </g>
  </g>

  <!-- Needle assembly -- JS-animated, oscillates randomly within the NW-to-NE arc -->
  <g id="overview-needle" fill="none" stroke-linecap="round">
    <line x1="-152" y1="0" x2="-50" y2="0" stroke="#8A9EB0" stroke-width="7.5" opacity="0.55"/>
    <line x1="50" y1="0" x2="152" y2="0" stroke="#8A9EB0" stroke-width="7.5" opacity="0.55"/>
    <path d="M -23,-12 Q -52,42 -80,137" stroke="#0FA8BC" stroke-width="8.5" opacity="0.72"/>
    <path d="M  23,-12 Q  52,42  80,137" stroke="#0FA8BC" stroke-width="8.5" opacity="0.72"/>
    <path d="M -23,-12 Q -61,52 -105,168" stroke="#0FA8BC" stroke-width="4.2" opacity="0.34"/>
    <path d="M  23,-12 Q  61,52  105,168" stroke="#0FA8BC" stroke-width="4.2" opacity="0.34"/>
    <path d="M -23,-12 Q -70,63 -126,200" stroke="#0FA8BC" stroke-width="1.8" opacity="0.16"/>
    <path d="M  23,-12 Q  70,63  126,200" stroke="#0FA8BC" stroke-width="1.8" opacity="0.16"/>
    <polygon points="0,-172 -25,-39 7,-32" fill="url(#needle-bright)" stroke="none"/>
    <polygon points="0,-172 7,-32 25,-39" fill="#C0822F" stroke="none"/>
    <circle cx="0" cy="0" r="20" fill="#fff" stroke="#FFB256" stroke-width="7"/>
    <circle cx="0" cy="0" r="10" fill="#FFB256" stroke="none"/>
  </g>
</svg>"""

LANDING_COMPASS_JS = r"""(function(){
  var needle = document.getElementById('overview-needle');
  if (!needle) return;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  needle.setAttribute('transform', 'rotate(0)');
  if (reduceMotion) return;

  var current = 0;

  function easeInOutCubic(t){
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function animateTo(target, duration){
    var start = current;
    var startTime = null;
    function frame(ts){
      if (startTime === null) startTime = ts;
      var t = Math.min((ts - startTime) / duration, 1);
      var angle = start + (target - start) * easeInOutCubic(t);
      needle.setAttribute('transform', 'rotate(' + angle.toFixed(2) + ')');
      if (t < 1) {
        requestAnimationFrame(frame);
      } else {
        current = target;
        setTimeout(swing, 500 + Math.random() * 900);
      }
    }
    requestAnimationFrame(frame);
  }

  function swing(){
    // Stay pointing generally north: random angle within NW (-45deg) to NE (+45deg).
    var target = Math.random() * 90 - 45;
    var duration = 1600 + Math.random() * 1600;
    animateTo(target, duration);
  }
  swing();
})();"""


def landing_overview_html(paragraph: str) -> str:
    return (
        '<div class="landing-overview">\n'
        f'  <div class="landing-overview-logo">\n{LANDING_COMPASS_SVG}\n  </div>\n'
        f'  <p>{esc(paragraph)}</p>\n'
        "</div>\n"
        f"<script>{LANDING_COMPASS_JS}</script>"
    )


def render_index_page(track_info, track_title: str, chapters: list[dict]) -> str:
    hue, hue_l, hue_d = TRACK_HUES[track_info.track_slug]
    chapter_meta = CHAPTER_META[track_info.track_slug]
    title_bare, title_subtitle = split_paren_title(track_title)
    title_subtitle_html = (
        f'\n  <p class="header-subtitle">{esc(title_subtitle)}</p>' if title_subtitle else ""
    )
    cards = []
    for c in chapters:
        headline = esc(c["title"].split(":", 1)[0].strip())
        overview, art_style = chapter_meta[c["id"]]
        uid = f'{track_info.track_slug}-{c["id"]}'.replace(".", "-")
        cards.append(
            f'  <a class="chap-card" href="{c["slug"]}.html" '
            f'style="--hue:{hue};--hue-l:{hue_l};--hue-d:{hue_d};">\n'
            f'    <div class="cc-tile">{render_chapter_art(art_style, uid)}</div>\n'
            '    <div class="cc-body">\n'
            f'      <h3>{headline}</h3>\n'
            f'      <p>{esc(overview)}</p>\n'
            '      <span class="cc-cta">Read chapter '
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
            'stroke-linecap="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>\n'
            "    </div>\n"
            "  </a>"
        )

    body = f"""<div class="page-header">
  <div class="page-kicker">T.{track_info.display_num}</div>
  <h1>{esc(title_bare)}</h1>{title_subtitle_html}
</div>

<div class="crumb">
  <a href="../index.html">Academy</a>
  <span>›</span>
  <span>{esc(title_bare)}</span>
  <span style="margin-left:auto"></span>
  <a href="../index.html#search">🔍 Search Academy</a>
</div>

{overview_html(TRACK_OVERVIEWS[track_info.track_slug])}

{TRACK_GRAPHICS.get(track_info.track_slug, "")}

{ART_FILTER_DEFS}

<div class="track-wrap">
  <div class="chapters-heading">{len(chapters)} Chapters</div>
  <div class="chapter-grid">
{chr(10).join(cards)}
  </div>
</div>"""

    return PAGE_TEMPLATE.format(page_title=esc(title_bare), style=STYLE_BLOCK, body=body,
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
            hue, hue_l, hue_d = TRACK_HUES[t.track_slug]
            overview_p1 = TRACK_OVERVIEWS[t.track_slug][0]
            title_bare, title_subtitle = split_paren_title(smart_title(t.title))
            subtitle_html = (
                f'\n      <p class="tc-subtitle">{esc(title_subtitle)}</p>' if title_subtitle else ""
            )
            parts.append(
                f'  <a class="track-card" href="{t.track_slug}/index.html" '
                f'style="--hue:{hue};--hue-l:{hue_l};--hue-d:{hue_d};">\n'
                f'    <div class="tc-tile"><span class="tc-num">{esc(t.display_num)}</span>\n'
                f'      {render_track_icon(t.track_slug, size=44)}\n'
                "    </div>\n"
                '    <div class="tc-body">\n'
                f'      <h3>{esc(title_bare)}</h3>{subtitle_html}\n'
                f'      <p>{esc(overview_p1)}</p>\n'
                '      <span class="tc-cta">Start reading '
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
                'stroke-linecap="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>\n'
                "    </div>\n"
                "  </a>"
            )
        return "\n".join(parts)

    v1_tracks = [t for t in track_order if t.volume == 1]
    v2_tracks = [t for t in track_order if t.volume == 2]

    search_json = json.dumps(search_index, ensure_ascii=False).replace("</script", "<\\/script")

    body = f"""<div class="page-header">
  <div class="landing-brand">Plenee</div>
  <div class="page-kicker">Academy</div>
  <h1>A Guide for Wealth</h1>
  <p>Free financial education grounded in real research, not sales pitches — a reference library for every decision, and a psychology track for the biases quietly running your money.</p>
</div>

<p class="academy-pullquote">&ldquo;Rich is what people see. Wealth is what they don't.&rdquo;</p>

<div class="track-search-wrap">
{search_html()}
</div>

{landing_overview_html(ACADEMY_OVERVIEW)}

<div class="volume-section v1">
  <div class="volume-kicker">Reference Library</div>
  <h2 class="volume-h2">A Guide for Wealth</h2>
  <p class="volume-sub">Fifteen tracks, read in any order — pick whatever's relevant to the decision in front of you right now.</p>
  <div class="track-grid">
{cards_html(v1_tracks)}
  </div>
</div>

<div class="volume-section v2">
  <div class="volume-kicker">A Narrative Read</div>
  <h2 class="volume-h2">The Psychology of Money</h2>
  <p class="volume-sub">Two tracks, meant to be read in order — the mental wiring behind every money decision.</p>
  <div class="track-grid">
{cards_html(v2_tracks)}
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


def write_index_pages(track_results: list[dict]) -> None:
    for r in track_results:
        index_html = render_index_page(r["track_info"], r["track_title"], r["chapters"])
        index_path = r["outdir"] / "index.html"
        index_path.write_text(index_html, encoding="utf-8")
        print(f"  wrote {index_path.relative_to(WEBSITE_DIR)}")


def generate(source_filename: str) -> None:
    """Single-track regeneration -- fast for iterating on one file's content.
    Track index pages no longer embed their own search box (they link to the
    Academy landing page's corpus-wide search instead), so this no longer
    needs a cross-track search index at all."""
    idx = build_index()
    result = generate_track_pages(source_filename, idx)
    write_index_pages([result])


def generate_all() -> None:
    """Regenerate every track from current source and rebuild the Academy
    landing page, which embeds the one shared cross-track search index (its
    reading order/grouping comes from academy_curriculum.md, not from
    file-discovery order). Track index pages link out to that search rather
    than embedding their own."""
    idx = build_index()
    files = sorted(ACADEMY_SRC.glob("*_expanded.md"))
    results = [generate_track_pages(str(f), idx) for f in files]
    global_search_index = [e for r in results for e in r["search_entries"]]
    write_index_pages(results)
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
