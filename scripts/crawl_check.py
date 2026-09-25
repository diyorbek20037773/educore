"""AC4.1 crawl: fetch every URL of `/sitemap.xml` (and each language alternate) and require HTTP 200.

Usage: `python scripts/crawl_check.py [BASE_URL]` (default http://localhost:8100).
Standard library only, so it runs on the host or in CI against a running stack. Also checks that every
HTML page links its stylesheet and contains no leaked template syntax, and reports the slowest pages.
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree  # noqa: S405 - parses our own sitemap

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9", "xhtml": "http://www.w3.org/1999/xhtml"}
LEAKS = ("{{", "{%", "VariableDoesNotExist", "TemplateSyntaxError", "Traceback")


def rebase(url: str, base: str) -> str:
    """Sitemap URLs carry the request host; crawl through BASE_URL instead."""
    target, parts = urlsplit(base), urlsplit(url)
    return urlunsplit((target.scheme, target.netloc, parts.path, parts.query, ""))


def fetch(url: str) -> tuple[int, bytes, float]:
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "educore-crawl-check"})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - our own site
            return response.status, response.read(), time.perf_counter() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), time.perf_counter() - started


def sitemap_urls(base: str) -> list[str]:
    status, body, _elapsed = fetch(f"{base}/sitemap.xml")
    if status != 200:
        raise SystemExit(f"sitemap.xml returned {status}")
    root = ElementTree.fromstring(body)  # noqa: S314
    urls: set[str] = set()
    for entry in root.findall("sm:url", NS):
        loc = entry.findtext("sm:loc", namespaces=NS)
        if loc:
            urls.add(rebase(loc, base))
        for alternate in entry.findall("xhtml:link", NS):
            urls.add(rebase(alternate.attrib["href"], base))
    return sorted(urls)


def check(url: str) -> tuple[str, int, float, str]:
    status, body, elapsed = fetch(url)
    problem = ""
    if status == 200:
        text = body.decode("utf-8", errors="replace")
        leak = next((marker for marker in LEAKS if marker in text), None)
        if leak:
            problem = f"template leak: {leak}"
        elif "css/output" not in text:
            problem = "stylesheet missing"
    return url, status, elapsed, problem


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8100").rstrip("/")
    urls = sitemap_urls(base)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(check, urls))
    failures = [r for r in results if r[1] != 200 or r[3]]
    for url, status, _elapsed, problem in failures:
        print(f"FAIL {status} {url} {problem}")
    slowest = sorted(results, key=lambda r: r[2], reverse=True)[:5]
    print("slowest:", ", ".join(f"{urlsplit(u).path} {t * 1000:.0f} ms" for u, _s, t, _p in slowest))
    print(f"checked {len(results)} URLs, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
