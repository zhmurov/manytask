# Fallback page assets

The HTML variants are generated from `manytask/templates/backend_error.html`,
`manytask/error_pages.py`, `messages.json`, and the assets in this directory.
All assets are embedded so each page requires no
additional requests when the backend is unavailable. Rebuild from `manytask/`
with `.venv/bin/python scripts/build_error_page.py` and include the generated
documents in the change. They can also be opened directly for a preview:

- `internal.html`: an internal Manytask error, with the mascot in bed.
- `unavailable.html` and `50x.html`: the backend is unavailable or the cause is unknown.
- `gitlab.html`, `sourcecraft.html`, `yandex-id.html`: a known service connection failure.
- `*-access.html`: the named service rejected authentication or authorization.
- `timeout.html` and `*-timeout.html`: a timeout, with the clock illustration.
- `database.html`: a database request failed.

Service names are selected from typed exceptions and configured request hosts,
including wrapped causes. Unknown errors stay generic. Provider response bodies,
exception strings, SQL, credentials, and internal URLs are never shown on the page.
An already handled form or API error keeps its existing response.

`mascot-timeout.png` is the existing deadline sticker from the Manytask style
guide. `mascot-disconnected.jpg` was created with the built-in image generation
tool using the same character reference. Its prompt was:

> Use case: illustration-story. Create a single production web error illustration of the exact Manytask mascot from the reference, discovering a disconnected network cable. Turquoise rounded square tile body with large yellow/coral/cream ribbon M, small charcoal face above the central M valley, two thin black arms and exactly two separate black legs with black feet. Short free M ribbon ends are not limbs and do not hold anything. One black hand holds one unplugged network connector, the other hand gestures toward its matching connector resting on the ground just nearby; make the separation visually clear. Concerned but calm expression. Entire mascot and both feet visible, uncluttered. Paper cutout and colored pencil texture, warm off-white #FFFCF7 background, palette #17C3B2 #33879E #FFE2B3 #F4717D #FFCB77. Landscape 3:2 layout with generous margins. No bed, no room scene, no words, no UI, no logos apart from mascot's own M, no watermark.

The logo and Nunito Sans fonts come from the Manytask style assets. Their
licenses are included alongside these files.

The disconnected-cable illustration was then corrected with the built-in image
editing tool: one male RJ45 plug remains in the mascot's hand, and a router
with an empty female Ethernet socket replaces the second loose male connector.
The final edit prompt was:

> Edit this existing Manytask mascot illustration. Correct only the impossible cable connection. Keep the mascot, pose, expression, colors, ribbon M, two black arms, exactly two black legs and feet, paper texture, camera composition, warm off-white background, and the male RJ45 plug held by its left-side hand unchanged. REMOVE the second male RJ45 connector on the ground at lower right AND its cable running out to the right edge. Replace that second loose connector with one small simple neutral-gray network router sitting on the ground, with a clearly visible FEMALE RJ45 ETHERNET SOCKET on its near/front-left face, facing toward the held male plug. The socket must be an empty dark rectangular recessed hole, with tiny gold contacts inside and an empty keyed opening; NO projecting connector and NO plug sticking out of the router. The two connectors are not joined: the mascot is pointing at the empty router socket, showing where the unplugged cable belongs. This is a male PLUG to a female SOCKET connection, physically plausible. Keep props subordinate to the mascot, preserve generous margins. No text, no labels, no additional characters, no watermark. Preserve the existing 3:2 landscape framing.

`mascot-sick.jpg` was generated with the built-in image generation tool, using
the Manytask mascot character sheet as a visual reference, and converted to
JPEG for the fallback page. The final generation prompt was:

> Use case: illustration-story. Asset type: production illustration for the Manytask backend error web page. Input image is a character reference, not an edit target. Create a single scene of this exact Manytask mascot sick in bed, resting against a cream pillow in a simple low wooden bed under a warm cream blanket, one thin black hand holding a thermometer near its small face, other hand resting on blanket. Tired closed eyes, tiny weary mouth, gentle reassuring mood. Preserve turquoise rounded square body, broad yellow/coral/cream ribbon M, small charcoal face ABOVE the central M valley, short free ribbon ends. Arms black; exactly two separate black legs may be naturally hidden under blanket, do not turn M ribbons into limbs. Keep upper M visible. Paper cutout and colored pencil grain, warm hand-drawn edges, soft internal blue shadow, matching reference. Palette #17C3B2 #33879E #FFE2B3 #F4717D #FFCB77. Landscape 3:2 composition, entire bed and character centered with generous clear margin. Solid warm off-white #FFFCF7 background, no room scenery, no text, no logos, no watermark.
