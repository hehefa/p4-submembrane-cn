#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, urllib.parse, urllib.request
from pathlib import Path

SOURCE = "https://s.p4theater.top"
TARGET = "https://s.p4theater.cn"
ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/127 Mobile Safari/537.36 MicroMessenger/8.0.50"
ROUTES = ["/", "/en/", "/ja/"]
SEEDS = ["/favicon.svg", "/assets/app.987bc776488f.css", "/assets/app.1ead4747ed54.js"]
ASSET_RE = re.compile(r"/assets/[A-Za-z0-9._-]+")


def fetch(path: str) -> bytes:
    req = urllib.request.Request(SOURCE + path, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 200:
            raise RuntimeError(f"{path}: HTTP {r.status}")
        return r.read()


def write(path: str, data: bytes) -> None:
    dest = PUBLIC / path.lstrip("/")
    if path.endswith("/"):
        dest = dest / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def patch_html(raw: str, route: str) -> str:
    raw = raw.replace(SOURCE, TARGET)
    global_url = SOURCE + route
    marker = f'<link rel="alternate" href="{global_url}" data-edition="global-top">'
    if marker not in raw:
        raw = raw.replace("</head>", marker + "</head>", 1)

    edition_text = {
        "/": "国际版·.TOP",
        "/en/": "GLOBAL·.TOP",
        "/ja/": "GLOBAL·.TOP",
    }[route]
    edition_css = """<style id="edition-switch-style">
#edition-switch{position:fixed;left:14px;bottom:calc(14px + env(safe-area-inset-bottom));z-index:30;display:inline-flex;align-items:center;justify-content:center;min-height:46px;box-sizing:border-box;padding:0 13px;text-decoration:none;font-family:var(--mono);font-size:10px;letter-spacing:.13em;color:#9a948b;background:rgba(8,8,6,.64);border:1px solid rgba(244,239,228,.08);border-radius:3px;backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);touch-action:manipulation;transition:color .5s,border-color .5s}
#edition-switch:hover,#edition-switch:focus-visible{color:var(--bone);border-color:rgba(244,239,228,.2)}
@media(max-width:600px){#edition-switch{left:10px;min-height:44px;padding:0 11px}}
</style>"""
    if 'id="edition-switch-style"' not in raw:
        raw = raw.replace("</head>", edition_css + "</head>", 1)

    edition_link = (
        f'<a id="edition-switch" href="{global_url}" rel="alternate noopener" '
        f'hreflang="{route_language(route)}" aria-label="{edition_text}">{edition_text}</a>'
    )
    if 'id="edition-switch"' not in raw:
        raw = raw.replace(
            '<button id="exit" class="pill ui-control" type="button"></button>',
            '<button id="exit" class="pill ui-control" type="button"></button>\n' + edition_link,
            1,
        )
    return raw


def route_language(route: str) -> str:
    return {"/": "zh-Hans", "/en/": "en", "/ja/": "ja"}[route]


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    assets = set(SEEDS)
    pages = {}
    for route in ROUTES:
        text = fetch(route).decode("utf-8")
        text = patch_html(text, route)
        write(route, text.encode("utf-8"))
        pages[route] = len(text.encode("utf-8"))
        assets.update(ASSET_RE.findall(text))
    # JS contains all focus frames and texture atlases.
    queue = list(sorted(assets))
    seen = set()
    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        data = fetch(path)
        write(path, data)
        if path.endswith((".js", ".css")):
            text = data.decode("utf-8", errors="ignore")
            for child in ASSET_RE.findall(text):
                if child not in seen:
                    queue.append(child)
    robots = f"User-agent: *\nAllow: /\n\nSitemap: {TARGET}/sitemap.xml\n"
    write("/robots.txt", robots.encode())
    sitemap = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
'''
    for route in ROUTES:
        sitemap += f'''  <url><loc>{TARGET}{route}</loc><xhtml:link rel="alternate" hreflang="zh-Hans" href="{TARGET}/"/><xhtml:link rel="alternate" hreflang="en" href="{TARGET}/en/"/><xhtml:link rel="alternate" hreflang="ja" href="{TARGET}/ja/"/><xhtml:link rel="alternate" hreflang="x-default" href="{TARGET}/"/></url>\n'''
    sitemap += "</urlset>\n"
    write("/sitemap.xml", sitemap.encode())
    report = {
        "source": SOURCE,
        "target": TARGET,
        "routes": pages,
        "assets": len(seen),
        "bytes": sum(p.stat().st_size for p in PUBLIC.rglob("*") if p.is_file()),
        "files": sorted(str(p.relative_to(PUBLIC)) for p in PUBLIC.rglob("*") if p.is_file()),
    }
    (ROOT / "snapshot-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "files"}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
