# BS2 → BS5 Admin Dashboard Parity Audit

Findings and methodology from a debugging session comparing the admin dashboard
page under the old Bootstrap 2 build against the in-progress Bootstrap 5 port
(Phase 2.1b, branch `feature/phase2.1b-bootstrap5`). Written so a fresh
conversation can pick this up without re-deriving root causes already found.

## Setup / ground truth

- **`http://localhost:8890`** — old reference app (Bootstrap 2). Whatever
  renders here is ground truth for "how it should look/behave."
- **`http://localhost:8888`** — new app (Bootstrap 5), the one being fixed.
- Login on both: `admin` / `rootthebox`.
- Admin's `/user` link redirects to the admin dashboard (`/admin/home`-ish;
  actual route is just the app root once logged in as admin).

## Methodology (worth reusing)

1. **Never trust a screenshot alone.** Pull `getComputedStyle()` (every
   property, not a curated subset) and `getBoundingClientRect()` for the same
   element on both pages and diff them. Screenshots are for final sanity
   checks only, after the numbers already agree.
2. **Cache-busting is mandatory after every CSS edit.** Tornado's static file
   handler doesn't make the browser revalidate, so an already-loaded tab keeps
   serving stale CSS. Before re-measuring after any edit, run in the target
   tab:
   ```js
   [...document.querySelectorAll('link[rel=stylesheet]')].forEach(l=>{
     const u=new URL(l.href); u.searchParams.set('bust',Date.now()); l.href=u.toString();
   })
   ```
   Skipping this produced false "still broken" readings more than once.
3. **`:hover` doesn't reliably trigger via synthetic coordinate-based hover**
   in the browser tool. Either hover a specific element `ref` (not raw x/y
   coordinates), or — more reliably — read the declared `:hover` rules
   straight out of `document.styleSheets` on both pages and compare those
   instead of trusting live computed style during a simulated hover.
4. **Read the actual vendor/theme CSS source before guessing.** Several bugs
   were only findable by `fetch()`-ing the raw CSS file and grepping for the
   real rule (e.g. Bootstrap 2's actual grid math, or the exact `.btn-close`
   default). Don't assume what a framework default is — pull it.
5. **A cascade gotcha that caused two separate bugs**: when two rules have
   **equal specificity**, the one **later in source order** wins for any
   property it sets, even if the earlier rule is a `:hover` rule and the
   later one isn't. This silently broke hover-underline behavior twice (nav
   links, alert links) because a later "always apply `text-decoration:none`"
   rule beat an earlier `a:hover{text-decoration:underline}` rule despite the
   hover rule being intuitively "more specific to the situation." CSS doesn't
   see it that way — check source order whenever a `:hover` effect
   mysteriously doesn't show up.
6. **A layout gotcha that caused a whole category of bugs**: Bootstrap 5's
   `.card` is `display:flex; flex-direction:column`. Bootstrap 2's `.well`
   (the component `.card` replaced) is a plain block box. **Adjacent sibling
   margins only collapse in normal block flow, never between flex items.**
   Porting `.well` → `.card` without accounting for this silently added the
   sum of two margins everywhere BS2 was only showing their collapsed max.
   Look for this pattern anywhere a block-to-flex component swap happened.
7. **Fix location convention established in this codebase**:
   - Site-wide theme restorations → `static/css/themes/cyborg.min.css`, in a
     hand-written, readable, commented section appended after the
     minified vendor Bootswatch build (starts around line 14 with a
     `/* Base: ... */` comment). Every override rule there has a comment
     explaining what the BS5/Cyborg default was and citing the measured BS2
     value — keep following that convention.
   - Page-specific layout → `static/css/pages/admin/home.css`, scoped under
     `.admin-dashboard`.
   - Occasionally the correct fix is in the **template markup**
     (`templates/admin/home.html`), not CSS — e.g. a Bootstrap utility class
     (`mb-3`) added during the port with no BS2 equivalent, or a missing grid
     class. Don't force a CSS-only fix when the root cause is a markup diff.
