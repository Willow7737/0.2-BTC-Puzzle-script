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
allows 12/15/18/21/24, so it is 21 or 24 - and HOUR_HAND_IS_THE_LENGTH
argues 21. Either way this is why every 12-word search
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


def numeral_rays() -> dict[int, list[tuple[int, int, float]]]:
    """Even positions: a feature sitting **on** a numeral, not between two.

    Rune 2 says "sum of two numbers". Two *adjacent* numerals sum to ``2n+1``,
    always odd - which is why the midpoint mechanism alone can never reach an
    even position. Numerals **two apart** sum to ``2n``, always even, and
    their geometric midpoint is exactly *on* the numeral between them.

    So it is one rule with two alignments:

    * between two numerals -> odd position
    * on a numeral, summing its neighbours -> even position

    Together the 12 midpoints and 12 numerals give 24 rays covering positions
    **3 to 23 with no gaps**. Position 1 comes from the plinth; 2 and 24 are
    not reachable from the clock at all and need separate clues.
    """
    out: dict[int, list[tuple[int, int, float]]] = {}
    for n in range(1, 13):
        lo = 12 if n == 1 else n - 1
        hi = 1 if n == 12 else n + 1
        out.setdefault(lo + hi, []).append((lo, hi, NUMERAL_BEARING[n]))
    return out


def all_rays() -> dict[int, list[tuple[int, int, float]]]:
    """Every clock ray, odd and even, keyed by the position it encodes."""
    out = {k: list(v) for k, v in midpoint_bearings().items()}
    for pos, rays in numeral_rays().items():
        out.setdefault(pos, []).extend(rays)
    return out


#: Positions the clock cannot produce under either alignment. 1 is supplied by
#: the plinth; 2 and 24 have no known clue and are the gap in the model.
CLOCK_CANNOT_REACH = (1, 2, 24)

#: The three axes whose two ends give the *same* position. Every other axis is
#: ambiguous between two, resolved only by which end carries the word. That
#: these three land on 12, 13, 14 - consecutive, and the exact middle of a
#: 24-position phrase - is the structure's most distinctive signature, and the
#: moon hand sits on the middle one.
SELF_MATCHING_AXES = {12: ("on numeral 6", "on numeral 12"),
                      13: ("midpoint(6,7)", "midpoint(12,1)"),
                      14: ("on numeral 7", "on numeral 1")}


def bearing_of(x: float, y: float) -> float:
    """Compass bearing of an image point from the clock centre (0 = up)."""
    cx, cy = CLOCK_CENTRE
    return math.degrees(math.atan2(x - cx, -(y - cy))) % 360


def chance_probability(error_deg: float, n_rays: int = 24) -> float:
    """Probability a *random* bearing lands this close to some midpoint ray.

    This is the sanity check that keeps ray-matching honest, and admitting the
    even mechanism makes it *stricter*, not looser: 24 rays 15 degrees apart
    means a random feature is within 1.3 degrees of one about **17%** of the
    time, against 9% when only the 12 midpoints were in play.

    So the more complete the mechanism becomes, the weaker any single object
    match is. Only a joint alignment of several independent features, or a
    feature the mechanism is intrinsically *about* (a clock's own hands),
    carries real weight.
    """
    spacing = 360.0 / n_rays
    return min(1.0, 2.0 * error_deg / spacing)


def position_at(x: float, y: float, tolerance: float = 3.0, include_even: bool = True):
    """Which position, if any, an image feature at (x, y) encodes.

    Returns ``(position, n, m, bearing, error_degrees)`` for the nearest
    midpoint ray within *tolerance*, else ``None``. This is the falsifiable
    test that confirmed the three clock hands and the Great Seal's eye: state
    where a feature should sit, then measure whether it does.
    """
    b = bearing_of(x, y)
    best = None
    table = all_rays() if include_even else midpoint_bearings()
    for pos, rays in table.items():
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

