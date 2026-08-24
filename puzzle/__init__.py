"""Tooling for the 0.2 BTC puzzle (address 1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ).

The package is deliberately dependency-light: everything except secp256k1
point multiplication runs on the Python standard library, and even that has a
pure-Python fallback so the tool works on a machine with no build toolchain.
"""

__all__ = [
    "wordlist",
    "bip39",
    "keys",
    "derive",
    "brainwallet",
    "feasibility",
    "search",
    "candidates",
]
