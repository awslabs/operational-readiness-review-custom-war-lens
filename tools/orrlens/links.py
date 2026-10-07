"""Link checker (run in CI and weekly).

- Every URL in lens-src/, data/, docs/ and README.md; https only; allowlisted hosts.
- HTTP 200 after redirects, with the final URL recorded in build/links-report.json.
- docs.aws.amazon.com: fails when the final URL differs from the requested URL (missing pages redirect to the
  guide's landing page with HTTP 200).
- builder.aws.com: article ids (/content/<id>/...) must be on data/builder-allowlist.yaml; up to 5 GETs with
  backoff; passes if any response title is "<article title> | AWS Builder Center"; "unverified" (not broken) when
  every attempt returns the generic shell; fails only for ids that are not on the allowlist; never uses body size.
  Other builder.aws.com pages (for example /build/capabilities) need HTTP 200 only.
- Well-Architected best-practice pages (URLs recorded in data/wa-best-practices.yaml): fail when the live title no
  longer contains the recorded best-practice id and title.
- Other redirects are reported; with --strict-redirects (the weekly run) they fail.
- URLs of this repository are host-checked only; /blob/main/<path> and /tree/main/<path> must exist locally.
- --changed-only <git-ref> checks only URLs added since that ref (pull requests fail only on links they add).
"""

from __future__ import annotations

import html
import json
import random
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config as C
from . import data as D
from .textscan import extract_urls, is_self_repo_url, url_allowed

MAX_WORKERS = 8
PER_HOST = 3
TIMEOUT = 25
GENERIC_BUILDER_TITLE = "AWS Builder Center"
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)

_host_locks: dict = {}
_host_guard = threading.Lock()


def _host_sem(host):
    with _host_guard:
        if host not in _host_locks:
            _host_locks[host] = threading.BoundedSemaphore(PER_HOST)
        return _host_locks[host]


# ---------------------------------------------------------------------------
# Collecting URLs
# ---------------------------------------------------------------------------

def source_files(root: Path) -> list:
    seen, out = set(), []
    for g in C.LINK_SOURCE_GLOBS:
        for p in sorted(root.glob(g)):
            rel = str(p.relative_to(root))
            if p.is_file() and rel not in seen:
                seen.add(rel)
                out.append(rel)
    return out


def collect(root: Path) -> dict:
    """url -> [file:line, ...] for every URL in the link sources."""
    urls: dict = {}
    for rel in source_files(root):
        try:
            lines = (root / rel).read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for ln, line in enumerate(lines, 1):
            for u in extract_urls(line):
                urls.setdefault(u, []).append(f"{rel}:{ln}")
    return urls


def urls_at_ref(root: Path, ref: str) -> set:
    paths = ["lens-src", "data", "docs", "README.md"]
    res = subprocess.run(["git", "-C", str(root), "grep", "-h", "-o", "-I", "-E", r"https?://[^[:space:]<>\"'`)|]+",
                          ref, "--", *paths], capture_output=True, text=True)
    if res.returncode not in (0, 1):
        raise RuntimeError(res.stderr.strip() or f"git grep failed for {ref}")
    return {u for line in res.stdout.splitlines() for u in extract_urls(line)}