#: Downgraded twice, and now WEAK. The eye does sit 1.4 degrees off the
#: midpoint(4,5) ray, but a survey of 32 catalogued objects (see
#: RAY_MATCHING_REFUTED) found the Space Needle at **0.5 degrees** on the same
#: ray, plus the toppled bust and the map of China within 2.2. Four objects on
#: one ray cannot name one word, and by proximity the eye is not even the best
#: candidate. It is kept only as a record of a tested and failed promotion.
EYE = _a(9, "eye", Evidence.WEAK,
         "midpoint(4,5) at 1.4 deg - but the Space Needle is at 0.5 deg on the "
         "same ray and two more objects within 2.2, so the ray names no word")
PROPOSED_STRONG: list[Assignment] = []

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
    provenance: dict[int, Assignment] = field(default_factory=dict)

    def place(self, a: Assignment) -> "PositionMap":
        if not 1 <= a.position <= self.length:
            raise ValueError(f"position {a.position} outside 1..{self.length}")
        self.slots[a.position] = a.words
        self.provenance[a.position] = a
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

    def to_dict(self) -> dict:
        """Serialise with per-position confidence and provenance.

        Unresolved positions are emitted with an empty candidate list and
        ``"unresolved"``, so a consumer can tell "no word yet" apart from
        "any word" and refuse to enumerate the difference.
        """
        out = {"phrase_length": self.length, "positions": {}}
        for i in range(1, self.length + 1):
            a = self.provenance.get(i)
            out["positions"][str(i)] = {
                "candidates": sorted(self.slots.get(i, ())),
                "confidence": a.evidence.name.lower() if a else "unresolved",
                "basis": a.basis if a else "",
            }
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "PositionMap":
        pm = cls(length=int(data["phrase_length"]))
        for k, v in data.get("positions", {}).items():
            words = v.get("candidates") or []
            if not words:
                continue
            ev = Evidence[v.get("confidence", "weak").upper()]
            pm.place(Assignment(int(k), frozenset(words), ev, v.get("basis", "")))
        return pm

    def enumerable(self) -> tuple[bool, str]:
        """Whether this map may be handed to a search at all.

        Refuses a map with unresolved positions rather than silently filling
        them from the 2048-word list. Enumerating a position the image has not
        supplied tests arbitrary guesses, and a negative from that says
        nothing about the puzzle - it only looks like a result.
        """
        missing = self.unresolved()
        if missing:
            return False, (f"positions {missing} have no image-derived candidates. "
                           "Enumerating them would test guesses, not the puzzle.")
        return True, f"all {self.length} positions have candidates"

    def summary(self) -> str:
        lines = [f"position map, length {self.length}"]
        for i in range(1, self.length + 1):
            words = self.slots.get(i)
            a = self.provenance.get(i)
            conf = f"  [{a.evidence.name.lower()}]" if a else ""
            lines.append(f"  {i:>2}  " + (" | ".join(sorted(words)) if words else "?") + conf)
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
#: A survey of 32 objects catalogued from the artwork *before* being measured,
#: testing whether "an object sits on a ray" can assign words to positions.
#: It cannot, and this records why so the approach is not retried:
#:
#: * the hit rate tracks the null as the tolerance is varied, and the p-value
#:   wanders (0.125, 0.017, 0.061, 0.016, 0.021, 0.195, 0.630 at 1.0 to 5.0
#:   degrees) instead of holding - researcher degrees of freedom, not signal;
#: * the objects are angularly clustered (13 of 32 between 45 and 90 degrees,
#:   none between 135 and 180), because the artwork's content is concentrated;
#: * **5 of the 9 occupied positions carry more than one object**, and
#:   position 9 carries four. A ray that four objects sit on names no word.
#:
#: What survives is narrower and more demanding: a clue needs the word
#: *written on* the object (moon and tower along the hands, food down the
#: Needle's shaft, subject underlined, real inserted into an inscription).
#: The ray then supplies that object's number - but only three hands exist,
#: so the clock yields three positions, not twenty-one.
#: Two words are *marked* the way the confirmed ones are - written on or
#: inserted into an object - but carry no number. Both neighbourhoods were
#: searched for an adjacent numeral, the way "Section 1" sits beside
#: "subject". Neither has one.
#:
#: ``food``  (written down the Space Needle's shaft)
#:   The whole tower was examined. The only linear marking on the shaft is the
#:   elevator track, drawn as a dashed line - a real feature of the building,
#:   so its dash count is rendering texture rather than a chosen number. No
#:   digits anywhere on or beside the Needle.
#:
#: ``real``  (inserted into "ONLY real Bitcoin" on the Statue's base)
#:   The inscription band, every pedestal tier, and the object the Statue
#:   holds were all examined. The real Statue's tablet bears a date,
#:   ``JULY IV MDCCLXXVI``, and here it has been replaced by a phone showing
#:   "BLM" and a raised fist - the one place a number would traditionally sit,
#:   and the artist put a symbol there instead. No digits.
MARKED_WITHOUT_NUMBER = {
    "food": "Space Needle shaft; no adjacent numeral, elevator track is a "
            "real building feature not a count",
    "real": "Statue's inscription; no adjacent numeral, and the tablet that "
            "would carry a date was replaced by a BLM phone",
}

