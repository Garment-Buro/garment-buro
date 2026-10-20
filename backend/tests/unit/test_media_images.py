import unittest
from io import BytesIO

from PIL import Image

from app.modules.media.images import optimize_image_bytes


def make_png(size=(800, 600), *, alpha=True) -> bytes:
    mode = "RGBA" if alpha else "RGB"
    color = (20, 40, 60, 180) if alpha else (20, 40, 60)
    image = Image.new(mode, size, color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class ImageOptimizationTests(unittest.TestCase):
    def test_png_becomes_smaller_webp_and_keeps_alpha(self):
        original = make_png()
        optimized = optimize_image_bytes(original)

        self.assertIsNotNone(optimized)
        self.assertLess(len(optimized), len(original))
        with Image.open(BytesIO(optimized)) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.mode, "RGBA")

    def test_large_image_is_resized(self):
        original = make_png((3000, 2000), alpha=False)
        optimized = optimize_image_bytes(original, max_dimension=1200)

        self.assertIsNotNone(optimized)
        with Image.open(BytesIO(optimized)) as image:
            self.assertEqual(max(image.size), 1200)


if __name__ == "__main__":
    unittest.main()
