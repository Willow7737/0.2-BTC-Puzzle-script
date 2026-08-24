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

import math

from .wordlist import is_valid

#: Centre of the clock dial in the 1600x1200 artwork, and its radius.
CLOCK_CENTRE = (473.0, 940.0)
CLOCK_RADIUS = 185.0

#: Bearings of the drawn numerals, measured from the artwork. Eight are
#: measured directly; 4-7 lie behind the Great Seal and are interpolated at
#: 30 degree steps from 12.
#:
#: The measured steps run 28.0 to 32.0 degrees - hand-drawn scatter of about
#: +/-2 degrees. **That scatter is the noise floor for every prediction made
#: here**, so a 1-2 degree match is a hit and anything past ~4 is not. It also
#: means midpoints between two *measured* numerals (moon, tower, the hour
#: hand) are firmer than ones involving an interpolated numeral (the eye).
NUMERAL_BEARING: dict[int, float] = {
    12: 287.4, 1: 317.4, 2: 347.5, 3: 17.9,
    8: 166.1, 9: 197.7, 10: 225.7, 11: 257.7,
}
for _n in (4, 5, 6, 7):
    NUMERAL_BEARING[_n] = (287.4 + 30.0 * _n) % 360


def midpoint_bearings() -> dict[int, list[tuple[int, int, float]]]:
    """Map each attainable position to the midpoint rays that produce it.

    A clue's number is the sum of the two numerals its bearing falls between.
    Because consecutive numerals always sum to ``2n+1``, **every position this
    mechanism can produce is odd** - 3, 5, 7 ... 23. Even positions must come
    from some other mechanism, which is a hard structural constraint on any
    proposed position table.
    """
    out: dict[int, list[tuple[int, int, float]]] = {}
    for n in range(1, 13):
        m = n + 1 if n < 12 else 1
        a, b = NUMERAL_BEARING[n], NUMERAL_BEARING[m]
        bearing = (a + ((b - a) % 360) / 2) % 360
        out.setdefault(n + m, []).append((n, m, bearing))
    return out


def bearing_of(x: float, y: float) -> float:
    """Compass bearing of an image point from the clock centre (0 = up)."""
    cx, cy = CLOCK_CENTRE
    return math.degrees(math.atan2(x - cx, -(y - cy))) % 360


def chance_probability(error_deg: float, n_rays: int = 12) -> float:
    """Probability a *random* bearing lands this close to some midpoint ray.

    This is the sanity check that keeps ray-matching honest. Twelve rays 30
    degrees apart means a random feature is within 1.3 degrees of one about
    **9%** of the time - so a single tight alignment is suggestive, not proof.
    Only a joint alignment of several independent features, or a feature the
    mechanism is intrinsically *about* (a clock's own hands), carries weight.
    """
    spacing = 360.0 / n_rays
    return min(1.0, 2.0 * error_deg / spacing)


def position_at(x: float, y: float, tolerance: float = 3.0):
    """Which position, if any, an image feature at (x, y) encodes.

    Returns ``(position, n, m, bearing, error_degrees)`` for the nearest
    midpoint ray within *tolerance*, else ``None``. This is the falsifiable
    test that confirmed the three clock hands and the Great Seal's eye: state
    where a feature should sit, then measure whether it does.
    """
    b = bearing_of(x, y)
    best = None
    for pos, rays in midpoint_bearings().items():
        for n, m, rb in rays:
            err = min(abs(b - rb), 360 - abs(b - rb))
            if best is None or err < best[4]:
                best = (pos, n, m, rb, err)
    return best if best and best[4] <= tolerance else None


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

#: Downgraded after a chance calculation. The eye really does sit 1.3 degrees
#: off the midpoint(4,5) ray - but with 12 rays 30 degrees apart, a random
#: feature lands that close about 9% of the time (Monte-Carlo: 8.6%). One
#: tight alignment is not proof. It stays STRONG because the community
#: proposed eye = 4+5 = 9 independently of this measurement, so the
#: measurement is a successful *prediction* rather than a fitted result.
EYE = _a(9, "eye", Evidence.STRONG,
         "Great Seal's eye at midpoint(4,5): predicted 62.4, measured 61.1 "
         "(off 1.3 deg, ~9% by chance). Independently proposed as 4+5 before "
         "being measured, which is what lifts it above coincidence")
PROPOSED_STRONG = [EYE]

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
    _a(11, "pyramid", Evidence.WEAK,
       "the midpoint(5,6) ray at 92.4 deg passes through the pyramid's brick "
       "body, but its centroid bearing is 101.1 - off 8.7 deg, too loose to "
       "confirm the way the eye was"),
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


def build(length: int = 24, include_proposed: bool = False,
          include_strong: bool = False) -> PositionMap:
    """Assemble a map: confirmed always, then optionally strong, then weak."""
    pm = PositionMap(length=length)
    for a in CONFIRMED:
        pm.place(a)
    if include_strong or include_proposed:
        for a in PROPOSED_STRONG:
            if a.position <= length:
                pm.place(a)
    if include_proposed:
        for a in PROPOSED:
            if a.position <= length:
                pm.place(a)
    return pm


#: The three axes that carry no drawn hand. Each ray was traced across the
#: artwork and none lands on a crisp, isolated feature the way the eye does -
#: they pass through large text blocks and several objects at once. So the
#: "object sits on a ray" mechanism does **not** obviously extend beyond the
#: clock's own hands, and positions 5, 7, 11, 15, 17, 19 and 23 remain open.
UNCLAIMED_AXES: dict[tuple[int, int], tuple[float, float, str]] = {
    (5, 17):  (2.7, 181.9, "up through the SEED PHRASE display text; "
                           "down into the bottom whitepaper strip"),
    (7, 19):  (32.6, 211.7, "up-right through NEW WORLD toward Floyd; "
                            "down-left across the dial past numeral 10"),
    (11, 23): (92.4, 272.5, "right through the pyramid, Trump/Biden and the "
                            "plinth; left through the Statue's robe"),
}