#: The capacity bound this exposes, and the reason the position model cannot
#: currently scale.
#:
#: The bearing mechanism needs the object to *be* a clock hand, and a clock
#: has exactly **three** hands. There is no fourth. So that mechanism can
#: never yield more than three positions, however much of the artwork is
#: searched. The only other confirmed mechanism - a numeral written beside the
#: word and underlined - has exactly **one** instance.
#:
#: Confirmed mechanisms therefore cap out at **four positions**, and a 21- or
#: 24-position construction needs seventeen to twenty more from mechanisms
#: that have not been found. That is a statement about the model, not about
#: how hard anyone has looked.
MECHANISM_CAPACITY = {
    "clock_hands": 3,          # hard limit: a clock has three hands
    "explicit_adjacent_numeral": 1,   # "Section 1" beside "subject"
    "total_reachable": 4,
    "needed_for_24": 24,
    "note": "the shortfall is missing mechanisms, not missing search effort",
}

RAY_MATCHING_REFUTED = {
    "objects_surveyed": 32,
    "hit_rate_at_3deg": 0.594,
    "null_at_3deg": 0.400,
    "p_values_by_tolerance": {1.0: 0.125, 1.5: 0.017, 2.0: 0.061,
                              2.5: 0.016, 3.0: 0.021, 4.0: 0.195, 5.0: 0.630},
    "positions_with_multiple_objects": 5,
    "max_objects_on_one_position": 4,
    "conclusion": "ray proximity does not assign words; only the clock's own "
                  "hands carry both a word and a number",
}

UNCLAIMED_AXES: dict[tuple[int, int], tuple[float, float, str]] = {
    (5, 17):  (2.7, 181.9, "up through the SEED PHRASE display text; "
                           "down into the bottom whitepaper strip"),
    (7, 19):  (32.6, 211.7, "up-right through NEW WORLD toward Floyd; "
                            "down-left across the dial past numeral 10"),
    (11, 23): (92.4, 272.5, "right through the pyramid, Trump/Biden and the "
                            "plinth; left through the Statue's robe"),
}


# ---------------------------------------------------------------------------
# Re-examination for a fourth number-bearing object
# ---------------------------------------------------------------------------

#: The capacity bound above was argued from "a clock has three hands". This
#: measures it instead, so the ceiling rests on the image rather than on a
#: fact about clocks.
#:
#: Method: high-pass the artwork, then sweep a ray out from the hub at
#: ``CLOCK_CENTRE`` for every whole-degree bearing and take the mean ink
#: between radius 40 and 150 (skipping the hub, where every hand overlaps).
#: A hand is a sustained radial ink ridge; engraving and lettering are not.
#:
#: Twelve bearings exceed 1.7x the mean. **Exactly three of them are hands**,
#: and each lands within 1.7 degrees of a numeral midpoint. The other nine sit
#: 3.7 to 13.7 degrees off, and all nine fall inside the arc occupied by the
#: Great Seal coin, which overlaps the dial and hides numerals 4 through 7 -
#: they are its rim, rays and pyramid courses, not hands.
#:
#: So the clock is exhausted: three hands, all three already read, no fourth.
CLOCK_HAND_CENSUS = {
    "method": "radial high-pass ink profile about the hub, 1-degree steps, "
              "radius 40-150 px",
    "peaks_above_1_7x_mean": 12,
    "hands": {
        332.0: "midpoint(1,2)=3, off 0.4 deg - TOWER",
        304.0: "midpoint(12,1)=13, off 1.6 deg - MOON",
        240.0: "midpoint(10,11)=21, off 1.7 deg - unlabelled hour hand",
    },
    "non_hand_peaks": 9,
    "non_hand_offset_range_deg": (3.7, 13.7),
    "non_hand_explanation": "all nine lie in the arc covered by the Great "
                            "Seal coin, which occludes numerals 4-7",
    "verdict": "exactly three hands; the clock cannot yield a fourth number",
}

