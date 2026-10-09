# BS2 → BS5 Player-Facing Pages Parity

Findings and methodology from a session bringing five player-facing pages to
BS2 visual/structural parity under the Cyborg theme, verified across desktop
widths 1280/1440/1600/1920px. Companion doc to
[BS5-ADMIN-DASHBOARD-PARITY.md](BS5-ADMIN-DASHBOARD-PARITY.md), which covers
the admin dashboard (a **separate, still-open** effort — not touched here).
Written so a fresh conversation can pick up where this one left off without
re-deriving root causes already found.

## Scope

**In scope, all fixed this session**: Login (`public/login.html`),
Registration (`public/registration.html`), User Home
(`user/home.html`), Scoreboard Summary + Teams (`scoreboard/summary.html`,
`scoreboard/teams.html`), Missions list + box detail
(`missions/view.html`, `missions/box.html`). Cyborg theme only.

**Explicitly out of scope**: the admin dashboard (separate doc, still open),
all themes except Cyborg, mobile/tablet widths (<1280px), restoring BS2's
true nested-flyout "New Flag" dropdown (deferred).

**Known gaps within the in-scope pages** (not fixed — config/data
limitations, not bugs):
- Scoreboard's `options.teams`/`options.show_mvp`/`scoreboard_right_image`
  branches (a `col-md-3` MVP/image card, a team-avatar grid) aren't
  reachable with the currently seeded game config. The same fix mechanism
  was applied by inference from the branch that does render, but never
  screenshotted live. Re-verify if that config ever gets flipped on.
- Missions' `.levelheader` (h3/h4) `display:inline` BS2 behavior (meant to
  put a level name and its description on the same line) couldn't be
  visually confirmed — no seeded level currently has both a name and a
  description at once. `.card` blockifies these by default; if this ever
  needs fixing it's a markup change (shared wrapper), not CSS alone.

## Methodology (built on, and extending, the admin-dashboard doc's)

1. **A purpose-built diff tool**, `dev-tools/bs-parity/` (`extract.js` +
   `diff.py` + `README.md`), built and validated this session. It walks the
   full DOM via the Browser tool's `javascript_tool` (read-only — capturing
   every visible element's `getBoundingClientRect()` and ~60 computed-style
   properties) and diffs two such dumps with a heuristic tag+text/href/
   data-attr alignment (falls back to a narrow positional match, never a
   naive whole-list one — see the module docstring in `diff.py` for why the
   naive version was tried first and rejected: one extra wrapper element
   cascades into misaligning every sibling after it). Validated by
   independently rediscovering the admin-dashboard doc's exact documented
   numbers before being trusted on new pages. Ignores `boxSizing` (universal
   BS5 border-box-reset noise). **Caveat discovered this session**: two
   accounts with different seeded game data (e.g. `foo` on 8890 vs 8888)
   produce full-page structural-diff noise from mismatched content, not real
   bugs — prefer targeted geometry/computed-style checks over the tool's
   full-page mode when the two apps' data isn't identical.
2. **Cache-busting is mandatory after every CSS edit, every time, no
   exceptions** — confirmed to produce a fully misleading "still broken"
   reading at least twice this session. Run in every tab before re-measuring:
   ```js
   [...document.querySelectorAll('link[rel=stylesheet]')].forEach(l=>{
     const u=new URL(l.href); u.searchParams.set('bust',Date.now()); l.href=u.toString();
   })
   ```
   After a **template** change (not just CSS), a full navigate is required,
   not just a cache-bust. When a page looks unexpectedly broken after a fix,
   check `[...document.styleSheets].find(s=>s.href.includes('...')).cssRules`
   for what's *actually* loaded before assuming the fix is wrong.
3. **A scoped fix can break something else on the same page.** Happened
   twice this session (zeroing Registration's row gutter exposed a masked
   `.form-horizontal` label-width conflict; the User Home column-width fix
   needed a companion gutter fix to avoid a new gap regression). Always
   re-screenshot and re-check the **whole** page after a fix, not just the
   one property being fixed.
