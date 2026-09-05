"""Print story outline data from the project's Manrope font.

Run with: uv run --with fonttools --with brotli --with skia-pathops
    python scripts/build-story-outlines.py /path/to/manrope.woff2
Unioning the filled glyphs before stroking removes variable-font overlaps.
"""

import json
import sys

import pathops
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

font = TTFont(sys.argv[1])
if "fvar" in font:
    font = instantiateVariableFont(font, {"wght": 800}, inplace=True)
glyphs = font.getGlyphSet()
cmap = font.getBestCmap()
scale = 1000 / font["head"].unitsPerEm
result = []
for word in ("NIKITA", "MOISEEV", "GARMENT", "BURO"):
    outline = pathops.Path()
    x = 0
    for character in word:
        glyph = glyphs[cmap[ord(character)]]
        glyph.draw(TransformPen(outline.getPen(), (scale, 0, 0, -scale, x, 800)))
        x += glyph.width * scale - 55
    outline = pathops.simplify(outline)
    pen = SVGPathPen(None, ntos=lambda number: str(round(number, 2)))
    outline.draw(pen)
    result.append({"label": word, "width": round(x + 55, 2), "path": pen.getCommands()})
print(json.dumps(result))
