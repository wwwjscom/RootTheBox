#!/usr/bin/env python3
"""BS2 vs BS5 parity: align two DOM/style trees (from extract.js dumps) and
report only what actually differs. Stdlib only, no dependencies.

Usage:
    python3 diff.py old.json new.json [--tol 2] [--out report.md]

old.json / new.json are the raw objects returned by extract.js, written
verbatim to disk. Alignment aligns each parent's children as a sequence
(difflib LCS) using a key of (tag, href/data-attrs/name/title/id/text) --
never raw class name, since class renames (.well -> .card etc.) are expected
everywhere in this port and are not bugs. Exact tag is used for the primary
LCS "equal" pass (tag renames are rare and exact-tag matching is far more
reliable when many sibling divs share no other discriminator); inside a
narrow "replace" window left over after that pass, unmatched children are
then paired positionally regardless of tag, as a best-effort last resort --
this is deliberately scoped to *just* that window, not the whole sibling
list, because pairing positionally across the whole list breaks badly the
moment one side has an extra wrapper (e.g. BS5 wrapping the navbar in a new
`<nav>` that BS2 didn't have at that position): everything after it would
otherwise silently pair against the wrong element. That whole-list version
was tried first against the real app and produced exactly that cascade.
"""
import argparse
import difflib
import json
import sys

# Properties that differ on essentially every element as a side effect of
# BS5's global `*{box-sizing:border-box}` reset (BS2 left box-sizing at its
# UA default of content-box everywhere). This is a real, universal, and
# harmless framework-level difference, not a per-element bug -- reporting it
# on every single row is pure noise, so it's excluded from the diff by
# default.
IGNORE_PROPS = {"boxSizing"}


def load(path):
    with open(path) as f:
        data = json.load(f)
    by_path = {}
    children = {}
    for el in data["elements"]:
        by_path[el["path"]] = el
        parent = el["path"].rsplit(".", 1)[0]
        if parent != el["path"]:
            children.setdefault(parent, []).append(el)
    return data, by_path, children


def direct_children(children_map, path):
    return children_map.get(path, [])


def child_key(el):
    """Identity key for sequence alignment: exact tag plus the most
    specific available discriminator. Two children with the same key are
    candidates to be "the same logical node" even if their class changed
    during the port (BS2's .well and BS5's .card, etc. still match here as
    long as tag+text/attrs line up)."""
    tag = el["tag"]
    attrs = el.get("attrs", {})
    if attrs.get("href"):
        return (tag, "href", attrs["href"])
    data_attrs = tuple(sorted((k, v) for k, v in attrs.items() if k.startswith("data-")))
    if data_attrs:
        return (tag, "data", data_attrs)
    if attrs.get("name"):
        return (tag, "name", attrs["name"], attrs.get("value", ""))
    if attrs.get("title"):
        return (tag, "title", attrs["title"])
    if el.get("id"):
        return (tag, "id", el["id"])
    text = el.get("text")
    if text:
        return (tag, "text", text)
    return (tag, None)


def pair_children(old_kids, new_kids):
    """Returns (pairs, unmatched_old, unmatched_new). See module docstring
    for the two-pass (LCS anchor, then windowed positional fallback)
    strategy and why it's split that way."""
    old_keys = [child_key(el) for el in old_kids]
    new_keys = [child_key(el) for el in new_kids]
    matcher = difflib.SequenceMatcher(a=old_keys, b=new_keys, autojunk=False)

    pairs = []
    unmatched_old = []
    unmatched_new = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            pairs.extend(zip(old_kids[i1:i2], new_kids[j1:j2]))
        elif tag == "replace":
            olds = old_kids[i1:i2]
            news = new_kids[j1:j2]
            n = min(len(olds), len(news))
            pairs.extend(zip(olds[:n], news[:n]))
            unmatched_old.extend(olds[n:])
            unmatched_new.extend(news[n:])
        elif tag == "delete":
            unmatched_old.extend(old_kids[i1:i2])
        elif tag == "insert":
            unmatched_new.extend(new_kids[j1:j2])

    return pairs, unmatched_old, unmatched_new


def describe(el):
    bits = [el["tag"]]
    if el.get("id"):
        bits.append("#" + el["id"])
    if el.get("text"):
        t = el["text"]
        if len(t) > 40:
            t = t[:40] + "..."
        bits.append('"%s"' % t)
    return " ".join(bits) + " (@%s)" % el["path"]


def rect_diff(old_rect, new_rect, tol):
    diffs = []
    labels = ["x", "y", "w", "h"]
    for label, o, n in zip(labels, old_rect, new_rect):
        if abs(o - n) > tol:
            diffs.append((label, o, n))
    return diffs


