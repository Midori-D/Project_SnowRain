from types import SimpleNamespace
import unittest

from Tools.portraits import character_layers


class PortraitTests(unittest.TestCase):
    def exists(self, name):
        return True

    def horizontal_bounds(self, name):
        return (0, 200) if "Cloth" in name else (0, 104)

    def layer(self, name, x, y):
        return {"image": name, "x": x, "y": y}

    def test_cloth_base_and_expression_use_the_same_anchor(self):
        actor = SimpleNamespace(actor=0, outfit=3, expression=10)
        self.assertEqual(character_layers(self, {0: actor}), [
            {"image": "character_0_Cloth_3.png", "x": 80, "y": 134},
            {"image": "character_bface_1.png", "x": 162, "y": 55},
            {"image": "character_face_0_10.png", "x": 176, "y": 86},
        ])

    def test_two_portraits_face_inward_and_keep_their_own_outfits(self):
        first = SimpleNamespace(actor=0, outfit=3, expression=10)
        second = SimpleNamespace(actor=3, outfit=1, expression=6)
        layers = character_layers(self, {0: first, 1: second})
        self.assertEqual([layer["image"] for layer in layers], [
            "character_0_Cloth_3.png", "character_bface_1.png", "character_face_0_10.png",
            "character_3_Cloth_1.png", "character_bface_2.png", "character_face_3_6.png",
        ])
        self.assertTrue(all(layer.get("mirrored") for layer in layers))
        self.assertEqual([layer["x"] for layer in layers], [-20, 19, 52, 202, 221, 228])

    def test_character_without_loaded_cloth_has_no_portrait_parts(self):
        actor = SimpleNamespace(actor=0, outfit=-1, expression=10)
        self.assertEqual(character_layers(self, {0: actor}), [])
