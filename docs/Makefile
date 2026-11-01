# Diplodoc: from repo root: `make -C docs`; from docs/: `make` or `make docs`.
DOCS_HTML_DIR := html

.PHONY: docs landing

docs:
	@command -v npm >/dev/null 2>&1 || { echo "\033[0;31mError: npm is not installed.\033[0m"; exit 1; }
	@command -v yfm >/dev/null 2>&1 || { echo "\033[0;31mError: yfm is not installed. Run: sudo npm i @diplodoc/cli -g\033[0m"; exit 1; }
	node scripts/build-docs.mjs "$(DOCS_HTML_DIR)"

# Quick landing-only preview; a full docs build supplies the linked guide pages.
landing:
	node scripts/build-landing.mjs "$(DOCS_HTML_DIR)"
