"""Text scanning helpers: rendered-text walking, language rules, denylist matching, service-name matching."""

from __future__ import annotations

import codecs
import re
import urllib.parse
from pathlib import Path

from . import config as C

URL_RE = re.compile(r"""https?://[^\s<>"'`)\]|]+""", re.I)
# Scheme-less host names in display text, for example "example.com/page" or "www.example.net".
BARE_HOST_RE = re.compile(r"(?<![A-Za-z0-9@/._-])((?:[A-Za-z0-9-]+\.)+(?:com|net|org|io|dev|app|co|info|biz|me|us|ai|cloud))"
                          r"(?=/|\b)(?![.-]?[A-Za-z0-9])", re.I)
_TRAIL = ".,;:!?*_"


def extract_urls(text: str) -> list:
    out = []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0)
        while u and u[-1] in _TRAIL:
            u = u[:-1]
        out.append(u)
    return out


def bare_hosts(text: str) -> list:
    """Host names written without a scheme (outside URLs), for example "evil.example.com/page"."""
    stripped = URL_RE.sub(" ", text or "")
    return [m.group(1).lower() for m in BARE_HOST_RE.finditer(stripped)]


def host_allowed(host: str) -> bool:
    return (host or "").lower() in C.ALLOWED_URL_HOSTS or (host or "").lower() == "github.com"


def url_allowed(url: str) -> bool:
    """https only; an allowlisted host; github.com only under an AWS organization; no path tricks."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    if any(ch.isspace() for ch in url) or "\\" in url:
        return False
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https" or parts.port is not None or "@" in parts.netloc or ":" in parts.netloc:
        return False
    host = (parts.hostname or "").lower()
    path = parts.path
    low = path.lower()
    if "//" in path or "%2e" in low or "%2f" in low or "%5c" in low:
        return False
    if any(seg in (".", "..") for seg in path.split("/")):
        return False
    if host in C.ALLOWED_URL_HOSTS:
        return True
    if host == "github.com":
        segs = [x for x in path.split("/") if x]
        return bool(segs) and segs[0].lower() in C.ALLOWED_GITHUB_ORGS
    return False


def is_self_repo_url(url: str) -> bool:
    """True for this repository's own URL, exactly or followed by "/", "#" or "?"."""
    base = C.SELF_REPO_URL
    if not url.startswith(base):
        return False
    rest = url[len(base):]
    return rest == "" or rest[0] in "/#?"


# ---------------------------------------------------------------------------
# Rendered lens text
# ---------------------------------------------------------------------------

def rendered_strings(doc: dict, lens_key: str):
    """Yield (where, field, text, statement_id_or_None, question_id_or_None) for every string in a rendered lens."""
    yield f"{lens_key}", "name", doc.get("name", ""), None, None
    yield f"{lens_key}", "description", doc.get("description", ""), None, None
    for p in doc.get("pillars", []):
        yield f"{lens_key}/{p['id']}", "name", p.get("name", ""), None, None
        for q in p.get("questions", []):
            qw = f"{lens_key}/{q['id']}"
            for k in ("title", "description"):
                yield qw, k, q.get(k, ""), None, q["id"]
            hr = q.get("helpfulResource") or {}
            yield qw, "helpfulResource.displayText", hr.get("displayText", ""), None, q["id"]
            if hr.get("url"):
                yield qw, "helpfulResource.url", hr["url"], None, q["id"]
            for c in q.get("choices", []):
                cw = f"{qw}/{c['id']}"
                sid = c["id"]
                yield cw, "title", c.get("title", ""), sid, q["id"]
                for k in ("helpfulResource", "improvementPlan"):
                    r = c.get(k) or {}
                    yield cw, f"{k}.displayText", r.get("displayText", ""), sid, q["id"]
                    if r.get("url"):
                        yield cw, f"{k}.url", r["url"], sid, q["id"]
                for a in c.get("additionalResources", []):
                    for i, item in enumerate(a.get("content", [])):
                        yield cw, f"additionalResources.{a['type']}[{i}].displayText", item.get("displayText", ""), sid, q["id"]
                        if item.get("url"):
                            yield cw, f"additionalResources.{a['type']}[{i}].url", item["url"], sid, q["id"]


READER_NOTE_LABEL = "Reader note:"
READER_NOTE_RE = re.compile(r"Reader note:.*?(?=(?:\s(?:Good looks like|Platform notes|Partition notes):)|$)", re.S)
# An inline reader note at the end of an improvement text must say why the linked page names a service.
READER_NOTE_STATUS_RE = re.compile(r"closed to new customers|end of support|maintenance|discontinued|"
                                   r"no longer (?:available|accept)|not needed|not required", re.I)


