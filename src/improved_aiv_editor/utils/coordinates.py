"""Coordinate encoding/decoding for the .aivjson tile position format.

The 98x98 map encodes positions as y * 100 + x, where x,y are in [1..98].
The file uses bottom-left origin (y increases upward).
Internally we use top-left origin (y increases downward) to match the Qt scene.
decode_position flips y on load; encode_position flips it back on save.
"""

MAP_SIZE = 98
MIN_COORD = 1
MAX_COORD = 98

_Y_FLIP = MAP_SIZE + 1  # 99


def decode_position(encoded: int) -> tuple[int, int]:
    """Decode an aivjson tilePositionOfset into scene-compatible (x, y) coords.

    Flips y from bottom-left origin (file) to top-left origin (scene).
    """
    x = encoded % 100
    file_y = encoded // 100
    return x, _Y_FLIP - file_y


def encode_position(x: int, y: int) -> int:
    """Encode scene-compatible (x, y) coords into an aivjson tilePositionOfset.

    Flips y from top-left origin (scene) back to bottom-left origin (file).
    """
    file_y = _Y_FLIP - y
    return file_y * 100 + x


def is_valid_position(x: int, y: int) -> bool:
    return MIN_COORD <= x <= MAX_COORD and MIN_COORD <= y <= MAX_COORD


def clamp_position(x: int, y: int) -> tuple[int, int]:
    return (
        max(MIN_COORD, min(MAX_COORD, x)),
        max(MIN_COORD, min(MAX_COORD, y)),
    )
