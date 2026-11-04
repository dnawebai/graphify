"""Refuse XML that declares a DTD or entities before ElementTree parses it.

Stdlib ``xml.etree.ElementTree`` expands internal entities, and expat only
caps that amplification from 2.4.0 on, so a Python linked against an older
system libexpat would expand a billion-laughs file in full. graphify parses
project XML (.csproj/.slnx/.xaml/.lpk) and Maven POMs, none of which ever
declare a DTD, so it refuses any input that does.

A substring scan for ``<!DOCTYPE`` only works when the text is ASCII-compatible.
UTF-16 puts a NUL between every letter, yet expat detects UTF-16 from the
first bytes and parses the DTD anyway, with or without a byte-order mark,
and even when the UTF-16 bytes arrive inside a ``str`` that was decoded as
UTF-8. So :func:`declares_dtd` also asks expat itself, given exactly the
object ElementTree will be given, and stops at the root element: a DOCTYPE
can only come before it.
"""
from __future__ import annotations


class _HasDTD(Exception):
    """Raised from an expat handler when a DOCTYPE or ENTITY is declared."""


class _RootReached(Exception):
    """Raised from an expat handler at the root element; no DTD can follow."""


def declares_dtd(data: str | bytes) -> bool:
    """True if ``data`` declares a DOCTYPE or ENTITY in any encoding expat reads.

    Pass the same ``str`` or ``bytes`` object that will go to
    ``ElementTree.fromstring``, so both see identical input. Malformed input
    before the root returns False: ElementTree then reports the parse error.
    """
    if isinstance(data, bytes):
        lowered_bytes = data.lower()
        if b"<!doctype" in lowered_bytes or b"<!entity" in lowered_bytes:
            return True
    else:
        lowered_text = data.lower()
        if "<!doctype" in lowered_text or "<!entity" in lowered_text:
            return True

    import xml.parsers.expat as expat

    def _found_dtd(*_args: object) -> None:
        raise _HasDTD

    def _reached_root(*_args: object) -> None:
        raise _RootReached

    parser = expat.ParserCreate()
    parser.StartDoctypeDeclHandler = _found_dtd
    parser.EntityDeclHandler = _found_dtd
    parser.StartElementHandler = _reached_root
    try:
        parser.Parse(data, True)
    except _HasDTD:
        return True
    except (_RootReached, expat.ExpatError):
        pass
    return False