def strip_reader_notes(text: str) -> str:
    """Remove every "Reader note: ..." segment from rendered text (used where no source fields are available).

    The checks use strip_statement_reader_notes instead, which exempts only the reader_note source field and a
    trailing note in the improvement text, so an author cannot exempt text by typing "Reader note:" anywhere.
    """
    return READER_NOTE_RE.sub("", text or "")


def _norm(v) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def split_trailing_reader_note(text: str):
    """(body, note) for an improvement text that ends with exactly one "Reader note: ..."; note is None otherwise."""
    t = text or ""
    if t.count(READER_NOTE_LABEL) != 1:
        return t, None
    i = t.index(READER_NOTE_LABEL)
    return t[:i].rstrip(), t[i:]


def strip_statement_reader_notes(field: str, text: str, statement: dict | None):
    """Return (text_without_exempt_reader_notes, problems) for one rendered choice field.

    Exempt: the rendered reader_note field at the end of helpfulResource.displayText, and one trailing
    "Reader note:" in improvementPlan.displayText that states a lifecycle status ("closed to new customers",
    "end of support", ...). Any other "Reader note:" is a problem and is not exempt.
    """
    text = text or ""
    problems = []
    if statement is not None and field == "helpfulResource.displayText" and statement.get("reader_note"):
        suffix = f" {READER_NOTE_LABEL} {_norm(statement['reader_note'])}"
        if text.endswith(suffix):
            text = text[:-len(suffix)]
    elif statement is not None and field == "improvementPlan.displayText":
        body, note = split_trailing_reader_note(text)
        if note is not None:
            if READER_NOTE_STATUS_RE.search(note):
                text = body
            else:
                problems.append("the trailing 'Reader note:' in the improvement text must say why the linked page "
                                "names the service (for example 'closed to new customers' or 'end of support')")
    if READER_NOTE_LABEL.lower() in text.lower():
        problems.append("'Reader note:' may appear only in the reader_note field or once at the end of the "
                        "improvement text")
    return text, problems


# ---------------------------------------------------------------------------
# Language rules
# ---------------------------------------------------------------------------

_FWD = [re.compile(p, re.I) for p in C.FORWARD_LOOKING]
_INCL = [re.compile(p, re.I) for p in C.INCLUSIVE_DENYLIST]


def language_problems(text: str, ascii_only: bool = True) -> list:
    """Return a list of (kind, detail) language problems in one piece of text."""
    out = []
    if not text:
        return out
    for ch, name in C.DASHES.items():
        if ch in text:
            out.append(("dash", name))
    if ascii_only:
        bad = sorted({ch for ch in text if ord(ch) > 127 and ch not in C.DASHES})
        if bad:
            out.append(("non-ascii", " ".join(f"U+{ord(ch):04X}" for ch in bad)))
    prose = URL_RE.sub(" ", text)     # URL paths are not wording ("...-ending-soon/")
    for rx in _FWD:
        for m in rx.finditer(prose):
            out.append(("forward-looking", m.group(0)))
    for rx in _INCL:
        for m in rx.finditer(text):
            out.append(("inclusive-language", m.group(0)))
    return out


# ---------------------------------------------------------------------------
# Internal-wording denylist (private/denylist.txt)
# ---------------------------------------------------------------------------

def parse_denylist(text: str):
    """One regex per line; blank lines and # comments are skipped; case-insensitive unless prefixed "cs:".

    Returns (patterns, problems) where patterns is a list of (source_line_number, compiled_regex).
    """
    pats, problems = [], []
    for n, line in enumerate(text.splitlines(), 1):
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        flags = re.I
        if raw.startswith("cs:"):
            raw, flags = raw[3:], 0
        try:
            pats.append((n, re.compile(raw, flags)))
        except re.error as exc:
            problems.append(f"denylist line {n}: invalid regex ({exc})")
    return pats, problems


_EMPHASIS = "*_`~"


def _normalized(text: str, drop: str):
    """Collapse whitespace runs to one space and drop the characters in drop; return (text, original indexes)."""
    out, idx = [], []
    prev_space = False
    for i, ch in enumerate(text):
        if ch in drop:
            continue
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            idx.append(i)
            prev_space = True
            continue
        out.append(ch)
        idx.append(i)
        prev_space = False
    return "".join(out), idx


