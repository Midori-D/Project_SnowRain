"""Compile the playable opening from a local Korean SnowRain 1.4 IPA."""

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import struct
import sys
import zipfile

from first_day import first_day
from portraits import character_layers
from prepare_data import APP_PREFIX
from scene_script import scene_steps


# _vFindScriptPos indexes CRLF records. _vTransScript consumes commands
# inside each record; only text consumes a variable number of bytes.
OPERANDS = {
    1: 2, 2: 1, 3: 1, 4: 1, 5: 2, 6: 1, 7: 1, 8: 2, 9: 1,
    10: 1, 11: 1, 14: 2, 15: 2, 16: 2, 17: 2, 20: 2, 21: 1,
    22: 2, 23: 1,
}
SCENE_KINDS = {14: "cartoon", 15: "illuster", 16: "comic", 17: "miniilluster"}
SPEAKERS = (
    "다혜", "미나", "아라", "소희", "윤아", "지훈", "태균", "만복", "최 건",
    "순덕", "승훈", "엄마", "방송", "취객", "의사", "학생", "학생회",
    "선생님", "???", "여학생", "관장", "주임", "기현",
)
def commands(data, name):
    record_start = 0
    for record in data.split(b"\r\n"):
        offset = 0
        while offset < len(record):
            address = record_start + offset
            opcode = record[offset]
            first = offset + 1
            if opcode == 12:
                end = record.find(b"\0", first)
                if end < 0:
                    raise ValueError(f"{name} at {address:#x}: unterminated dialogue")
                yield address, opcode, record[first:end].decode("cp949").replace("\r", "\n")
                offset = end + 1
                continue
            width = OPERANDS.get(opcode)
            if width is None or first + width > len(record):
                raise ValueError(f"{name} at {address:#x}: unsupported or truncated opcode {opcode:#x}")
            offset = first + width
            yield address, opcode, tuple(record[first:offset])
        record_start += len(record) + 2


@dataclass
class Character:
    actor: int
    expression: int
    outfit: int


@dataclass
class Stage:
    background: str | None = None
    music: str | None = None
    effect: str | None = None
    date: str | None = None
    speaker: int | None = None
    speech_mode: int = 1
    sprites: dict = field(default_factory=dict)
    outfits: dict = field(default_factory=dict)
    scene_images: dict = field(default_factory=dict)
    scene_order: list = field(default_factory=list)


