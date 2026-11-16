"""Write synthetic StoryPackage fixtures without game data."""

import json
import struct
import sys
import zipfile
from pathlib import Path


def main(destination):
    destination.mkdir(parents=True, exist_ok=True)
    program = {
        "version": 1,
        "start": "opening",
        "beats": {
            "opening": {"text": "Pick a path.", "next": "choose"},
            "choose": {
                "choices": [
                    {"text": "Left", "target": "garden"},
                    {"text": "Right", "target": "bridge"},
                ],
            },
            "garden": {"text": "You visit the garden.", "end": "Complete."},
            "bridge": {"text": "You cross the bridge.", "end": "Complete."},
        },
    }
    valid_path = destination / "valid.zip"
    with zipfile.ZipFile(valid_path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps({"formatVersion": 1}))
        archive.writestr("program.json", json.dumps(program))
        program_header_offset = archive.getinfo("program.json").header_offset

    program["beats"]["bridge"]["sceneHeight"] = 200
    with zipfile.ZipFile(destination / "new-layout.zip", "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps({"formatVersion": 1}))
        archive.writestr("program.json", json.dumps(program))
    program["beats"]["choose"]["choices"][1]["target"] = "garden"
    with zipfile.ZipFile(destination / "new-story.zip", "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps({"formatVersion": 1}))
        archive.writestr("program.json", json.dumps(program))

    corrupt = bytearray(valid_path.read_bytes())
    name_length, extra_length = struct.unpack_from("<HH", corrupt, program_header_offset + 26)
    program_offset = program_header_offset + 30 + name_length + extra_length
    # Change a letter inside a JSON string without updating the declared ZIP CRC.
    text_offset = corrupt.index(b"Pick a path.", program_offset)
    corrupt[text_offset] = ord("T")
    (destination / "corrupt.zip").write_bytes(corrupt)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 Tests/make_story_fixtures.py FIXTURE_DIRECTORY")
    main(Path(sys.argv[1]))