#: The other confirmed mechanism, checked the same way for a second instance.
#:
#: The 13th Amendment has two sections, so a second underlined numeral/word
#: pair was possible in principle. Reading the plinth through the blue channel
#: (which lifts the ink out from under the translucent red graffiti) shows the
#: rendered text is **Section 1 only**, ending at "their jurisdiction". There
#: is no Section 2 on the stone, so there is no second pairing to find.
PLINTH_SINGLE_SECTION = {
    "method": "blue-channel isolation + autocontrast + unsharp, 7x",
    "sections_rendered": 1,
    "text_ends_at": "their jurisdiction",
    "underlined_numeral": "1 (in the heading 'Section 1')",
    "underlined_word": "subject",
    "verdict": "one pairing only; the plinth cannot yield a second",
}

#: Every numeral visible in the artwork, including three that no previous
#: record in this repository mentions. Catalogued so the census is closed:
#: the question "is there a number somewhere nobody looked at?" now has a
#: written answer rather than an assumption.
#:
#: ``role`` is the honest reading, not a hopeful one. A numeral counts as
#: *puzzle-marked* only if it meets one of the two conventions the artwork
#: actually established - underlined and paired with an underlined word, or
#: carried on an object that points at the dial. None of the new three does.
NUMERAL_CENSUS = {
    "clock_dial": {
        "where": "numerals 12,1,2,3 and 8,9,10,11; 4-7 occluded by the Seal",
        "role": "puzzle-marked - the scale the hands are read against",
    },
    "section_1": {
        "where": "plinth heading, underlined, beside underlined 'subject'",
        "role": "puzzle-marked - the one explicit numeral/word pairing",
    },
    "hoodie_date": {
        "where": "05.25.20 on George Floyd's hoodie, directly above "
                 "'I can't BREATHE'",
        "new": True,
        "role": "editorial - the date of the death depicted. Not underlined; "
                "'BREATHE' is not a BIP-39 word",
    },
    "election_date": {
        "where": "11.03.20 beneath the red 'VS' between Trump and Biden",
        "new": True,
        "role": "editorial - the 2020 election date, drawn before the result "
                "was known. No adjacent word",
    },
    "emancipation_range": {
        "where": "1865 - 202...? beside the Statue, ellipsis and ? in red",
        "new": True,
        "role": "editorial - emancipation to an unfinished present. The red ? "
                "is the artwork's own device for an open question",
    },
    "price_axis": {
        "where": "1800/1600/1400/1200/... on the chart behind the figures",
        "role": "depicted content - a price axis under a BTC curve",
    },
    "covid_slogan": {
        "where": "'COVID 19 IS A HOAX / 5G IS THE KILLER', and a vial "
                 "labelled COVID19",
        "role": "depicted content - graffiti slogans",
    },
    "target_address": {
        "where": "vertical text, left edge",
        "role": "the puzzle's target, not a clue",
    },
}

