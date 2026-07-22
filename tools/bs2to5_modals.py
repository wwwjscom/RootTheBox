#!/usr/bin/env python3
"""
Bootstrap 2 -> 5 modal *structural* transform for Root the Box templates (2.1b).

BS5 modals need a `.modal-dialog > .modal-content` wrapper that BS2 did not have,
so this cannot be a class rename (the mechanical codemod handles the class/attr
renames, including the modal close button). Here we:

  1. find each BS2 modal: <div ... class="... modal hide fade ...">
  2. balance <div>/</div> to locate its matching close tag,
  3. rewrite the opening tag (drop `hide`, add tabindex="-1"),
  4. wrap the inner markup in <div class="modal-dialog"><div class="modal-content">.

Safety: the match must be div-balanced AND contain `modal-body`; otherwise the
modal is SKIPPED and reported for manual handling (guards against conditionally
unbalanced <div> in template branches). Idempotent: after the rewrite the class is
`modal fade` (no `hide`), so the opening regex no longer matches.

Run from repo root:  python3 tools/bs2to5_modals.py [templates_dir]
"""

import os
import re
import sys

# Match a <div ...> opening tag, treating {% %}/{{ }} template tags as opaque
# units so a `>` *inside* a tag (e.g. style="...{% if x > 0 %}...") is not mistaken
# for the tag's real closing `>`. Filtered afterwards to the modal openings.
DIV_OPEN_RE = re.compile(r"<div\b(?:\{%.*?%\}|\{\{.*?\}\}|[^>])*?>", re.DOTALL)


def _modal_opens(text):
    for m in DIV_OPEN_RE.finditer(text):
        if "modal hide fade" in m.group(0):
            yield m
DIV_TOKEN_RE = re.compile(r"<div\b|</div>", re.IGNORECASE)
WRAP_OPEN = '\n    <div class="modal-dialog">\n    <div class="modal-content">'
WRAP_CLOSE = "\n    </div>\n    </div>"


def _matching_close(text, start):
    """Return (close_start, close_end) of the </div> that closes the div whose
    content begins at `start` (depth already 1). None if it never balances."""
    depth = 1
    for m in DIV_TOKEN_RE.finditer(text, start):
        if m.group(0).lower().startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return m.start(), m.end()
    return None


def _rewrite_open(tag):
    tag = tag.replace("modal hide fade", "modal fade")
    if "tabindex=" not in tag:
        tag = tag[:-1].rstrip() + ' tabindex="-1">'
    return tag


def transform_text(text, report):
    # process modals last-to-first so earlier offsets stay valid after inserts
    opens = list(_modal_opens(text))
    for m in reversed(opens):
        close = _matching_close(text, m.end())
        if close is None:
            report.append(("UNBALANCED", m.group(0)[:60]))
            continue
        close_start, close_end = close
        inner = text[m.end():close_start]
        if "modal-body" not in inner:
            report.append(("NO-MODAL-BODY", m.group(0)[:60]))
            continue
        new = (
            _rewrite_open(m.group(0))
            + WRAP_OPEN
            + inner
            + WRAP_CLOSE
            + text[close_start:close_end]
        )
        text = text[: m.start()] + new + text[close_end:]
    return text


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "templates"
    changed = 0
    skips = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as fh:
                original = fh.read()
            report = []
            updated = transform_text(original, report)
            for kind, snippet in report:
                skips.append("  [%s] %s :: %s" % (kind, path, snippet))
            if updated != original:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(updated)
                changed += 1
                print("  wrapped modals in %s" % path)
    print("Done. %d file(s) changed." % changed)
    if skips:
        print("SKIPPED (need manual handling):")
        print("\n".join(skips))


if __name__ == "__main__":
    main()