def diff_tree(old_root, new_root, old_children, new_children, tol,
              structural_only_old, structural_only_new, prop_diffs):
    pairs, unmatched_old, unmatched_new = pair_children(
        direct_children(old_children, old_root["path"]),
        direct_children(new_children, new_root["path"]),
    )
    structural_only_old.extend(unmatched_old)
    structural_only_new.extend(unmatched_new)

    for old_el, new_el in pairs:
        diffs = rect_diff(old_el["rect"], new_el["rect"], tol)
        style_diffs = []
        for prop, old_val in old_el["style"].items():
            if prop in IGNORE_PROPS:
                continue
            new_val = new_el["style"].get(prop)
            if old_val != new_val:
                style_diffs.append((prop, old_val, new_val))
        if diffs or style_diffs:
            prop_diffs.append((old_el, new_el, diffs, style_diffs))
        diff_tree(old_el, new_el, old_children, new_children, tol,
                  structural_only_old, structural_only_new, prop_diffs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--tol", type=float, default=2.0, help="px tolerance for rect diffs")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    old_data, old_by_path, old_children = load(args.old)
    new_data, new_by_path, new_children = load(args.new)

    old_root = old_by_path.get("0")
    new_root = new_by_path.get("0")
    if not old_root or not new_root:
        sys.exit("Could not find root element (path '0') in one of the inputs.")

    structural_only_old = []
    structural_only_new = []
    prop_diffs = []

    root_rdiffs = rect_diff(old_root["rect"], new_root["rect"], args.tol)
    root_sdiffs = [(p, v, new_root["style"].get(p)) for p, v in old_root["style"].items()
                   if p not in IGNORE_PROPS and v != new_root["style"].get(p)]
    if root_rdiffs or root_sdiffs:
        prop_diffs.append((old_root, new_root, root_rdiffs, root_sdiffs))

    diff_tree(old_root, new_root, old_children, new_children, args.tol,
              structural_only_old, structural_only_new, prop_diffs)

    lines = []
    lines.append("# Parity diff report")
    lines.append("")
    lines.append("- OLD: %s (viewport %sx%s, scrollWidth=%s, clientWidth=%s)" % (
        old_data["url"], old_data["viewport"][0], old_data["viewport"][1],
        old_data["scrollWidth"], old_data["clientWidth"]))
    lines.append("- NEW: %s (viewport %sx%s, scrollWidth=%s, clientWidth=%s)" % (
        new_data["url"], new_data["viewport"][0], new_data["viewport"][1],
        new_data["scrollWidth"], new_data["clientWidth"]))
    if new_data["scrollWidth"] > new_data["clientWidth"] + 1:
        lines.append("- **WARNING: NEW page has horizontal overflow** "
                      "(scrollWidth %s > clientWidth %s)" % (
                          new_data["scrollWidth"], new_data["clientWidth"]))
    lines.append("- old elements: %d, new elements: %d, matched-with-diffs: %d, "
                  "structural-only-old: %d, structural-only-new: %d" % (
                      old_data["count"], new_data["count"], len(prop_diffs),
                      len(structural_only_old), len(structural_only_new)))
    lines.append("")

    if structural_only_old:
        lines.append("## Present only in OLD (%d) -- missing/removed in the port" % len(structural_only_old))
        for el in structural_only_old:
            lines.append("- " + describe(el))
        lines.append("")

    if structural_only_new:
        lines.append("## Present only in NEW (%d) -- added during the port" % len(structural_only_new))
        for el in structural_only_new:
            lines.append("- " + describe(el))
        lines.append("")

    if prop_diffs:
        lines.append("## Property diffs on matched elements (%d)" % len(prop_diffs))
        for old_el, new_el, rdiffs, sdiffs in prop_diffs:
            lines.append("")
            lines.append("### " + describe(old_el) + "  vs  " + describe(new_el))
            for label, o, n in rdiffs:
                lines.append("- rect.%s: OLD %s -> NEW %s (delta %.1f)" % (label, o, n, n - o))
            for prop, o, n in sdiffs:
                lines.append("- %s: OLD `%s` -> NEW `%s`" % (prop, o, n))
    else:
        lines.append("## No property diffs on matched elements.")

    report = "\n".join(lines) + "\n"
    if args.out:
        with open(args.out, "w") as f:
            f.write(report)
        print("Wrote %s (%d matched-with-diffs, %d old-only, %d new-only)" % (
            args.out, len(prop_diffs), len(structural_only_old), len(structural_only_new)))
    else:
        print(report)


if __name__ == "__main__":
    main()
