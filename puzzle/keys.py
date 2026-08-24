"""secp256k1 keys, Base58Check, and Bitcoin address encoding.

Uses libsecp256k1 through ``coincurve`` when it is installed (roughly 50x
faster) and falls back to a pure-Python implementation otherwise.
"""

from __future__ import annotations

import hashlib

# --- RIPEMD-160: prefer hashlib, fall back to the bundled implementation ----
try:
    hashlib.new("ripemd160")

    def _ripemd160(data: bytes) -> bytes:
        h = hashlib.new("ripemd160")
        h.update(data)
        return h.digest()

    RIPEMD160_BACKEND = "hashlib"
except (ValueError, TypeError):  # pragma: no cover - depends on OpenSSL build
    from ._ripemd160 import ripemd160 as _ripemd160

    RIPEMD160_BACKEND = "pure-python"

# --- secp256k1 --------------------------------------------------------------
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

try:
    from coincurve.keys import PrivateKey as _CCPrivateKey

    def pubkey_from_privkey(priv: bytes, compressed: bool = True) -> bytes:
        """Serialised secp256k1 public key for a 32-byte private key."""
        return _CCPrivateKey(priv).public_key.format(compressed=compressed)

    EC_BACKEND = "coincurve"
except ImportError:  # pragma: no cover - exercised only without coincurve

    def _point_add(p1, p2):
        if p1 is None:
            return p2
        if p2 is None:
            return p1
        x1, y1 = p1
        x2, y2 = p2
        if x1 == x2:
            if (y1 + y2) % P == 0:
                return None
            lam = (3 * x1 * x1) * pow(2 * y1, P - 2, P) % P
        else:
            lam = (y2 - y1) * pow(x2 - x1, P - 2, P) % P
        x3 = (lam * lam - x1 - x2) % P
        return (x3, (lam * (x1 - x3) - y1) % P)

    def _point_mul(k: int):
        result = None
        addend = (GX, GY)
        while k:
            if k & 1:
                result = _point_add(result, addend)
            addend = _point_add(addend, addend)
            k >>= 1
        return result

    def pubkey_from_privkey(priv: bytes, compressed: bool = True) -> bytes:
        """Serialised secp256k1 public key for a 32-byte private key."""
        k = int.from_bytes(priv, "big")
        if not 0 < k < N:
            raise ValueError("private key out of range")
        x, y = _point_mul(k)
        if compressed:
            return bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
        return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")

    EC_BACKEND = "pure-python"


# --- hashing and encoding ---------------------------------------------------
B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_MAP = {c: i for i, c in enumerate(B58_ALPHABET)}


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hash160(data: bytes) -> bytes:
    """RIPEMD-160(SHA-256(data)) - the Bitcoin public key hash."""
    return _ripemd160(hashlib.sha256(data).digest())


def b58check_encode(payload: bytes) -> str:
    """Base58Check-encode *payload* (version byte included)."""
    checksum = sha256(sha256(payload))[:4]
    full = payload + checksum
    num = int.from_bytes(full, "big")
    out = ""
    while num > 0:
        num, rem = divmod(num, 58)
        out = B58_ALPHABET[rem] + out
    for byte in full:
        if byte != 0:
            break
        out = "1" + out
    return out


def b58check_decode(text: str) -> bytes:
    """Decode Base58Check, returning the payload without the checksum."""
    num = 0
    for ch in text:
        try:
            num = num * 58 + _B58_MAP[ch]
        except KeyError:
            raise ValueError(f"invalid base58 character {ch!r}") from None
    body = num.to_bytes((num.bit_length() + 7) // 8, "big")
    pad = len(text) - len(text.lstrip("1"))
    full = b"\x00" * pad + body
    if len(full) < 5:
        raise ValueError("base58 string too short")
    payload, checksum = full[:-4], full[-4:]
    if sha256(sha256(payload))[:4] != checksum:
        raise ValueError("bad Base58Check checksum")
    return payload


def address_from_hash160(h160: bytes, version: int = 0x00) -> str:
    """Encode a 20-byte public key hash as a Base58Check address."""
    return b58check_encode(bytes([version]) + h160)


def hash160_from_address(address: str) -> bytes:
    """Extract the 20-byte hash from a P2PKH/P2SH address.

    Comparing 20-byte hashes instead of Base58 strings removes an expensive
    big-integer encode from the inner search loop.
    """
    payload = b58check_decode(address)
    if len(payload) != 21:
        raise ValueError(f"not a P2PKH/P2SH address: {address}")
    return payload[1:]


def address_from_privkey(priv: bytes, compressed: bool = True, version: int = 0x00) -> str:
    """Full private key -> P2PKH address path, for tests and reporting."""
    return address_from_hash160(hash160(pubkey_from_privkey(priv, compressed)), version)


def privkey_to_wif(priv: bytes, compressed: bool = True, version: int = 0x80) -> str:
    """Encode a private key in Wallet Import Format."""
    payload = bytes([version]) + priv + (b"\x01" if compressed else b"")
    return b58check_encode(payload)