class OpeningCompiler:
    def __init__(self, archive):
        self.archive = archive
        self.names = set(archive.namelist())
        self.stage = Stage()
        self.beats = {}
        self.previous = None
        self.dimensions = {}

    def read(self, name):
        return self.archive.read(APP_PREFIX + name)

    def exists(self, name):
        return APP_PREFIX + name in self.names

    def size(self, name):
        if name not in self.dimensions:
            with self.archive.open(APP_PREFIX + name) as image:
                header = image.read(48)
            ihdr = header.index(b"IHDR")
            self.dimensions[name] = struct.unpack_from(">II", header, ihdr + 4)
        return self.dimensions[name]

    def add(self, key, **beat):
        if key in self.beats:
            raise ValueError(f"Duplicate step {key}.")
        if self.previous is not None:
            self.beats[self.previous]["next"] = key
        self.beats[key] = beat
        self.previous = key

    def layer(self, name, x, y):
        if self.exists(name):
            return {"image": f"assets/{name}", "x": x, "y": y}
        return None

    def character_layers(self):
        return character_layers(self, self.stage.sprites)

    def snapshot(self):
        stage = self.stage
        scenes = [
            layer.copy()
            for kind in stage.scene_order
            for _, layer in sorted(stage.scene_images.get(kind, {}).items())
            if "image" in layer
        ]
        speaker = stage.speaker
        return {
            "background": stage.background,
            "layers": self.character_layers() + scenes,
            "music": stage.music,
            "effect": stage.effect,
            "date": stage.date,
            "speaker": SPEAKERS[speaker] if stage.speech_mode == 1
                and speaker is not None and 0 <= speaker < len(SPEAKERS) else None,
            "sceneHeight": 530 if scenes else 336,
        }

    def animation(self, key, kind, number, segment):
        stage = self.stage
        if number == 255:
            stage.scene_images.pop(kind, None)
            if kind in stage.scene_order:
                stage.scene_order.remove(kind)
            return
        if segment == 0:
            stage.scene_images.pop(kind, None)
        if kind not in stage.scene_order:
            stage.scene_order.append(kind)
        frames = scene_steps(self.read(f"{kind}txt_{number}"), kind, segment, stage.scene_images)
        other = [
            layer.copy()
            for active_kind in stage.scene_order if active_kind != kind
            for layer in stage.scene_images[active_kind].values()
            if "image" in layer
        ]
        for index, frame in enumerate(frames):
            if frame["delay"] > 0:
                animation = self.snapshot()
                animation["layers"] = self.character_layers() + other + frame["layers"]
                animation["sceneHeight"] = 530
                animation["delay"] = frame["delay"]
                self.add(f"{key}-frame-{index}", **animation)
                stage.effect = None

    def script(self, index):
        stage = self.stage
        stage.speaker = None
        stage.speech_mode = 1
        name = f"Scripttxt_{index}"
        first = None
        for address, opcode, values in commands(self.read(name), name):
            key = f"script-{index}-{address:04x}"
            if opcode == 1:
                kind, _ = values
                if kind in (1, 2, 3):
                    stage.speech_mode = kind
                elif kind not in (9, 249, 251, 252, 253):
                    raise ValueError(f"{name} at {address:#x}: unsupported control kind {kind:#x}")
            elif opcode == 2:
                number, = values
                stage.background = None if number == 255 else f"assets/Bg_{number}.png"
                stage.sprites.clear()
            elif opcode == 3:
                # The effect opcode changes screen transitions, not the story position.
                continue
            elif opcode == 4:
                sound, = values
                if sound == 255:
                    stage.music = None
                elif sound < 20:
                    stage.music = f"assets/sound_0{sound}.mp3"
                else:
                    stage.effect = f"assets/sound_0{sound}.mp3"
            elif opcode in (5, 8):
                slot = 0 if opcode == 5 else 1
                actor, expression = values
                if actor == 255:
                    stage.sprites.pop(slot, None)
                else:
                    stage.sprites[slot] = Character(actor, expression, stage.outfits.get(slot, -1))
            elif opcode in (6, 9):
                slot = 0 if opcode == 6 else 1
                stage.outfits[slot] = values[0]
                if slot in stage.sprites:
                    stage.sprites[slot].outfit = values[0]
            elif opcode == 11:
                stage.speaker, = values
            elif opcode == 12:
                if values.strip():
                    self.add(key, text=values, **self.snapshot())
                    first = first or key
                    stage.effect = None
            elif opcode in SCENE_KINDS:
                number, segment = values
                self.animation(key, SCENE_KINDS[opcode], number, max(0, segment - 1))
            elif opcode == 20:
                month, day = values
                stage.date = f"{month}월 {day}일"
            elif opcode == 21:
                # A phone overlay in the conversation is a visual cue.
                if values[0] == 255:
                    stage.scene_images.pop("phone", None)
                    if "phone" in stage.scene_order:
                        stage.scene_order.remove("phone")
                else:
                    if "phone" not in stage.scene_order:
                        stage.scene_order.append("phone")
                    stage.scene_images["phone"] = {0: {
                        "image": "assets/ui_hm_13.png", "x": 78, "y": 20,
                        "sourceX": 0, "sourceY": 0, "sourceWidth": 204, "sourceHeight": 278,
                    }}
            else:
                raise ValueError(f"{name} at {address:#x}: unimplemented opcode {opcode:#x}")
        if first is None:
            raise ValueError(f"{name} has no dialogue.")
        return first

    def compile(self):
        self.stage.music = "assets/sound_012.mp3"
        for segment in range(6):
            self.animation(f"intro-{segment}", "illuster", 1000, segment)
        start = next(iter(self.beats))
        self.stage.scene_images.clear()
        self.stage.scene_order.clear()
        for index in range(1, 7):
            self.script(index)
        before_weekday = self.previous
        weekday_music = self.stage.music
        self.stage = Stage(date="3월 2일", music=weekday_music)
        self.previous = None
        script7 = self.script(7)
        self.add("first-day-end", end="첫 평일 이후의 시나리오를 마쳤습니다.", **self.snapshot())
        self.beats[before_weekday]["next"] = "weekday"
        self.beats.update(first_day("assets/Bg_1.png", [], weekday_music, script7))
        program = {
            "version": 1, "start": start, "title": "assets/titlebg.png", "firstActivity": "weekday",
            "titleMusic": "assets/sound_018.mp3",
            "canvasWidth": 360, "canvasHeight": 530, "beats": self.beats,
        }
        self.check_assets(program)
        return program

    def check_assets(self, program):
        for key, beat in self.beats.items():
            layers = beat.get("layers", [])
            for asset in [beat.get(property) for property in ("background", "music", "effect")] + [
                layer["image"] for layer in layers
            ]:
                if asset and not self.exists(asset.removeprefix("assets/")):
                    raise ValueError(f"{key} requires missing asset {asset}.")
            for layer in layers:
                if "sourceWidth" not in layer:
                    continue
                width, height = self.size(layer["image"].removeprefix("assets/"))
                if layer["sourceX"] + layer["sourceWidth"] > width or layer["sourceY"] + layer["sourceHeight"] > height:
                    raise ValueError(f"{key} requests invalid image region in {layer['image']}.")
        for field in ("title", "titleMusic"):
            if not self.exists(program[field].removeprefix("assets/")):
                raise ValueError(f"Missing title resource {program[field]}.")


def compile_opening(archive):
    return OpeningCompiler(archive).compile()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        with zipfile.ZipFile(args.ipa) as archive:
            program = compile_opening(archive)
        args.output.write_text(json.dumps(program, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Compiled {len(program['beats'])} opening steps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
