# Manytask landing page

The homepage is standalone HTML and CSS. The guides remain in Diplodoc, at their
existing URLs. Edit `index.html` and `assets/style.css` here; do not edit the
generated `html/index.html`.

From `docs/`, build the complete site:

```sh
make docs
python3 -m http.server 8000 --directory html
```

Open <http://localhost:8000/>. For a quick homepage-only build, use `make landing`;
guide links require a full docs build.

`scripts/build-landing.mjs` copies the page to the build's root `index.html` and
its assets to `landing-assets/`. The Make target, Docker image, and GitHub Pages
workflow all run this step after Diplodoc. Relative links support root domains
and project subpaths such as `/manytask/`.

`scripts/build-docs.mjs` renders from a temporary input snapshot that excludes
generated output and the standalone page's source, then packages both the guides
and homepage. This prevents a previous `html/` build from being copied over
freshly rendered guide pages on repeated builds. A failed build leaves the
previous output available.

The logo, Nunito Sans fonts, mascot illustration, and woven-ribbon pattern come
from the Manytask style guide. The mascot uses an existing illustration,
converted to JPEG for the web. Logo and font licenses are in `assets/licenses/`.
The course scoreboard contains explicitly labeled example data.
