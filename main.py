#!/usr/bin/env python3
"""Front-page validator for the Wednesday 25 November 2026 news image.

The file beside this program, entry.png, is a single-page newspaper
front page summing up the day's world news: three lead stories, four
medium stories, two one-liners, a small world map, and a box listing
items that were checked and dropped, with their true dates.

This program draws nothing. It reads the stored image, checks that it
is a complete, well-formed PNG inside the competition's size and
dimension limits, and copies it unchanged into the output folder,
verifying the copy byte for byte afterwards. Pass --check to validate
without copying.
"""

import hashlib
import os
import struct
import sys
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_FILE_BYTES = 1048576
PAGE_WIDTH = 1024
PAGE_HEIGHT = 1024

# Bit depths each PNG colour type is allowed to use.
LEGAL_DEPTHS = {
    0: (1, 2, 4, 8, 16),
    2: (8, 16),
    3: (1, 2, 4, 8),
    4: (8, 16),
    6: (8, 16),
}


class BadImage(Exception):
    """A validation check on the stored image failed."""


def stored_path():
    folder = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(folder, "entry.png")


def read_stored():
    path = stored_path()
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        raise BadImage("cannot read the stored image: %s" % exc)


def validate(data):
    """Run every check in order; return a dict of facts about the image."""
    if len(data) > MAX_FILE_BYTES:
        raise BadImage(
            "image is %d bytes, over the %d byte limit"
            % (len(data), MAX_FILE_BYTES)
        )
    if data[:8] != PNG_SIGNATURE:
        raise BadImage("file does not begin with the PNG signature")

    width = height = depth = colour = None
    palette_entries = 0
    saw_palette = False
    saw_data = False
    position = 8
    chunk_index = 0

    while True:
        if position + 8 > len(data):
            raise BadImage("file stops before the end chunk")
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        payload_start = position + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            raise BadImage(
                "chunk %s is cut off at the end of the file"
                % kind.decode("latin-1", "replace")
            )
        stored_crc = struct.unpack(">I", data[payload_end:payload_end + 4])[0]
        actual_crc = zlib.crc32(data[position + 4:payload_end]) & 0xFFFFFFFF
        if stored_crc != actual_crc:
            raise BadImage(
                "chunk %s fails its checksum"
                % kind.decode("latin-1", "replace")
            )
        payload = data[payload_start:payload_end]

        if chunk_index == 0:
            if kind != b"IHDR":
                raise BadImage(
                    "first chunk is %s, expected the header chunk"
                    % kind.decode("latin-1", "replace")
                )
            if length != 13:
                raise BadImage(
                    "header chunk holds %d bytes, expected 13" % length
                )
            width, height, depth, colour = struct.unpack(">IIBB", payload[:10])
            if width != PAGE_WIDTH or height != PAGE_HEIGHT:
                raise BadImage(
                    "image is %d by %d, expected 1024 by 1024"
                    % (width, height)
                )
            if colour != 3:
                raise BadImage(
                    "colour type is %d, expected 3"
                    % colour)
            if colour not in LEGAL_DEPTHS or depth not in LEGAL_DEPTHS[colour]:
                raise BadImage(
                    "bit depth %d is not allowed for colour type %d"
                    % (depth, colour)
                )

        if kind == b"PLTE":
            saw_palette = True
            palette_entries = length // 3
            if colour == 3 and length != 3 * (1 << depth):
                raise BadImage(
                    "palette holds %d bytes, expected %d for bit depth %d"
                    % (length, 3 * (1 << depth), depth)
                )

        if kind == b"IDAT":
            if colour == 3 and not saw_palette:
                raise BadImage("image data comes before the palette chunk")
            saw_data = True

        if kind == b"IEND":
            if length != 0:
                raise BadImage("end chunk must carry no payload")
            if position + 12 != len(data):
                raise BadImage("extra bytes follow the end chunk")
            break

        position += 12 + length
        chunk_index += 1

    if not saw_data:
        raise BadImage("no image data chunk found")

    return {
        "size": len(data),
        "width": width,
        "height": height,
        "bit_depth": depth,
        "colour_type": colour,
        "palette_entries": palette_entries,
    }


def copy_image(data):
    """Write the bytes out and check the copy matches the stored image."""
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    target = os.path.join(outdir, "entry.png")
    try:
        os.makedirs(outdir, exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
        with open(target, "rb") as handle:
            written = handle.read()
    except OSError as exc:
        print("error: cannot write the output file: %s" % exc, file=sys.stderr)
        return 3
    if written != data:
        print(
            "error: the written copy does not match the stored image",
            file=sys.stderr,
        )
        return 3
    digest = hashlib.sha256(data).hexdigest()
    print(
        "wrote entry.png to %s: %d bytes, sha256 %s"
        % (target, len(data), digest)
    )
    return 0


def main(argv):
    try:
        data = read_stored()
        info = validate(data)
    except BadImage as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    digest = hashlib.sha256(data).hexdigest()
    if argv and argv[0] == "--check":
        print(
            "entry.png OK: %d bytes, %dx%d, colour type %d, bit depth %d, "
            "%d palette entries, sha256 %s"
            % (
                info["size"],
                info["width"],
                info["height"],
                info["colour_type"],
                info["bit_depth"],
                info["palette_entries"],
                digest,
            )
        )
        return 0

    return copy_image(data)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
