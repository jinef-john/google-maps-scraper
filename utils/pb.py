"""Protobuf-style URL parameter builder for Google Maps internal API."""

from urllib.parse import quote


def _encode_value(field_num, type_char, value):
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
    inner = "".join(children)
    return f"!{field_num}m{len(children)}{inner}"


def build(*parts):
    return "".join(parts)
