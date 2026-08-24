"""Position-map construction: each clue supplies a word *and* its index.

The artwork does not hand over an unordered bag of words to permute. Each
clue pairs a word with a number, and the number is that word's position in the
mnemonic. Two mechanisms are confirmed directly from the image:

**The plinth.** ``Section 1`` and ``subject`` carry identical underlines, in
the same hand and weight, giving ``subject -> 1``.

**The clock.** All three hands point *midway between two numerals* rather than
at one, and the two numerals sum to the position. Verified against bearings
measured from the artwork (numerals sit at 30.0 degree steps with 12 at
287.4 degrees):

===========  ==============  ===========  =========  =========
Hand         Label           Midpoint     Predicted  Measured
===========  ==============  ===========  =========  =========
seconds      ``moon``        12 + 1 = 13  302.4 deg  302-304 deg
minutes      ``tower``       1 + 2 = 3    332.4 deg  on-hand
hours        (unlabelled)    10 + 11 = 21 241.7 deg  on-hand
===========  ==============  ===========  =========  =========

The red seconds hand is measurable in isolation because it is the only red
line on the dial; its dominant bearing lands within 1 degree of prediction.
The two grey hands cannot be separated from grey artwork by ridge detection,
but the predicted bearings lie along them visibly.

**Consequence: position 21 exists, so the phrase is not 12 words.** BIP-39
allows 12/15/18/21/24, so it is 21 or 24 - which is why every 12-word search
ever run against this puzzle was structurally unable to succeed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from .wordlist import is_valid


class Evidence(IntEnum):
    """How well supported an assignment is. Only CONFIRMED is safe to pin.

    The test that actually separates signal from noise here is **deviation
    from the default**. A number is evidence only if the artist had to make a
    deliberate, non-obvious choice to produce it:

    * clock hands at *midpoints* - a deviation; hands normally point at a
      numeral, so putting all three between numerals is a decision
    * underlines on the plinth - a deviation; the mark is added on top of text
      that did not need it
    * the Statue's crown having 7 rays - **not** a deviation; the real Statue
      has 7 rays, so an accurate drawing yields 7 whether or not 7 means
      anything
    * 2 cameras, 4 masked figures - **not** deviations; those are ordinary
      compositional counts

    Counting objects in an illustration will always produce numbers. Only the
    deliberate ones carry information, which is why the crown, camera and
    mask clues stay WEAK however cleanly they can be counted.
    """

    CONFIRMED = 3   # mechanism is a verified deviation from the default
    STRONG = 2      # deviation is plausible but the mechanism is unverified
    WEAK = 1        # number is an incidental count, not a deliberate choice
    SPECULATIVE = 0 # proposed elsewhere, no stated basis


@dataclass
class Assignment:
    """One word placed at one position, with its provenance."""

    position: int
    words: frozenset[str]
    evidence: Evidence
    basis: str

    def __post_init__(self):
        bad = sorted(w for w in self.words if not is_valid(w))
        if bad:
            raise ValueError(f"position {self.position}: not BIP-39 words: {bad}")


def _a(pos, words, ev, basis) -> Assignment:
    return Assignment(pos, frozenset(words.split()), ev, basis)


#: Verified in this repository against the artwork.
CONFIRMED: list[Assignment] = [
    _a(1,  "subject", Evidence.CONFIRMED,
       "underlined beside an underlined 'Section 1' on the monument plinth"),
    _a(3,  "tower",   Evidence.CONFIRMED,
       "clock minute hand at midpoint(1,2); predicted bearing 332.4 deg"),
    _a(13, "moon",    Evidence.CONFIRMED,
       "clock seconds hand at midpoint(12,1); predicted 302.4, measured 302-304"),
]

#: The unlabelled hour hand gives a number with no word attached to it.
ORPHAN_NUMBERS: dict[int, str] = {
    21: "clock hour hand at midpoint(10,11); word not identified",
}

#: Proposed by the community analysis (HomelessPhD/BLM_0.2BTC). Recorded so
#: they can be tested, NOT promoted: each needs its number clue verified
#: against the image the way the clock and plinth were.
PROPOSED: list[Assignment] = [
    _a(2,  "camera",  Evidence.WEAK,
       "two cameras drawn - counted and correct, but an incidental count"),
    _a(4,  "mask",    Evidence.WEAK,
       "four masked figures, each in a face-detection box - counted and "
       "correct; the boxes are deliberate but the count of people is not"),
    _a(5,  "police",  Evidence.WEAK, "five-line police text"),
    _a(7,  "liberty", Evidence.WEAK,
       "crown has 7 rays - counted and correct, but the real Statue has 7, "
       "so the number is incidental rather than chosen"),
    _a(9,  "eye",     Evidence.WEAK, "4 + 5 pyramid/eye clue"),
    _a(10, "black day", Evidence.WEAK, "rune 4 'black day number X'; word unresolved"),
    _a(11, "pyramid", Evidence.WEAK, "5 + 6 in/behind the pyramid"),
    _a(12, "vote",    Evidence.WEAK, "mirrored '.vs.' read as 12"),
    _a(16, "rifle",   Evidence.WEAK, "M16 clue"),
    _a(17, "gold",    Evidence.WEAK, "chart spans 17 years"),
    _a(19, "glove",   Evidence.SPECULATIVE, "CVD19 / five fingers; mapping interpretive"),
    _a(20, "apple",   Evidence.SPECULATIVE, "proposed without stated basis"),
]

#: Valid BIP-39 mnemonic lengths that can host a position 21.
VIABLE_LENGTHS = (21, 24)


@dataclass
class PositionMap:
    """Candidate words per position, plus the positions still unknown."""

    length: int = 24
    slots: dict[int, frozenset[str]] = field(default_factory=dict)

    def place(self, a: Assignment) -> "PositionMap":
        if not 1 <= a.position <= self.length:
            raise ValueError(f"position {a.position} outside 1..{self.length}")
        self.slots[a.position] = a.words
        return self

    def unresolved(self) -> list[int]:
        return [i for i in range(1, self.length + 1) if i not in self.slots]

    def combinations(self, vocabulary: int = 2048) -> int:
        """How many phrases this map still admits.

        Multiplies the alternatives at resolved positions by the full
        vocabulary at every unresolved one - the number that decides whether a
        search is worth starting.
        """
        total = 1
        for i in range(1, self.length + 1):
            total *= len(self.slots[i]) if i in self.slots else vocabulary
        return total

    #: Enumeration, not PBKDF2, is the wall. At ~2M orderings/sec/core for the
    #: checksum filter on four cores, three unresolved positions (2048**3) take
    #: about an hour to enumerate and five to derive; four (2048**4) take three
    #: months. So three is the practical ceiling.
    MAX_SEARCHABLE_UNRESOLVED = 3

    def searchable(self) -> bool:
        """Can this map be brute-forced in a sane amount of time?"""
        return len(self.unresolved()) <= self.MAX_SEARCHABLE_UNRESOLVED

    def verdict(self) -> str:
        n = len(self.unresolved())
        if self.searchable():
            return f"searchable: {n} unresolved position(s)"
        need = n - self.MAX_SEARCHABLE_UNRESOLVED
        return (f"NOT searchable: {n} unresolved, {self.combinations():.3g} phrases. "
                f"Resolve {need} more position(s) first - no amount of CPU "
                f"substitutes for one more decoded clue.")

    def summary(self) -> str:
        lines = [f"position map, length {self.length}"]
        for i in range(1, self.length + 1):
            words = self.slots.get(i)
            lines.append(f"  {i:>2}  " + (" | ".join(sorted(words)) if words else "?"))
        n = len(self.unresolved())
        lines.append(f"\n  {self.length - n} resolved, {n} unresolved")
        return "\n".join(lines)


def build(length: int = 24, include_proposed: bool = False) -> PositionMap:
    """Assemble a map from the confirmed assignments, optionally the weak ones."""
    pm = PositionMap(length=length)
    for a in CONFIRMED:
        pm.place(a)
    if include_proposed:
        for a in PROPOSED:
            if a.position <= length:
                pm.place(a)
    return pm
