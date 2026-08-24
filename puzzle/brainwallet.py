"""Brainwallet candidates: SHA-256(passphrase) used directly as a private key.

The puzzle text says "the seed *passphrase* is hidden in the picture", and two
of the strongest published hints - "breathe" and the "Tuesday" rune - are not
BIP-39 words at all. That combination is consistent with a brainwallet, where
the phrase is free-form. Brainwallet candidates cost one SHA-256 plus one EC
multiplication instead of 2048 PBKDF2 rounds, so this mode runs far faster and
places no restriction on the vocabulary.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Iterator, Sequence

from .keys import hash160, pubkey_from_privkey

#: Ways a phrase might have been rendered before hashing.
JOINERS: dict[str, str] = {
    "space": " ",
    "none": "",
    "dash": "-",
    "comma": ",",
}

CASINGS: dict[str, callable] = {
    "lower": str.lower,
    "upper": str.upper,
    "title": str.title,
    "asis": lambda s: s,
}


def variants(words: Sequence[str], joiners: Sequence[str], casings: Sequence[str]) -> Iterator[str]:
    """Yield the phrase renderings implied by the chosen joiners and casings."""
    for joiner in joiners:
        sep = JOINERS[joiner]
        base = sep.join(words)
        for casing in casings:
            yield CASINGS[casing](base)


def iter_hash160s(phrase: str, compressed_modes: Sequence[bool] = (True, False)) -> Iterator[tuple[bytes, str]]:
    """Yield ``(hash160, label)`` for a brainwallet phrase."""
    priv = sha256(phrase.encode("utf-8")).digest()
    for compressed in compressed_modes:
        try:
            pub = pubkey_from_privkey(priv, compressed)
        except ValueError:  # pragma: no cover - astronomically unlikely
            continue
        yield hash160(pub), "compressed" if compressed else "uncompressed"


def privkey_for(phrase: str) -> bytes:
    """The private key a brainwallet phrase maps to."""
    return sha256(phrase.encode("utf-8")).digest()
