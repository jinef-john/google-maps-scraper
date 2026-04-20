"""Protobuf-style URL parameter builder for Google Maps internal API.

Google Maps uses a custom serialization format in URL parameters (the `pb=` param)
that resembles Protocol Buffers. This module builds those parameter strings.

Format: !{field_number}{type}{value}
Types:
  m = message (nested, value is count of sub-fields)
  s = string
  d = double
  f = float
  i = int32/int64
  b = bool (0/1)
  e = enum (int)
"""

from urllib.parse import quote


def _encode_value(field_num, type_char, value):
    """Encode a single field."""
    return f"!{field_num}{type_char}{value}"


def string(field_num, value):
    return _encode_value(field_num, "s", quote(str(value), safe=""))


def double(field_num, value):
    return _encode_value(field_num, "d", value)


def integer(field_num, value):
    return _encode_value(field_num, "i", int(value))


def boolean(field_num, value):
    return _encode_value(field_num, "b", "1" if value else "0")


def enum(field_num, value):
    return _encode_value(field_num, "e", int(value))


def message(field_num, *children):
    """Build a nested message from child fields."""
    inner = "".join(children)
    return f"!{field_num}m{len(children)}{inner}"


def raw(text):
    """Pass through a raw pb fragment."""
    return text


def build(*parts):
    """Concatenate parts into a full pb= parameter value."""
    return "".join(parts)
