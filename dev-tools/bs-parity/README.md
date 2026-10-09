# BS2 vs BS5 parity diff tool

Exhaustive, low-token comparison of a page rendered on the old Bootstrap 2
app (`http://localhost:8890`) against its Bootstrap 5 port
(`http://localhost:8888`), used while porting Root the Box's templates. See
`/BS5-ADMIN-DASHBOARD-PARITY.md` and `/BS5-PLAYER-PAGES-PARITY.md` for the
methodology this supports and the findings produced with it.

No new dependencies: extraction runs through Claude Code's built-in Browser
tool (`javascript_tool`, read-only inspection only), and `diff.py` is
Python stdlib only.

## Workflow

1. Log in to both apps in two Browser tool tabs, resize both to the target
   viewport width, navigate both to the corresponding page.
2. Run the contents of `extract.js` via `javascript_tool` in each tab.
   The result is large (a real page is 150-500KB of JSON) and will usually
   get written to a tool-result file rather than returned inline -- read
   that file's `[0]["text"]` field (ignore any trailing "Tab Context"
   chunk) and write it verbatim to `old-<page>-<width>.json` /
   `new-<page>-<width>.json`. Never read the raw JSON into your own
   context; only the diff report below is worth reading directly.
3. `python3 diff.py old.json new.json --tol 2 --out report.md`
4. Read `report.md` (small -- only actual diffs) to drive fixes.

## What it does well

- Finds structural adds/removes (a missing/extra wrapper div, a component
  that changed tag) and, for everything it can align, every computed-style
  and geometry property that actually differs -- validated against the
  already-known admin-dashboard bugs in BS5-ADMIN-DASHBOARD-PARITY.md,
  where it independently rediscovered the exact same numbers (e.g. the
  documented 283.8px vs 248.9px sidebar-width gap at ~1280px, and the
  "Resume Registration" label's 2-line-wrap height).
- Ignores `boxSizing` by default (`IGNORE_PROPS` in `diff.py`) since BS5's
  global border-box reset makes it differ on literally every element and
  carries no signal.
- Never matches on raw class name, so expected class renames from the port
  (`.well` -> `.card`, etc.) don't show up as noise.

## Known limitations -- read the diff, don't trust it blindly

- Alignment is heuristic (tag + text/href/data-attrs/id, then a narrow
  positional fallback -- see the module docstring in `diff.py` for why a
  naive whole-list positional fallback was tried first and rejected). It
  will occasionally mismatch a pair of leaf elements that were deeply
  restructured between versions (e.g. BS2's literal `×` text-glyph close
  button vs BS5's contentless SVG-background `.btn-close` sometimes pairs
  against the wrong sibling). When a diff under a heading looks nonsensical
  (wildly different rect/role), don't chase it as a bug -- go look at the
  actual page/markup instead.
- It is a *style + geometry* snapshot, not a behavior test. It cannot see
  anything that only appears on hover/focus/scroll (popovers, `:hover`
  rules, `position: sticky`) -- verify those manually.
- Always confirm both apps are in the same config/data state before
  diffing (`options.teams`, `options.show_mvp`, game-started state, etc.)
  or you'll get real-looking "structural-only" noise from legitimate
  conditional rendering, not port bugs.
