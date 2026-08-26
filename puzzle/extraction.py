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


#: Source texts the artwork **quotes or references verbatim**. Nothing here
#: was chosen after seeing a result: the artwork prints the Amendment on the
#: plinth, renders whitepaper prose twice (the calligram and the bottom
#: strip), and replaces the Great Seal's three inscriptions with three
#: specific Latin quotations. Arbitrary passages are deliberately excluded -
#: with enough source texts something always fits.
SOURCE_TEXTS: dict[str, tuple[str, str]] = {
    "amendment_s1": (
        "Neither slavery nor involuntary servitude except as a punishment for "
        "crime whereof the party shall have been duly convicted shall exist "
        "within the United States or any place subject to their jurisdiction",
        "13th Amendment Section 1, printed verbatim on the plinth "
        "(text from the US National Archives)",
    ),
    "amendment_full": (
        "Neither slavery nor involuntary servitude except as a punishment for "
        "crime whereof the party shall have been duly convicted shall exist "
        "within the United States or any place subject to their jurisdiction "
        "Congress shall have power to enforce this article by appropriate "
        "legislation",
        "13th Amendment, both sections",
    ),
    "whitepaper_abstract": (
        "A purely peer-to-peer version of electronic cash would allow online "
        "payments to be sent directly from one party to another without going "
        "through a financial institution Digital signatures provide part of "
        "the solution but the main benefits are lost if a trusted third party "
        "is still required to prevent double-spending We propose a solution to "
        "the double-spending problem using a peer-to-peer network The network "
        "timestamps transactions by hashing them into an ongoing chain of "
        "hash-based proof-of-work forming a record that cannot be changed "
        "without redoing the proof-of-work",
        "Bitcoin whitepaper abstract (bitcoin.org/bitcoin.pdf); the artwork "
        "renders whitepaper prose in the calligram and the bottom strip",
    ),
    "whitepaper_transactions": (
        "We define an electronic coin as a chain of digital signatures Each "
        "owner transfers the coin by digitally signing a hash of the previous "
        "transaction and the public key of the next owner and adding these to "
        "the end of the coin A payee can verify the signatures to verify the "
        "chain of ownership",
        "whitepaper section 2, the text the BRAVE NEW WORLD calligram is "
        "built from",
    ),
    "seal_latin": (
        "RERUM COGNOSCERE CAUSAS FIAT JUSTITIA ET PEREAT MUNDUS "
        "UBI BENE IBI PATRIA",
        "the Great Seal's three inscriptions, all replaced by the artist",
    ),
}

#: Selection conventions, fixed before running. A correct one must map every
#: number to a BIP-39 word - a seed phrase has no non-BIP-39 members - so the
#: bar is 4 of 4, not "better than the null".
SOURCE_CONVENTIONS = (
    ("word", 1, False), ("word", 0, False),
    ("word", 1, True), ("word", 0, True),
    ("initial", 1, False), ("char", 1, False),
)


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


