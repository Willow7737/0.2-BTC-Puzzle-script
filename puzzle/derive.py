"""BIP-32 hierarchical derivation and the address schemes worth testing.

A 2020-era wallet holding a legacy ``1...`` address could have been created
by any of several tools that disagree about the derivation path. Checking a
single path - as the original script did - risks walking straight past the
answer, so every scheme below is tested for each candidate seed.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass, replace
from hashlib import sha512
from typing import Iterator, Sequence

from .keys import N, hash160, pubkey_from_privkey

HARDENED = 0x80000000


@dataclass(frozen=True)
class Node:
    """A BIP-32 extended private key."""

    key: bytes
    chain_code: bytes


def master_from_seed(seed: bytes) -> Node:
    """Derive the BIP-32 master node from a 64-byte seed."""
    digest = hmac.new(b"Bitcoin seed", seed, sha512).digest()
    return Node(digest[:32], digest[32:])


def ckd_priv(node: Node, index: int) -> Node:
    """Child key derivation (private parent -> private child)."""
    if index & HARDENED:
        data = b"\x00" + node.key + index.to_bytes(4, "big")
    else:
        data = pubkey_from_privkey(node.key, True) + index.to_bytes(4, "big")
    digest = hmac.new(node.chain_code, data, sha512).digest()
    child = (int.from_bytes(digest[:32], "big") + int.from_bytes(node.key, "big")) % N
    if child == 0 or int.from_bytes(digest[:32], "big") >= N:
        raise ValueError("invalid child key")  # ~2^-127, retry with next index
    return Node(child.to_bytes(32, "big"), digest[32:])


def parse_path(path: str) -> list[int]:
    """Parse ``m/44'/0'/0'/0`` style paths into a list of child indices."""
    parts = path.strip().split("/")
    if parts and parts[0] in ("m", "M"):
        parts = parts[1:]
    out = []
    for part in parts:
        if not part:
            continue
        hardened = part[-1] in ("'", "h", "H")
        num = int(part[:-1] if hardened else part)
        out.append(num + HARDENED if hardened else num)
    return out


def derive_path(node: Node, path: str | Sequence[int]) -> Node:
    """Walk a derivation path from *node*."""
    indices = parse_path(path) if isinstance(path, str) else path
    for index in indices:
        node = ckd_priv(node, index)
    return node


@dataclass(frozen=True)
class Scheme:
    """A named derivation path plus how many address indices to scan."""

    name: str
    path: str
    depth: int = 1
    compressed: bool = True
    note: str = ""


#: Ordered by how likely each is for a 2020 legacy-address puzzle wallet.
SCHEMES: tuple[Scheme, ...] = (
    Scheme("bip44", "m/44'/0'/0'/0", 5, True, "BIP-44 standard (Trezor, Ledger, most wallets)"),
    Scheme("bip32-legacy", "m/0'/0", 5, True, "bitcoinjs / blockchain.info legacy default"),
    Scheme("bip32-root", "m/0", 5, True, "Electrum-style root/receive chain"),
    Scheme("master", "m", 1, True, "master private key used directly"),
    Scheme("bip44-uncompressed", "m/44'/0'/0'/0", 5, False, "BIP-44 with uncompressed pubkeys"),
    Scheme("bip32-root-uncompressed", "m/0", 5, False, "root chain, uncompressed pubkeys"),
)

SCHEMES_BY_NAME = {s.name: s for s in SCHEMES}
DEFAULT_SCHEMES = ("bip44", "bip32-legacy", "bip32-root", "master")


def iter_hash160s(seed: bytes, schemes: Sequence[Scheme]) -> Iterator[tuple[bytes, str, int]]:
    """Yield ``(hash160, scheme_name, address_index)`` for a seed.

    The parent node for each scheme is derived once and reused across address
    indices, so scanning five addresses costs barely more than scanning one.
    """
    master = master_from_seed(seed)
    for scheme in schemes:
        try:
            if scheme.path in ("m", "M", ""):
                yield hash160(pubkey_from_privkey(master.key, scheme.compressed)), scheme.name, 0
                continue
            parent = derive_path(master, scheme.path)
            for i in range(scheme.depth):
                child = ckd_priv(parent, i)
                yield hash160(
                    pubkey_from_privkey(child.key, scheme.compressed)
                ), scheme.name, i
        except ValueError:
            continue


def resolve_schemes(names: Sequence[str], depth: int | None = None) -> list[Scheme]:
    """Map scheme names (or ``all``) to Scheme objects.

    ``depth`` overrides how many address indices each scheme scans. Dropping
    from 5 to 1 roughly doubles throughput, because the EC work after PBKDF2
    is comparable in cost to PBKDF2 itself - worth it when trading breadth for
    coverage of the single most likely path.
    """
    if not names or "all" in names:
        chosen = list(SCHEMES)
    else:
        missing = [n for n in names if n not in SCHEMES_BY_NAME]
        if missing:
            raise ValueError(
                f"unknown scheme(s): {', '.join(missing)}; "
                f"available: {', '.join(SCHEMES_BY_NAME)}, all"
            )
        chosen = [SCHEMES_BY_NAME[n] for n in names]
    if depth is not None:
        chosen = [replace(s, depth=max(1, depth)) for s in chosen]
    return chosen
