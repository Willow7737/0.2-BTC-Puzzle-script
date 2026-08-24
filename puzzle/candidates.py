"""Candidate vocabulary derived from the puzzle image and published hints.

Words are grouped by how directly the evidence supports them. The tiers exist
because search cost grows super-exponentially with pool size: a 12-word pool
finishes in hours, a 16-word pool takes most of a year. Choosing which tier to
include is the highest-leverage decision a solver makes.
"""

from __future__ import annotations

from .wordlist import is_valid

#: Named outright in the puzzle's published hints, and valid BIP-39 words.
TIER_A = ["moon", "tower", "food", "this", "subject", "real", "black"]

#: Prominent rendered text in the artwork.
#: "BRAVE NEW WORLD", "Order and stability", "ONLY real Bitcoin",
#: "FIND THE SEED PHRASE IN THIS PICTURE".
TIER_B = ["brave", "world", "order", "only", "seed", "phrase", "picture", "find"]

#: Objects drawn in the image, in rough order of visual prominence.
TIER_C = [
    "flag", "mask", "face", "camera", "eye", "pyramid", "clock", "hand",
    "liberty", "space", "virus", "police", "peace", "life", "matter",
    "blood", "market", "riot", "health",
]

#: Concepts from the dense handwritten Bitcoin-whitepaper text and the runes.
TIER_D = [
    "coin", "digital", "public", "private", "key", "network", "trust", "proof",
    "spend", "double", "history", "time", "first", "future", "predict",
    "number", "secret", "rain", "day", "two",
]

#: Words the hints point at that are NOT in the BIP-39 list. Any of these
#: being part of the real answer would rule out a plain BIP-39 mnemonic and
#: point at a free-form passphrase instead - see ANALYSIS.md.
NOT_IN_BIP39 = [
    "breathe",    # "I can't BREATHE" - the single most-cited hint
    "tuesday",    # rune 3, Bill Cipher
    "statue", "justice", "lives", "fist", "protest", "monument", "needle",
    "vaccine", "syringe", "money", "chart", "graph", "bitcoin", "new",
    "stability", "prediction", "hash", "block", "chain", "transaction", "sum",
]

TIERS = {"A": TIER_A, "B": TIER_B, "C": TIER_C, "D": TIER_D}


def build_pool(tiers: str = "A") -> list[str]:
    """Concatenate the requested tiers, e.g. ``"AB"``, preserving order."""
    pool: list[str] = []
    for letter in tiers.upper():
        if letter not in TIERS:
            raise ValueError(f"unknown tier {letter!r}; choose from {''.join(TIERS)}")
        for word in TIERS[letter]:
            if word not in pool:
                pool.append(word)
    return pool


def audit() -> dict[str, list[str]]:
    """Sanity-check that every tier word really is in the BIP-39 list."""
    problems = {}
    for name, words in TIERS.items():
        bad = [w for w in words if not is_valid(w)]
        if bad:
            problems[name] = bad
    return problems
