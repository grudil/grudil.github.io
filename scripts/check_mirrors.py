#!/usr/bin/env python3
"""Fail CI when index.html and ru.html drift apart (structure, scripts, headline title)."""
import re
import sys
from html.parser import HTMLParser

# These attributes (values and even presence) legitimately differ between mirrors.
IGNORED_ATTRS = {"lang", "aria-label", "aria-current", "hreflang", "content"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}
HEADLINE = re.compile(r"\b(Senior|Lead)\s+Python\s+Backend")


def tag_signature(tag, attrs):
    parts = sorted(f"class={v}" if n == "class" else n
                   for n, v in attrs if n not in IGNORED_ATTRS)
    return f"<{tag} {' '.join(parts)}>" if parts else f"<{tag}>"


class Skeleton(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        self.events.append((" > ".join(self.stack + [tag]), tag_signature(tag, attrs)))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.events.append((" > ".join(self.stack + [tag]), tag_signature(tag, attrs)))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]
        self.events.append((" > ".join(self.stack + [tag]), f"</{tag}>"))


def skeleton_events(text):
    parser = Skeleton()
    parser.feed(text)
    return parser.events


def check_skeletons(en, ru, errors):
    a, b = skeleton_events(en), skeleton_events(ru)
    for i, ((path_a, sig_a), (path_b, sig_b)) in enumerate(zip(a, b)):
        if sig_a != sig_b:
            errors.append(f"tag skeleton diverges at event {i}: "
                          f"index.html has {sig_a} at '{path_a}', "
                          f"ru.html has {sig_b} at '{path_b}'")
            return
    if len(a) != len(b):
        longer, path, sig = ("index.html", *a[len(b)]) if len(a) > len(b) else ("ru.html", *b[len(a)])
        errors.append(f"tag skeleton diverges: {longer} has extra {sig} at '{path}'")


def check_scripts(en, ru, errors):
    a, b = (re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", t, re.S) for t in (en, ru))
    if len(a) != len(b):
        errors.append(f"inline <script> count differs: index.html has {len(a)}, ru.html has {len(b)}")
    for i, (sa, sb) in enumerate(zip(a, b)):
        if sa != sb:
            errors.append(f"inline <script> block #{i + 1} is not byte-identical between index.html and ru.html")


def headline_strings(name, text):
    if name.endswith(".md"):
        heading = re.search(r"^#\s+(.+)$", text, re.M)
        return [("README heading", heading.group(1) if heading else "")]
    found = [("<title>", re.search(r"<title>(.*?)</title>", text, re.S)),
             ("og:title", re.search(r'property="og:title"\s+content="([^"]*)"', text)),
             ("meta description", re.search(r'name="description"\s+content="([^"]*)"', text)),
             (".role", re.search(r'class="role"[^>]*>(.*?)</p>', text, re.S))]
    return [(label, m.group(1) if m else "") for label, m in found]


def check_titles(files, errors):
    qualifiers = {}
    for name, text in files.items():
        for label, value in headline_strings(name, text):
            m = HEADLINE.search(value)
            if not m:
                errors.append(f"{name}: {label} has no 'Senior/Lead Python Backend' headline (got: '{value.strip()[:80]}')")
            else:
                qualifiers[f"{name} {label}"] = m.group(1)
    if len(set(qualifiers.values())) > 1:
        detail = ", ".join(f"{k}='{v}'" for k, v in sorted(qualifiers.items()))
        errors.append(f"headline title qualifier inconsistent across files: {detail}")


def main():
    files = {name: open(name, encoding="utf-8").read()
             for name in ("index.html", "ru.html", "README.md")}
    errors = []
    check_skeletons(files["index.html"], files["ru.html"], errors)
    check_scripts(files["index.html"], files["ru.html"], errors)
    check_titles(files, errors)
    for error in errors:
        print(f"MIRROR CHECK FAILED: {error}")
    if errors:
        sys.exit(1)
    print("Mirror check passed: skeletons match, scripts identical, titles consistent.")


if __name__ == "__main__":
    main()
