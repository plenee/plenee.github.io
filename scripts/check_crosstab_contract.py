#!/usr/bin/env python3
"""Verify the cross-tab contract still matches on both sides.

website/nav.js and plenee_app/frontend/src/utils/crossTab.ts are two halves of ONE
mechanism living in two repos that deploy independently. They agree only by having the
same five strings written into both. Rename one on either side and nothing errors: the
switcher quietly opens duplicate tabs instead of focusing, and plenee.com's account menu
shows signed-out forever because it is reading a cookie nobody writes any more.

A comment in each file is not a guard — it only helps someone who already went looking.
This is the guard. Run it after touching either file:

    python3 scripts/check_crosstab_contract.py

Exit 0 = the two sides agree. Exit 1 = they have drifted. Exit 2 = could NOT check,
which is deliberately not a pass: a checker that goes quiet when it cannot see one side
is worse than no checker, because it reads as green.
"""
import os
import sys
from pathlib import Path

# Every string both sides must spell identically.
SHARED = [
    "plenee_auth_hint",     # the display-only signed-in hint cookie
    "plenee_tab_",          # heartbeat cookie prefix, + surface name
    "plenee-home",          # window.name / window.open target
    "plenee-academy",
    "plenee-navigator",
]

WEBSITE = Path(__file__).resolve().parents[1]
NAV_JS = WEBSITE / "nav.js"

# The app lives in a sibling repo. Overridable, because a checkout is not guaranteed
# to sit where this one does.
CROSSTAB = Path(os.environ.get(
    "PLENEE_CROSSTAB",
    WEBSITE.parent / "plenee_app" / "frontend" / "src" / "utils" / "crossTab.ts",
))


def main() -> int:
    if not NAV_JS.exists():
        print(f"CANNOT CHECK: {NAV_JS} is missing.", file=sys.stderr)
        return 2
    if not CROSSTAB.exists():
        print(f"CANNOT CHECK: the app half is not at {CROSSTAB}.\n"
              f"  Set PLENEE_CROSSTAB to its path, or check out plenee_app beside this repo.\n"
              f"  Reporting 'cannot check' rather than 'ok' on purpose — a silent pass here\n"
              f"  would hide exactly the drift this script exists to catch.", file=sys.stderr)
        return 2

    nav = NAV_JS.read_text(encoding="utf-8")
    app = CROSSTAB.read_text(encoding="utf-8")

    missing = []
    for name in SHARED:
        in_nav, in_app = name in nav, name in app
        if not (in_nav and in_app):
            where = "nav.js" if not in_nav else "crossTab.ts"
            missing.append(f"  {name!r} is absent from {where}")

    if missing:
        print("CROSS-TAB CONTRACT BROKEN — the two halves have drifted:", file=sys.stderr)
        print("\n".join(missing), file=sys.stderr)
        print(f"\n  website: {NAV_JS}\n  app:     {CROSSTAB}\n"
              "  Both files must spell all five identically, or tab focus and the\n"
              "  signed-in menu fail silently in production.", file=sys.stderr)
        return 1

    print(f"cross-tab contract ok — all {len(SHARED)} names match")
    print(f"  {NAV_JS.name} <-> {CROSSTAB.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
