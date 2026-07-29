"""Walk the real module graph the browser would load.

This is the test that catches the failure the microapp guide warns is the most
expensive one: the server is healthy, the page returns 200, and the app sits on
a blank screen forever because one ES module import resolved *above* the mount
point and 404'd. Nothing logs an error you would see -- the module graph simply
fails and your entry point never runs.

A hardcoded list of URLs to curl does not catch it, because it checks paths you
wrote rather than the ones the browser derives. So: fetch the entry point,
follow every `import ... from`, and assert each resolved URL both returns 200
*and* stays inside the mount prefix.

Run against a container started with BASE_PATH=/tycooncraft:
    BASE_URL=http://127.0.0.1:8081/tycooncraft pytest tests/test_module_graph.py
"""

from __future__ import annotations

import os
import re
import urllib.error          # explicit: importing urllib.request only happens to
import urllib.parse          # pull this in as a side effect in CPython
import urllib.request

import pytest

pytestmark = pytest.mark.live

BASE_URL = os.environ.get("BASE_URL")

# Matches `import x from './y.js'`, `import './y.css'`, and `export ... from '...'`.
IMPORT_RE = re.compile(
    r"""(?:^|\n)\s*(?:import|export)\b[^;'"\n]*?from\s*['"]([^'"]+)['"]|"""
    r"""(?:^|\n)\s*import\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)
HREF_SRC_RE = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""")


def fetch(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "module-graph-test"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, ""


@pytest.fixture(scope="module")
def base() -> str:
    if not BASE_URL:
        pytest.skip("set BASE_URL to run the module-graph test")
    return BASE_URL.rstrip("/") + "/"


def test_every_module_resolves_inside_the_mount(base):
    mount = urllib.parse.urlparse(base).path            # e.g. /tycooncraft/

    status, html = fetch(base)
    assert status == 200, f"the entry point itself returned {status}"
    assert "<script" in html, "no script tag -- did index.html get served?"

    # Seed the queue with everything the document references directly.
    queue: list[tuple[str, str]] = []
    for match in HREF_SRC_RE.finditer(html):
        raw = match.group(1)
        if raw.startswith(("data:", "http:", "https:", "#", "mailto:")):
            continue
        queue.append((urllib.parse.urljoin(base, raw), "index.html"))

    assert queue, "the document references no local assets at all"

    seen: set[str] = set()
    checked = 0
    problems: list[str] = []

    while queue:
        url, referrer = queue.pop()
        if url in seen:
            continue
        seen.add(url)

        path = urllib.parse.urlparse(url).path
        # The core assertion. A `../..` import climbing out of the mount lands
        # on the homepage's namespace, not ours, and 404s in production while
        # passing every test that only checks status codes at paths you chose.
        if not path.startswith(mount):
            problems.append(
                f"{path} (imported by {referrer}) escapes the mount {mount!r}"
            )
            continue

        status, body = fetch(url)
        checked += 1
        if status != 200:
            problems.append(f"{path} (imported by {referrer}) returned {status}")
            continue

        if url.endswith((".js", ".mjs")):
            for match in IMPORT_RE.finditer(body):
                spec = match.group(1) or match.group(2)
                if not spec or not spec.startswith("."):
                    continue        # bare specifiers would need an import map
                queue.append((urllib.parse.urljoin(url, spec), path))

    assert not problems, "module graph problems:\n  " + "\n  ".join(problems)
    assert checked >= 4, f"only walked {checked} assets; the graph looks too small"


def test_no_absolute_asset_urls_in_the_document(base):
    """An absolute `/src/main.js` resolves to the domain root, so it works at /
    and breaks under a subpath. Catch it in the source, not just in the graph."""
    _, html = fetch(base)
    offenders = [
        raw
        for raw in HREF_SRC_RE.findall(html)
        if raw.startswith("/") and not raw.startswith("//")
    ]
    assert not offenders, f"absolute asset URLs will 404 under a subpath: {offenders}"