4. **Session/login flakiness**: UI click-to-submit was unreliable in this
   browser-tool environment across many rounds. Prefer submitting forms
   directly via JS: `document.querySelector('form').requestSubmit()`. To
   trigger a Bootstrap modal for inspection without a working click:
   `bootstrap.Modal.getOrCreateInstance(el).show()` (BS5) /
   `$(el).modal('show')` (BS2, jQuery-based).
5. **Screenshots can render at misleading apparent scale** between browser
   tabs with different `devicePixelRatio` (observed: identical CSS-pixel
   viewports rendering visually tiny in one tab vs normal in another, purely
   a screenshot-capture artifact). Trust `getBoundingClientRect()`/computed
   style numbers over eyeballing screenshot pixel sizes; only use screenshots
   for structural sanity checks once the numbers already agree.
6. **Independently re-verify every subagent's claims** against the live
   pages before accepting — caught real gaps every single round this
   session (an unfixed input-width bug on Registration that had been
   explicitly flagged and skipped; a stale-cache false-positive on
   Registration's grid fix; the `.pagination` margin gap the user caught
   after the fact on Scoreboard). Delegate root-caused mechanisms and exact
   measured numbers to subagents, not just symptoms.

## The recurring bug patterns (read this before touching any new page)

These are not one-off bugs — every single page fixed this session hit
several of them. Check for all of them by default on any future page.

### 1. `.card`'s `flex: 1 1 auto` silently overrides an intended fixed/percentage width
BS5's `.card` is `display:flex` and (unlike a plain grid column) defaults to
`flex-grow:1; flex-shrink:1`. Any `.card` that's *also* supposed to be a
specific grid-column width — via a `col-md-N` class, or an inline
`style="width: N%"` inherited from the port — will instead grow to
consume whatever flex space is left over and ignore that width entirely.
This bit User Home (a `col-md-5.card` with a correct inline `width:46%`
that never took effect), Scoreboard's results card (`col-md-10.card`
measuring 130px too wide), and would bite any future page with the same
combination. **Fix**: `flex-grow:0; flex-shrink:0;` on the specific card,
plus correcting its width to the real BS2 percentage/px (BS5's own
`col-md-N` default is usually close but not exact — see pattern 7).

### 2. `.row > *` resets `margin-top` on any direct child, beating a plain element selector
Bootstrap 5 ships a row-gap utility rule, `.row > * { margin-top:
var(--bs-gutter-y) }` (defaults to 0). It has **one class of specificity**
(`.row` + universal selector), which beats a plain type selector like `h1`
— so it silently zeroes the sitewide heading-margin restoration
(`cyborg.min.css`'s `h1,h2,...{margin:10px 0}`) for any heading sitting
**directly** inside a `.row`, *regardless of source order in the
stylesheet*. This is a genuine specificity trap, not a caching or ordering
issue — confirmed by injecting a `<style>` rule at the very end of
`<head>` and watching it still lose. Found on Scoreboard's page title
(rendered 20px higher than BS2, misaligned with the "Players per page"
control next to it). **Only bites when the element is a direct `.row`
child** — the same heading one level deeper inside a `.col-*`/`.card` is
unaffected (confirmed: Missions' identical-looking heading, nested inside
`.col-md-10`, was never affected). **Fix**: give the specific
page-scoped selector for that heading enough specificity to win (e.g.
`.scoreboard-summary > .row:first-child > h1.offset-md-1 { margin-top:
10px; }`) rather than touching the sitewide rule.

### 3. A `float` trick stops working once its container becomes `display:flex`
BS2 leaned on `float:right`/`float:left` + negative margins for a lot of
positioning (a rank badge beside a name, pagination controls beside a
title). Per spec, `float` is a no-op on a flex item — the element instead
resolves via flex's own auto-sizing (often "fill 100% of the row", stacking
everything via `flex-wrap` instead of positioning beside it). Two different
fixes depending on intent:
  - If the float was meant to sit **beside** a sibling in normal flow →
    wrap both in `d-flex justify-content-between` (used for User Home's
    "Rank" block and previously for the admin dashboard's Notifications
    title).
  - If the float was meant to **escape the flow entirely** and hug a
    corner → `position:absolute` with explicit `top`/`right`/`left:auto`/
    `width:auto` (used for Scoreboard's pagination controls — all four of
    those properties had to be stated explicitly; leaving any of them
    implicit made the browser skip the CSS2.1 shrink-to-fit algorithm and
    just use the full containing-block width instead).

