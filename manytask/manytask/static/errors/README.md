# Fallback page assets

`50x.html` is generated from `manytask/templates/backend_error.html` and the
assets in this directory. All assets are embedded so the page requires no
additional requests when the backend is unavailable. Rebuild from `manytask/`
with `.venv/bin/python scripts/build_error_page.py` and include the generated
document in the change. It can also be opened directly for a preview.

The logo and Nunito Sans fonts come from the Manytask style assets. Their
licenses are included alongside these files.

`mascot-sick.jpg` was generated with the built-in image generation tool, using
the Manytask mascot character sheet as a visual reference, and converted to
JPEG for the fallback page. The final generation prompt was:

> Use case: illustration-story. Asset type: production illustration for the Manytask backend error web page. Input image is a character reference, not an edit target. Create a single scene of this exact Manytask mascot sick in bed, resting against a cream pillow in a simple low wooden bed under a warm cream blanket, one thin black hand holding a thermometer near its small face, other hand resting on blanket. Tired closed eyes, tiny weary mouth, gentle reassuring mood. Preserve turquoise rounded square body, broad yellow/coral/cream ribbon M, small charcoal face ABOVE the central M valley, short free ribbon ends. Arms black; exactly two separate black legs may be naturally hidden under blanket, do not turn M ribbons into limbs. Keep upper M visible. Paper cutout and colored pencil grain, warm hand-drawn edges, soft internal blue shadow, matching reference. Palette #17C3B2 #33879E #FFE2B3 #F4717D #FFCB77. Landscape 3:2 composition, entire bed and character centered with generous clear margin. Solid warm off-white #FFFCF7 background, no room scenery, no text, no logos, no watermark.
