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
JSONLD_RE = re.compile(r'(<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>)(.*?)(</script>)', re.S | re.I)
P4 = "https://p4theater.cn/#organization"
PERSON = "https://hefa.p4theater.cn/#person"
MOVIE = "https://p4theater.cn/shoot-self-with-you/#movie"
PARENT = "https://p4theater.cn/human-surrender/#work"


def patch_structured_data(raw: str, route: str) -> str:
    """Resolve the mirror's public entities without changing the artwork DOM."""
    address = TARGET + route
    work_id = address + "#work"
    matched = 0

    def replace(match: re.Match) -> str:
        nonlocal matched
        data = json.loads(match[2])
        nodes = data.get("@graph", [data])
        work = next((node for node in nodes if node.get("@type") == "CreativeWork"
                     and node.get("@id") == work_id), None)
        if work is None:
            return match[0]
        matched += 1
        work = dict(work)
        work["isBasedOn"] = {"@id": MOVIE}
        work["creator"] = {"@id": P4}
        work["publisher"] = {"@id": P4}
        work["mainEntityOfPage"] = {"@id": address + "#webpage"}
        work["description"] = work["description"].replace("Human Surrender Faction", "Human Surrender / Shoot Self with You")
        # The archive membership remains; the mother project and its work also
        # explicitly refer to one another. No work is attributed to He Fa alone.
        parts = work.get("isPartOf", [])
        parts = parts if isinstance(parts, list) else [parts]
        work["isPartOf"] = [item for item in parts if item.get("@id") != PARENT] + [{"@id": PARENT}]
        english_parent = route in ["/en/", "/ja/"]
        parent_page = "https://p4theater.cn/" + ("en/" if english_parent else "") + "human-surrender/"
        parent_name = "Human Surrender" if english_parent else "人类投降派"
        graph = [
            work,
            {"@type": "WebPage", "@id": address + "#webpage", "url": address,
             "name": work["name"], "inLanguage": route_language(route),
             "isPartOf": {"@id": TARGET + "/#website"},
             "mainEntity": {"@id": work_id},
             "breadcrumb": {"@id": address + "#breadcrumb"}},
            {"@type": "WebSite", "@id": TARGET + "/#website", "url": TARGET + "/",
             "name": "膜下 / Under the Membrane / 膜の下", "inLanguage": ["zh-Hans", "en", "ja"],
             "publisher": {"@id": P4}},
            {"@type": "Organization", "@id": P4, "name": "P4剧场",
             "alternateName": ["P4 Theater", "P4 Theatre"], "url": "https://p4theater.cn/"},
            {"@type": "Person", "@id": PERSON, "name": "何发", "alternateName": ["He Fa", "Fa He"],
             "url": "https://hefa.p4theater.cn/", "affiliation": {"@id": P4}},
            {"@type": "Movie", "@id": MOVIE, "name": "人类投降派",
             "alternateName": ["Human Surrender", "Shoot Self with You"],
             "url": "https://p4theater.cn/shoot-self-with-you/",
             "producer": {"@id": PERSON}, "editor": {"@id": PERSON},
             "creditText": "何发：发起、制片、剪辑；导演与编剧由剧组成员共同创作。",
             "isPartOf": {"@id": PARENT}, "subjectOf": {"@id": work_id}},
            {"@type": "CreativeWork", "@id": PARENT, "name": "人类投降派",
             "alternateName": "Human Surrender", "url": "https://p4theater.cn/human-surrender/",
             "hasPart": [{"@id": MOVIE}, {"@id": work_id}]},
            {"@type": "BreadcrumbList", "@id": address + "#breadcrumb", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "P4 Theater", "item": "https://p4theater.cn/"},
                {"@type": "ListItem", "position": 2, "name": parent_name, "item": parent_page},
                {"@type": "ListItem", "position": 3, "name": work["name"], "item": address},
            ]},
        ]
        encoded = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        return match[1] + encoded + match[3]

    result = JSONLD_RE.sub(replace, raw)
    if matched != 1:
        raise ValueError(f"{route}: expected exactly one existing artwork schema, found {matched}")
    return result


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
    return patch_structured_data(raw, route)


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
