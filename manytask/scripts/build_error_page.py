"""Build the self-contained fallback shared by Flask and the edge proxy.

Run from manytask/: .venv/bin/python scripts/build_error_page.py
"""

import base64
from pathlib import Path

COMPONENT = Path(__file__).resolve().parent.parent
ASSETS = COMPONENT / "manytask" / "static" / "errors"
EMBEDS = {
    "FONT_REGULAR": ("NunitoSans-Regular.woff2", "font/woff2"),
    "FONT_SEMIBOLD": ("NunitoSans-SemiBold.woff2", "font/woff2"),
    "LOGO": ("logo.svg", "image/svg+xml"),
    "MASCOT": ("mascot-sick.jpg", "image/jpeg"),
}


def build_error_page() -> str:
    document = (COMPONENT / "manytask" / "templates" / "backend_error.html").read_text()
    for name, (filename, mimetype) in EMBEDS.items():
        encoded = base64.b64encode((ASSETS / filename).read_bytes()).decode("ascii")
        document = document.replace(f"@@{name}@@", f"data:{mimetype};base64,{encoded}")
    return document


if __name__ == "__main__":
    (ASSETS / "50x.html").write_text(build_error_page())
