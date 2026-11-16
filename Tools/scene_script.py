"""Read the layered scene scripts used by SnowRain 1.4."""

SCENE_IMAGES = {
    "cartoon": "Cartoon",
    "illuster": "Illuster",
    "comic": "Comic",
    "miniilluster": "MiniIlluster",
}


def rendered_layer(kind, layer):
    """Translate authored scene positions to the iOS texture framebuffer."""
    if kind not in SCENE_IMAGES:
        return layer.copy()
    return {**layer, "x": int(layer["x"] * 1.5), "y": int(layer["y"] * 1.5)}


# Widths from the ARMv7 _vTransSceneScript dispatch and operand readers.
WIDTHS = {0x00: 2, 0x01: 4, 0x02: 4, 0x03: 4, 0x06: 5, 0x07: 8,
          0x08: 3, 0x09: 3, 0xFC: 3, 0xFE: 2, 0xFF: 1}


def scene_steps(data: bytes, kind: str, segment: int, state: dict) -> list[dict]:
    """Decode a scene segment and update the scene's persistent layer state."""
    prefix = SCENE_IMAGES[kind]
    records = data.split(b"##")
    if records[-1] or not 0 <= segment < len(records) - 1:
        raise ValueError(f"{kind}: missing or incomplete scene segment {segment}")
    record = records[segment]
    if len(record) < 2 or int.from_bytes(record[:2], "big") != segment:
        raise ValueError(f"{kind}: wrong scene record index at segment {segment}")

    layers = state.setdefault(kind, {})
    steps = []
    offset = 2
    elapsed = 0
    while offset < len(record):
        command = record[offset]
        width = WIDTHS.get(command)
        if width is None or offset + width > len(record):
            raise ValueError(
                f"{kind}: invalid scene opcode {command:#04x} "
                f"in segment {segment} at byte {offset}"
            )

        operands = record[offset + 1:offset + width]
        offset += width
        if command == 0xFF:
            layers.clear()
            continue
        if command == 0x00:
            continue
        if command == 0xFC:
            wait = int.from_bytes(operands, "big")
            steps.append(_snapshot(layers, max(wait, elapsed)))
            elapsed = 0
            continue

        slot = operands[0]
        if command == 0xFE:
            layers.pop(slot, None)
            continue
        layer = layers.setdefault(slot, {"x": 0, "y": 0, "opacity": 1.0})
        if command == 0x01:
            image_number = int.from_bytes(operands[1:3], "big")
            layer["image"] = f"assets/{prefix}_{image_number}.png"
        elif command in (0x02, 0x03):
            axis = "x" if command == 0x02 else "y"
            layer[axis] = int.from_bytes(operands[1:3], "big", signed=True)
        elif command == 0x06:
            alpha, increment, frames = operands[1:]
            increment = int.from_bytes(bytes([increment]), "big", signed=True)
            layer["opacity"] = min(100, max(0, alpha + increment * frames)) / 100
            elapsed = max(elapsed, frames)
        elif command == 0x07:
            dx = int.from_bytes(operands[1:3], "big", signed=True)
            dy = int.from_bytes(operands[3:5], "big", signed=True)
            frames = int.from_bytes(operands[5:7], "big")
            layer["x"] += dx * frames
            layer["y"] += dy * frames
            elapsed = max(elapsed, frames)
        elif command == 0x08:
            layer["mirrored"] = bool(operands[1])
        elif command == 0x09:
            elapsed = max(elapsed, operands[1])

    final = _snapshot(layers, elapsed)
    if not steps or final["layers"] != steps[-1]["layers"] or elapsed:
        steps.append(final)
    return steps


def _snapshot(layers: dict, frames: int) -> dict:
    return {
        "layers": [layer.copy() for _, layer in sorted(layers.items()) if "image" in layer],
        "delay": frames / 60,
    }