### 4. `align-items: stretch` (the flex-row default) forces mismatched-height siblings to match
BS2's floated columns each sized to their own content height
independently. BS5's `.row` is flex with `align-items:stretch` by default,
so a shorter sibling column visibly stretches to match a taller one,
filling the gap with empty background. Bit User Home (Mission Progress
card extending to the page bottom for no reason) and Scoreboard/Missions'
side-by-side cards. **Fix**: `align-items: flex-start` on the row (same
mechanism already used for `.alert` sitewide in `main.css`, pre-dating this
session).

### 5. `.form-horizontal .col-form-label { width: 160px; float: left }` fights `col-sm-3`'s flex-basis
A sitewide `main.css` rule from the original float-based BS2
form-horizontal pattern. Several ported forms use the newer `col-sm-3`/
`col-sm-9` flex-grid pattern instead — `float` no-ops as before, but the
fixed `width:160px` still wins over `col-sm-3`'s ~25% flex-basis, and is
just wide enough (combined with a zeroed row gutter, see pattern 6) to tip
the row into wrapping onto two lines. Found on Registration (3 fields) and
recurred exactly as predicted on Missions' flag-submission modals/forms (3
more occurrences). **Fix** (established on Registration, reused verbatim
on Missions): zero the row's gutter, then override the label:
`width: 25%; float: none; padding-right: 20px` (the `padding-right`
restores BS2's real label-to-input gap, which the zeroed gutter removes).

### 6. Zeroing a fluid row's gutter to fix a width bug can reopen a spacing bug
BS2's `.row-fluid [class*="span"]` gutter is a real
`2.127659574468085%` `margin-left` on every non-first-child column. BS5's
equivalent (`--bs-gutter-x` column padding) silently disappears the moment
a column's `flex-grow`/`shrink` gets zeroed (pattern 1) or it's given a
fixed/hardcoded width — so fixing the width bug can introduce a *new*,
previously-masked missing-gutter bug between siblings. Always check the gap
between fixed-up siblings after applying pattern 1's fix, and restore it
explicitly with `margin-left: 2.127659574468085%` if missing.

### 7. Two genuinely different BS2 grid techniques — don't apply the wrong one
- **Technique A — fluid percentage grid** (`.row-fluid` + `span*`,
  page examples: User Home, Scoreboard). Real measured percentages (from
  `cyborg.min.css`'s `.row-fluid [class*="span"]` rules): gutter
  `2.127659574468085%`; `span1` `6.382978723404255%`; `span2`
  `14.893617021276595%`; `span3` `23.404255319148934%`; `span4`
  `31.914893617021278%`; `span5` `40.42553191489362%`; `span6`
  `48.93617021276595%`; `span7` `57.44680851063829%`; `span8`
  `65.95744680851064%`; `span10` `82.97872340425532%`; `span11`
  `91.48936170212765%`. Inherently responsive (pure percentages) — give the
  BS5 `.col-md-*` replacement matching `flex-basis`/`max-width`/
  `margin-left` percentages, scoped per-page.
- **Technique B — fixed-width container** (plain `.container` + fixed-px
  `span*`/`offset1`, page examples: Registration, Missions). BS2's
  `.container` here is **genuinely fixed at 940px at every desktop width**,
  not responsive — confirmed live, not assumed from the framework docs.
  Root cause: `cyborg.min.css` bundles its own unconditional
  `.container{width:940px}` (no media query) which, loaded after
  `bootstrap-responsive.css`, always wins at equal specificity regardless of
  viewport. Fix with a `max-width:940px` cap, not a percentage — and derive
  any nested fixed-grid math (e.g. Missions' `span3`/`offset1` box grid)
  from *that* 940px basis, not the viewport.
- **Never apply Technique A's percentages to a Technique B page or vice
  versa** — check which one a page's *original* BS2 template actually used
  (`git worktree` checkout of the pre-port commit) before choosing.

### 8. `.bar` → `.progress-bar`
BS2's progress-fill class name was never renamed during the port in several
templates. `.bar` has no BS5 styling at all, so these rendered
empty/invisible. Fixed this session in `user/home.html`,
`scoreboard/{teams,summary_table}.html`, `missions/{box,view}.html` (18
occurrences total). **Check any future template for `class="bar` before
assuming progress bars work.** Once renamed, no further sitewide styling
was needed — Bootstrap 5's Cyborg vendor build already ships a gradient
`.progress-bar` look matching BS2's, since Bootswatch keeps that theme's
personality consistent across Bootstrap versions.

### 9. `.btn:hover` needs its own `text-decoration: none` — and its color variables were never actually wired to a different hover color
Found after this doc's first draft, on Missions' box page, then confirmed
platform-wide. Two separate bugs stacked on the same rule:
- BS2's `.btn:hover, .btn:focus { text-decoration: none; ... }` out-
  specifies the sitewide `a:hover{text-decoration:underline}` restoration
  for any real `<a>`. BS5's own default `.btn:hover` only sets color/
  background/border via CSS custom properties and never touches
  `text-decoration` — so on any `<a class="btn ...">` (box/mission action
  links, "Hint"/"Submit"/"Return to Missions", etc. — anywhere a link is
  styled as a button, on every page), the global underline rule was
  winning through. Fixed with `.btn:hover, .btn:focus, .btn:active {
  text-decoration: none; }`, specificity-checked to beat `a:hover` and to
  not affect the unused, template-absent `.btn-link:hover` variant (which
  BS2 genuinely does want underlined — not a live conflict since
  `.btn-link` isn't used anywhere in this app).
- Fixing the underline exposed that the hover tint never actually worked
  either — every `.btn-<variant>` rule set `--bs-btn-hover-bg`/
  `--bs-btn-hover-border-color` equal to the *resting* color instead of
  copying it from `--bs-btn-active-bg`/`--bs-btn-active-border-color`
  (which already held the real, correctly-measured BS2 darker value — BS2
  groups `:hover` and `:active` into one rule with an identical
  background-color, confirmed live: resting `#5c5c5c` → hover/active
  `#4d4d4d` for the plain/secondary variant). Fixed by copying the active
  value into the hover variables for all 6 variants. On top of that, every
  variant also paints a literal (non-variable) `background-image` gradient
  needed because Bootswatch hardcodes gradients that bypass `--bs-btn-bg`
  — that gradient is opaque and sits on top of `background-color`, so it
  would have hidden the hover-bg fix even after correcting the variables.
  Added `background-image: none` to the same shared `:hover,:focus,:active`
  rule (its (0,2,0) specificity beats a bare `.btn-<variant>` class's
  (0,1,0), so one rule covers every variant) so the flat hover color
  actually becomes visible. Note this doesn't reproduce BS2's *exact*
  historical mechanism (a `background-position` slide across a taller
  gradient sprite) — it produces the same end result (the whole button
  visibly darkens on hover) via a simpler flat-color swap, which was judged
  close enough rather than replicating a legacy sliding-sprite technique.
- **The generic `.btn:hover` fix doesn't reach every button.** The navbar's
  top-right user/admin dropdown toggle (`.navbar .nav-link.nav-user-btn`)
  has its own dedicated, higher-specificity rule (3 classes, pre-dating this
  session, needed to out-specify Bootstrap's own `.navbar-nav .nav-link`)
  that reasserts the same resting gradient. Its own `:hover`/`:focus`
  variant previously only restated `color:#fff` — already the resting
  color, a no-op — so this one button kept doing nothing on hover even
  after the sitewide fix. Fixed the same way, scoped to that selector.
  **Any other page-specific `.btn`-alike rule with 3+ classes of
  specificity should be checked for the same gap**: search for other
  unconditional (non-`:hover`) rules that set `background-image` at higher
  specificity than `.btn:hover`'s (0,2,0) before assuming the sitewide fix
  reached everywhere.

### 10. Sitewide component defaults that were never fully restored
Found and fixed as each page first touched the affected component
(sitewide fixes in `cyborg.min.css`/`main.css`, so already benefiting pages
not explicitly re-audited):
- **`.img-polaroid`**: BS2's base reset made every `<img>` responsive by
  default (`img{max-width:100%}`); BS5 dropped that global default. A
  literal `width:500px` was always meant as a cap, not a forced width.
  Fixed in `main.css` (used by 12 templates).
- **`.pagination`**: BS2's real Bootstrap 2 component default is
  `margin: 20px 0` — not just its link colors/padding (which a prior round
  restored). Missing this made pagination content (e.g. the "Players per
  page" selector) render 20px closer to the navbar and lose 20px of
  trailing space. Fixed in `cyborg.min.css`.
- **`.form-select`**: had borders/line-height restored in an earlier round
  but never its font-size or padding. BS5 default is 16px text with ~48px
  of caret padding vs BS2's plain native select at 14px with 6px padding —
  visibly bigger text and a taller control. Fixed sitewide (18 templates
  use `.form-select`); the caret still needs more right-padding than BS2's
  native arrow did, so it's not a full match, but font-size and overall
  proportions now line up.

## Findings by page

### Login (`public/login.html`)
Nearly perfect already from prior sitewide restorations (no BS2 grid
classes on this page at all — simple centered card). One real bug: BS5's
global border-box reset made `.form-signin`'s BS2 content-box `max-width:
400px` render as the wrong (smaller, shifted) box; restated as the real
outer width (460px). A `.container` width mismatch (940 vs 1140) was
investigated and found **not** to matter here — nested `margin:auto`
centering is mathematically independent of the intermediate container's
width, so the visible box lands identically either way; left as-is.

### Registration (`public/registration.html`)
Technique B page. Fixed the 940px container/card width (pattern 7), the
label/input wrap bug (pattern 5, first occurrence — established the fix
reused later on Missions), stretched `<input>` fields (BS5's
`.form-control` is `width:100%` by design; BS2's plain inputs had no width
at all, ~220px natural), and a missing submit-button indent
(`offset-sm-3`). Also found and fixed sitewide: `.form-control`/
`.form-select` `line-height` (BS2's was a fixed 20px; BS5's scales with
font-size) and an unthemed `.popover` header (Cyborg never overrode
`--bs-popover-header-bg`, leaving white text on a near-white bar).

### User Home (`user/home.html`)
Technique A page. Fixed the two-column split (pattern 1), the missing
column gutter (pattern 6), the "Rank" block (pattern 3, `d-flex` variant),
the Mission Progress card stretching to the page bottom (pattern 4), and
sitewide `.img-polaroid` responsiveness (pattern 9). `.bar`→`.progress-bar`
renamed here first (pattern 8).

### Scoreboard Summary + Teams (`scoreboard/{summary,teams}.html`)
Technique A pages, split into new `static/css/pages/scoreboard/
{summary,teams}.css` files (previously shared `public/summary.css` with
out-of-scope History/Projector — do not add rules to that shared file).
Fixed the results-card width (pattern 1), the sidebar/main split (pattern
7), the pagination controls' position (pattern 3, `position:absolute`
variant — the one that needed all 4 properties stated explicitly), the
page-title margin (pattern 2), and sitewide `.pagination` margin +
`.form-select` sizing (pattern 9). Restored the sticky sidebar
(`#navWrapper.affix`) sitewide via `.affix{position:fixed}` — this class
was completely inert before (zero BS5 CSS existed for it anywhere); the
page's own `anchor.js` (already shipping, previously doing nothing) now
correctly keeps it pinned during scroll. **This sitewide fix also affects
two out-of-scope admin pages** (`admin/view/{statistics,game_objects}.html`
use the identical `#navWrapper.affix` pattern) — checked live as admin,
confirmed it's a strict improvement there too (their sidebars now actually
stick, no overlap/breakage), not a regression.

### Missions list + box (`missions/{view,box}.html`)
Technique B pages, new `static/css/pages/missions/{view,box}.css` files.
Fixed the 940px container (pattern 7) on both, the box-grid math (BS2's
real fixed-px `span3`/`offset1` model, not row-fluid — verified live: a
100px gap between sibling box columns, not the naive `20+80`), the
recurring label/input wrap bug (pattern 5, 3 more occurrences, same fix as
Registration), a bare-BS2-grid-class float bug (`.span4`/`col-md-4` avatar
column: BS2's `[class*="span"]` floats left even *outside* a `.row`,
letting description text wrap beside it — BS5's `.col-md-4` has no such
default, so text was dropping below instead of beside), and a
table-auto-layout shrink-to-fit wrap on a "Flag" button (`white-space:
nowrap`). 9 more `.bar`→`.progress-bar` renames (pattern 8).

## Files touched

- `dev-tools/bs-parity/` — new: `extract.js`, `diff.py`, `README.md`.
- `static/css/main.css` — `.img-polaroid` max-width/height restoration.
- `static/css/themes/cyborg.min.css` — sitewide additions: `.form-select`
  font-size/padding, `.popover`, `.affix`, `.pagination`/`.page-item`/
  `.page-link` (colors/padding from an earlier round, margin from this
  doc's Scoreboard fix), form-control `line-height`, `.btn:hover`/`:focus`/
  `:active` `text-decoration:none` (pattern 9).
- `static/css/pages/public/login.css`, `static/css/pages/public/
  registration.css` — page-specific fixes described above.
- `static/css/pages/user/home.css` — page-specific fixes described above.
- `static/css/pages/scoreboard/summary.css`,
  `static/css/pages/scoreboard/teams.css` — new files.
- `static/css/pages/missions/box.css`, `static/css/pages/missions/
  view.css` — new files.
- `templates/public/registration.html` — 2 class additions
  (`registration-page`, `registration-card`), 1 offset fix.
- `templates/user/home.html` — wrapper class, `d-flex` rank fix, 4 `.bar`
  renames.
- `templates/scoreboard/summary.html`, `templates/scoreboard/teams.html`,
  `templates/scoreboard/summary_table.html` — wrapper classes, CSS links, 8
  `.bar` renames total.
- `templates/missions/box.html`, `templates/missions/view.html` — wrapper
  classes, CSS links, 9 `.bar` renames total.

## Known open issues (not fixed, tracked for later)

1. Scoreboard's MVP/team-avatar branches — not exercised by current seed
   data, fix applied by inference only (see "Known gaps" above).
2. Missions' `.levelheader` `display:inline` behavior — not exercised by
   current seed data (see "Known gaps" above).
3. Admin dashboard remains fully out of scope and untouched this session —
   its own doc's open issues (grid-width brittleness, the 2px Game Control
   gap, the flattened "New Flag" dropdown) are all still open.
4. Sitewide fixes made this session (`.img-polaroid`, `.pagination`,
   `.form-select`, `.popover`, `.affix`) benefit every page that uses those
   components, including ones never explicitly re-audited (e.g. `.affix` on
   the two admin pages, spot-checked and confirmed fine; other pages using
   `.form-select`/`.pagination` were not individually re-verified).
5. Only the Cyborg theme was touched. The other 10 themes (2 more
   hand-built like Cyborg — `386`, `cyberpunk` — and 8 raw Bootswatch
   swaps) have none of this parity work applied.
6. Only desktop widths (1280-1920px) were verified. Mobile/tablet
   breakpoints are untested.