def scan_text_with_denylist(text: str, patterns):
    """Yield (line_number, matched_text) for every denylist hit in text.

    Three passes, so a phrase is found even when it is wrapped across lines, written with extra spaces, or split by
    Markdown emphasis: the raw text line by line, the whole text with whitespace collapsed, and the whole text with
    whitespace collapsed and the emphasis characters * _ ` ~ removed. Hits are reported once per line and match.
    """
    text = text or ""
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())

    def line_of(pos):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    seen = set()
    for ln, line in enumerate(text.splitlines(), 1):
        for _, rx in patterns:
            for m in rx.finditer(line):
                key = (ln, " ".join(m.group(0).split()).lower())
                if key not in seen:
                    seen.add(key)
                    yield ln, m.group(0)
    for drop in ("", _EMPHASIS):
        norm, idx = _normalized(text, drop)
        for _, rx in patterns:
            for m in rx.finditer(norm):
                if m.end() <= m.start():
                    continue
                ln = line_of(idx[m.start()])
                key = (ln, " ".join(m.group(0).split()).lower())
                if key not in seen:
                    seen.add(key)
                    yield ln, m.group(0)


def decode_text(data: bytes):
    """Decode file bytes as text: UTF-8 (optional BOM), or UTF-16/UTF-32 with a BOM. None when not text."""
    for bom, enc in ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
                     (codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"),
                     (codecs.BOM_UTF16_BE, "utf-16")):
        if data.startswith(bom):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                return None
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def is_binary(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return True
    return decode_text(data) is None


# ---------------------------------------------------------------------------
# Service names (partition check)
# ---------------------------------------------------------------------------

_WORD = r"(?:[A-Z0-9][A-Za-z0-9]*(?:[-.@&/][A-Za-z0-9]+)*)"
_CONNECT = r"(?:[ ]+(?:and|for|of|on)(?=[ ]+(?!AWS\b|Amazon\b)[A-Z0-9]))"
PRODUCT_RE = re.compile(r"(?<![A-Za-z0-9_-])(?:AWS|Amazon)(?:" + _CONNECT + r"?[ ]+" + _WORD + r")+")


def _words(s: str) -> list:
    """Words for prefix comparison: parentheticals dropped, hyphens and slashes treated as spaces."""
    s = re.sub(r"\([^)]*\)", " ", s)
    return re.sub(r"[-/]", " ", s).split()


def _is_word_prefix(prefix: list, words: list) -> bool:
    return bool(prefix) and len(prefix) <= len(words) and words[:len(prefix)] == prefix


class ServiceMatcher:
    """Find AWS and Amazon product names in text and map them to entries of data/partition-availability.yaml."""

    def __init__(self, entries: dict, ignore: list):
        self.names = {}                                   # display name or alias -> service key
        for key, e in entries.items():
            self.names[key] = key
            for a in e.get("aliases", []):
                self.names[a] = key
        # not_services entries match the whole run exactly, or by word prefix when they end with " *"
        self.ignore = []
        for x in ignore:
            x = str(x).strip()
            prefix = x.endswith(" *")
            self.ignore.append((_words(x[:-2] if prefix else x), prefix))
        self._name_words = sorted(((_words(n), k) for n, k in self.names.items()), key=lambda x: -len(x[0]))
        # Full "AWS ..."/"Amazon ..." names and CamelCase aliases match case-insensitively ("amazon cloudfront",
        # "cloudfront"); acronyms (ARC, IAM) and plain-word aliases (Budgets) stay case-sensitive, so ordinary words
        # ("an arc", "pod disruption budgets") do not match.
        self._name_res = []
        for n, k in sorted(self.names.items(), key=lambda x: -len(x[0])):
            camel = " " not in n and any(c.isupper() for c in n[1:]) and any(c.islower() for c in n)
            flags = re.I if (n.startswith(("AWS ", "Amazon ")) or camel) else 0
            self._name_res.append((re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(n) + r"(?![A-Za-z0-9_])", flags), k))

    def candidates(self, text: str) -> list:
        """Every capitalized run after AWS or Amazon, for example 'Amazon API Gateway' or 'AWS WAF'."""
        return [m.group(0) for m in PRODUCT_RE.finditer(text or "")]

    def resolve(self, run: str):
        """Return ('service', key), ('ignored', None) or ('unregistered', run) for one candidate run."""
        words = _words(run)
        for nw, key in self._name_words:
            if _is_word_prefix(nw, words):
                return "service", key
        for iw, prefix in self.ignore:
            if (prefix and _is_word_prefix(iw, words)) or (not prefix and iw == words):
                return "ignored", None
        if words and words[-1] in ("Blog", "Blogs", "Whitepaper", "Workshop", "Workshops"):
            return "ignored", None          # publication names, for example "AWS Security Blog"
        return "unregistered", run

    def unregistered(self, text: str) -> list:
        out = []
        for run in self.candidates(text):
            kind, val = self.resolve(run)
            if kind == "unregistered":
                out.append(val)
        return out

    def name_spans(self, text: str) -> list:
        """(start, end, key) for each registered name or alias in text, longest match first, without overlaps.

        "AWS Backup restore testing" yields the feature entry, not "AWS Backup"; the shorter name inside a longer
        match is dropped.
        """
        spans = []
        for rx, key in self._name_res:
            for m in rx.finditer(text or ""):
                spans.append((m.start(), m.end(), key))
        spans.sort(key=lambda x: (x[0], x[0] - x[1]))
        out, end = [], -1
        for st, en, key in spans:
            if st >= end:
                out.append((st, en, key))
                end = en
        return out

    def services_named(self, text: str) -> set:
        """Registered services named in text, by full name or alias (with or without the AWS/Amazon prefix)."""
        found = set()
        for run in self.candidates(text):
            kind, key = self.resolve(run)
            if kind == "service":
                found.add(key)
        for rx, key in self._name_res:
            if rx.search(text or ""):
                found.add(key)
        return found


