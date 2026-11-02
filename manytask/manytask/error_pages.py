"""Public error copy shared by the HTTP handler and static page builder."""

import json
from pathlib import Path

ERROR_ASSETS = Path(__file__).parent / "static" / "errors"
SERVICES = {"gitlab": "GitLab", "sourcecraft": "SourceCraft", "yandex-id": "Yandex ID"}
ERROR_PAGES: dict[str, dict[str, str]] = json.loads((ERROR_ASSETS / "messages.json").read_text())

for service, label in SERVICES.items():
    ERROR_PAGES[service] = {
        **ERROR_PAGES["unavailable"],
        "title": f"{label} is unavailable",
        "description": f"Manytask couldn't connect to {label}. Please try again in a few minutes.",
    }
    ERROR_PAGES[f"{service}-timeout"] = {
        **ERROR_PAGES["timeout"],
        "title": f"{label} didn't respond in time",
        "description": f"The request to {label} timed out. Please try again in a few minutes.",
    }
    ERROR_PAGES[f"{service}-access"] = {
        **ERROR_PAGES["unavailable"],
        "title": f"{label} denied access",
        "description": f"{label} rejected Manytask's request. Please contact your course staff.",
    }
