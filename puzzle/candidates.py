"""Candidate vocabulary derived from the puzzle image and published hints.

Words are grouped by how directly the evidence supports them. The tiers exist
because search cost grows super-exponentially with pool size: a 12-word pool
finishes in hours, a 16-word pool takes most of a year. Choosing which tier to
include is the highest-leverage decision a solver makes.
"""

from __future__ import annotations

from .wordlist import is_valid

#: Words located by direct inspection of the artwork (see ANALYSIS.md section 2).
#: Each was read off the image with ``forensics.py``, not taken on trust from
#: the published hints.
#:   moon    - written along the red clock hand
#:   tower   - written along the black clock hand
#:   food    - written down the Space Needle's shaft
#:   subject - underlined in the 13th Amendment text on the monument plinth
#:   real    - inserted into "ONLY real Bitcoin" on the Statue's base
#:   this    - "IN THE THIS PICTURE", "FUCK THIS SHIT", "THIS IS THE FIRST..."
#:   black   - rune 4's "chorny den" (black day) plus the BLM text and the Latin
#:   one     - the numeral 1 in "Section 1" carries the same underline as
#:             "subject", in the same hand and weight (verified at 20x)
TIER_A = ["moon", "tower", "food", "this", "subject", "real", "black", "one"]

#: Prominent rendered text, also read directly off the artwork.
#:   brave/world - "WELCOME TO THE BRAVE NEW WORLD" (the whitepaper calligram)
#:   order       - "Order and stability" across the top
#:   only        - "ONLY real Bitcoin" on the Statue's base
#:   first/future- "PAY FOR THE FUTURE. THIS IS THE FIRST PREDICTION."
#:   seed/phrase/picture/find - "FIND THE SEED PHRASE IN THE THIS PICTURE"
TIER_B = ["brave", "world", "order", "only", "first", "future",
          "seed", "phrase", "picture", "find"]

#: The words that are *marked* rather than merely present: written tiny along
#: a thin object, inserted, or underlined. This is the mechanism the artist
#: actually used, and it is a much stronger signal than display text.
MARKED = ["moon", "tower", "food", "real", "subject", "one"]

#: Set faintly rendered rather than displayed - "PAY FOR THE FUTURE. THIS IS
#: THE FIRST PREDICTION." is barely visible without a contrast stretch, which
#: puts it closer to MARKED than to the banner text.
FAINT = ["future", "this", "first"]

#: The pool actually being searched: everything marked or faint, plus "black"
#: (rune 4's "chorny den", the Latin kettle proverb and the BLM text all point
#: at it) and the two strongest display words. Exactly twelve.
BEST_12 = MARKED + FAINT + ["black", "only", "world"]

#: Wider pool, tier A plus the six tier-B display words. P(13,12) is about
#: 4 days on four cores, or half that on the BIP-44 fast path.
BEST_13 = ["moon", "tower", "food", "this", "subject", "real", "black",
           "only", "first", "future", "brave", "world", "order"]

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
    "breathe",    # printed on Floyd's hoodie; claimed on the Statue's neck too,
                  # which could not be confirmed at 1600x1200
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
