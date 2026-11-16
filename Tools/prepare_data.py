"""Prepare a local data ZIP from a Korean SnowRain 1.4 iOS archive."""

import argparse
import hashlib
import json
import plistlib
import re
import struct
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
APP_PREFIX = "Payload/SnowRain.app/"
IMAGE_AUDIO_EXTENSIONS = {".png", ".mp3", ".wav"}
RESOURCE_NAME = re.compile(r"[A-Za-z0-9_.@-]+")
SCRIPT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9-]+")
NUMBERED_SCRIPT_NAME = re.compile(r"Scripttxt_[0-9]+")


def png_chunks(image):
    """Read and verify the original PNG chunks in display order."""
    if not image.startswith(PNG_SIGNATURE):
        raise ValueError("Invalid PNG signature.")
    offset = len(PNG_SIGNATURE)
    while offset + 12 <= len(image):
        size, kind = struct.unpack_from(">I4s", image, offset)
        end = offset + 8 + size
        if end + 4 > len(image):
            break
        payload = image[offset + 8:end]
        crc = struct.unpack_from(">I", image, end)[0]
        if zlib.crc32(kind + payload) != crc:
            raise ValueError(f"Invalid PNG chunk CRC for {kind!r}.")
        yield kind, payload
        offset = end + 4
        if kind == b"IEND" and offset == len(image):
            return
    raise ValueError("Missing PNG terminator or invalid chunk length.")


def png_chunk(kind, payload):
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload))
    )


