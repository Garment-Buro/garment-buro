import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from image_optimization import optimize_image_bytes
from optimize_existing_images import convert_uploads, update_database_references


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

    def test_existing_upload_migration_updates_text_urls_and_backs_up_database(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            uploads = root / "uploads"
            uploads.mkdir()
            source = uploads / "product.png"
            source.write_bytes(make_png())

            database = root / "ecommerce.db"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE products (image_url TEXT, gallery TEXT)")
            connection.execute(
                "INSERT INTO products VALUES (?, ?)",
                ("/uploads/product.png", "/uploads/product.png,/uploads/other.webp"),
            )
            connection.commit()
            connection.close()

            replacements, source_bytes, webp_bytes = convert_uploads(uploads)
            updated_rows, backup = update_database_references(database, replacements)

            self.assertEqual(
                replacements,
                {"/uploads/product.png": "/uploads/product.webp"},
            )
            self.assertLess(webp_bytes, source_bytes)
            self.assertTrue((uploads / "product.webp").exists())
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertEqual(updated_rows, 2)

            connection = sqlite3.connect(database)
            row = connection.execute("SELECT image_url, gallery FROM products").fetchone()
            connection.close()
            self.assertEqual(row[0], "/uploads/product.webp")
            self.assertIn("/uploads/product.webp", row[1])


if __name__ == "__main__":
    unittest.main()