# ---------------------------------------------------------------------------
# GovCloud availability claims (partition check, reverse direction)
# ---------------------------------------------------------------------------

# "<subject> is|are|remains not available in AWS GovCloud (US)" (or "... there" in a sentence that names GovCloud),
# and the positive form. A sentence that starts "In AWS GovCloud (US) ..., <subject> is available" counts as well.
GOV_CLAIM_RE = re.compile(r"\b(?:is|are|remains?)\s+(?P<neg>not\s+)?available\b"
                          r"(?P<where>\s+in\s+(?:both\s+|all\s+)?(?:of\s+)?(?:the\s+)?(?:AWS\s+)?GovCloud\b|\s+there\b)?")
GOV_PREFIX_RE = re.compile(r"(?:^|[:.;]\s*)In\s+(?:the\s+)?AWS\s+GovCloud\s+\(US\)[^,;]*,", re.I)
# Where the subject of a claim starts: the last clause boundary before the verb.
CLAUSE_BOUNDARY_RE = re.compile(r"[;:.!?](?:\s|$)|\((?=[^)]*$)|\b(?:but|so|while|because|since|where|whereas|that|"
                                r"which|though|although|unless|if|when)\b|\bas\b(?!\s+of\b)|"
                                r"\bIn\s+(?:the\s+)?AWS\s+GovCloud\s+\(US\)[^,;]*,", re.I)
# A name is the subject itself (not a modifier of a feature, as in "AWS CodePipeline cross-Region actions") when
# only the end of the subject, a comma or a list conjunction follows it.
TERMINAL_RE = re.compile(r"^\s*(?:\([^)]*\)\s*)?(?:$|,|\band\b|\bor\b|\bnor\b)")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def gov_availability_claims(text: str, matcher: ServiceMatcher) -> list:
    """(service_key, claims_available, subject) for each statement that text makes about AWS GovCloud (US).

    Only names that are the whole subject of the claim count: "Shield Advanced and CloudFront are not available in
    AWS GovCloud (US)" claims both, while "Lambda JSON log formatting is not available in AWS GovCloud (US)" claims
    nothing about AWS Lambda (the feature, if it has its own entry, is matched instead).
    """
    out, seen = [], set()
    for sentence in SENTENCE_SPLIT_RE.split(" ".join((text or "").split())):
        prev = 0
        for m in GOV_CLAIM_RE.finditer(sentence):
            before = sentence[:m.start()]
            where = m.group("where")
            gov = ("GovCloud" in where or "GovCloud" in before) if where else bool(GOV_PREFIX_RE.search(before))
            if gov:
                start = prev
                for b in CLAUSE_BOUNDARY_RE.finditer(sentence, prev, m.start()):
                    start = b.end()
                subject = sentence[start:m.start()]
                available = not m.group("neg")
                for _st, en, key in matcher.name_spans(subject):
                    if TERMINAL_RE.match(subject[en:]) and (key, available, subject) not in seen:
                        seen.add((key, available, subject))
                        out.append((key, available, subject.strip()))
            prev = m.end()
    return out


# ---------------------------------------------------------------------------
# Leftover placeholders
# ---------------------------------------------------------------------------

_PLACEHOLDERS = [(kind, re.compile(rx, flags)) for kind, rx, flags in C.PLACEHOLDER_PATTERNS]


def placeholder_problems(text: str) -> list:
    """(kind, match) for each leftover placeholder in text, for example {{RELEASE_DATE}} or <release date>."""
    out = []
    for kind, rx in _PLACEHOLDERS:
        for m in rx.finditer(text or ""):
            out.append((kind, m.group(0)))
    return out
