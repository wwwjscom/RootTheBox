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
    # alerts
    (re.compile(r"\balert-error\b"), "alert-danger"),
    # forms (BS2 horizontal-form scaffolding -> BS5 grid). control-group becomes a
    # grid row; control-label/controls become the 3/9 columns. All RTB control-
    # groups live in .form-horizontal forms (bar 2 minor sidebar forms, tuned by
    # hand), so the horizontal mapping is correct.
    (re.compile(r"\bcontrol-group\b"), "row mb-3"),
    (re.compile(r"\bcontrol-label\b"), "col-sm-3 col-form-label"),
    (re.compile(r"\bcontrols\b"), "col-sm-9"),
    (re.compile(r"\bhelp-inline\b"), "form-text"),
    (re.compile(r"\binput-block-level\b"), "w-100"),
    # (.form-horizontal is left in place; BS5 defines no such class, so it is inert
    #  and the grid columns above do the layout.)
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

# Dismissible-alert pattern: an alert <div> immediately followed by the BS2 close
# anchor. Add `alert-dismissible` to the div and swap the anchor for BS5 .btn-close.
# (RTB's dismissible alerts consistently place the close as the div's first child.)
ALERT_DISMISS_RE = re.compile(
    r"""(?P<open><div\s+class=")(?P<cls>[^"]*\balert\b[^"]*)(?P<mid>"[^>]*>\s*)"""
    r"""<a\s+class="close"\s+data-bs-dismiss="alert"[^>]*>\s*&times;\s*</a>""",
    re.DOTALL,
)


# Form controls need a BS5 class to pick up styling (BS2 styled bare inputs).
FORM_TAG_RE = re.compile(
    r"<(?P<tag>input|select|textarea)\b(?P<attrs>[^>]*?)(?P<slash>\s*/?)>",
    re.IGNORECASE | re.DOTALL,
)
TYPE_RE = re.compile(r"""type\s*=\s*(["'])(?P<t>.*?)\1""", re.IGNORECASE)
TAG_CLASS_RE = re.compile(r"""class\s*=\s*(?P<q>["'])(?P<val>.*?)(?P=q)""", re.IGNORECASE | re.DOTALL)
# input types that are NOT text-like form controls
_SKIP_TYPES = {"hidden", "submit", "button", "reset", "image"}
_CHECK_TYPES = {"radio", "checkbox"}


def _form_class_for(tag, attrs):
    if tag == "select":
        return "form-select"
    if tag == "textarea":
        return "form-control"
    # input: decide by type
    m = TYPE_RE.search(attrs)
    itype = (m.group("t").lower() if m else "text")
    if itype in _SKIP_TYPES:
        return None
    if itype in _CHECK_TYPES:
        return "form-check-input"
    if itype == "range":
        return "form-range"
    return "form-control"


def _form_tag_sub(match):
    tag = match.group("tag").lower()
    attrs = match.group("attrs")
    target = _form_class_for(tag, attrs)
    if target is None:
        return match.group(0)
    cm = TAG_CLASS_RE.search(attrs)
    if cm:
        tokens = cm.group("val").split()
        if any(t == target or t.startswith("form-control") or t == "form-select" or t == "form-check-input" or t == "form-range" for t in tokens):
            return match.group(0)  # already a BS5 control (idempotent)
        new_val = (cm.group("val").rstrip() + " " + target).strip()
        new_attrs = (
            attrs[: cm.start()]
            + "class=%s%s%s" % (cm.group("q"), new_val, cm.group("q"))
            + attrs[cm.end():]
        )
    else:
        # no class attr: add one right after the tag name. `attrs` (captured
        # between the tag name and the closing slash/>) already begins with
        # whitespace when non-empty, so no extra separator is needed.
        new_attrs = ' class="%s"%s' % (target, attrs)
    return "<%s%s%s>" % (match.group("tag"), new_attrs, match.group("slash"))


# Modal close button: BS2 <button class="close" data-bs-dismiss="modal">&times;</button>
# -> BS5 <button class="btn-close" ...></button>. Preserve id/style; keep the
# dismiss hook; drop the &times; (BS5 draws the X via CSS). The JS-controlled
# #closebutton overlays (no data-bs-dismiss, <h2>x</h2> content) don't match.
MODAL_CLOSE_RE = re.compile(
    r"""<button\b(?P<attrs>[^>]*\bclass=["']close["'][^>]*\bdata-bs-dismiss=["']modal["'][^>]*)>\s*&times;\s*</button>""",
    re.DOTALL,
)
_ID_RE = re.compile(r"""\bid=(["']).*?\1""")
_STYLE_RE = re.compile(r"""\bstyle=(["']).*?\1""")


def _modal_close_sub(match):
    attrs = match.group("attrs")
    keep = []
    for rx in (_ID_RE, _STYLE_RE):
        m = rx.search(attrs)
        if m:
            keep.append(m.group(0))
    extra = (" " + " ".join(keep)) if keep else ""
    return (
        '<button type="button"%s class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>'
        % extra
    )


def _alert_dismiss_sub(match):
    cls = match.group("cls")
    if "alert-dismissible" not in cls.split():
        cls = cls + " alert-dismissible"
    return (
        match.group("open")
        + cls
        + match.group("mid")
        + '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>'
    )


def _sub_plain(segment):
    for pattern, repl in CLASS_SUBS:
        segment = pattern.sub(repl, segment)
    return segment


# A bare `.btn` (no colour variant) is unstyled in BS5; give it btn-secondary,
# the BS5 equivalent of BS2's default grey button.
_BTN_VARIANTS = {
    "btn-primary", "btn-secondary", "btn-success", "btn-danger", "btn-warning",
    "btn-info", "btn-light", "btn-dark", "btn-link",
}


def _plain_tokens(value):
    """Class tokens outside any {% %}/{{ }} template tag."""
    plain = TEMPLATE_TAG_RE.sub(" ", value)
    return plain.split()


def _add_btn_variant(value):
    tokens = _plain_tokens(value)
    if "btn" not in tokens:
        return value
    if any(t in _BTN_VARIANTS or t.startswith("btn-outline-") for t in tokens):
        return value
    return value.rstrip() + " btn-secondary" if value.strip() else value


def transform_class_value(value):
    """Rewrite class tokens, leaving {% %}/{{ }} template tags opaque."""
    out = []
    last = 0
    for tag in TEMPLATE_TAG_RE.finditer(value):
        out.append(_sub_plain(value[last:tag.start()]))
        out.append(tag.group(0))  # template tag, untouched
        last = tag.end()
    out.append(_sub_plain(value[last:]))
    return _add_btn_variant("".join(out))


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
    # 3) dismissible alerts: .alert-dismissible + BS5 .btn-close
    text = ALERT_DISMISS_RE.sub(_alert_dismiss_sub, text)
    # 4) form controls: add BS5 form-control/form-select/form-check-input classes
    text = FORM_TAG_RE.sub(_form_tag_sub, text)
    # 5) modal close buttons -> BS5 .btn-close
    text = MODAL_CLOSE_RE.sub(_modal_close_sub, text)
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
