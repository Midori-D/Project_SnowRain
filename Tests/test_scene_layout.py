import struct
import unittest
import zlib

from Tools.prepare_data import PNG_SIGNATURE, png_chunk, sprite_horizontal_bounds
from Tools.scene_script import rendered_layer


class SceneLayoutTests(unittest.TestCase):
    def test_expression_and_base_use_the_same_coordinate_scale(self):
        base = {"x": 0, "y": 19, "image": "placeholder-base.png"}
        expression = {"x": 81, "y": 60, "image": "placeholder-expression.png"}
        self.assertEqual(rendered_layer("illuster", base)["y"], 28)
        patch = rendered_layer("illuster", expression)
        self.assertEqual((patch["x"], patch["y"]), (121, 90))
        self.assertEqual(rendered_layer("phone", expression), expression)
        self.assertEqual(rendered_layer("cartoon", {"x": -3, "y": 1})["x"], -4)

    def test_centering_ignores_transparent_sprite_columns(self):
        rows = [bytes([1]) + b"".join(bytes((0, 0, 0, value)) for value in row)
                for row in ((0, 0, 120, 135), (0, 0, 80, 176))]
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        pixels = compressor.compress(b"".join(rows)) + compressor.flush()
        header = struct.pack(">II5B", 4, len(rows), 8, 6, 0, 0, 0)
        png = (PNG_SIGNATURE + png_chunk(b"CgBI", b"") + png_chunk(b"IHDR", header)
               + png_chunk(b"IDAT", pixels) + png_chunk(b"IEND", b""))
        self.assertEqual(sprite_horizontal_bounds(png), (2, 4))
