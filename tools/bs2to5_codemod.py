#!/usr/bin/env python3
"""
Bootstrap 2 -> 5 mechanical codemod for Root the Box templates (Phase 2.1b).

Scope: the *mechanical* class/attribute renames only — the transforms that are a
safe 1:1 (or 1:2) token swap. Structural rewrites (forms/control-group, modal
markup, the navbar/Menu module, .hide visibility) are intentionally NOT handled
here; they are done by hand per page-group in later commits.

Design for safety:
  * Class-token transforms run ONLY inside class="..."/class='...' attributes, so
    prose like "as well as" or a <span> tag can never be rewritten.
  * Within a class value, Tornado template tags ({% ... %} / {{ ... }}) are treated
    as opaque and left untouched — only the plain-text segments between them are
    rewritten. This preserves embedded control flow, e.g.
    class="{% if x %}span8 offset1{% end %}well" -> "...col-md-8 offset-md-1...card".
    (Grid classes built dynamically *inside* a {% set %} are out of scope and left
    for manual review.)
  * Replacements are word-boundary regex subs on the raw string (no tokenize /
    whitespace-collapse / de-dup), so original spacing and repeated template tags
    are preserved exactly.
  * data-* renames are BS attribute *names* and are applied as literal substrings;
    each chosen name is verified to not be a prefix of an unrelated app attribute
    (e.g. data-clipboard-target is untouched by the data-target rule).

Idempotent: re-running produces no further changes. Run from the repo root:
    python3 tools/bs2to5_codemod.py [templates_dir]
"""

import os
import re
import sys

# --- class-token replacements, applied in order as word-boundary regex subs ---
# order matters: well-small/well-large before the bare well rule.
CLASS_SUBS = [
    # grid
    (re.compile(r"\bspan(\d+)\b"), r"col-md-\1"),
    (re.compile(r"\boffset(\d+)\b"), r"offset-md-\1"),
    (re.compile(r"\brow-fluid\b"), "row"),
    # buttons
    (re.compile(r"\bbtn-mini\b"), "btn-sm"),
    (re.compile(r"\bbtn-small\b"), "btn-sm"),
    (re.compile(r"\bbtn-large\b"), "btn-lg"),
    (re.compile(r"\bbtn-inverse\b"), "btn-dark"),
    # wells -> cards
    (re.compile(r"\bwell-small\b"), "card card-body"),
    (re.compile(r"\bwell-large\b"), "card card-body"),
    (re.compile(r"\bwell\b"), "card card-body"),
    # floats
    (re.compile(r"\bpull-left\b"), "float-start"),
    (re.compile(r"\bpull-right\b"), "float-end"),
    # BS2 glyphicons still in use -> FontAwesome 4 (already vendored). icon-bar
    # (navbar toggle) is deliberately excluded — handled in the navbar rewrite.
    (re.compile(r"\bicon-chevron-right\b"), "fa fa-chevron-right"),
    (re.compile(r"\bicon-bookmark\b"), "fa fa-bookmark"),
    (re.compile(r"\bicon-book\b"), "fa fa-book"),
]

# Tornado template tags to treat as opaque within a class value.
TEMPLATE_TAG_RE = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)

# --- data-* attribute-name renames (literal, whole-document) -----------------
DATA_ATTR_MAP = {
    "data-toggle=": "data-bs-toggle=",
    "data-dismiss=": "data-bs-dismiss=",
    "data-target=": "data-bs-target=",
    "data-parent=": "data-bs-parent=",
    "data-content=": "data-bs-content=",
    "data-html=": "data-bs-html=",
    "data-original-title=": "data-bs-title=",
}

CLASS_ATTR_RE = re.compile(r"""class\s*=\s*(?P<q>["'])(?P<val>.*?)(?P=q)""", re.DOTALL)


def _sub_plain(segment):
    for pattern, repl in CLASS_SUBS:
        segment = pattern.sub(repl, segment)
    return segment


def transform_class_value(value):
    """Rewrite class tokens, leaving {% %}/{{ }} template tags opaque."""
    out = []
    last = 0
    for tag in TEMPLATE_TAG_RE.finditer(value):
        out.append(_sub_plain(value[last:tag.start()]))
        out.append(tag.group(0))  # template tag, untouched
        last = tag.end()
    out.append(_sub_plain(value[last:]))
    return "".join(out)


def transform_text(text):
    # 1) class-token transforms, scoped to class attributes
    def _class_sub(match):
        new_val = transform_class_value(match.group("val"))
        q = match.group("q")
        return "class=%s%s%s" % (q, new_val, q)

    text = CLASS_ATTR_RE.sub(_class_sub, text)
    # 2) data-* attribute-name renames
    for old, new in DATA_ATTR_MAP.items():
        text = text.replace(old, new)
    return text


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "templates"
    changed = 0
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, "r", encoding="utf-8") as fh:
                original = fh.read()
            updated = transform_text(original)
            if updated != original:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(updated)
                changed += 1
                print("  updated %s" % path)
    print("Done. %d file(s) changed." % changed)


if __name__ == "__main__":
    main()