#: Why the three newly catalogued dates are not a fourth mechanism.
#:
#: They fail both established conventions - none is underlined, none rides a
#: pointer - but that alone is soft. The hard check is range. A 24-word
#: phrase has positions 1..24, and read as positions the dates overflow it:
#: ``05.25.20`` yields 25, and ``1865 - 202...?`` yields 1865 and 2020. Only
#: ``11.03.20`` stays in range, and one date in range out of three is what
#: chance looks like.
#:
#: They also have a complete non-puzzle explanation, which is the part that
#: matters: each captions a real event the artwork depicts. The red ``?``
#: appears on exactly the two open questions - when does the struggle end,
#: and who wins - matching the artwork's own caption, "THIS IS THE FIRST
#: PREDICTION". Nothing is left over for a puzzle role to explain.
DATES_NOT_A_MECHANISM = {
    "candidates": ("05.25.20", "11.03.20", "1865 - 202...?"),
    "underlined": 0,
    "on_a_pointer": 0,
    "out_of_range_for_24": ("05.25.20 -> 25", "1865 - 202...? -> 1865, 2020"),
    "in_range": ("11.03.20 -> 11, 3, 20",),
    "alternative_explanation": "each dates an event the artwork depicts; the "
                               "red ? marks predictions, per the artwork's "
                               "own 'THIS IS THE FIRST PREDICTION'",
    "verdict": "catalogued, not promoted - no fourth mechanism here",
}


def scan_hands(image_path: str, r0: int = 40, r1: int = 150,
               threshold: float = 1.7) -> dict:
    """Re-derive ``CLOCK_HAND_CENSUS`` from the artwork.

    Sweeps a ray from the hub at every whole-degree bearing and measures mean
    high-pass ink between *r0* and *r1*. Returns the peaks and, for each, the
    nearest numeral midpoint and how far off it is. Kept here rather than in
    ``forensics`` because it reads ``CLOCK_CENTRE`` and the numeral bearings
    that the rest of this module is built on.
    """
    import math
    from PIL import Image, ImageChops, ImageFilter, ImageOps

    im = Image.open(image_path).convert("RGB")
    grey = ImageOps.grayscale(im)
    hp = ImageChops.subtract(grey.filter(ImageFilter.GaussianBlur(10)), grey)
    px, cx, cy = hp.load(), CLOCK_CENTRE[0], CLOCK_CENTRE[1]

    def ink(bearing: float) -> float:
        th = math.radians(bearing)
        dx, dy = math.sin(th), -math.cos(th)
        vals = [px[int(cx + dx * r), int(cy + dy * r)]
                for r in range(r0, r1)
                if 0 <= cx + dx * r < im.width and 0 <= cy + dy * r < im.height]
        return sum(vals) / len(vals) if vals else 0.0

    profile = [(b, ink(b)) for b in range(360)]
    mean = sum(v for _, v in profile) / len(profile)

    peaks = []
    for i, (b, v) in enumerate(profile):
        window = [profile[(i + d) % 360][1] for d in range(-6, 7)]
        if v == max(window) and v > mean * threshold:
            if peaks and b - peaks[-1][0] <= 8:
                if v > peaks[-1][1]:
                    peaks[-1] = (b, v)
            else:
                peaks.append((b, v))

    out = []
    for b, v in peaks:
        best = min(
            ((a, a % 12 + 1) for a in range(1, 13)),
            key=lambda ac: abs((b - _midpoint_bearing(*ac) + 180) % 360 - 180))
        off = abs((b - _midpoint_bearing(*best) + 180) % 360 - 180)
        out.append({"bearing": float(b), "ink": v, "pair": best,
                    "position": best[0] + best[1], "off_deg": off})
    return {"mean_ink": mean, "peaks": out,
            "hands": [p for p in out if p["off_deg"] <= 2.0]}


def _midpoint_bearing(a: int, c: int) -> float:
    """Bearing of the midpoint between two adjacent numerals."""
    delta = (NUMERAL_BEARING[c] - NUMERAL_BEARING[a] + 540) % 360 - 180
    return (NUMERAL_BEARING[a] + delta / 2) % 360


# ---------------------------------------------------------------------------
# Systematic sweep for further marked words
# ---------------------------------------------------------------------------