def make_alpha_lookup():
    # Apple has already rounded the color samples when storing premultiplied BGRA.
    return [
        bytes(min(255, (color * 255 + alpha // 2) // alpha) for color in range(256))
        if alpha else bytes(256)
        for alpha in range(256)
    ]


ALPHA_LOOKUP = make_alpha_lookup()


def rgba_sub_row(row):
    """Convert one CgBI Sub-filtered row to a standard PNG Sub-filtered row."""
    alpha_deltas = row[3::4]
    # When alpha is opaque for the entire row, the Sub deltas can be swapped directly.
    if alpha_deltas[0] == 255 and not any(alpha_deltas[1:]):
        swapped = bytearray(row)
        swapped[0::4] = row[2::4]
        swapped[2::4] = row[0::4]
        return swapped

    converted = bytearray(len(row))
    blue = green = red = alpha = 0
    previous_red = previous_green = previous_blue = 0
    for offset in range(0, len(row), 4):
        # Inverse Sub filter, then convert premultiplied BGRA to straight RGBA.
        blue = (blue + row[offset]) & 255
        green = (green + row[offset + 1]) & 255
        red = (red + row[offset + 2]) & 255
        alpha = (alpha + row[offset + 3]) & 255
        lookup = ALPHA_LOOKUP[alpha]
        straight_red = lookup[red]
        straight_green = lookup[green]
        straight_blue = lookup[blue]

        # Write the re-filtered straight pixels to keep the new IDAT compact.
        converted[offset] = (straight_red - previous_red) & 255
        converted[offset + 1] = (straight_green - previous_green) & 255
        converted[offset + 2] = (straight_blue - previous_blue) & 255
        converted[offset + 3] = row[offset + 3]
        previous_red = straight_red
        previous_green = straight_green
        previous_blue = straight_blue
    return converted


def cgbi_pixels(chunks):
    header = next((payload for kind, payload in chunks if kind == b"IHDR"), b"")
    if len(header) != 13:
        raise ValueError("Missing or malformed CgBI IHDR chunk.")
    width, height, depth, color_type, compression, filtering, interlacing = struct.unpack(
        ">II5B", header
    )
    if (depth, color_type, compression, filtering, interlacing) != (8, 6, 0, 0, 0):
        raise ValueError("Expected an 8-bit noninterlaced CgBI RGBA image.")
    if not (0 < width <= 2048 and 0 < height <= 2048):
        raise ValueError("CgBI dimensions exceed the supported resource size.")

    row_size = width * 4 + 1
    expected_size = row_size * height
    compressed = b"".join(payload for kind, payload in chunks if kind == b"IDAT")
    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
    pixels = decompressor.decompress(compressed, expected_size + 1)
    if len(pixels) != expected_size or not decompressor.eof or decompressor.unused_data:
        raise ValueError("Invalid CgBI pixel data.")
    return width, height, pixels


def standard_png(image):
    chunks = list(png_chunks(image))
    if not any(kind == b"CgBI" for kind, _ in chunks):
        return image

    width, _, pixels = cgbi_pixels(chunks)
    row_size = width * 4 + 1
    rows = bytearray(pixels)
    for offset in range(0, len(pixels), row_size):
        if pixels[offset] != 1:
            raise ValueError("Expected the Sub filter used by SnowRain 1.4.")
        rows[offset + 1:offset + row_size] = rgba_sub_row(pixels[offset + 1:offset + row_size])

    standard = bytearray(PNG_SIGNATURE)
    wrote_pixels = False
    for kind, payload in chunks:
        if kind == b"CgBI":
            continue
        if kind == b"IDAT":
            if wrote_pixels:
                continue
            payload = zlib.compress(rows, level=6)
            wrote_pixels = True
        standard.extend(png_chunk(kind, payload))
    return bytes(standard)


def sprite_horizontal_bounds(image):
    """Return the left and exclusive right visible edges of an original sprite."""
    chunks = list(png_chunks(image))
    if not any(kind == b"CgBI" for kind, _ in chunks):
        raise ValueError("Expected a SnowRain CgBI sprite.")
    width, _, pixels = cgbi_pixels(chunks)
    row_size = width * 4 + 1
    left, right = width, 0
    for row in range(0, len(pixels), row_size):
        if pixels[row] != 1:
            raise ValueError("Expected the Sub filter used by SnowRain 1.4.")
        alpha = 0
        for x, component in enumerate(pixels[row + 4:row + row_size:4]):
            alpha = (alpha + component) & 255
            if alpha != 0:
                left = min(left, x)
                right = max(right, x + 1)
    return (left, right) if left < right else (0, width)


def pack_resources(ipa, destination, program):
    with zipfile.ZipFile(ipa) as source, zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_STORED
    ) as output:
        info = plistlib.loads(source.read(APP_PREFIX + "Info.plist"))
        if (info.get("CFBundleIdentifier"), info.get("CFBundleVersion")) != (
            "kr.gameday.snowrainKR", "1.4"
        ):
            raise ValueError("Select the Korean SnowRain 1.4 IPA.")

        assets = []
        scripts = []
        for entry in source.infolist():
            if not entry.filename.startswith(APP_PREFIX):
                continue
            name = entry.filename.removeprefix(APP_PREFIX)
            if not RESOURCE_NAME.fullmatch(name) or name in {".", ".."}:
                continue
            extension = Path(name).suffix.lower()
            if extension in IMAGE_AUDIO_EXTENSIONS:
                path = f"assets/{name}"
                try:
                    data = source.read(entry)
                    if extension == ".png":
                        data = standard_png(data)
                except (ValueError, zipfile.BadZipFile, zlib.error) as error:
                    raise ValueError(f"{name}: {error}") from error
                output.writestr(path, data)
                assets.append(path)
            elif not name.startswith("ja_") and SCRIPT_NAME.fullmatch(name):
                path = f"scripts/{name}"
                output.writestr(path, source.read(entry))
                scripts.append(path)

        numbered_scripts = sum(NUMBERED_SCRIPT_NAME.fullmatch(Path(path).name) is not None for path in scripts)
        if numbered_scripts != 272 or not assets:
            raise ValueError("The archive is missing SnowRain 1.4 resources.")
        paths = assets + scripts
        if len(paths) != len(set(paths)):
            raise ValueError("The archive has duplicate resource paths.")
        with ipa.open("rb") as source_bytes:
            source_hash = hashlib.file_digest(source_bytes, "sha256").hexdigest()
        manifest = {
            "formatVersion": 1,
            "sourceVersion": info["CFBundleVersion"],
            "sourceSHA256": source_hash,
            "assets": sorted(assets),
            "scripts": sorted(scripts),
        }
        if program is not None:
            output.writestr("program.json", program)
            manifest["program"] = "program.json"
        output.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))
    return len(assets), numbered_scripts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa", type=Path, help="Path to the Korean SnowRain 1.4 IPA")
    parser.add_argument("--output", type=Path, help="Output ZIP (default: next to the IPA)")
    parser.add_argument("--program", type=Path, help="Optional compiled scene program JSON")
    options = parser.parse_args()
    output = options.output or options.ipa.with_name("SnowRain-data.zip")
    if output.suffix.lower() != ".zip":
        parser.error("The output path must end in .zip.")
    if output.resolve() == options.ipa.resolve():
        parser.error("The output cannot replace the input IPA.")

    temporary_path = None
    try:
        program = options.program.read_bytes() if options.program else None
        if program is not None and not isinstance(json.loads(program), dict):
            raise ValueError("The compiled scene program must be a JSON object.")
        # A failed conversion leaves any previously working archive intact.
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
        asset_count, script_count = pack_resources(options.ipa, temporary_path, program)
        temporary_path.replace(output)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, plistlib.InvalidFileException) as error:
        print(f"Cannot prepare SnowRain data: {error}", file=sys.stderr)
        return 1
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    print(f"Prepared {output} ({asset_count} images/audio, {script_count} numbered scripts).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
