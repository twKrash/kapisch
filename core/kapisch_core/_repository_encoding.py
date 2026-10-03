"""Canonical Stage 6.1 byte encoding primitives."""

from .bundle import canonical_json


def encode_git_path(path: bytes) -> str:
    if (
        type(path) is not bytes
        or not path
        or path.startswith(b"/")
        or b"\0" in path
        or any(part in (b"", b".", b"..") for part in path.split(b"/"))
    ):
        raise ValueError("invalid Git path")
    return path.hex()


def encode_projected_fact(projected: dict[str, object]) -> bytes:
    """Encode a facade-owned, schema-shaped projection."""
    if type(projected) is not dict:
        raise TypeError("repository facts must project to dictionaries")
    return canonical_json(projected)
