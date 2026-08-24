"""Electrum seed derivation.

Electrum does not use BIP-39. Its seeds have a different checksum, a
different PBKDF2 salt, and the wallet's *script type* is encoded in the seed
itself. A phrase can therefore be a perfectly valid Electrum seed while being
an invalid BIP-39 mnemonic, and vice versa - so a BIP-39-only search will
walk straight past an Electrum wallet.

Algorithm as implemented by Electrum (electrum/mnemonic.py, electrum/version.py):

* normalise: NFKD, lowercase, strip combining marks, collapse whitespace
* seed type: first hex digits of HMAC-SHA512(b"Seed version", seed) -
  ``01`` standard (P2PKH), ``100`` segwit, ``101``/``102`` two-factor
* root seed: PBKDF2-HMAC-SHA512(seed, b"electrum" + passphrase, 2048)
* standard wallet: receiving addresses at m/0/i, change at m/1/i
"""

from __future__ import annotations

import hashlib
import hmac
import unicodedata
from typing import Iterator, Sequence

from .derive import Node, ckd_priv, master_from_seed
from .keys import hash160, pubkey_from_privkey

PBKDF2_ROUNDS = 2048

#: Seed-version prefixes. The value is the wallet's script type.
SEED_PREFIX = "01"          # standard wallet, P2PKH - the only one that can
SEED_PREFIX_SW = "100"      # segwit, bc1... - cannot match a "1..." target
SEED_PREFIX_2FA = "101"
SEED_PREFIX_2FA_SW = "102"

#: Only a standard-type seed can produce a legacy "1..." address.
LEGACY_PREFIX = SEED_PREFIX


def normalize_text(seed: str) -> str:
    """Electrum's seed normalisation. CJK handling is omitted: the puzzle's
    vocabulary is Latin, and Electrum only strips spaces between CJK chars."""
    seed = unicodedata.normalize("NFKD", seed)
    seed = seed.lower()
    seed = "".join(c for c in seed if not unicodedata.combining(c))
    return " ".join(seed.split())


def seed_version_hex(seed: str) -> str:
    """Hex of HMAC-SHA512(b'Seed version', normalised seed)."""
    return hmac.new(b"Seed version", normalize_text(seed).encode("utf-8"),
                    hashlib.sha512).hexdigest()


def is_seed_type(seed: str, prefix: str = LEGACY_PREFIX) -> bool:
    """Does this phrase carry the given Electrum seed-version prefix?"""
    return seed_version_hex(seed).startswith(prefix)


def seed_type(seed: str) -> str | None:
    """Electrum's own name for the seed type, or None if not an Electrum seed."""
    h = seed_version_hex(seed)
    for prefix, name in ((SEED_PREFIX_SW, "segwit"), (SEED_PREFIX_2FA_SW, "2fa_segwit"),
                         (SEED_PREFIX_2FA, "2fa"), (SEED_PREFIX, "standard")):
        if h.startswith(prefix):
            return name
    return None


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """Electrum's root seed: note the b'electrum' salt, not b'mnemonic'."""
    m = normalize_text(mnemonic).encode("utf-8")
    salt = b"electrum" + normalize_text(passphrase).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha512", m, salt, PBKDF2_ROUNDS, dklen=64)


def master(mnemonic: str, passphrase: str = "") -> Node:
    return master_from_seed(mnemonic_to_seed(mnemonic, passphrase))


def iter_hash160s(mnemonic: str, passphrase: str = "", depth: int = 5,
                  chains: Sequence[int] = (0, 1)) -> Iterator[tuple[bytes, str, int]]:
    """Yield ``(hash160, chain_name, index)`` for a standard Electrum wallet.

    Receiving addresses live at m/0/i and change at m/1/i - directly off the
    master node, with no BIP-44 purpose/coin/account levels.
    """
    root = master(mnemonic, passphrase)
    names = {0: "electrum-receiving", 1: "electrum-change"}
    for chain in chains:
        try:
            parent = ckd_priv(root, chain)
        except ValueError:  # pragma: no cover - negligible probability
            continue
        for i in range(depth):
            try:
                child = ckd_priv(parent, i)
            except ValueError:  # pragma: no cover
                continue
            yield hash160(pubkey_from_privkey(child.key, True)), names.get(chain, str(chain)), i