def source_sweep(indices=CONFIRMED_NUMBERS) -> list[Result]:
    """Test the pre-registered sources under the pre-registered conventions."""
    out = []
    for name, (text, _) in SOURCE_TEXTS.items():
        for unit, base, rev in SOURCE_CONVENTIONS:
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
    "source_text_indexing": {
        "tested": "25 attempts - 5 pre-registered source texts (13th Amendment "
                  "Section 1 and full, the whitepaper abstract and its "
                  "Transactions section, the Great Seal's three Latin "
                  "inscriptions) x 6 pre-registered conventions",
        "sources_chosen": "only texts the artwork quotes or references "
                          "verbatim; arbitrary passages excluded, because with "
                          "enough source texts something always fits",
        "four_of_four": 0,
        "best": "2 of 4, against nulls of 0.24-0.30 - i.e. at the noise floor",
        "verdict": "refuted",
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


#: The responsible stopping point.
#:
#: Across **83 pre-registered attempts** - 58 over text rendered in the
#: artwork, 25 over the source texts it quotes - under every reasonable
#: indexing convention, **not one produced a complete BIP-39 set**. That is
#: the discriminating test: a seed phrase has no non-BIP-39 members, so a
#: correct convention yields 4 of 4 by construction, not merely a good score.
#:
#: Combined with the capacity bound in ``positions.MECHANISM_CAPACITY``, the
#: honest classification of this puzzle is **underdetermined**: the artwork
#: does not supply enough recoverable structure to determine a phrase.
#:
#: What is established, and is not in doubt:
#:   * three clock hands encode 3, 13 and 21 by the midpoint rule (~1 in 2,500
#:     by chance), captioned by rune 2's "sum of two numbers" inside the dial;
#:   * the plinth pairs an underlined ``subject`` with an underlined ``1``;
#:   * five words are deliberately marked - moon, tower, food, subject, real.
#:
#: What is closed:
#:   * ray-matching cannot name words (5 of 9 positions carry >1 object);
#:   * text indexing, wordlist indices, derivation paths, source-text indexing;
#:   * date references and numbered-source references, refuted against the
#:     three anchors the artwork supplies - see ``puzzle.references``;
#:   * steganography; brainwallet to 6 words; BEST_12 as an Electrum seed.
#:
#: What would change the picture, in descending order of value:
#:   1. a higher-resolution original - runes 1 and 2, the clock bearings and
#:      the claimed neck text are all blocked on resolution, not on method;
#:   2. a fourth number-bearing mechanism, which the capacity bound says must
#:      exist if the position reading is right;
#:   3. the puzzle author's own confirmation of the construction.
#:
#: What will **not** help: more CPU. Every remaining search is unbounded
#: because the word set is unknown, and a negative from guessed fillers is not
#: a result. The engine has never been the constraint.
UNDERDETERMINED = {
    "attempts_total": 83,
    "attempts_artwork_text": 58,
    "attempts_source_text": 25,
    "all_bip39_results": 0,
    "confirmed_positions": 3,
    "mechanism_capacity": 4,
    "positions_needed": 24,
    "reference_schemes_tested": 1_167_608,
    "reference_schemes_fitting_anchors": 0,
    "verdict": "underdetermined - insufficient recoverable structure, "
               "not insufficient compute",
}


#: **The whitepaper typos are hand-lettering noise, not a cipher.**
#:
#: The artwork hand-copies ~1180 characters of the whitepaper's section 2 into
#: the ``BRAVE NEW WORLD`` calligram and the bottom strip. Six words deviate
#: from the source, and the deviations are tempting: a known source text plus
#: deliberate errors is a classic carrier, and the whitepaper (2008) sits
#: comfortably inside the pre-2020-05-10 window the chronology requires.
#:
#: They do not survive testing. Four independent reasons:
#:
#: 1. **Every one is a canonical copying slip.** A dropped letter twice, a
#:    doubled letter, two transpositions, and a ``b``/``d`` confusion - which
#:    is the single most common error in hand lettering.
#: 2. **The rate is uniform, not sparse.** The ~240 characters the community
#:    transcribed in full contain two typos: 0.8%. Across 1180 characters that
#:    projects to about nine, and six were found. A deliberate payload would
#:    be sparse and placed; this is a flat error rate.
#: 3. **The deviation letters spell nothing.** In the order the passage
#:    presents them, deleted letters give ``cnncet`` and inserted letters give
#:    ``ncenr``.
#: 4. **The marked words are not BIP-39 words**, and a control settles it:
#:    2 of the 6 typo-bearing words are in the wordlist (``double``, ``sign``),
#:    against **5 of 10** ordinary words drawn from the same passage
#:    (``problem``, ``solution``, ``history``, ``company``, ``system``). The
#:    typos point at BIP-39 words *less* often than chance.
#:
#: The control is the part that matters. Without it, "two of the six typo
#: words are BIP-39" reads as a hit.
WHITEPAPER_TYPOS = {
    "source": "Bitcoin whitepaper section 2, ~1180 characters",
    "deviations": (
        {"artwork": "doudle", "source": "double", "kind": "b/d confusion"},
        {"artwork": "introdue", "source": "introduce", "kind": "dropped letter"},
        {"artwork": "sing", "source": "sign", "kind": "transposition"},
        {"artwork": "abcense", "source": "absence", "kind": "transposition"},
        {"artwork": "arrrived", "source": "arrived", "kind": "doubled letter"},
        {"artwork": "participans", "source": "participants",
         "kind": "dropped letter"},
    ),
    "deleted_letters_in_order": "cnncet",
    "inserted_letters_in_order": "ncenr",
    "typo_words_in_bip39": 2,
    "typo_words_total": 6,
    "control_words_in_bip39": 5,
    "control_words_total": 10,
    "observed_rate": 0.008,
    "verdict": "noise - all six are canonical copying slips occurring at a "
               "flat rate, the deviation letters spell nothing, and the "
               "marked words hit BIP-39 below the control rate",
}

#: A correction. Section 10 of ANALYSIS.md described the calligram as
#: "uniform whitepaper prose, no word emphasised or altered". The first half
#: stands - nothing is emphasised - but the second half is **wrong**: six
#: words are altered. They were missed because that sweep looked for
#: *emphasis* (underlining, weight, colour) rather than for *spelling*.
#: The conclusion is unchanged, and now rests on a test instead of an
#: oversight.
CALLIGRAM_CLAIM_CORRECTED = {
    "was": "uniform whitepaper prose, no word emphasised or altered",
    "now": "no word emphasised; six words altered, and the alterations are "
           "hand-lettering noise (see WHITEPAPER_TYPOS)",
    "why_missed": "the sweep looked for emphasis, not for spelling",
}