8. **When delegating to a subagent**: hand it the already-root-caused
   mechanism and exact measured numbers, not just symptoms — otherwise it
   burns its budget rediscovering things already known. Require it to report
   live before/after numbers, not qualitative "looks right now" claims.
   **Always independently re-verify a subagent's claims** against the live
   pages afterward — this caught at least one real gap (see "Known open
   issues" below) that the subagent's own report had noted but framed as
   out-of-scope/unrelated.
9. Independent parallel subagents worked fine when scopes were genuinely
   disjoint (navbar vs. dashboard body). When fixes were interdependent
   (e.g. a grid-width fix changing measurements a spacing fix depends on),
   they were run sequentially in one agent instead, to avoid one agent
   measuring against a moving target.

## Findings, by component

### WARNING alert box (`alert alert-warning alert-dismissible` vs BS2's `span8 alert alert-warning`)
- `.alert-heading` had a leftover `margin-top:10px` (only `margin-bottom` had
  been zeroed by an earlier fix) → alert 66px tall instead of BS2's 56px.
  Fixed: `.alert-heading{margin:0}`.
- Cyborg's vendor rule force-underlines all links inside `.alert`; fixed with
  `.alert a{text-decoration:none}` — but this also killed BS2's genuine
  **hover** underline (global `a:hover` rule got shadowed, see cascade gotcha
  above). Follow-up fix: `.alert a:hover, .alert a:focus{text-decoration:underline}`.
- `.admin-dashboard .alert{max-width:89%}` in `home.css` was based on a false
  premise (a comment claimed BS2's `span8` was narrower than the column) —
  live measurement proved BS2's alert was exactly as wide as its sibling
  panel, no cap. Removed entirely.
- Close control (BS2 `.close` vs BS5 `.btn-close`) differed in every
  dimension: offset, color, box size, and the alert's own reserved padding.
  All fixed to exact live-measured parity:
  - Offset: `top:6px; right:14px` (was flush to the corner at `top:0;right:0`
    with huge default padding).
  - Color: black fill @ `opacity:0.2` with a white `drop-shadow(0 1px 0 #fff)`
    (was Cyborg's default white @ opacity 0.6 — meant for dark surfaces like
    modals, wrong here).
  - Box size: `11px × 20px` (was `14×14`; BS2's is a 20px-font-size character
    glyph, taller than wide, not a square icon).
  - `.alert-dismissible{padding-right:35px}` (BS5 default reserves 48px).
  - `.alert-heading` also needed `text-rendering:optimizeLegibility` (BS2 set
    it on all headings; BS5 default is `auto`, a subtle kerning difference).

### Navbar
- Height 66px vs BS2's 50px — BS5's default `0.5rem` navbar padding stacks on
  top of child padding that already accounted for the full height. Fixed:
  `.navbar{padding-top:0;padding-bottom:0}`.
- `.navbar.bg-dark` background/border a shade off: `#060606`→`#020202`,
  `#282828`→`#222` (needed `!important` + the 2-class `.navbar.bg-dark`
  selector to out-specificity Bootstrap's utility + dark-theme rules).
- Nav-link hover was color-only; BS2 also draws a `1px solid #33b5e5` bottom
  border (padding was already pre-reserving exactly 1px for this, a strong
  sign it was dropped, not a deliberate change). Fixed, and **also had to add
  `text-decoration:none`** to that same hover rule — a separate, earlier fix
  (`a:hover{text-decoration:underline}`, global) was bleeding an underline
  onto hovered nav links since the nav-specific rule never touched that
  property.
- `.navbar-brand` color `#fff`→`#eee`.
- `.dropdown-menu`: wrong background, border, radius, shadow (BS5 had none),
  font-size (16px vs BS2's 14px — visibly oversized), padding.
- `.dropdown-item`: wrong text color (`#fff` vs BS2's muted `#999`), padding.
- `.dropdown-item:hover/:focus`: flat `#2a9fd6` vs BS2's two-tone blue
  gradient (`linear-gradient(#33b5e5,#1dade2)`).
- **Not fixed (out of CSS scope)**: BS2's "New Flag" dropdown item was a true
  nested `<li class="dropdown-submenu">` flyout; the BS5 template flattened
  it to a flat list with a dim `<h6 class="dropdown-header">` and a stray
  `<hr>`. Bootstrap 5 dropped built-in nested-submenu support — restoring
  this needs new markup + JS, not a CSS fix.
- **Left alone (not a regression)**: BS5's focus-ring (`box-shadow` glow)
  differs from BS2's native outline — reads as an accessibility improvement.

### Global link hover color
- The already-restored `a:hover{color:...}` rule used `#33b5e5` (no visible
  change from the link's own color). Live BS2 inspection showed the real
  rule is `color:#fff` on hover (turns white). Fixed globally — this affects
  every in-page link, e.g. the Notifications "See All »" link.

### Buttons
- `.btn-secondary` (BS2's plain, no-color-variant `.btn` — e.g. modal Close,
  "Check Now") wrongly inherited a `text-shadow` shared with true color
  variants; BS2 explicitly zeroed it for this one. Fixed: own rule with
  `text-shadow:none`.
- `.btn-sm` border-radius `4px`→`3px` (BS2's small/mini buttons had a tighter
  corner than default-size buttons).

### Form controls
- `.form-control` padding `6px/16px` (Bootstrap 5 default) vs BS2's
  `4px/6px` — made inputs visibly fatter/taller than the original.
- `.form-control:disabled` had entirely wrong tokens: Cyborg's default is
  `background:#adafae; border-color:transparent; cursor:default`; BS2's real
  disabled state is `background:#555; border-color:#bbb; cursor:not-allowed`.

### Global `<hr>` divider
- A previous "restore" fabricated a two-tone groove (`border-bottom:#808080`)
  that never existed in BS2. Live inspection of both a body `<hr>` and the
  actual footer `<hr>` showed the true rule: single top border only, no
  bottom border at all (`border-top:1px solid #222; border-bottom:0`). This
  one rule affects every divider on the page.
- `.table` margin-bottom: Bootstrap 5 default `16px` vs BS2's `20px` — fixed
  globally on `.table`.

### Grid architecture — `.span*` float-grid vs `.col-md-*` flex-grid
BS2's actual grid CSS (pulled live from the reference build's theme file):
```css
.container-fluid { padding-right: 20px; padding-left: 20px; }
.row { margin-left: -20px; }
[class*="span"] { float: left; min-height: 1px; margin-left: 20px; }
[class*="span"]:first-child { margin-left: 0; }
.span8 { width: 620px; } /* etc, fixed px per span number */
```
This is BS2's classic fixed-grid cancellation trick: the row's `-20px`
margin cancels the container's `20px` padding so the first column sits
flush; each following column gets `+20px` as the gutter.

**Fix applied** (in `home.css`, scoped to `.admin-dashboard`): hardcoded pixel
corrections calibrated at a **1117px** viewport —
```css
.admin-dashboard > .col-md-8 { margin-left: 22.64px; }
.admin-dashboard > .col-md-3 .row > .col-md-11.offset-md-1 {
  margin-left: 38.06px; flex: 0 0 248.91px; max-width: none;
}
```
This achieved exact pixel parity **at that one viewport width**.

**⚠️ Known limitation — confirmed, not yet fixed**: this does *not* scale with
viewport width. BS2's own grid is itself responsive (breakpoint-based); the
patch is a fixed-px snapshot of one width. Re-measured at 1280px: BS2's
sidebar column renders **283.8px** wide; BS5's fixed patch still gives
**248.9px** — a ~35px gap. Visible consequence: at 1280px, BS2's "Resume
Registration" label fits on one line; BS5's still wraps to two, because the
column is narrower than it should be at that width. **If the app is used at
any width other than ~1117px, this will visibly drift.** A real fix needs to
replicate BS2's actual breakpoint behavior (or otherwise make the correction
width-aware), not just patch one snapshot. This is the single biggest open
item from this whole audit.

### Game Control panel
- BS2's technique: the button is a floated Bootstrap button; the label
  (`.game_button_text`, `display:inline`) is genuine inline text that
  **wraps around the float** — confirmed live: the longest label wraps to 2
  lines, with the wrapped line reflowing to the *full container width* (past
  the float), not staying indented beside the button.
- The in-progress BS5 fix had reimplemented this with `display:flex`, which
  cannot reproduce float-wrap behavior. **Reverted to BS2's actual
  technique**: inline-block button (`margin-right:12px`) + genuinely inline
  `.game_button_text` (`margin:10px 0`).
- Also fixed `.game_button_area` margin `18px 10px` (was `14px 4px`), and a
  double-margin bug between consecutive rows (flex children don't collapse
  margins the way block siblings do — moot once the flex approach was
  reverted, but the mechanism is the same one described in the methodology
  section above).
- Final measured parity: row heights 30/50.75/30px, gap 15.64px, wrap-line
  heights matching BS2 to the sub-pixel — **except** a small unexplained 2px
  residual on the heading→first-row gap (18px BS5 vs 20px BS2). Not chased
  further; diminishing returns.
- This fix only became fully correct once the grid-width fix (above) landed
  — before that, the sidebar card was ~11.7px too narrow and caused a row to
  wrap that shouldn't have. **This is exactly why the grid-width brittleness
  above matters**: at a different viewport, the card is narrow again and the
  same wrong-wrap can reappear (confirmed at 1280px, see above).

### Automatic Ban panel
- The "Threshold" input was stretching to fill the card width. Root cause:
  BS2's `#threshold-size` is a completely unclassed `<input type="text">` —
  its only styling is the base BS2 input rule, which is `display:inline-block`
  with **no width set at all** (natural browser default, measures ~220px
  live). Bootstrap 5's `.form-control` is `display:block; width:100%` by
  design. Fixed narrowly (not a global `.form-control` width change, which
  would break every other form on the site): `#threshold-size{width:220px}`
  in `home.css`.
- Row-to-row spacing was 16px (BS5's `.row.mb-3` utility, `!important`) vs
  BS2's `.control-group` default of 10px. Fixed:
  `.admin-dashboard .card form .row.mb-3{margin-bottom:10px!important}`.

### `.card` vs `.well` systemic margin-collapse (see methodology gotcha #6)
Because `.card` is a flex column, every panel with `<h3>` immediately
followed by `<hr>` (Game Metrics, App Updates, Automatic Ban, Failed Logins,
Banned IPs) measured a 30px gap instead of BS2's collapsed 20px (`h3`'s
`margin-bottom:10px` + `hr`'s `margin-top:20px`, summed instead of
collapsed). Fixed by extending the existing global rule
`.card h1, .card h2, ... h6 { color:#fff; }` to also set `margin-bottom:0`,
which makes the flex-sum equal BS2's collapsed total without touching the
shared `hr` rule or `.card`'s flex display. Spot-checked 3 other pages
(scoreboard, user settings, admin game-objects view) for regressions — none
found.

### Notifications panel
- Title ("Notifications") + "Create Notification" button are wrapped in
  `<div class="d-flex justify-content-between align-items-center mb-3">` in
  the BS5 template — a wrapper with **no BS2 counterpart at all** (BS2 just
  floats the button in its own div, no shared wrapper). That wrapper's
  `mb-3` (16px, `!important`) inflated the title→"See All »" gap from BS2's
  9.5px to 25.5px. Fixed by changing `mb-3` → `mb-0` directly on that div in
  `templates/admin/home.html` (the `d-flex justify-content-between
  align-items-center` part is a legitimate, non-buggy way to replicate BS2's
  float-right button and was kept).
- Confirmed via full template read: this specific wrapper pattern occurs
  **only once** in this template — no other panel needed the same fix.

### Horizontal page overflow (~71px, initially misattributed to the navbar)
- Root cause was **not** the navbar itself — it was
  `<div class="offset-md-1">` (the "Administrator Panel" `<h1>`'s wrapper,
  `templates/admin/home.html` line 100) missing its `col-md-11` companion
  class. Bootstrap 5's `.row > * {width:100%}` default stretched the bare
  offset div to full row width *plus* its own 8.33% offset margin, pushing
  the row past the viewport. Fixed by adding the missing `col-md-11` class.
  Verified: `document.documentElement.scrollWidth === clientWidth` on both
  pages after the fix.

## Files touched

- `static/css/themes/cyborg.min.css` — the large majority of fixes (site-wide
  theme restoration). Custom readable section starts ~line 14.
- `static/css/pages/admin/home.css` — page-specific layout, scoped under
  `.admin-dashboard`.
- `templates/admin/home.html` — 2 markup-level fixes: missing `col-md-11` on
  the header offset div (line ~100), `mb-3`→`mb-0` on the Notifications
  title wrapper (line ~284).

## Known open issues (not yet fixed)

1. **Grid-width fix is viewport-brittle** (see above) — only exact at
   1117px; confirmed drifting at 1280px. Needs a genuinely responsive fix if
   the app isn't used at a single fixed browser width. This is the most
   important unresolved item.
2. Game Control heading→first-button-row gap: 18px (BS5) vs 20px (BS2), a 2px
   residual not explained by the margin-collapse model. Low priority.
3. "New Flag" nested dropdown submenu is flattened in the BS5 template —
   needs new markup + JS to restore a true nested flyout; out of CSS scope.
4. A likely-dead CSS rule was flagged (not removed):
   `.row.mb-3[style*="float: right"]` in `home.css` — appears to no longer
   match any element in the current template after the Notifications
   button's markup moved to `d-flex`. Candidate for cleanup, not yet
   verified/removed.
5. **Scope was the admin dashboard page only.** Most fixes were made at the
   theme level (`cyborg.min.css`), so other pages sharing these components
   (navbar, alerts, cards, tables, dropdowns, buttons, forms) should already
   benefit — but they haven't been individually audited the way this page
   was. The two page-specific fixes (`home.css`, `home.html`) only apply to
   this page.
