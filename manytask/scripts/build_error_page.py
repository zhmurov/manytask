"""Build the self-contained fallback shared by Flask and the edge proxy.

Run from manytask/: .venv/bin/python scripts/build_error_page.py
"""

import base64
import mimetypes
import sys
from html import escape
from pathlib import Path

COMPONENT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(COMPONENT))

from manytask.error_pages import ERROR_PAGES  # noqa: E402

ASSETS = COMPONENT / "manytask" / "static" / "errors"
EMBEDS = {
    "FONT_REGULAR": ("NunitoSans-Regular.woff2", "font/woff2"),
    "FONT_SEMIBOLD": ("NunitoSans-SemiBold.woff2", "font/woff2"),
    "LOGO": ("logo.svg", "image/svg+xml"),
}


def build_error_page(page_name: str = "50x") -> str:
    document = (COMPONENT / "manytask" / "templates" / "backend_error.html").read_text()
    page = ERROR_PAGES[page_name]
    embeds = {**EMBEDS, "MASCOT": (page["image"], mimetypes.guess_type(page["image"])[0] or "image/jpeg")}
    for name, (filename, mimetype) in embeds.items():
        encoded = base64.b64encode((ASSETS / filename).read_bytes()).decode("ascii")
        document = document.replace(f"@@{name}@@", f"data:{mimetype};base64,{encoded}")
    for key in ("title", "description", "alt"):
        document = document.replace(f"@@{key.upper()}@@", escape(page[key]))
    return document


if __name__ == "__main__":
    for name in ERROR_PAGES:
        (ASSETS / f"{name}.html").write_text(build_error_page(name))
