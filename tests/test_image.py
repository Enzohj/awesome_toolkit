"""Tests for the public image conversion APIs."""

from __future__ import annotations

import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image as PIL_Image

from my_toolkit import image as image_mod


class TestImageConversions(unittest.TestCase):
    def _make_img(self):
        # 生成一个小的 RGBA 图像，覆盖 JPEG 兼容转换路径
        return PIL_Image.new("RGBA", (16, 8), color=(10, 20, 30, 40))

    def test_img_bytes_roundtrip(self):
        img = self._make_img()
        b = image_mod.img_to_bytes(img, fmt="png")
        self.assertIsInstance(b, (bytes, bytearray))
        img2 = image_mod.bytes_to_img(b)
        self.assertEqual(img2.size, img.size)

    def test_formatless_alpha_capable_images_default_to_png_bytes(self):
        images = (
            PIL_Image.new("RGBA", (2, 2), color=(10, 20, 30, 40)),
            PIL_Image.new("LA", (2, 2), color=(10, 40)),
            PIL_Image.new("P", (2, 2)),
        )

        for img in images:
            with self.subTest(mode=img.mode):
                encoded = image_mod.img_to_bytes(img)
                decoded = image_mod.bytes_to_img(encoded)
                self.assertEqual(decoded.format, "PNG")

    def test_base64_roundtrip_with_prefix(self):
        img = self._make_img()
        b64 = image_mod.img_to_base64(img, with_data_prefix=True, fmt="png")
        self.assertTrue(b64.startswith("data:image/"))
        raw = image_mod.base64_to_bytes(b64)
        self.assertGreater(len(raw), 0)
        img2 = image_mod.base64_to_img(b64)
        self.assertEqual(img2.size, img.size)

    def test_download_invalid_url(self):
        with self.assertRaises(ValueError):
            image_mod.download_bytes_from_url("not-a-url")


class TestMyImage(unittest.TestCase):
    def _make_img(self):
        return PIL_Image.new("RGB", (10, 10), color=(255, 0, 0))

    def test_construct_from_img_and_properties(self):
        mi = image_mod.MyImage(img=self._make_img())
        self.assertEqual(mi.size, (10, 10))
        self.assertEqual(mi.mode, "RGB")
        self.assertIsInstance(mi.byte, (bytes, bytearray))
        self.assertIsInstance(mi.base64, str)
        self.assertTrue(mi.base64_with_prefix.startswith("data:image/"))

    def test_formatless_alpha_capable_myimage_defaults_to_png(self):
        images = (
            PIL_Image.new("RGBA", (2, 2), color=(10, 20, 30, 40)),
            PIL_Image.new("LA", (2, 2), color=(10, 40)),
            PIL_Image.new("P", (2, 2)),
        )

        for img in images:
            with self.subTest(mode=img.mode):
                wrapped = image_mod.MyImage(img=img)
                self.assertEqual(wrapped.format, "png")
                self.assertEqual(image_mod.bytes_to_img(wrapped.byte).format, "PNG")

    def test_construct_from_bytes(self):
        raw = image_mod.img_to_bytes(self._make_img(), fmt="png")
        mi = image_mod.MyImage(byte=raw)
        self.assertEqual(mi.size, (10, 10))

    def test_byte_is_isolated_from_mutating_the_returned_img_copy(self):
        raw = image_mod.img_to_bytes(self._make_img(), fmt="png")
        mi = image_mod.MyImage(byte=raw)
        self.assertEqual(image_mod.bytes_to_img(mi.byte).getpixel((0, 0)), (255, 0, 0))

        editable_copy = mi.img
        editable_copy.putpixel((0, 0), (0, 255, 0))

        self.assertEqual(image_mod.bytes_to_img(mi.byte).getpixel((0, 0)), (255, 0, 0))

    def test_construct_from_base64(self):
        b64 = image_mod.img_to_base64(self._make_img(), with_data_prefix=True, fmt="png")
        mi = image_mod.MyImage(base64=b64)
        self.assertEqual(mi.size, (10, 10))
        # base64 属性为纯 base64，不含前缀
        self.assertFalse(mi.base64.startswith("data:image/"))

    def test_base64_is_isolated_from_mutating_the_returned_img_copy(self):
        encoded = image_mod.img_to_base64(
            self._make_img(), with_data_prefix=True, fmt="png"
        )
        mi = image_mod.MyImage(base64=encoded)
        self.assertEqual(image_mod.base64_to_img(mi.base64).getpixel((0, 0)), (255, 0, 0))

        editable_copy = mi.img
        editable_copy.putpixel((0, 0), (0, 0, 255))

        self.assertEqual(image_mod.base64_to_img(mi.base64).getpixel((0, 0)), (255, 0, 0))

    def test_mode_changing_edits_are_rewrapped_without_losing_alpha(self):
        jpeg = image_mod.img_to_bytes(self._make_img(), fmt="jpeg")
        original = image_mod.MyImage(byte=jpeg)

        edited = original.img
        edited.putalpha(0)
        replacement = image_mod.MyImage(img=edited)

        self.assertEqual(original.mode, "RGB")
        self.assertEqual(replacement.format, "png")
        decoded = image_mod.bytes_to_img(replacement.byte)
        self.assertEqual(decoded.mode, "RGBA")
        self.assertEqual(decoded.getpixel((0, 0))[3], 0)

    def test_rejects_data_url_when_declared_mime_conflicts_with_payload(self):
        buffer = io.BytesIO()
        self._make_img().save(buffer, format="PNG")
        payload = base64.b64encode(buffer.getvalue()).decode("ascii")

        with self.assertRaises(image_mod.ImageFormatError):
            image_mod.MyImage(base64=f"data:image/jpeg;base64,{payload}")

    def test_reject_multiple_sources(self):
        with self.assertRaises(ValueError):
            image_mod.MyImage(path="x.png", url="https://example.com/x.png")

    def test_save_creates_parent_dir(self):
        mi = image_mod.MyImage(img=self._make_img())
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b.png"
            out = mi.save(p, fmt="png")
            self.assertTrue(out.exists())

    def test_context_manager_close(self):
        raw = image_mod.img_to_bytes(self._make_img(), fmt="png")
        with image_mod.MyImage(byte=raw) as mi:
            self.assertEqual(mi.size, (10, 10))


if __name__ == "__main__":
    unittest.main(verbosity=2)