#: The real bottleneck was never the numbers - it is the **word set**. Five
#: marked words cannot seed any search, and the five were found ad hoc by the
#: community rather than by a sweep. So the artwork was swept properly.
#:
#: **The automated attempt failed, and that is recorded because it is useful.**
#: A glyph-and-line detector was calibrated on the five known words, then run
#: over the whole image, then re-run at every 10 degrees of rotation to catch
#: text following an object's axis. It recovered **1 of 5** positive controls.
#: The diagnosis is instructive: MOON and TOWER ride diagonal clock hands and
#: FOOD runs down the needle shaft, so a horizontal-line detector cannot see
#: them by construction - and even rotated, the letters are 3-6 px tall in
#: line art, smaller and fainter than the objects' own edges. A detector that
#: cannot recover its own controls proves nothing about what it fails to find,
#: so its negatives were discarded rather than reported.
DETECTOR_FAILED = {
    "approach": "connected-component glyph detection, line grouping, swept "
                "over 18 rotations x 12 channel/radius/threshold variants",
    "positive_controls_recovered": 1,
    "positive_controls_total": 5,
    "why": "marked words follow the object's axis, and the letters are 3-6 px "
           "tall - smaller and fainter than the line art around them",
    "verdict": "discarded - a detector that misses its own controls cannot "
               "support a negative",
}

#: What was done instead: a **visual sweep of every object surface that could
#: carry a word**, at the enhancement that renders the known ones legibly.
#: The pipeline was validated on the way past - it reads ``ONLY real BITCOIN``
#: off the Statue's base clearly.
#:
#: Nineteen surfaces examined, none carrying a word that was not already
#: catalogued:
SURFACE_SWEEP = {
    "surfaces_examined": (
        "Statue torch and flame", "Statue crown and head",
        "BLM phone screen", "Statue books and base",
        "flag", "STOP fist sign", "vaccine vial", "gloved hand",
        "camera 1", "camera 2", "camera junction box",
        "toppled bust head", "wreath on the bust's plinth",
        "Great Seal pyramid", "Great Seal eye and rays",
        "clock hub", "Trump face and suit", "Trump lapel",
        "Biden face and suit", "Biden lapel", "map of China",
    ),
    "new_words_found": 0,
    "incidental_text_confirmed": (
        "BLM and a fist icon on the phone screen",
        "COVID19 on the vaccine vial",
        "a plain dark lapel pin on Biden, no device or text",
        "a three-bar emblem inside the wreath on the bust's plinth",
    ),
    "pipeline_validated_by": "the same enhancement reads 'ONLY real BITCOIN' "
                             "off the Statue's base",
    "verdict": "no sixth marked word on any object surface",
}

#: What the sweep changes.
#:
#: Before it, "there might be more marked words nobody has spotted" was a live
#: hope, and it was the only thing that could have made a search tractable:
#: five words seed nothing. After it, that hope is closed by method rather
#: than by assumption - the marking conventions the artwork actually uses
#: (a word written along an object's axis; a word underlined or inserted in
#: running text) have been swept across every surface that carries either.
#:
#: This does not make the puzzle harder. It makes the existing verdict firmer:
#: **underdetermined** is now supported from the word side as well as the
#: number side. The shortfall is 19 or 22 words and 20 positions, and neither
#: gap has a mechanism behind it.
WORD_SUPPLY = {
    "marked_words": 5,
    "words_needed_min": 12,
    "words_needed_max": 24,
    "surfaces_swept": 21,
    "new_words": 0,
    "consequence": "the word set cannot be completed from the artwork by any "
                   "convention it demonstrably uses; search remains unseedable",
}


