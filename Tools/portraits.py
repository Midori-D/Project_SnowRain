"""Compose the Korean iOS 1.4 opening's layered portraits."""

import struct


BASE_FACES = (1, 1, 2, 2, 3, 17, 4, 5, 6, 7, 7, 8, 9, 10, 11, 12, 12, 13, 13, 14, 15)
EXPRESSION_FACES = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 10, 11, 12, 13, 0, 1, 2, 3, 4, 5, 14, 15, 16, 17)

# The iOS 1.4 coordinate setters contain these pixel corrections for the
# outfits reached in the opening. Each entry is the cloth, base face and
# expression triplet after _vSetChaDefault, _vSetChaBface and _vSetChaface.
OPENING_OFFSETS = {
    (0, 1): ((-75, -120, 3), (82, 82, 39), (31, 96, 72)),
    (0, 3): ((-75, -120, 3), (82, 82, 39), (31, 96, 72)),
    (1, 1): ((-60, -120, 0), (79, 40, 39), (31, 54, 72)),
    (1, 3): ((-60, -120, 0), (79, 40, 39), (31, 54, 72)),
    (2, 1): ((-51, -132, 9), (75, 28, 26), (31, 61, 33)),
    (2, 3): ((-51, -132, 9), (75, 28, 28), (31, 61, 35)),
    (3, 1): ((-48, -132, 9), (79, 28, 19), (31, 61, 26)),
    (3, 3): ((-48, -132, 9), (79, 28, 16), (31, 61, 23)),
    (4, 1): ((-48, -72, 3), (80, 19, 45), (33, 28, 55)),
    (4, 8): ((-46, -70, 3), (80, 16, 45), (33, 25, 56)),
    (5, 8): ((-46, -67, 0), (76, 21, 21), (32, 28, 31)),
    (8, 1): ((-77, -142, 4), (88, 57, 93), (41, 83, 98)),
    (9, 1): ((-40, -107, 0), (85, 14, 15), (32, 21, 38)),
}

METADATA_OUTFITS = {
    2: {7: 6},
    3: {3: 2, 5: 2, 6: 2},
    4: {5: 4, 8: 4, 9: 4},
    5: {6: 5, 9: 4},
    6: {5: 4},
}
MIRROR_LEFT = {0, 1, 4, 6, 7, 9, 10, 11, 12, 15, 16, 19, 20, 21}
MIRROR_RIGHT = {2, 3, 8, 13, 14, 17, 18}


def character_layers(compiler, sprites):
    """Render two independently staged slots in the original draw order."""
    layers = []
    active = sorted(
        (slot, item) for slot, item in sprites.items()
        if item.actor is not None and item.actor >= 0 and item.outfit not in (-1, None)
    )
    for slot, character in active:
        actor, outfit, expression = character.actor, character.outfit, character.expression
        offsets = OPENING_OFFSETS.get((actor, outfit))
        if offsets is None:
            metadata_outfit = METADATA_OUTFITS.get(actor, {}).get(outfit, outfit)
            metadata = f"character_{actor}_{metadata_outfit}"
            if actor == 7 and expression == 7:
                metadata = f"character_7_{max(0, outfit) if outfit > 1 else 0}7"
            if not compiler.exists(metadata):
                metadata = f"character_{actor}_0"
            if not compiler.exists(metadata):
                continue
            coords = struct.unpack_from(">9h", compiler.read(metadata))
            # The port keeps the authoring coordinates for the clothing.
            # _imagesize is 1.5 for the fallback face coordinates.
            offsets = (
                coords[:3],
                tuple(int(value * 1.5) for value in coords[3:6]),
                tuple(int(value * 1.5) for value in coords[6:9]),
            )

        # The old framebuffer stores 360×444. _vSetChaDrawPosition places
        # the characters at quarter points or centers the lone character.
        paired = len(active) == 2
        anchor_x = (90 if slot == 0 else 270) if paired else 180
        anchor_x -= 35 if slot == 0 else 20
        flip = paired and actor in (MIRROR_LEFT if slot == 0 else MIRROR_RIGHT)
        cloth, head, face = offsets
        x, y = anchor_x + cloth[0], 254 + cloth[1]
        head_y = y + cloth[2] - head[0]
        facing = 2 if flip else 1

        parts = [(f"character_{actor}_Cloth_{outfit}.png", x, y)]
        base_id = BASE_FACES[actor] if actor < len(BASE_FACES) else actor if actor in range(90, 95) else None
        if base_id is not None:
            parts.append((f"character_bface_{base_id}.png", x + head[facing], head_y))
        face_id = EXPRESSION_FACES[actor] if actor < len(EXPRESSION_FACES) else actor if actor in range(90, 95) else None
        if face_id is not None and expression not in (-1, None):
            parts.append((f"character_face_{face_id}_{expression}.png", x + face[facing], head_y + face[0]))

        for name, part_x, part_y in parts:
            layer = compiler.layer(name, part_x, part_y)
            if layer is not None:
                if flip:
                    layer["mirrored"] = True
                layers.append(layer)
    return layers
