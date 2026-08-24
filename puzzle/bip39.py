"""BIP-39 mnemonic checksum verification and seed generation.

The checksum filter is the single most important optimisation in this
project. Only 1 in 16 orderings of a 12-word set has a valid checksum, and
rejecting the other 15 costs one SHA-256 over 16 bytes rather than 2048
rounds of HMAC-SHA-512 - a difference of roughly three orders of magnitude.
"""

from __future__ import annotations

import hashlib
import unicodedata
from typing import Iterable, Sequence

from .wordlist import INDEX, WORDS

#: Valid mnemonic lengths -> (entropy bytes, checksum bits).
LENGTHS: dict[int, tuple[int, int]] = {
    12: (16, 4),
    15: (20, 5),
    18: (24, 6),
    21: (28, 7),
    24: (32, 8),
}

_SHA256 = hashlib.sha256


def checksum_ok_12(indices: Sequence[int]) -> bool:
    """Fast path: is this 12-index sequence a checksum-valid BIP-39 mnemonic?

    132 bits = 128 bits of entropy + a 4-bit checksum equal to the top four
    bits of SHA-256(entropy).
    """
    v = 0
    for i in indices:
        v = (v << 11) | i
    return _SHA256(((v >> 4) & (1 << 128) - 1).to_bytes(16, "big")).digest()[0] >> 4 == v & 0xF


def checksum_ok(indices: Sequence[int]) -> bool:
    """Checksum check for any supported mnemonic length."""
    n = len(indices)
    try:
        ent_bytes, cs_bits = LENGTHS[n]
    except KeyError:
        raise ValueError(f"unsupported mnemonic length {n}") from None
    v = 0
    for i in indices:
        v = (v << 11) | i
    cs = v & ((1 << cs_bits) - 1)
    entropy = (v >> cs_bits).to_bytes(ent_bytes, "big")
    return _SHA256(entropy).digest()[0] >> (8 - cs_bits) == cs


def is_valid_mnemonic(mnemonic: str) -> bool:
    """True if *mnemonic* is a well-formed, checksum-valid BIP-39 phrase."""
    words = mnemonic.split()
    if len(words) not in LENGTHS:
        return False
    try:
        return checksum_ok([INDEX[w] for w in words])
    except KeyError:
        return False


def entropy_to_mnemonic(entropy: bytes) -> str:
    """Build the mnemonic for a given entropy blob (used by the tests)."""
    bits = len(entropy) * 8
    cs_bits = bits // 32
    v = (int.from_bytes(entropy, "big") << cs_bits) | (
        _SHA256(entropy).digest()[0] >> (8 - cs_bits)
    )
    total = bits + cs_bits
    return " ".join(
        WORDS[(v >> shift) & 0x7FF] for shift in range(total - 11, -1, -11)
    )


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """BIP-39 mnemonic -> 64-byte seed via PBKDF2-HMAC-SHA512, 2048 rounds."""
    m = unicodedata.normalize("NFKD", mnemonic).encode("utf-8")
    salt = unicodedata.normalize("NFKD", "mnemonic" + passphrase).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha512", m, salt, 2048, dklen=64)


def indices_to_mnemonic(indices: Iterable[int]) -> str:
    return " ".join(WORDS[i] for i in indices)
