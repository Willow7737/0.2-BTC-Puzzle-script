"""Do the numbers index text rather than mnemonic positions?

The position-map model is capacity-bounded: the bearing rule needs the object
to *be* a clock hand and there are three, so four positions is its ceiling
(see ``positions.MECHANISM_CAPACITY``). That makes the leap from "these are
numbers" to "these are mnemonic positions" the weakest link, and the numbers
worth testing against other readings.

The obvious alternative is that **1, 3, 13 and 21 index into text** — take the
1st, 3rd, 13th and 21st word (or character) of a marked passage. The artwork
is full of deliberately rendered text, and one of the numbers is even written
into a passage (``Section 1`` heads the Amendment).

This module tests that exhaustively and honestly. It extracts under every
combination of unit, base and direction, scores each result by how many
extracted tokens are BIP-39 words, and compares against a null of random
index sets drawn from the same passage. A hypothesis only counts if it beats
the null it is measured against.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from itertools import product

from .wordlist import is_valid

#: The confirmed numbers, in the order they were established.
CONFIRMED_NUMBERS = (1, 3, 13, 21)

#: Text rendered deliberately in the artwork. Each entry is
#: ``name -> (text, provenance)``. Only passages actually read off the image
#: (or decoded from a rune) are included - nothing invented to make a fit.
CORPUS: dict[str, tuple[str, str]] = {
    "amendment": (
        "Neither slavery nor involuntary servitude except as a punishment for "
        "crime whereof the party shall have been duly convicted shall exist "
        "within the United States or any place subject to their jurisdiction",
        "13th Amendment Section 1, on the monument plinth; carries the "
        "underlined 1 and the underlined word subject",
    ),
    "find_the_seed": (
        "FIND THE SEED PHRASE IN THE THIS PICTURE",
        "large display text across the top; note the doubled THE THIS",
    ),
    "brave_new_world": (
        "WELCOME TO THE BRAVE NEW WORLD",
        "the whitepaper calligram spells this",
    ),
    "order_stability": ("Order and stability", "handwritten banner, top"),
    "only_real_bitcoin": (
        "ONLY real Bitcoin",
        "Statue's base; 'real' was inserted over an original 'Only Bitcoin'",
    ),
    "pay_for_the_future": (
        "PAY FOR THE FUTURE THIS IS THE FIRST PREDICTION",
        "faint vertical text at the left edge",
    ),
    "whitepaper_bottom": (
        "in which they were received the payee needs proof that at the time of "
        "each transaction the majority of nodes agreed it was the first received",
        "handwritten strip along the bottom edge",
    ),
    "seal_top": ("RERUM COGNOSCERE CAUSAS",
                 "Great Seal top arc, replacing ANNUIT COEPTIS"),
    "seal_pyramid": ("FIAT JUSTITIA ET PEREAT MUNDUS",
                     "Great Seal pyramid base, replacing MDCCLXXVI"),
    "seal_bottom": ("UBI BENE IBI PATRIA",
                    "Great Seal bottom arc, replacing NOVUS ORDO SECLORUM"),
    "latin_kettle": ("Esse quam niger es sic dixit caccabus ollae",
                     "bottom right; the pot calling the kettle black"),
    "blm_slogans": (
        "BLACK LIVES MATTER NO JUSTICE NO PEACE END POLICE BRUTALITY "
        "STOP KILLING US NOT ONE MORE",
        "five stacked slogans, upper right",
    ),
    "rune4": (
        "ZDES ZASHIFROVANY BITKOINY NA CHORNYY DEN NOMER",
        "rune 4 decoded and verified against its crib, transliterated",
    ),
    "rune1": (
        "YA NADEYUS CHTO SYUDA BUDUT PRISYLAT MNOGO BITKOINOV",
        "rune 1 published plaintext, transliterated; not independently verified",
    ),
    "hoodie": ("I cant BREATHE", "printed on the hoodie"),
}


def tokens(text: str, unit: str) -> list[str]:
    """Split a passage into indexable units."""
    if unit == "word":
        return text.split()
    if unit == "char":
        return list(re.sub(r"\s+", "", text))
    if unit == "initial":
        return [w[0] for w in text.split()]
    raise ValueError(f"unknown unit {unit!r}")


def extract(text: str, indices, unit: str = "word", base: int = 1,
            reverse: bool = False) -> list[str] | None:
    """Pull the given indices out of a passage, or None if any is out of range."""
    toks = tokens(text, unit)
    if reverse:
        toks = toks[::-1]
    out = []
    for i in indices:
        j = i - base
        if not 0 <= j < len(toks):
            return None
        out.append(toks[j])
    return out


@dataclass
class Result:
    """One extraction attempt and how well it scored."""

    passage: str
    unit: str
    base: int
    reverse: bool
    extracted: list[str]
    bip39_hits: int

    @property
    def score(self) -> float:
        return self.bip39_hits / len(self.extracted) if self.extracted else 0.0


def score_tokens(toks: list[str]) -> int:
    """How many extracted tokens are BIP-39 words."""
    return sum(1 for t in toks if is_valid(t.lower().strip(".,;:!?'\"")))


def sweep(indices=CONFIRMED_NUMBERS, corpus=None) -> list[Result]:
    """Every passage x unit x base x direction, scored."""
    corpus = corpus or CORPUS
    out = []
    for name, (text, _) in corpus.items():
        for unit, base, rev in product(("word", "char", "initial"), (0, 1), (False, True)):
            got = extract(text, indices, unit, base, rev)
            if got is None:
                continue
            out.append(Result(name, unit, base, rev, got, score_tokens(got)))
    return sorted(out, key=lambda r: (-r.bip39_hits, r.passage))


def null_rate(passage: str, unit: str, n_indices: int, trials: int = 4000,
              seed: int = 0) -> float:
    """Expected BIP-39 hit rate for *random* indices into the same passage.

    Without this the sweep is meaningless: a passage of ordinary English will
    yield BIP-39 words at some background rate no matter which indices are
    chosen, because the wordlist is 2048 common words.
    """
    toks = tokens(passage, unit)
    if len(toks) < n_indices:
        return 0.0
    rng = random.Random(seed)
    total = 0
    for _ in range(trials):
        pick = rng.sample(range(len(toks)), n_indices)
        total += score_tokens([toks[i] for i in pick])
    return total / (trials * n_indices)


#: Results of testing the alternative readings of 1, 3, 13, 21. All three
#: were cheap, bounded and falsifiable, and all three failed. Recorded so
#: they are not retried.
REFUTED = {
    "text_indexing": {
        "tested": "58 extractions - every passage x {word, char, initial} x "
                  "{0,1}-based x {forward, reverse}",
        "best": "2 of 4 BIP-39 words, against a null of 1 of 4; with 58 "
                "attempts the best beating the null is expected",
        "four_of_four": 0,
        "decisive": "In the Amendment - the one passage carrying both a "
                    "marked number and a marked word - 'subject' is word 29 "
                    "of 32, not word 1. If the underlined 1 indexed that "
                    "text, subject would sit at position 1. It does not.",
        "verdict": "refuted",
    },
    "wordlist_indices": {
        "tested": "WORDS[1], WORDS[3], WORDS[13], WORDS[21], 0- and 1-based",
        "result": "['abandon','able','account','action'] / "
                  "['ability','about','accuse','actor'] - the head of the "
                  "alphabetical list, not a phrase",
        "verdict": "no signal",
    },
    "derivation_path": {
        "tested": "568,800 derivations - 900 candidate seeds (the marked "
                  "words in every order of 3-5, as BIP-39, BIP-39 with the "
                  "'breathe' passphrase, and Electrum) x 632 paths (every "
                  "ordering of 1/3/13/21, every hardened/soft combination, "
                  "and every prefix), compressed and uncompressed",
        "matches": 0,
        "verdict": "refuted",
    },
}
