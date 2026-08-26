"""Do 1, 3, 13 and 21 reference a date or a numbered source?

``extraction`` tested whether the numbers *index text*. This module tests the
other two readings that keep coming up: that each number **references a date**
(1/3 for the genesis block, 13 for the Amendment, and so on), or that it
**references a numbered source** (Amendment 13, whitepaper section 3, BIP-21),
with the reference then naming a BIP-39 word.

Both readings resolve a number to a word. That forces a change of test.

**The usual bar does not apply here.** ``extraction`` could score a hypothesis
by "are all four extracted tokens BIP-39 words?", because it pulled tokens out
of English prose, where landing on a wordlist entry is informative. A scheme
that resolves a number to a *wordlist index* returns a BIP-39 word by
construction, every time, for every input. Scoring it that way would pass
everything. So a forward sweep of "what word does 13 give?" cannot discriminate
and is not evidence, however good the word looks.

**The test that does discriminate runs backwards, off the anchors.** The
artwork pairs three numbers with three words: an underlined ``1`` with an
underlined ``subject`` on the plinth, and clock hands giving 3 and 13 beside
``tower`` and ``moon``. The position model reads those pairings as "this word
sits at that position". The reference model reads the same pairings as "this
number names that word" - the same evidence, the other way round. So any
reference scheme ``f`` is pinned by three simultaneous constraints:

    f(1) = subject      f(3) = tower      f(13) = moon

That is falsifiable, and it is cheap to falsify exhaustively. A scheme that
misses any anchor is refuted regardless of how appealing ``f(21)`` looks.

**A fit found by sweeping is not a confirmation.** Fitting on one anchor and
checking two leaves a chance pass rate of 1/2048² per scheme. Sweeping ~4.2
million schemes therefore *expects* about one accidental fit. The sweeps below
are sized so that a single hit would be at the noise floor and would have to be
pre-registered and simple to mean anything. Zero hits is the informative
outcome, and zero is what they return.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import permutations, product

from .wordlist import load_wordlist

_W = load_wordlist()
_IDX = {w: i for i, w in enumerate(_W)}

#: The numbers, in the order they were established.
NUMBERS = (1, 3, 13, 21)

#: The three number/word pairings the artwork actually shows, read the way the
#: reference model reads them: the number *names* the word.
ANCHORS: dict[int, str] = {1: "subject", 3: "tower", 13: "moon"}

#: The same anchors as 0-based wordlist indices - what a scheme must produce.
ANCHOR_INDICES: dict[int, int] = {n: _IDX[w] for n, w in ANCHORS.items()}

#: The five deliberately marked words, as 0-based wordlist indices. Recorded
#: because the reachability checks below ask whether a scheme can name any of
#: them - they are the only words known to belong to the phrase.
MARKED_INDICES: dict[str, int] = {
    w: _IDX[w] for w in ("subject", "tower", "moon", "food", "real")
}

_EPOCH = date(1970, 1, 1)
_MODULUS = 2048


def word_at(index: int, base: int = 0) -> str | None:
    """The wordlist entry at *index*, or None if it falls outside the list."""
    j = index - base
    return _W[j] if 0 <= j < _MODULUS else None


def chance_fit_rate(schemes_tested: int, anchors_checked: int = 2) -> float:
    """Expected number of schemes passing the anchor test by luck alone.

    A scheme is fitted on one anchor, so only the remaining ones discriminate;
    each has a 1/2048 chance of matching at random. Without this figure a
    sweep large enough to find something proves nothing.
    """
    return schemes_tested / (_MODULUS ** anchors_checked)


@dataclass
class Sweep:
    """One family of schemes, how many were tried, and what survived."""

    family: str
    tested: int
    hits: list[tuple] = field(default_factory=list)
    note: str = ""

    @property
    def expected_by_chance(self) -> float:
        return chance_fit_rate(self.tested)

    @property
    def refuted(self) -> bool:
        return not self.hits

    def __str__(self) -> str:
        verdict = "refuted" if self.refuted else f"{len(self.hits)} fit"
        return (f"{self.family}: {self.tested:,} schemes, {verdict} "
                f"(chance-fit expectation {self.expected_by_chance:.3f})")


# --------------------------------------------------------------------------
# Family 1: affine index schemes
# --------------------------------------------------------------------------

def affine_sweep() -> Sweep:
    """Every scheme of the form ``f(n) = WORDS[(a*n + b) mod 2048]``.

    Complete, not sampled: fixing *a* and the ``f(1) = subject`` anchor
    determines *b*, so sweeping *a* over 0..2047 covers the whole family. This
    subsumes every "multiply the number by something" and "count from an
    offset" reading in one pass, including all of the date schemes whose
    date-to-index step happens to be linear.
    """
    hits = []
    for a in range(_MODULUS):
        b = (ANCHOR_INDICES[1] - a) % _MODULUS
        if all((a * n + b) % _MODULUS == t for n, t in ANCHOR_INDICES.items()):
            hits.append((a, b))
    return Sweep("affine", _MODULUS, hits,
                 "complete over the family, not a sample")


def affine_near_miss() -> list[tuple[int, int, str]]:
    """Schemes fitting anchors 1 and 3 but not 13, with what they predict at 13.

    Recorded deliberately. Both of them send 13 to ``coin`` - a word that looks
    perfect for a Bitcoin puzzle and is simply wrong, because the artwork puts
    ``moon`` there. Anyone re-deriving this will hit the same near-miss, and
    it is worth having the refutation written down next to the temptation.
    """
    out = []
    for a in range(_MODULUS):
        b = (ANCHOR_INDICES[1] - a) % _MODULUS
        if (a * 3 + b) % _MODULUS == ANCHOR_INDICES[3]:
            if (a * 13 + b) % _MODULUS != ANCHOR_INDICES[13]:
                out.append((a, b, _W[(a * 13 + b) % _MODULUS]))
    return out


# --------------------------------------------------------------------------
# Family 2: date schemes
# --------------------------------------------------------------------------

#: Dates the artwork actually points at, with provenance. Chronological, so
#: that "the n-th of these" is well defined. Nothing speculative: each is
#: either on-chain, or printed/quoted in the image.
ARTWORK_DATES: list[tuple[date, str]] = [
    (date(1776, 7, 4), "Declaration; MDCCLXXVI on the Great Seal, which the "
                       "artist replaced with FIAT JUSTITIA ET PEREAT MUNDUS"),
    (date(1865, 1, 31), "13th Amendment passed the House"),
    (date(1865, 12, 6), "13th Amendment ratified; its Section 1 is on the plinth"),
    (date(2008, 10, 31), "Bitcoin whitepaper published; its prose is rendered twice"),
    (date(2009, 1, 3), "genesis block"),
    (date(2020, 3, 13), "Breonna Taylor killed"),
    (date(2020, 5, 10), "the puzzle address was funded (on-chain)"),
    (date(2020, 5, 25), "George Floyd killed - after the address was funded"),
]

#: Ways of turning a date into a candidate index, fixed before running. Both
#: monotone maps (year, day-of-year) and wrapping ones (mod 2048, MMDD) are
#: included: the anchor indices are not monotone in n, so a family containing
#: only monotone maps would be refuted trivially and prove nothing.
DATE_TO_INDEX = (
    "year", "MMDD", "DDMM", "YYYYMMDD%2048", "y+m+d", "doy",
    "doy*7%2048", "days_since_epoch%2048", "yy*100+doy",
)


def date_index(y: int, m: int, d: int, how: str) -> int | None:
    """Map a calendar date to a candidate wordlist index, or None if invalid."""
    try:
        dt = date(y, m, d)
    except ValueError:
        return None
    doy = dt.timetuple().tm_yday
    return {
        "year": y,
        "MMDD": m * 100 + d,
        "DDMM": d * 100 + m,
        "YYYYMMDD%2048": (y * 10000 + m * 100 + d) % _MODULUS,
        "y+m+d": y + m + d,
        "doy": doy,
        "doy*7%2048": (doy * 7) % _MODULUS,
        "days_since_epoch%2048": (dt - _EPOCH).days % _MODULUS,
        "yy*100+doy": (y % 100) * 100 + doy,
    }[how]


def date_sweep(years: range = range(1700, 2101)) -> Sweep:
    """Number-as-date-component schemes, swept against the three anchors.

    Two shapes, each covering a natural reading:

    * **the number is the day of the month** - 1, 3, 13 and 21 as four dates in
      one fixed month, the reading behind "1/3 is the genesis block";
    * **the number is an offset in years** from some base year.

    The year range is deliberately far wider than the artwork's own dates, so
    that a negative result is not an artefact of a stingy search.
    """
    tested, hits = 0, []
    months, days = range(1, 13), range(1, 29)

    for y, m, base, how in product(years, months, (0, 1), DATE_TO_INDEX):
        tested += 1
        ok = True
        for n, target in ANCHOR_INDICES.items():
            idx = date_index(y, m, n, how)
            if idx is None or idx - base != target:
                ok = False
                break
        if ok:
            hits.append(("day=n", y, m, how, base))

    for by, m, d, base, how in product(
            years, months, days, (0, 1),
            ("year", "YYYYMMDD%2048", "y+m+d", "days_since_epoch%2048")):
        tested += 1
        ok = True
        for n, target in ANCHOR_INDICES.items():
            idx = date_index(by + n, m, d, how)
            if idx is None or idx - base != target:
                ok = False
                break
        if ok:
            hits.append(("year=base+n", by, m, d, how, base))

    return Sweep("date", tested, hits,
                 f"years {years.start}-{years.stop - 1}; "
                 f"{len(DATE_TO_INDEX)} date-to-index maps")


def artwork_date_index_scheme() -> str:
    """Why "the n-th artwork date" cannot be the scheme.

    Only eight dates in the artwork are datable at all, so 13 and 21 have
    nothing to select. This one is refuted by construction - no sweep needed.
    """
    return (f"{len(ARTWORK_DATES)} datable references in the artwork; "
            f"n=13 and n=21 are out of range - refuted by construction")


def combined_date_sweep() -> Sweep:
    """All four numbers as the components of a *single* date.

    A single date resolves to a single word, so it cannot name four positions.
    The one thing it could still do is name a word already known to be in the
    phrase, so that is the test: does any calendar-valid arrangement of
    1, 3, 13, 21 land on one of the five marked words?
    """
    tested, hits = 0, []
    marked = set(MARKED_INDICES)
    for p in permutations(NUMBERS):
        a, b, c, d = p
        for yr in (c * 100 + d, d * 100 + c, c, d):
            for day, mon in ((a, b), (b, a)):
                for how in ("year", "MMDD", "DDMM", "YYYYMMDD%2048", "doy",
                            "days_since_epoch%2048"):
                    idx = date_index(yr, mon, day, how)
                    if idx is None:
                        continue
                    for base in (0, 1):
                        got = word_at(idx, base)
                        if got is None:
                            continue
                        tested += 1
                        if got in marked:
                            hits.append((yr, mon, day, how, base, got))
    return Sweep("combined-date", tested, hits,
                 "one date names one word; tested against the marked words")


# --------------------------------------------------------------------------
# Family 3: numbered-source references
# --------------------------------------------------------------------------

#: Vocabulary checks against numbered sources, fetched from primary sources on
#: 2026-08-26. A source-reference scheme has to select its word *from the
#: referenced text*, so if a word does not occur there, no selection rule can
#: produce it. That reduces the whole family to a vocabulary question, and the
#: vocabulary settles it.
SOURCE_VOCABULARY = {
    "us_amendments": {
        "source": "all 27 Amendments, archives.gov/founding-docs "
                  "(bill-of-rights-transcript and amendments-11-27)",
        "parsed": 27,
        "distinct_words": 822,
        "contains": {"subject": True, "tower": False, "moon": False,
                     "food": False, "real": False},
        "subject_appears_in": (5, 13, 14, 21),
        "sanity_checks": "slavery (13th), quartered (3rd), liquors (18th/21st) "
                         "all present, so the parse covers the real text",
    },
    "bips": {
        "source": "raw.githubusercontent.com/bitcoin/bips",
        "bip_1": {"distinct_words": 744, "subject": True, "tower": False,
                  "moon": False, "food": False, "real": True},
        "bip_3": "404 - never published, so f(3) has no text to select from",
        "bip_13": {"distinct_words": 256, "subject": False, "tower": False,
                   "moon": False, "food": False, "real": False},
        "bip_21": {"distinct_words": 406, "subject": False, "tower": False,
                   "moon": False, "food": False, "real": False},
        "provenance_note": "included only to foreclose the objection; the "
                           "artwork references the whitepaper, not the BIPs, "
                           "so this is an arbitrary source by the standard "
                           "extraction.SOURCE_TEXTS already applies",
    },
    "whitepaper_sections": {
        "source": "bitcoin.org/bitcoin.pdf",
        "sections": 12,
        "note": "n=13 and n=21 exceed the section count - refuted by "
                "construction, as for the Great Seal's three inscriptions",
    },
}


def source_reference_verdict() -> dict[str, str]:
    """Why every numbered-source reading fails, one line each."""
    amd = SOURCE_VOCABULARY["us_amendments"]
    return {
        "us_amendments":
            "'tower' and 'moon' occur in no Amendment, so f(3) and f(13) are "
            "unreachable under any selection rule. 'subject' does occur - but "
            f"in Amendments {amd['subject_appears_in']}, never the 1st, so "
            "f(1)=subject fails too.",
        "whitepaper_sections":
            "12 sections; 13 and 21 are out of range.",
        "bips":
            "BIP-3 was never published, so f(3) has no text. BIP-13 and BIP-21 "
            "contain none of the anchor words.",
        "great_seal":
            "three inscriptions; 13 and 21 are out of range.",
    }


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

def run_all() -> dict[str, Sweep]:
    """Every sweep in this module, for the CLI and the tests."""
    return {
        "affine": affine_sweep(),
        "date": date_sweep(),
        "combined_date": combined_date_sweep(),
    }


#: What these sweeps establish. Recorded so the readings are not retried.
REFUTED = {
    "affine_index_schemes": {
        "tested": "2,048 - complete over f(n) = WORDS[(a*n + b) mod 2048]",
        "fits": 0,
        "why_it_matters": "subsumes every linear number-to-index reading, "
                          "including any date scheme whose date-to-index step "
                          "is linear",
        "near_miss": "exactly two schemes fit anchors 1 and 3; both send 13 to "
                     "'coin', which is thematically perfect and contradicted "
                     "by the artwork's 'moon'",
        "verdict": "refuted",
    },
    "date_reference": {
        "tested": "1,164,504 schemes - number-as-day-of-month and "
                  "number-as-year-offset, over years 1700-2100 and nine "
                  "date-to-index maps, 0- and 1-based",
        "fits": 0,
        "chance_expectation": 0.28,
        "also": "'the n-th datable reference in the artwork' is refuted by "
                "construction: there are eight, and 13 and 21 overrun them",
        "combined_date": "1,056 calendar-valid readings of 1/3/13/21 as a "
                         "single date; none names any of the five marked words",
        "verdict": "refuted",
    },
    "numbered_source_reference": {
        "tested": "US Amendments (all 27, primary source), whitepaper "
                  "sections, BIP-1/3/13/21, Great Seal inscriptions",
        "decisive": "a source-reference scheme must select its word from the "
                    "referenced text. 'tower' and 'moon' appear in no "
                    "Amendment and in no BIP checked, and 'subject' appears in "
                    "Amendments 5, 13, 14 and 21 but never the 1st. The "
                    "whitepaper has 12 sections and the Seal three, so 13 and "
                    "21 are out of range there.",
        "verdict": "refuted",
    },
    "method_note": {
        "point": "a forward sweep of 'what word does 13 give?' cannot "
                 "discriminate, because indexing the wordlist returns a BIP-39 "
                 "word for every input. The all-BIP-39 bar that refuted text "
                 "indexing is vacuous here; the anchor test replaces it.",
        "second_point": "a fit discovered by sweeping millions of schemes is "
                        "at the chance floor (1/2048 squared per scheme) and "
                        "would not be evidence. Only zero is informative, and "
                        "only because the schemes were pre-registered.",
    },
}