#: **The clock does not show a time.** The three hands are pointers.
#:
#: This is worth establishing because "the clock encodes a timestamp" is the
#: obvious rival to the position-map reading, and it is cheap to kill.
#:
#: Converting each hand's bearing to a dial position (12 sits at 287.4 deg,
#: 30 deg per numeral):
#:
#: =========  =========  ==================
#: bearing    dial       reads as
#: =========  =========  ==================
#: 240.0 deg  10.420     hour ~10:25
#: 304.0 deg   0.553     2.77 min/sec marks
#: 332.0 deg   1.487     7.43 min/sec marks
#: =========  =========  ==================
#:
#: The hour hand sits at 10.42 on the dial, which on a working clock means
#: **25 minutes past** - but no hand points at minute 25. The only minute
#: readings available are 2.8, 7.4 and 52.1.
#:
#: All six assignments of the three hands to (hour, minute, second) were
#: tried. Every one fails on the hour hand, by **8.9 to 13.2 degrees**,
#: against a measured drawing scatter of about +/-2 degrees (numeral steps run
#: 28.0-32.0). The best, 8.9 deg, is still 4.5x the noise floor.
#:
#: So no reading of this clock as a clock survives, and the hands cannot
#: encode a timestamp, a date, or a time of death. They point.
CLOCK_SHOWS_NO_TIME = {
    "dial_positions": {240.0: 10.420, 304.0: 0.553, 332.0: 1.487},
    "hour_hand_implies_minute": 25.2,
    "minute_readings_available": (2.77, 7.43, 52.10),
    "assignments_tried": 6,
    "hour_hand_error_range_deg": (8.9, 13.2),
    "drawing_scatter_deg": 2.0,
    "verdict": "not a time - the hands are pointers, so no timestamp, date "
               "or time-of-day can be read from the clock",
}


def clock_time_consistency() -> dict:
    """Recompute ``CLOCK_SHOWS_NO_TIME`` from the measured bearings.

    For each of the six ways the three hands could play (hour, minute,
    second), check the one constraint a working clock must satisfy: the hour
    hand's fractional part equals minutes/60.
    """
    import itertools

    twelve = NUMERAL_BEARING[12]
    dial = lambda b: ((b - twelve) / 30.0) % 12
    hands = {"A": 240.0, "B": 304.0, "C": 332.0}
    out = []
    for hour, minute, second in itertools.permutations(hands):
        h_d = dial(hands[hour])
        minutes = dial(hands[minute]) * 5
        implied = (int(h_d) + minutes / 60.0) % 12
        err = abs(((h_d - implied + 6) % 12) - 6) * 30
        out.append({"hour": hour, "minute": minute, "second": second,
                    "reads": f"{int(h_d):02d}:{minutes:05.2f}",
                    "hour_hand_error_deg": round(err, 1)})
    return {"assignments": out,
            "best_error_deg": min(a["hour_hand_error_deg"] for a in out),
            "drawing_scatter_deg": 2.0}


#: **Chosen numbers are evidence. Inherited numbers are not.**
#:
#: This is the distinction that decides most of the community's 24-word table,
#: and it is worth stating precisely because it is easy to miss.
#:
#: A number is **chosen** when the artist had to act to put it there: underline
#: it, aim a clock hand at it, write a word along it. A number is **inherited**
#: when the object simply carries it and the object is in the artwork for
#: thematic reasons anyway.
#:
#: The Statue of Liberty's crown has seven points whether or not the puzzle
#: needs a 7. An M16 is called an M16. ``COVID19`` contains 19. In each case
#:
#:     P(object shows the number | the puzzle needs it)
#:   = P(object shows the number | the puzzle does not)
#:   = 1
#:
#: so the likelihood ratio is 1 and the observation updates nothing. For an
#: inherited number to be evidence, the artist's decision to *include that
#: object* would have to need a puzzle explanation - and every object here is
#: fully explained by the artwork's subject matter.
#:
#: Applying the split to the community's 16 filled entries:
#:
#: =========================  ==========================================
#: chosen (5)                 1 subject, 3 tower, 9 eye, 11 pyramid,
#:                            13 moon
#: inherited (10)             2 camera, 4 mask, 5 police, 7 liberty,
#:                            10 black, 12 vote, 16 rifle, 17 gold,
#:                            19 glove, 20 apple
#: =========================  ==========================================
#:
#: **The chosen set is exactly what this repository already holds**: three
#: CONFIRMED, one STRONG, and ``pyramid`` rejected on measurement (its centroid
#: sits 8.7 degrees off the ray, against a 2-degree noise floor).
#:
#: So the table adds nothing. It is not wrong so much as unconstrained: an
#: artwork this dense offers inherited numbers for almost any target, which is
#: why 16 slots could be filled and why filling them means so little.
CHOSEN_VERSUS_INHERITED = {
    "chosen": {1: "subject", 3: "tower", 9: "eye", 11: "pyramid", 13: "moon"},
    "inherited": {2: "camera", 4: "mask", 5: "police", 7: "liberty",
                  10: "black", 12: "vote", 16: "rifle", 17: "gold",
                  19: "glove", 20: "apple"},
    "likelihood_ratio_of_an_inherited_number": 1.0,
    "chosen_set_equals_repo_state": True,
    "community_table_adds": 0,
    "verdict": "the community's table reduces to the assignments already "
               "established; every further entry rests on a number the artist "
               "did not have to choose",
}