def ref_exists(root: Path, ref: str) -> bool:
    return subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                          capture_output=True).returncode == 0


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.chain = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, attempts: int = 3, backoff: float = 2.0):
    """GET a URL. Returns dict(status, final_url, title, redirects, error)."""
    host = urllib.parse.urlsplit(url).netloc
    last = {"status": None, "final_url": None, "title": None, "redirects": [], "error": None}
    for i in range(attempts):
        handler = _Redirects()
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request(url, headers={"User-Agent": C.USER_AGENT,
                                                   "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                                                   "Accept-Language": "en-US,en;q=0.8"})
        try:
            with _host_sem(host):
                with opener.open(req, timeout=TIMEOUT) as resp:
                    body = resp.read(600_000).decode("utf-8", "replace")
                    m = TITLE_RE.search(body)
                    last = {"status": resp.status, "final_url": resp.geturl(),
                            "title": html.unescape(" ".join(m.group(1).split())) if m else None,
                            "redirects": handler.chain, "error": None}
            return last
        except urllib.error.HTTPError as exc:
            last = {"status": exc.code, "final_url": exc.geturl(), "title": None, "redirects": handler.chain,
                    "error": f"HTTP {exc.code}"}
            if exc.code not in (429, 500, 502, 503, 504):
                return last
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = {"status": None, "final_url": None, "title": None, "redirects": handler.chain,
                    "error": f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"}
        if i + 1 < attempts:
            time.sleep(backoff * (2 ** i) + random.uniform(0, 0.5))
    return last


def _same(a: str, b: str) -> bool:
    """Equal URLs, ignoring the fragment."""
    return a.split("#")[0] == b.split("#")[0]


def _trivial_redirect(a: str, b: str) -> bool:
    a, b = a.split("#")[0], b.split("#")[0]
    return a == b or a.rstrip("/") == b.rstrip("/") or a.replace("http://", "https://", 1) == b


def builder_article_id(url: str):
    parts = urllib.parse.urlsplit(url).path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "content":
        return parts[1]
    return None


def _norm(s: str) -> str:
    s = html.unescape(s or "").replace("\u2019", "'").replace("\u2018", "'")
    return " ".join(s.split()).lower()


# ---------------------------------------------------------------------------
# Checking one URL
# ---------------------------------------------------------------------------

def check_url(root: Path, url: str, builder: dict, bp_by_url: dict, strict_redirects: bool) -> dict:
    r = {"url": url, "status": "ok", "detail": "", "http": None, "final_url": None, "title": None}
    if not url.startswith("https://"):
        r.update(status="broken", detail="not https")
        return r
    if not url_allowed(url):
        r.update(status="broken", detail="host not on the allowlist")
        return r
    if is_self_repo_url(url):
        rest = url[len(C.SELF_REPO_URL):].split("#")[0].split("?")[0]
        m = re.match(r"^/(?:blob|tree)/main/(.+)$", rest)
        if m and not (root / urllib.parse.unquote(m.group(1))).exists():
            r.update(status="broken", detail=f"{m.group(1)} does not exist in this repository")
        else:
            r.update(status="skipped", detail="this repository (published at release)")
        return r
    host = urllib.parse.urlsplit(url).netloc.lower()

    if host == "builder.aws.com" and builder_article_id(url) is None:
        # Not an article (for example /build/capabilities, AWS Capabilities by Region). Its title is the generic
        # shell even when valid, so only the status is checkable.
        res = fetch(url)
        r.update(http=res["status"], final_url=res["final_url"], title=res["title"])
        if res["status"] != 200:
            r.update(status="broken", detail=res["error"] or f"HTTP {res['status']}")
        else:
            r.update(status="ok", detail="Builder Center page (not an article): HTTP 200; title not checkable")
        return r

    if host == "builder.aws.com":
        aid = builder_article_id(url)
        if aid not in builder:
            r.update(status="broken", detail=f"Builder Center article id {aid!r} is not on {C.DATA_BUILDER}")
            return r
        want = _norm(f"{builder[aid]['title']} | {GENERIC_BUILDER_TITLE}")
        seen_titles = []
        for i in range(5):
            res = fetch(url, attempts=2)
            r.update(http=res["status"], final_url=res["final_url"], title=res["title"])
            seen_titles.append(res["title"] or res["error"] or "")
            if res["status"] == 200 and _norm(res["title"]) == want:
                r.update(status="ok", detail=f"title matched on attempt {i + 1}")
                return r
            if i < 4:
                time.sleep(1.5 * (2 ** i) + random.uniform(0, 0.5))
        generic = all(_norm(x) == _norm(GENERIC_BUILDER_TITLE) for x in seen_titles)
        r.update(status="unverified",
                 detail="every attempt returned the generic AWS Builder Center shell" if generic
                 else f"article title not seen in 5 attempts (last: {seen_titles[-1]!r})")
        return r

    res = fetch(url)
    r.update(http=res["status"], final_url=res["final_url"], title=res["title"])
    if res["status"] != 200:
        r.update(status="broken", detail=res["error"] or f"HTTP {res['status']}")
        return r
    final = res["final_url"] or url
    if host == "docs.aws.amazon.com" and not _same(final, url):
        r.update(status="broken", detail=f"redirected to {final} (missing docs pages redirect to a landing page)")
        return r
    if url.split("#")[0] in bp_by_url:
        bp = bp_by_url[url.split("#")[0]]
        title = _norm(res["title"])
        if bp["id"].lower() not in title or _norm(bp["title"]) not in title:
            r.update(status="broken", detail=f"live title {res['title']!r} no longer matches "
                                             f"{bp['id']} {bp['title']!r}")
            return r
    if not _trivial_redirect(url, final):
        fhost = urllib.parse.urlsplit(final).netloc.lower()
        if fhost == "builder.aws.com" and builder_article_id(final) in builder:
            r.update(status="ok", detail=f"redirects to allowlisted Builder Center article {final}")
        else:
            r.update(status="broken" if strict_redirects else "redirected", detail=f"redirects to {final}")
    return r


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_links(root: Path, changed_only: str | None = None, strict_redirects: bool = False, quiet: bool = False,
              report: Path | None = None) -> dict:
    notes, fails = [], []
    urls = collect(root)
    if changed_only:
        if ref_exists(root, changed_only):
            before = urls_at_ref(root, changed_only)
            urls = {u: loc for u, loc in urls.items() if u not in before}
            notes.append(f"{len(urls)} URLs added since {changed_only}")
        else:
            notes.append(f"git ref {changed_only!r} not found; checking every URL instead")
    bdf = D.load_builder_allowlist(root)
    builder = bdf.entries if bdf is not None else {}
    if bdf is None:
        notes.append(f"{C.DATA_BUILDER} does not exist; every builder.aws.com link will fail")
    elif bdf.problems:
        fails += bdf.problems
    wa = D.load_wa_bps(root)
    bp_by_url = {}
    for e in (wa.entries.values() if wa is not None else []):
        for u in [e.get("url")] + list(e.get("alt_urls") or []):
            if u:
                bp_by_url[u] = e

    results = []
    items = sorted(urls.items())
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = [(u, loc, pool.submit(check_url, root, u, builder, bp_by_url, strict_redirects)) for u, loc in items]
        for u, loc, f in futs:
            try:
                r = f.result()
            except Exception as exc:  # never let one URL abort the run
                r = {"url": u, "status": "broken", "detail": f"checker error: {exc}"}
            r["locations"] = loc
            results.append(r)
    counts: dict = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        where = r["locations"][0] + (f" (+{len(r['locations']) - 1})" if len(r["locations"]) > 1 else "")
        if r["status"] == "broken":
            fails.append(f"{r['url']}: {r['detail']} [{where}]")
        elif r["status"] in ("unverified", "redirected"):
            notes.append(f"{r['status']}: {r['url']}: {r['detail']} [{where}]")
    notes.insert(0, f"{len(results)} URLs: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    report = report or (root / "build" / "links-report.json")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"changed_only": changed_only, "strict_redirects": strict_redirects,
                                  "results": results}, indent=2) + "\n", encoding="utf-8")
    notes.append(f"report: {report.relative_to(root) if report.is_relative_to(root) else report}")
    return {"fails": fails, "notes": notes, "results": results}
