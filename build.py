#!/usr/bin/env python3
"""Build the «Лягушка VPN» subscription page for remnawave/subscription-page.

Reads src/page.html, config.json, apps.json, icons/*.png and vendor/qrcode.min.js and writes:

    dist/index.html    EJS template to mount over /opt/app/frontend/index.html in the container
    dist/preview.html  the same page with demo data, to open locally in a browser

Only the Python standard library is needed:  python3 build.py
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
PLATFORMS = {"ios", "macos", "appletv", "android", "androidtv", "windows"}

DEMO = {
    "response": {
        "isFound": True,
        "user": {
            "shortUuid": "demo",
            "daysLeft": 23,
            "trafficUsedBytes": str(int(18.4 * 1024**3)),
            "trafficLimitBytes": "0",
            "username": "demo_user",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(days=22, hours=6)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "isActive": True,
            "userStatus": "ACTIVE",
        },
        "links": [],
        "ssConfLinks": {},
        "subscriptionUrl": "https://sub.example.com/AbCdEf123456GhIj",
    }
}


def load_apps() -> list[dict]:
    apps = json.loads((ROOT / "apps.json").read_text("utf-8"))
    seen = set()
    for a in apps:
        for key in ("id", "name", "platforms", "stores"):
            if key not in a:
                raise SystemExit(f"apps.json: {a.get('id', '?')} has no '{key}'")
        if a["id"] in seen:
            raise SystemExit(f"apps.json: duplicate id {a['id']}")
        seen.add(a["id"])
        bad = set(a["platforms"]) - PLATFORMS
        if bad:
            raise SystemExit(f"apps.json: {a['id']} has unknown platforms {sorted(bad)}")
        deep = a.get("deep_link") or ""
        if deep and "{url}" not in deep and "{enc}" not in deep:
            raise SystemExit(f"apps.json: {a['id']} deep_link needs {{url}} or {{enc}}")
    return apps


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def attr(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def build() -> None:
    cfg = json.loads((ROOT / "config.json").read_text("utf-8"))
    apps = load_apps()
    icons = {a["id"]: data_uri(ROOT / "icons" / f"{a['id']}.png") for a in apps if (ROOT / "icons" / f"{a['id']}.png").exists()}
    src = (ROOT / "src" / "page.html").read_text("utf-8")

    common = {
        "@@META_DESCRIPTION@@": attr(cfg.get("description", "")),
        "@@FROG_ICON@@": data_uri(ROOT / "icons" / "frog.png"),
        "@@SUPPORT_URL@@": cfg.get("support_url", ""),
        "@@CABINET_URL@@": cfg.get("cabinet_url", ""),
        "@@QRCODE_LIB@@": (ROOT / "vendor" / "qrcode.min.js").read_text("utf-8"),
        "@@APPS_JSON@@": js(apps),
        "@@ICONS_JSON@@": js(icons),
    }

    def render(extra: dict) -> str:
        html = src
        for key, value in {**common, **extra}.items():
            html = html.replace(key, value)
        if "@@" in html:
            raise SystemExit("src/page.html has a placeholder build.py does not fill")
        return html

    title = attr(cfg.get("title", "Подписка"))
    tpl = render({"@@META_TITLE@@": title, "@@DEMO_JSON@@": "null", "@@PANEL_DATA@@": "\x00PANEL\x00"})
    # The container renders the file with EJS: nothing inlined may contain EJS tags.
    if "<%" in tpl or "%>" in tpl:
        raise SystemExit("inlined content contains EJS delimiters (<% or %>), refusing to build")
    tpl = tpl.replace("\x00PANEL\x00", "<%- panelData %>")

    preview = render({"@@META_TITLE@@": title + " (превью)", "@@DEMO_JSON@@": js(DEMO), "@@PANEL_DATA@@": ""})

    DIST.mkdir(exist_ok=True)
    (DIST / "index.html").write_text(tpl, "utf-8")
    (DIST / "preview.html").write_text(preview, "utf-8")
    print(f"dist/index.html {len(tpl) // 1024} KB, dist/preview.html {len(preview) // 1024} KB, apps: {', '.join(a['id'] for a in apps)}")


if __name__ == "__main__":
    build()