#: **The unlabelled hour hand names the phrase length, not a position.**
#:
#: An anomaly this repo recorded without explaining: of the three clock hands,
#: two carry words - ``tower`` on the minute hand at midpoint(1,2)=3, ``moon``
#: on the second hand at midpoint(12,1)=13 - and the third carries **none**.
#: It points at midpoint(10,11)=21 and is blank. Earlier notes called 21 an
#: "orphan number": a position whose word was never found.
#:
#: Read it instead as a **global parameter**. 21 is a valid BIP-39 mnemonic
#: length (12, 15, 18, 21, 24 are the permitted values), and a hand that names
#: a parameter rather than a word slot has no reason to carry a word. That
#: explains the blankness instead of positing a word nobody can find.
#:
#: **The counting argument.** The clock reaches positions 3 to 23 under its two
#: alignments. So a phrase of length *L* needs a mechanism outside the clock
#: for every position below 3:
#:
#: =========  =======================  ==============================
#: length     needs non-clock          available in the artwork
#: =========  =======================  ==============================
#: 21         positions 1, 2  -> **2**  the plinth, and rune 3  -> **2**
#: 24         positions 1, 2, 24 -> 3   the same two -> 2, one short
#: =========  =======================  ==============================
#:
#: **21 is exactly saturated; 24 leaves a position with no mechanism at all.**
#: The two non-clock mechanisms are the plinth (underlined ``subject`` beside
#: an underlined ``Section 1``) and rune 3 - the one strip deliberately set
#: apart, in a different cipher and a different language, attached to no
#: object, beside a question mark, and pointing at 2 under every reading.
#:
#: **Independent support.** 21 is Bitcoin's signature number: the supply cap is
#: 21 million. For a Bitcoin puzzle, a 21-word phrase is the thematically
#: obvious choice, and aiming the slowest hand at it is a natural way to say so.
#:
#: **A withdrawn argument.** ANALYSIS.md previously argued for 24 on the
#: grounds that "a 21-word phrase would leave the rays for 22 and 23 spurious".
#: That is weak: a clock is a coordinate system, and spare capacity in a
#: coordinate system is not evidence that every coordinate must be used. A
#: ruler with more marks than you need is still the right ruler.
#:
#: **What it does not do.** It changes no arithmetic. A 21-word phrase with
#: three confirmed positions still leaves 17 unknown words, and 2048^17 is as
#: unsearchable as 2048^20. This is a claim about the puzzle's architecture,
#: not a step toward enumerating it.
HOUR_HAND_IS_THE_LENGTH = {
    "anomaly": "two hands carry words; the third is blank and points at 21",
    "reading": "21 is the phrase length, not a position",
    "bip39_lengths": (12, 15, 18, 21, 24),
    "clock_reaches": (3, 23),
    "non_clock_needed": {21: (1, 2), 24: (1, 2, 24)},
    "non_clock_available": ("the plinth", "rune 3"),
    "saturated_at": 21,
    "thematic_support": "21 million is Bitcoin's supply cap",
    "withdraws": "the argument that 24 is preferred because a 21-word phrase "
                 "leaves rays 22 and 23 unused",
    "changes_tractability": False,
    "confidence": "inference, not measurement - it explains three anomalies "
                  "at once (the blank hand, rune 3's role, the length "
                  "ambiguity) but it was reached after the facts it explains",
}
