# Analysis: the 0.2 BTC seed-phrase puzzle

Target address `1KfZGvwZxsvSmemoCmEV75uqcNzYBHjkHZ`
HASH160 `ccbd031e54cde2a3189fd59bc49f731367a1779e`
Balance 0.20107284 BTC · posted 2020-05-10 · unsolved

This document records what can be established about the puzzle, what the
published hints do and do not support, and why the original brute-force
approach in this repository could never have finished. Everything asserted
here is reproducible with the tooling in this repo; the claims that matter are
pinned by tests in `tests/test_vectors.py`.

---

## 1. The finding that reframes the puzzle

Two of the most widely repeated hints point at words that **do not exist in
the BIP-39 English wordlist**:

| Hint | Word | In BIP-39? | Nearest BIP-39 words |
|---|---|---|---|
| "'Breathe' can be found on George Floyd's chest as well as the Statue's Neck" | `breathe` | **No** | `bread`, `breeze` |
| Rune 3 (above Trump), Bill Cipher, translates to "Tuesday" | `tuesday` | **No** | *(no weekday is in BIP-39)* |

Verify it yourself:

```console
$ ./solve.py validate --extra "breathe,tuesday,moon,tower,black"
  INVALID  breathe      suggest: bread, rather, rate, weather, brother
  INVALID  tuesday      suggest: today, essay, turkey, say, day
  ok       moon         #1148
  ...
```

This matters because BIP-39 is a closed vocabulary of exactly 2048 words. A
mnemonic *cannot* contain `breathe`. So at most one of the following is true:

**(a) The answer is not a BIP-39 mnemonic.** The puzzle's own wording supports
this — it says "the seed **passphrase** is hidden in the picture", not "seed
phrase". A free-form passphrase hashed straight to a private key (a
*brainwallet*) accepts any vocabulary, including `breathe` and `tuesday`. This
repository's original script could not have found such a key under any
circumstances, because it only ever built BIP-39 mnemonics.

**(b) `breathe` and `tuesday` are not literal seed words.** They may encode
something else. Note that rune 2 translates to "**sum of two numbers**", rune 4
to "rainy day number **X**", and rune 3 to a *weekday*. Three of the four runes
refer to numbers or ordinals rather than to nouns. A natural reading is that
the runes encode **positions or indices**, not words — for instance which slot
a word occupies, or an index into the 2048-word list. Under this reading
"Tuesday" is a number (2 or 3, depending on whether the week starts Sunday),
not a seed word.

**(c) The hints are simply wrong.** They are community-derived, not authored by
the puzzle's creator, and no one has verified them against a solution.

**Update after the image work in section 2 and the negatives in section 3:**
interpretation (a) has weakened considerably and (c) has strengthened.
`breathe` is *plain visible text on Floyd's hoodie* and nothing more — at 16x
the Statue's neck shows only robe drapery, no lettering, so it is not a
*marked* word the way `moon`, `tower`, `food`, `real`, `subject` and `one` are.
And brainwallet phrases of up to six words over a vocabulary that deliberately
included `breathe` and `tuesday` are now **exhausted** with no match.

So the working position is: the six marked words are real, `breathe` is
thematic decoration that the hint list over-read, and a 12-word BIP-39
mnemonic remains the best model. The tooling still supports (a) via
`--mode brain` for longer phrases.

### Words the hints support that *are* valid BIP-39

`moon` · `tower` · `food` · `this` · `subject` · `real` · `black`
— plus `one`, recovered in section 2.

Eight words. A 12-word mnemonic needs four more.

---

## 2. What the image actually contains

Everything below was read off the artwork with `forensics.py`, not taken from
the published hints. Reproduce any of it with:

```console
$ ./forensics.py regions puzzle.png -o out/
```

### Steganography is ruled out

```console
$ ./forensics.py probe puzzle.png
  chunks: IHDRx1, sRGBx1, sBITx1, IDATx291, IENDx1
  trailing data after IEND: 0 bytes
  alpha: 1 distinct value(s)  -> uniform, nothing hidden
  LSB plane means: R 0.4979  G 0.4995  B 0.5053
```

No text chunks, no appended archive, a completely uniform alpha channel, and
LSB planes sitting at ordinary image-noise levels. Nothing is hidden *below*
the pixels. The words are **drawn into the artwork at low contrast** — so the
right tools are tonal (contrast stretch, high-pass, channel isolation), not
bit-level. That is why `forensics.py` offers those three operations.

### Words recovered by direct inspection

| Word | Where it is | How it was read |
|---|---|---|
| `moon` | along the **red** clock hand | high-pass, x14 |
| `tower` | along the **black** clock hand | high-pass, x14 |
| `food` | down the **Space Needle's shaft**, rotated 90° | high-pass + rotate |
| `real` | inserted into "ONLY **real** Bitcoin" on the Statue's base | stretch |
| `only` | same inscription | stretch |
| `subject` | **underlined** in the monument plinth text | red-channel isolation |
| `first`, `future` | "PAY FOR THE **FUTURE**. THIS IS THE **FIRST** PREDICTION." | stretch + rotate |
| `brave`, `world` | "WELCOME TO THE **BRAVE NEW WORLD**" calligram | plainly visible |
| `order` | "Order and stability" banner | plainly visible |
| `this` | "IN THE **THIS** PICTURE", "FUCK **THIS** SHIT", "**THIS** IS THE FIRST…" | plainly visible |
| `black` | rune 4's *chorny den*, the BLM text, and the Latin kettle proverb | hint + text |

### The monument plinth: a word paired with a number

The toppled statue's plinth is not decoration. Under the red graffiti it
carries the **Thirteenth Amendment, Section 1**, and the red paint is
translucent — isolating the red channel reads the ink straight through it:

> Section **1**
> Neither slavery nor involuntary servitude, except as a punishment for crime
> whereof the party shall have been duly convicted, shall exist within the
> United States, or any place **subject** to their jurisdiction.

Exactly **two** things in that block are underlined: the word **`subject`**,
and the numeral **`1`** in "Section 1". Everything else is plain.

That is a seed word deliberately paired with a number — and it is the same
shape as the rest of the puzzle's structure:

- the clock carries two words **on hands that point at numbers**;
- rune 2 translates to "**sum of two numbers**";
- rune 4 ends "…for a black day **number X**".

The most economical reading of the whole puzzle is that **each word is paired
with an index giving its position in the phrase.** If that is right there is no
search to run at all — the phrase is assembled, not brute-forced. This is the
single most valuable thing left to nail down, and it is why decoding the runes
beats buying CPU.

### Rune 4 decoded — and a lead closed

The long rune strip up the right edge segments cleanly. Rotating it so reading
order runs left to right yields **50 glyphs: 43 characters and 7 separators**.
Two independent checks confirm the published Russian plaintext:

```console
$ ./forensics.py runes puzzle.png
rune 4: 50 glyphs (43 letters, 7 separators)
  word lengths from image : [5, 11, 8, 2, 6, 4, 5]
  word lengths from crib  : [5, 11, 8, 2, 6, 4, 5]
  -> MATCH

  recovered alphabet: ЁАБВДЕЗИЙКМНОРСТФЧШЫЬ (21 letters)
  mean distance between glyphs the crib calls the same letter: 27.2
  mean distance between all glyph pairs                     : 66.7
```

The word-length match alone could be luck. The second number is what settles
it: glyphs the crib says are the *same letter* are far more alike (27.2) than
glyphs picked at random (66.7). Both the segmentation and the translation are
sound, and the crib yields a **21-letter substitution alphabet** as a
by-product.

Reading direction is worth noting: the text runs **bottom-to-top**. The
word-length sequence only matches in that direction (reversed it would be
2,5,4,6,2,8,11,5, which matches nothing).

**The lead this closes.** Rune 4 ends "…НОМЕР X" — "number X" — and that
trailing value looked like the most promising index in the whole puzzle. It is
not recoverable, because it is not a digit:

```
  trailing glyphs - the 'number X':
    glyph 48: nearest letter Д  (distance 39)
    glyph 49: solid block - artwork frame, not a character
```

Glyph 49 is a fully-inked rectangle — the frame, not a character. Glyph 48 is a
six-pointed asterisk whose nearest letter sits at distance 39, well above the
27.2 same-letter average, so it is **not** in the cipher alphabet. The author
wrote a literal placeholder. "Number X" means number *X*; there is no hidden
digit to extract.

That is a genuine negative result, and worth having: it removes the strongest
apparent numeric lead and pushes the weight of the position hypothesis back
onto the plinth's underlined `1` and the clock hands.

**Runes 1 and 2 are below the resolution limit.** Their glyphs are drawn much
smaller. Connected components merge into blobs at every threshold tried, and
projection profiles split individual pen strokes rather than characters. That
is a property of the 1600x1200 scan, not of the method — the same code reads
rune 4 cleanly. A higher-resolution original would very likely let the same
crib approach verify rune 2's "sum of two numbers" too.

### The plinth's second underline is a word, not an index

Re-examined at 20x with the red channel isolated, the stroke under the numeral
`1` in "Section 1" is a **deliberate underline** — same hand, same weight, same
length-past-the-glyph as the one under `subject`. It is not a serif on the
numeral.

That changes the reading. Two identical marks are most economically explained
by one mechanism, not two: **underline marks a seed word**. And `one` is a
BIP-39 word. The earlier reading — that `1` is a positional index for
`subject` — needs a second, unevidenced mechanism to work.

So the plinth contributes **two** words, `subject` and `one`, and the position
hypothesis loses its clearest support. `puzzle/candidates.py` now exposes
`MARKED`, the six words the artist actually singled out:

    moon  tower  food     written tiny along a thin object
    real                  inserted into an existing inscription
    subject  one          underlined

### The Great Seal was rewritten

All three of the seal's inscriptions are replaced, which is deliberate but
appears to be thematic rather than a word source:

| Position | Artwork | Standard seal |
|---|---|---|
| top arc | `RERUM COGNOSCERE CAUSAS` | `ANNUIT COEPTIS` |
| pyramid base | `FIAT JUSTITIA ET PEREAT MUNDUS` | `MDCCLXXVI` |
| bottom arc | `UBI BENE IBI PATRIA` | `NOVUS ORDO SECLORUM` |

"To know the causes of things" (Virgil), "let justice be done though the world
perish", "where it is well, there is my homeland". `mundus` = world is a second
independent pointer at `world`, but none of the three is *marked* the way the
six words above are.

### What could not be confirmed

- **`breathe` on the Statue's neck.** It is plainly printed on Floyd's hoodie
  ("I can't BREATHE"), but at 1600x1200 the Statue's neck shows only shading,
  no legible lettering. A higher-resolution original may settle it. `breathe`
  is not a BIP-39 word either way — see section 1.
- **Which numerals the clock hands point at.** The face is *mirrored* and
  rotated (the numerals run clockwise but 12 sits at bearing 287°), only eight
  of the twelve numerals are drawn — 4, 5, 6, 7 are covered by the Great Seal —
  and the Seal's line work contaminates any automated ridge measurement. The
  measured hand bearings land 3–13° off the nearest numeral, which is not
  clean enough to call.

## 3. The construction rule: word plus number gives position

This is the finding that reframes everything else, and it invalidates most of
the search work in this repository — including several runs reported below.

The artwork does not hand over an unordered bag of words to permute. **Each
clue pairs a word with a number, and the number is that word's position in the
mnemonic.**

### The clock proves it

All three clock hands point *midway between two numerals* rather than at one,
and the two numerals sum to the position. Numeral bearings measured from the
artwork sit at exact 30.0 degree steps with 12 at 287.4 degrees, which makes
the midpoints predictable to a fraction of a degree:

| Hand | Label | Midpoint | Predicted bearing | Measured | Position |
|---|---|---|---:|---|---:|
| seconds | `moon` | 12 + 1 | 302.4° | **302–304°** | **13** |
| minutes | `tower` | 1 + 2 | 332.4° | on-hand | **3** |
| hours | *(none)* | 10 + 11 | 241.7° | on-hand | **21** |

The seconds hand is measurable in isolation because it is the only red line on
the dial: 604 red pixels in the annulus around the centre, with a dominant
bearing of 302–304° against a prediction of 302.4°, and the opposite end at
122–124° confirming a single line through the centre. The two grey hands
cannot be separated from grey artwork by ridge detection, but overlaying the
predicted bearings puts them exactly along the drawn hands — the red overlay
runs down the hand captioned `MOON`, the green down the one captioned `TOWER`.

Reproduce with `./forensics.py regions puzzle.png --only clock`.

### Why this is evidence and object-counting is not

The test is **deviation from the default**. Hands normally point *at* a
numeral, so placing all three between numerals is a deliberate choice that
carries information. Likewise the plinth's underlines are marks added on top
of text that did not need them.

Counting objects is different. The Statue's crown does have exactly 7 rays —
verified — but the real Statue has 7 rays, so an accurate drawing yields 7
whether or not 7 means anything. The same goes for 2 cameras and 4 masked
figures: both counts are correct, and both are ordinary composition. An
illustration will always yield numbers if you count things in it.

That criterion is encoded in `puzzle/positions.py` as the `Evidence` scale,
and it is why the community's proposed assignments stay `WEAK` however cleanly
they can be counted.

### The six axes, and why the moon hand is the giveaway

Each hand is a *line*, so it covers two opposite midpoints. There are six axes:

| Axis | ↔ | Carries a hand? |
|---|---|---|
| 3 (332.4°) | 15 (151.8°) | **tower** |
| 5 (2.7°) | 17 (181.9°) | no |
| 7 (32.6°) | 19 (211.7°) | no |
| **13 (302.4°)** | **13 (122.4°)** | **moon** |
| 9 (62.4°) | 21 (241.7°) | **hour** |
| 11 (92.4°) | 23 (272.5°) | no |

Two things fall out. The `13 ↔ 13` axis is the **only one whose two ends give
the same number** — 12+1 and 6+7 both sum to 13 — and it is opposite to 0.0°.
The artist put the unambiguous word on the unambiguous axis. Every other hand
is ambiguous between two positions, resolved only by which end the word is
written on.

Second, **the hour hand's far end lands on 9, exactly where the Seal's eye
sits**. The "unlabelled" hand is not unlabelled; it points at the eye.

### How surprising is any of this?

Ray-matching needs a false-positive rate or it degenerates into pattern
matching. Twelve rays 30° apart means a random bearing is within 1.3° of one
about **9% of the time** (Monte-Carlo over 200k samples: 8.6%).

| Claim | Error | By chance |
|---|---:|---:|
| all three hands within ~2° | — | **0.24%** |
| …and `moon` on the one self-matching axis (1 of 6) | — | **~0.04%** |
| the Seal's eye alone | 1.3° | **8.7%** |

So the **clock mechanism is strong** — about 1 in 2,500 by chance, and it
comes with its own caption (rune 2, "sum of two numbers", drawn inside the
dial). The **eye is not, on its own**. It stays `STRONG` rather than
`CONFIRMED` for one specific reason: the community proposed `eye = 4+5 = 9`
*before* it was measured, so the measurement is a successful prediction rather
than a fitted result. That is worth something, but it is not 1-in-2,500.

`positions.chance_probability(error)` computes this, and should be consulted
before promoting any future ray match.

### Can the rays name the words? No — a survey says they cannot

With 24 rays covering positions 3–23, the obvious next step is to read a word
off each ray. It does not work, and the failure is measurable.

Thirty-two objects were catalogued from the artwork **before** being measured,
to avoid picking the ones that happen to fit. Then all were tested at once:

| tolerance | hits | observed | null | p |
|---:|---:|---:|---:|---:|
| 1.0° | 7 | 21.9% | 13.3% | 0.125 |
| 1.5° | 12 | 37.5% | 20.0% | 0.017 |
| 2.0° | 13 | 40.6% | 26.7% | 0.061 |
| 2.5° | 17 | 53.1% | 33.3% | 0.016 |
| 3.0° | 19 | 59.4% | 40.0% | 0.021 |
| 4.0° | 20 | 62.5% | 53.3% | 0.195 |
| 5.0° | 21 | 65.6% | 66.7% | 0.630 |

**The p-value wanders instead of holding.** A real effect survives every
threshold; this one is significant at 1.5°, not at 2.0°, significant again at
2.5° and 3.0°, then gone. That is what researcher degrees of freedom look
like, not signal.

Two further problems finish it off:

* **The objects are angularly clustered** — 13 of 32 between 45° and 90°, none
  at all between 135° and 180° — because the artwork's content is concentrated
  to the upper right of the dial. Ray coverage is not uniform.
* **Five of the nine occupied positions carry more than one object**, and
  position 9 carries **four** (Space Needle 0.5°, eye 1.4°, toppled bust 2.2°,
  map of China 2.2°). A ray that four objects sit on cannot name a word.

That last point also kills the eye. It is not even the closest object on its
own ray — the Space Needle is nearer. `eye → 9` drops to `WEAK`, and
`PROPOSED_STRONG` is now empty.

### What actually survives

The confirmed clues share a property the survey objects do not: **the word is
written on the object**.

| Clue | Word | How the word is marked | How the number is given |
|---|---|---|---|
| seconds hand | `moon` | written along the hand | its own bearing → 13 |
| minutes hand | `tower` | written along the hand | its own bearing → 3 |
| hours hand | *(none)* | — | its own bearing → 21 |
| plinth | `subject` | underlined | underlined `Section 1` → 1 |

So the clock gives a number only for objects that *are* clock hands, and there
are three of them. The mechanism is real and it is narrow: **three positions
from the clock, one from the plinth, and no established mechanism for the
other twenty.**

### `food` and `real`: searched, and they carry no number

Both are marked the way the confirmed words are — written on or inserted into
an object — so both should carry a number. Neither does.

**`food`**, written down the Space Needle's shaft. The whole tower was
examined at 4x and 14x. The only linear marking on the shaft is the elevator
track, drawn as a dashed line — but that is a real feature of the building, so
its dash count is rendering texture, not a chosen number. No digits appear
anywhere on or beside the Needle.

**`real`**, inserted into "ONLY real Bitcoin". The inscription band, every
pedestal tier, and the object the Statue holds were all examined. The point
worth noting: the real Statue of Liberty's tablet bears a date,
`JULY IV MDCCLXXVI` — the one place a number traditionally sits — and here the
tablet has been **replaced by a phone showing "BLM" and a raised fist**. Where
a number would be, the artist drew a symbol. No digits.

### The capacity bound

That null result exposes something more useful than either number would have
been. The two confirmed mechanisms have hard ceilings:

| Mechanism | Instances possible | Why |
|---|---:|---|
| word on a clock hand, number from its bearing | **3** | a clock has three hands; there is no fourth |
| numeral written beside the word and underlined | **1** | only `Section 1` does this |
| | **4 total** | against 21 or 24 needed |

The bearing mechanism *requires the object to be a clock hand*. However much
of the artwork is searched, it can never yield a fourth position. So the
shortfall of twenty positions is **a statement about the model, not about how
hard anyone has looked** — it needs mechanisms that have not been found, and
possibly do not exist.

This is the point at which the position-map hypothesis should be held more
loosely. It is well evidenced for the three clock hands (~1 in 2,500 by
chance) and the plinth. It has no demonstrated way to reach the other twenty,
two independent attempts to extend it have failed (ray-matching, and the
search above), and every clue that *would* extend it has turned out to be an
incidental count. A construction that needs 24 word-number pairs, of which the
artwork demonstrably supplies four, may simply be the wrong construction.

### The unclaimed axes are empty too

Three axes carry no hand — 5↔17, 7↔19, 11↔23. Each was traced across the full
artwork:

| Axis | What the rays actually pass through |
|---|---|
| 5 ↔ 17 | up through the `SEED PHRASE` display text; down into the bottom whitepaper strip |
| 7 ↔ 19 | up-right through `NEW WORLD` toward Floyd; down-left across the dial past numeral 10 |
| 11 ↔ 23 | right through the pyramid, Trump/Biden and the plinth; left through the Statue's robe |

**None lands on a crisp, isolated feature.** They cross large text blocks and
several objects at once — consistent with the survey above, which shows ray
proximity is not discriminating at 15° spacing.

### The mechanism extends past the hands: the Great Seal's eye

Numerals 4, 5, 6 and 7 are hidden behind the Great Seal — and the Seal's own
features sit on the rays those numerals define. The community table proposes
`eye = 4+5 = 9` and `pyramid = 5+6 = 11`; both are testable the same way.

| Feature | Predicted ray | Measured bearing | Error | Verdict |
|---|---:|---:|---:|---|
| Seal's eye | midpoint(4,5) = 62.4° | **61.1°** | **1.3°** | **STRONG → 9** |
| Pyramid centroid | midpoint(5,6) = 92.4° | 101.1° | 8.7° | rejected (58% by chance) |

The eye lands inside the artwork's own drafting scatter. The pyramid does not:
the 92.4° ray passes *through* its brick body, but a large triangle's centroid
is a loose anchor and 8.7° is well outside the noise floor, so it stays
`STRONG` rather than `CONFIRMED`.

**The noise floor matters.** Measured numeral steps run 28.0° to 32.0° — about
±2° of hand-drawn scatter. That is what makes 1.3° a hit and 8.7° a miss, and
it is why midpoints between two *measured* numerals (`moon`, `tower`, the hour
hand) are firmer than ones involving an interpolated numeral (the `eye`).

`positions.position_at(x, y)` implements the test: give it an image
coordinate, and it returns the position that coordinate encodes, or nothing.

### The even mechanism: one rule, two alignments

Rune 2 says *"sum of two numbers"* — it never says *adjacent* numbers.

* two **adjacent** numerals sum to `2n+1`, always **odd**
* two numerals **two apart** sum to `2n`, always **even** — and their
  geometric midpoint is exactly *on* the numeral between them

So it is a single rule with two alignments: a feature **between** two numerals
encodes an odd position; a feature **on** a numeral encodes an even one, by
summing its two neighbours.

| Alignment | Rays | Positions |
|---|---:|---|
| between numerals | 12 | 3, 5, 7 … 23 (odd) |
| on a numeral | 12 | 4, 6, 8 … 22 (even) |
| **combined** | **24** | **3 … 23, no gaps** |

Twenty-four rays, 15° apart, covering every position from 3 to 23. Three axes
double up — and they are exactly the ones whose two ends give the *same*
number:

| Axis | Both ends give |
|---|---:|
| numeral 6 ↔ numeral 12 | **12** |
| midpoint(6,7) ↔ midpoint(12,1) | **13** |
| numeral 7 ↔ numeral 1 | **14** |

`12, 13, 14` — consecutive, and the exact middle of a 24-position phrase. Every
other axis is ambiguous between two positions, resolved only by which end
carries the word. The `moon` hand sits on the middle one.

**What the clock cannot reach: 1, 2 and 24.** Position 1 is supplied by the
plinth. Positions 2 and 24 have no known clue, and that is now the precise
shape of the gap — not "most of the table is missing" but "two positions plus
the words for twenty rays".

Note this also decides the length question in favour of **24** over 21: a
21-word phrase would leave the rays for 22 and 23 spurious, whereas 24 uses
every one of the clock's 21 reachable positions.

### The cost: a worse false-positive rate

Completing the mechanism makes single matches **weaker**, not stronger. Going
from 12 rays at 30° to 24 rays at 15° doubles the chance of a coincidental
hit:

| Model | Spacing | P(random bearing within 1.3°) |
|---|---:|---:|
| midpoints only | 30° | 8.7% |
| **both alignments** | **15°** | **17.3%** |

The Seal's eye re-scores from 8.7% to **18.7%**. It stays `STRONG` only
because it was predicted before being measured. Nothing else should be
promoted on a single ray match at this rate — a joint alignment of several
independent features, or a feature the mechanism is intrinsically about, is
now the minimum bar.

### A hard structural constraint on the odd half

Taking only the midpoint alignment, consecutive numerals sum to `n + (n+1) =
2n+1`, so every position *that* alignment can yield is odd:

```
3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23
```

This is what forced the search for an even mechanism, and the on-numeral
alignment above supplies it — except for `camera = 2`, which the clock
provably cannot reach under either alignment and which therefore still needs
a standalone clue. Two cameras are in fact drawn, which is the right *shape*
of clue for it, though a bare count remains weak evidence.

So the table is not one hypothesis of uniform strength. It is:

* **four positions** with a confirmed mechanism (1, 3, 9, 13) plus an orphan
  number at 21;
* **odd positions** that at least *could* come from the clock, if a feature
  can be shown to sit on the right ray;
* **even positions** resting on object counts, with no mechanism at all.

### A correction

Section 2 of this document argued the underlined `1` beside
`subject` was the *word* `one`, on the grounds that two identical underlines
were most economically explained by one mechanism. **That reading is
withdrawn.** With the word-plus-number mechanism now confirmed independently
on the clock, `Section 1` is a position marker: `subject -> 1`. `one` has been
removed from the confirmed vocabulary.

### Consequence: it is not a 12-word mnemonic

Position 21 exists. BIP-39 permits 12, 15, 18, 21 and 24 words, so the phrase
is **21 or 24 words**. Every 12-word search ever run against this puzzle —
including all of this repository's, and the original script's — was
structurally incapable of succeeding, no matter how long it ran.

### What it would take to search

`puzzle/positions.py` models the map and refuses to pretend:

```console
  len 21 confirmed only  : NOT searchable: 17 unresolved, ~2e+56 phrases
  len 24 confirmed only  : NOT searchable: 20 unresolved, 1.68e+66 phrases
  len 24 + all proposed  : NOT searchable:  9 unresolved, 1.27e+30 phrases
```

Enumeration, not PBKDF2, is the wall. Three unresolved positions is 2048³ ≈
8.6e9 — about an hour to enumerate and five to derive. Four is 2048⁴ ≈ 1.8e13,
roughly three months. **Three unresolved positions is the practical ceiling**,
so the map needs 18 more verified assignments before any search is worth
starting.

That is the whole game now. One more decoded clue is worth more than any
amount of hardware, and no amount of CPU substitutes for it.

## 4. If the numbers are not positions, what are they?

The capacity bound in section 3 makes the *inference* — that 1, 3, 13 and 21
are mnemonic positions — the weakest link, so the numbers were tested against
the obvious alternatives. All three are cheap, bounded and falsifiable, and
all three failed.

### Text indexing — refuted

Fifteen passages actually read off the artwork (the Amendment, the display
text, the Great Seal's three replaced inscriptions, the BLM slogans, the
decoded rune 4, the whitepaper strip, and so on), extracted under every
combination of unit (word / character / initial), 0- and 1-based indexing, and
both directions. **58 attempts.** Each scored by how many extracted tokens are
BIP-39 words, against a null of random indices drawn from the same passage.

```console
$ ./solve.py extract
0 of 58 attempts extracted all-BIP-39 tokens
```

Best result was 2 of 4 against a null of 1 of 4 — and with 58 attempts, the
best one beating the null is exactly what chance produces. A seed phrase is
*entirely* BIP-39, so any correct convention should give 4 of 4. None did.

The decisive point needs no statistics. The Amendment is the one passage
carrying **both** a marked number and a marked word. If the underlined `1`
indexed that text, `subject` would be word 1. It is **word 29 of 32**.

### Numbers as wordlist indices — no signal

`WORDS[1,3,13,21]` gives `abandon able account action` (1-based) or
`ability about accuse actor` (0-based) — the head of the alphabetical list,
not a phrase. Nothing to test further.

### Numbers as a derivation path — refuted

The most promising alternative: if 1/3/13/21 are path components, the seed
could be simple and the *path* is the secret. Tested exhaustively:

* **900 candidate seeds** — the five marked words (`subject tower moon food
  real`) in every ordering of length 3, 4 and 5, each as a BIP-39 seed, a
  BIP-39 seed with the `breathe` passphrase, and an Electrum seed;
* **632 candidate paths** — every ordering of 1/3/13/21, every
  hardened/soft combination, and every prefix;
* both compressed and uncompressed public keys.

**568,800 derivations, zero matches.**

### Source-text indexing — refuted

The last reading standing: the numbers select from a text the artwork
*references* rather than one it renders. Bounded deliberately — only sources
the artwork quotes or references verbatim, chosen and written down before the
run, because with enough source texts something always fits.

| Source | Why it qualifies |
|---|---|
| 13th Amendment, Section 1 and full | printed verbatim on the plinth |
| Bitcoin whitepaper abstract | whitepaper prose is rendered twice in the artwork |
| Whitepaper §2 (Transactions) | the text the `BRAVE NEW WORLD` calligram is built from |
| The Great Seal's three Latin inscriptions | all three replaced by the artist |

Six pre-registered conventions × 5 sources = **25 attempts. Zero produced a
complete BIP-39 set.** Best was 2 of 4, against nulls of 0.24–0.30 — the noise
floor.

### Date and numbered-source references — refuted

The two readings people reach for once text indexing is gone: each number
**references a date** (1/3 for the genesis block, 13 for the Amendment), or
**references a numbered source** (Amendment 13, whitepaper §3, BIP-21), with
the reference then naming a word.

**These need a different test, and the reason matters.** Every earlier sweep
scored a hypothesis by "are all four extracted tokens BIP-39 words?" That works
when tokens are pulled from English prose, where landing on a wordlist entry is
informative. It is *vacuous* for any scheme that resolves a number to a
wordlist index: such a scheme returns a BIP-39 word for every input, always. A
forward sweep of "what word does 13 give?" therefore passes everything and
proves nothing, however good the word looks.

**The test that discriminates runs backwards, off the anchors.** The artwork
pairs three numbers with three words. The position model reads that as "this
word sits at that position"; the reference model reads the same evidence as
"this number names that word." So any reference scheme `f` is pinned by three
simultaneous constraints:

    f(1) = subject      f(3) = tower      f(13) = moon

| Family | Schemes tested | Fitting all three anchors |
|---|---|---|
| Affine — `f(n) = WORDS[(a·n + b) mod 2048]` | 2,048 (**complete**, not sampled) | **0** |
| Date — number as day-of-month, or as year offset | 1,164,504 | **0** |
| Combined — all four numbers as one date | 1,056 | **0** |

The affine sweep is complete over its family: fixing `a` and the `f(1)` anchor
determines `b`. It subsumes every linear number-to-index reading in one pass.

**The near-miss is worth writing down.** Exactly two affine schemes fit anchors
1 and 3. Both send 13 to `coin` — thematically perfect for a Bitcoin puzzle,
and contradicted by the artwork, which puts `moon` there. Anyone re-deriving
this will hit the same seductive wrong answer.

**Numbered sources collapse to a vocabulary question.** A source-reference
scheme must select its word *from the referenced text*, so a word absent from
that text is unreachable under any selection rule:

| Source | Verdict |
|---|---|
| All 27 US Amendments (archives.gov) | `tower` and `moon` occur in **none** of them. `subject` does occur — in Amendments 5, 13, 14 and 21, **never the 1st**. So `f(1) = subject` fails too. |
| Whitepaper sections | 12 sections; 13 and 21 out of range |
| BIP-1 / 3 / 13 / 21 | **BIP-3 was never published**, so `f(3)` has no text; BIP-13 and BIP-21 contain none of the anchor words |
| Great Seal inscriptions | three of them; 13 and 21 out of range |
| "the n-th datable reference in the artwork" | eight exist; 13 and 21 overrun them |

**A fit found by sweeping would not have been evidence.** Fitting on one anchor
and checking two leaves a chance pass rate of 1/2048² per scheme, so the date
sweep *expects* 0.28 accidental fits. Zero is the informative outcome, and only
because the schemes were fixed before running. The test suite carries positive
controls — a planted affine scheme and a planted date scheme, both recovered —
so the refutations are not an artefact of machinery that can never pass.

Reproduce with `./solve.py references`.

## The responsible stopping point: underdetermined

Across **83 pre-registered attempts** — 58 over text rendered in the artwork,
25 over the sources it quotes — under every reasonable indexing convention,
**not one produced a complete BIP-39 set.**

That is the discriminating test, and it is worth being precise about why. A
seed phrase has no non-BIP-39 members, so a *correct* convention yields 4 of 4
by construction. It does not merely score well against a null; it is perfect.
None was. So either the convention lies outside a fairly exhaustive tested
set, or the numbers do not index text at all.

Combined with the capacity bound, the honest classification is that this
puzzle is **underdetermined by its artwork**: what can be recovered does not
determine a phrase.

**What is established, and is not in doubt:**

* three clock hands encode 3, 13 and 21 by the midpoint rule — about 1 in
  2,500 by chance, and captioned by rune 2's "sum of two numbers" drawn inside
  the dial;
* the plinth pairs an underlined `subject` with an underlined `1`;
* five words are deliberately marked: `moon`, `tower`, `food`, `subject`, `real`.

**What is closed:** ray-matching as a way to name words; text indexing;
wordlist indices; derivation paths; source-text indexing; date references
and numbered-source references; steganography; brainwallet to six words;
`BEST_12` as an Electrum seed.

**What would change the picture,** in descending order of value:

1. ~~**A higher-resolution original.**~~ **Closed — no better file exists.**
   Three independent sources serve byte-identical content
   (`d0b04378…`, 2,383,395 bytes, 1600×1200): privatekeys.pw,
   **`i.redd.it/n1x7g8ceaur51.png`**, and the `HomelessPhD/BLM_0.2BTC`
   repository. The middle one settles it — Reddit serves the *original upload*
   from i.redd.it and puts downscaled variants on preview.redd.it, so
   byte-identical content there means 1600×1200 is what was published. The
   BitcoinTalk thread links only to that repository, which holds the same
   bytes again.

   And the file is **not** a downscale of something larger: edge runs average
   1.61 px with **54.5% single-pixel edges** (downscaling smears every edge
   across two or more), and spectral energy persists to Nyquist with a
   tail/mid ratio of **0.526** (a downscale collapses well below ~0.3). The
   published raster is at or near native rendering resolution.

   This is worse news than it sounds. Runes 1 and 2, the clock bearings and
   the claimed neck text are limited by **the artwork as published**, not by a
   poor scan — so no amount of hunting for a better copy will unblock them.
   Only the artist's own source file could.
2. **A fourth number-bearing mechanism.** The capacity bound says one *must*
   exist if the position reading is right. Four attempts to find one have
   failed. The most recent re-examined the artwork directly: the clock is
   measured to have exactly three hands, the plinth carries only Section 1,
   and the three previously uncatalogued numerals are event captions that meet
   neither marking convention. If a fourth mechanism exists it is not in the
   places it could most easily have hidden.
3. **The author's own account** of the construction.

**What will not help: more CPU.** Every remaining search is unbounded because
the word set is unknown, and a negative from guessed fillers is not a result.
The engine has never been the constraint — it exhausted 479M orderings of a
12-word pool in 33 minutes.

### Reading the runes for a fourth mechanism

Rune 2 sits *inside* the clock dial, and its reading — "sum of two numbers" —
is what licenses the midpoint rule and therefore the three confirmed
positions. This repository had taken that reading on trust from the community
analysis. If the runes caption mechanisms, then a fourth mechanism should have
a caption too, so all four strips were read.

#### Rune 2 verified — and the check is strong

The alphabet used to read it was recovered from **rune 4's** crib and had
never seen rune 2.

**Structure.** The column-projection runs separate into **5 / 4 / 5** glyphs
around two narrow separators. `СУММА`(5) `ДВУХ`(4) `ЧИСЕЛ`(5) is 5, 4, 5.

**Letters.** At **8 of the 10** positions whose crib letter also occurs in
rune 4, that letter is the *nearest* of 21 candidates:

| Word | Positions | Distances |
|---|---|---|
| `СУММА` | С, М, М, А | 28, 41, 26, 14 |
| `ЧИСЕЛ` | Ч, И, С, Е | 24, 21, 25, 28 |

Those eight average **25.9**, sitting on the same-letter baseline of **27.2**
— against a different-letter baseline of 66.4. Against a null of random
assignment, 8 of 10 top-matches in a 21-letter alphabet is **p ≈ 1.1 × 10⁻⁹**.

The two misses are positions 5 and 6, both inside `ДВУХ` — the one word whose
glyphs cannot be separated at any threshold. The run stays merged at 150–185
and shatters into eight fragments at 215. Dividing it in three keeps the crib
positionally aligned but cannot land on true boundaries, so those positions
are a **segmentation artefact, not a failed decode**. They are reported and
excluded rather than dropped, and a test asserts that every miss is flagged
unreliable.

**Why this matters beyond rune 2.** The midpoint rule rests on this caption
saying "sum of two numbers". That is no longer an assumption carried from
elsewhere — it is verified against pixels with an independent key. The three
confirmed positions stand on firmer ground than they did.

#### Rune 3 does not decode in this alphabet

Mirrored, rune 3 resolves into seven legible glyphs: a triad of dots joined
into a `<`, an oval beneath a smaller oval, a hooked stroke with a dot, an
outline `▽`, an `N`, an `E`, and two stacked triangles.

Matched against the rune-4 alphabet they average **44.8** — between the
same-letter band (27.2) and the different-letter band (66.4) — with incoherent
assignments and no word emerging. Unmirrored is worse, 48.6. Its inventory
contains shapes rune 4 never uses, and it is drawn in thin precise outlines
where rune 4 is thick and hand-drawn.

So rune 3 is not a mechanism caption in the script the other runes use. It is
either a different sign system or not text, and is recorded as open rather
than forced into a reading.

#### The runes as a source of mechanisms

| Strip | Content | Mechanism? |
|---|---|---|
| Rune 1 | "I hope many bitcoins will be sent here" | no — a wish |
| Rune 2 | **"sum of two numbers"**, inside the dial | **yes — the clock, already counted** |
| Rune 3 | does not decode in this alphabet | open |
| Rune 4 | the framing statement, ending `НОМЕР` + one glyph | no — and that glyph resolves to no letter and is not a Dscript numeral |

Four strips, exactly one mechanism caption, and it captions the mechanism
already in hand. **No fourth mechanism in the runes.** The capacity bound is
unchanged at four.

Reproduce with `runes.verify_rune2(image)`.

### Is the rune script Dscript? — refuted

Dscript ("Dimensional Script", dscript.org) is a constructed 2D writing system
built from simple geometric pen strokes. The resemblance to these runes is real
enough to be worth testing — both alphabets are triangles, circles, bars and
crosses — and Dscript defines a **base-100 numeral**: a core circle with
directional strokes, nine for units and nine for tens, two decimal digits per
glyph.

That is why this mattered. Rune 4 reads "…НОМЕР" — *number* — and then one
unresolved glyph. If that glyph were a Dscript base-100 numeral it would read
out a two-digit number, and **that would be the fourth number-bearing mechanism
the capacity bound says must exist.**

It is not Dscript. Four checks, none depending on the others:

1. **Cyrillic-only letters have their own glyphs.** The recovered alphabet
   contains `Ь` (soft sign), `Ы`, `Ё`, `Й`, `Ч`, `Ш`, `Ф`. Dscript is optimised
   for English, and writing Russian in it means transliterating — its digraph
   set (`CH SH ST TH TS QU NG`) is exactly what a transliteration needs. A
   transliteration has no soft sign and no `Ы`.
2. **A Cyrillic diacritic relationship survives in the shapes** (below).
   Dscript has no device by which one letter is another plus a diacritic.
3. **The letter-to-shape assignments do not match.** Rune `О` is a chevron
   where Dscript `O` is a circle; rune `С` is a diamond where Dscript `S` is
   `C`; rune `И` is φ, which in Dscript is `M`. The visual vocabulary overlaps;
   the mapping does not.
4. **The trailing glyph is not a base-100 numeral.** It is one connected
   component — a vertical stem crossed by two diagonals — with no core circle.
   Every Dscript base-100 number is a circle plus strokes.

#### What the comparison did produce

The rune-4 alignment was fitted on two things only: word lengths between
separator glyphs, and the similarity of glyphs the crib says are the same
letter. **It never looked at diacritics.** So it makes a prediction it could not
have engineered — the glyph it lands on for `Й` should be the glyph it lands on
for `И`, plus a mark.

| Pair | As drawn | De-dotted | Base letter's own spread | Baseline |
|---|---|---|---|---|
| `И` → `Й` | 27 | **24** | 25, 30, 33 | 66.4 |
| `Е` → `Ё` | 71 | 71 | 20, 51, 59 | 66.4 |

`Й` sits **inside `И`'s own instance-to-instance spread** — it is as close to
`И` as `И` is to itself. That is independent corroboration of the decode, from
a direction the crib cannot reach.

`Е`/`Ё` does not corroborate. Reported anyway: at 71 it is at the baseline. But
`Е` is drawn inconsistently — its own three instances differ by as much as 59 —
so this is a weak negative, not a contradiction. One pair confirms, one is
uninformative, and the record says so.

**The trailing glyph stays unresolved.** Its nearest letter is `Д` at distance
39 — above the mean intra-letter distance of 27 but below the maximum of 59, so
the measurement neither identifies it nor excludes it. What can now be said is
narrower and firmer: it is *not* a Dscript numeral, so no reading of it is
available from that direction.

### Re-examining the artwork for a fourth number-bearing object

The capacity bound rested on an argument — "a clock has three hands" — and on
having looked at the two marked words that lack numbers. Both deserved to be
checked against pixels rather than reasoning.

**The clock, measured.** High-pass the artwork, sweep a ray from the hub at
every whole degree, and take mean ink between radius 40 and 150 (skipping the
hub, where all hands overlap). A hand is a sustained radial ink ridge.

Twelve bearings exceed 1.7× the mean. **Exactly three are hands:**

| Bearing | Nearest midpoint | Off by | Hand |
|---|---|---|---|
| 332.0° | midpoint(1,2) = **3** | 0.4° | `TOWER` |
| 304.0° | midpoint(12,1) = **13** | 1.6° | `MOON` |
| 240.0° | midpoint(10,11) = **21** | 1.7° | unlabelled hour hand |

The other nine sit 3.7–13.7° off, and every one falls inside the arc covered
by the Great Seal coin, which overlaps the dial and hides numerals 4–7. They
are its rim, rays and pyramid courses. **The clock is exhausted — there is no
fourth hand**, and the ceiling of three is now a measurement.

**The plinth, re-read.** The 13th Amendment has two sections, so a second
underlined pair was possible in principle. Isolating the blue channel lifts
the ink out from under the translucent red graffiti: the stone carries
**Section 1 only**, ending at "their jurisdiction". One pairing, no second.

**Three numerals nobody had catalogued.** A full numeral census turned up
three date inscriptions absent from every record in this repository:

| Numeral | Where | Reading |
|---|---|---|
| `05.25.20` | on George Floyd's hoodie, directly above `I can't BREATHE` | the date of the death depicted |
| `11.03.20` | beneath the red `·VS·` between Trump and Biden | the 2020 election, drawn before the result was known |
| `1865 - 202…?` | beside the Statue; ellipsis and `?` in red | emancipation to an unfinished present |

Finding them was worth the pass. Promoting them is not warranted, on three
counts. **Neither convention:** none is underlined and paired with an
underlined word, and none rides a pointer — the only two marking conventions
the artwork has ever established. **Range:** read as positions they overflow a
24-word phrase, since `05.25.20` yields 25 and `1865 - 202…?` yields 1865 and
2020; only `11.03.20` stays in range, and one in three is what chance looks
like. **They are already explained:** each captions a real event the artwork
depicts, and the red `?` appears on exactly the two open questions — when the
struggle ends, and who wins — matching the artwork's own vertical caption,
`THIS IS THE FIRST PREDICTION`. Nothing is left over for a puzzle role.

So the fourth mechanism was not overlooked in the places it could most easily
have hidden. The capacity bound stands at four, now measured rather than
argued. Reproduce the hand scan with `positions.scan_hands(image)`.

### Where that leaves the numbers

Three readings closed, and the position reading capacity-bounded at four. The
numbers are real — the clock measurement is ~1 in 2,500 by chance — but what
they index is now genuinely open. That is a more honest place to stand than a
24-position table with twenty guesses in it.

## 5. Negative results

Recorded so nobody re-treads them. Each of these looked promising and is now
closed.

| Checked | Result |
|---|---|
| Steganography (metadata, alpha, LSB) | nothing hidden below the pixels |
| Rune 4's "number X" | a placeholder asterisk, not a digit |
| `breathe` on the Statue's neck | **no lettering at 16x** — only robe drapery. It is plain visible text on Floyd's hoodie and nothing more |
| Flag stripes | clean; no text along any stripe |
| Whitepaper calligram | uniform whitepaper prose, no word emphasised or altered |
| Fine-detail sweep of unexamined regions | no further text cache — the marked-word list is likely complete for this scan |
| **Brainwallet, phrases of 3–6 words** | **exhausted, no match** (see below) |
| Blockchain history | funded 2020-05-10 08:01 UTC, 0.20000000 BTC, from four P2SH inputs; never spent; no OP_RETURN. Later deposits are third-party dust |

### Brainwallet is exhausted for short phrases

The puzzle says "seed **passphrase**", and a brainwallet — `SHA-256(phrase)`
used directly as a private key — accepts any vocabulary and any length. It is
also ~65x cheaper per candidate than BIP-39, which makes short phrases
*exhaustively* searchable rather than merely sampled. Nobody appears to have
closed this off, so it was worth doing properly.

Vocabulary: the six marked words plus `this black only first future brave
world order breathe tuesday` — 16 words, deliberately including the two that
are **not** BIP-39, since brainwallet mode does not care.

| Length | Orderings | Variants | Result |
|---:|---:|---|---|
| 3 | 3,360 | 9 (space/none/dash x lower/upper/title) | no match |
| 4 | 43,680 | 9 | no match |
| 5 | 524,160 | 9 | no match |
| 6 | 5,765,760 | 1 (space + lower) | no match |

Both compressed and uncompressed public keys were tested for every candidate.
**A brainwallet of up to six words from this vocabulary is ruled out.** That is
a real closure, not a sample: the space was covered completely.

## 6. Electrum seeds: a whole search space nobody had checked

Everything above assumes BIP-39. **Electrum does not use BIP-39**, and the
differences are not cosmetic:

| | BIP-39 | Electrum |
|---|---|---|
| checksum | 4 bits, in the last word | 8 bits, `HMAC-SHA512(b"Seed version", seed)` prefix |
| PBKDF2 salt | `b"mnemonic"` | `b"electrum"` |
| script type | chosen by the derivation path | **encoded in the seed itself** |
| legacy path | `m/44'/0'/0'/0/i` | `m/0/i` receiving, `m/1/i` change |

A phrase can be a perfectly valid Electrum seed and an invalid BIP-39
mnemonic, and vice versa — the two checksums are unrelated. So a BIP-39-only
search walks straight past an Electrum wallet no matter how long it runs. For
a 2020-era puzzle whose description says "seed **passphrase**", this was a
real gap.

`puzzle/electrum.py` implements it, verified against Electrum's own
`tests/test_wallet_vertical.py` vectors — seed typing for standard, segwit and
2FA-segwit phrases, and the `m/0/0` / `m/1/0` addresses of a known standard
seed.

Only the **standard** type (`01` prefix) can produce a legacy `1...` address;
segwit and 2FA seeds derive bech32, so they cannot match this target and are
skipped.

### It is also seven times cheaper to search

The 8-bit seed-version prefix rejects **255 of every 256** orderings for the
cost of one HMAC-SHA512, where BIP-39's 4-bit checksum only rejects 15 of 16.
That sixteen-fold stronger filter more than pays for the slightly dearer
derivation:

```
seed-version filter :  122,394 orderings/sec/core   (measured pass rate 0.00385, expected 1/256)
full candidate      :      518 /sec/core            (PBKDF2 + m/0/0 + m/1/0)
effective           :   63,677 orderings/sec/core -> 254,709/s on four cores
```

**A twelve-word pool takes 31 minutes in Electrum mode against 3.8 hours in
BIP-39 mode** — that is like-for-like, comparing Electrum's two chains against
BIP-39's *fast path* of one scheme and one address index. Compared at each
mode's default breadth the gap is wider still (14x), because BIP-39's default
scans 26 addresses per seed to Electrum's 10.

That changes the strategy: word *sets* can be swept, not just sampled. Where BIP-39 lets four cores exhaust roughly one set per working day,
Electrum lets them do a dozen.

## 7. Why the original script could not have worked

The script this repository shipped with did:

```python
seed_words = [...]                                   # 36 words
for combination in itertools.permutations(seed_words, 12):
```

`P(36, 12)` is **599,555,620,984,320,000** orderings — six hundred quadrillion.

```console
$ ./solve.py estimate --words seedwords.txt
  total candidates    599,555,620,984,320,000 (~6e+17)
  estimated wall time 625,757 years
  VERDICT: HOPELESS. This will never finish.
```

625,757 years on four cores. Buying a thousand times more CPU brings it to 625
years. This is not a tuning problem; the pool is too big by about nine orders
of magnitude.

The cost curve is brutal, and it is the single most important thing to
internalise before starting any run:

| Pool size | Orderings | Wall time (4 cores) |
|---:|---:|---:|
| 12 | 479,001,600 | **7.5 hours** |
| 13 | 6,227,020,800 | 4.1 days |
| 14 | 43,589,145,600 | 28.5 days |
| 15 | 217,945,728,000 | 142.7 days |
| 16 | 871,782,912,000 | 2 years |
| 18 | 8,892,185,702,400 | 16 years |
| 20 | 60,339,831,552,000 | 108 years |
| 36 | 599,555,620,984,320,000 | 625,757 years |

**Each extra candidate word multiplies the work by roughly the pool size.**
Identifying one more word correctly is worth more than a data centre. Twelve
words is a tractable search; sixteen is not.

### Three further defects in the original script

1. **No checksum pre-filter.** Only 1 in 16 orderings of a 12-word set has a
   valid BIP-39 checksum (128 entropy bits + 4 checksum bits). The original
   discovered this by calling `Bip39SeedGenerator` and catching the exception —
   paying full mnemonic parsing plus Python exception overhead for every one of
   the 15 rejects. Checking the checksum directly costs one SHA-256 over 16
   bytes.
2. **One derivation path only.** It tested `m/44'/0'/0'/0/0` and nothing else.
   A 2020 wallet with a legacy `1...` address might equally sit on `m/0'/0/0`
   (bitcoinjs, blockchain.info) or `m/0/0`. Testing one path risks deriving the
   right seed and walking straight past it.
3. **`random.shuffle(seed_words)` before enumerating.** Non-deterministic, so a
   run could not be resumed, reproduced, or divided between machines. Two runs
   would redo overlapping work while leaving other regions untouched.

---

## 8. What this toolkit does instead

| Problem | Fix | Measured effect |
|---|---|---|
| No checksum filter | Direct 132-bit packing + SHA-256 | 657,000 rejects/sec/core |
| PBKDF2 on every candidate | Only on the 1-in-16 that pass | ~16x fewer PBKDF2 calls |
| Base58 encode per candidate | Compare 20-byte HASH160 | big-int encode out of the hot path |
| Single derivation path | 6 schemes, parent node cached | ~26 addresses per seed |
| Single core | `multiprocessing`, unit-partitioned | ~4x on this machine |
| Not resumable | Deterministic units + checkpoint file | resume after interruption |
| No idea how long | Feasibility model, refuses hopeless runs | see `estimate` |
| BIP-39 only | `--mode brain` for free-form passphrases | ~65x faster per candidate |

Measured on 4 cores (`./solve.py bench`):

```
checksum filter :      657,069 perms/sec/core
bip39 candidate :          278 /sec/core   (PBKDF2-2048 + 4 schemes)
brain candidate :       18,154 /sec/core   (SHA-256 + EC + hash160)
```

PBKDF2 dominates BIP-39 mode: 2048 rounds of HMAC-SHA-512 is deliberately
expensive, and no amount of engineering removes it. The checksum filter is what
keeps it off 15 of every 16 candidates.

---

## 9. Recommended search order

Ranked by probability-per-CPU-hour.

**1 — Exhaust 12-word pools built from tier A plus five tier-B words.**
Seven hint-supported words plus five from the prominent rendered text
("BRAVE NEW WORLD", "Order and stability", "ONLY real Bitcoin", "FIND THE SEED
PHRASE IN THIS PICTURE"). Each such pool is 7.5 hours on four cores, and there
are only C(8,5) = 56 ways to pick the five. That is the highest-value region.

```console
$ ./solve.py search --tiers A --extra "brave,world,order,only,find" \
      --workers 4 --checkpoint runs/a12.json
```

**2 — Brainwallet mode on the same vocabulary, including the non-BIP-39 words.**
Sixty-five times cheaper per candidate and the only mode that can accommodate
`breathe`. If interpretation (a) is right, this is where the answer lives.

```console
$ ./solve.py search --mode brain --tiers A \
      --extra "breathe,tuesday,brave,world,only" \
      --joiners space,none --casings lower,title --workers 4
```

**3 — Pin positions using the runes.** If the runes encode positions, pinning
even one word divides the work by the pool size; pinning three makes a 15-word
pool cheaper than an unpinned 12-word one.

```console
$ ./solve.py search --tiers AB --pin 0=moon,11=black --workers 4
```

**4 — Only then widen the pool.** Adding tier C or D words without pinning
pushes the run past a year.

---

## 10. Coverage so far

Two runs, both against the target's HASH160, both checkpointed and resumable.

**Run 1 — breadth.** Twelve-word pool, four derivation schemes, five address
indices each (26 addresses per seed):

```
result   15,505,408 orderings (968,858 checksum-valid) in 15.0 minutes
         385 of 11,880 units = 3.2% of that pool, no match
         17,228 orderings/sec on four cores
```

**Run 2 — depth.** Thirteen words, BIP-44 fast path (`m/44'/0'/0'/0/0` only).
Halving the derivation work doubles throughput, which is the right trade when
only a small fraction of the space is reachable anyway:

```
pool     moon tower food subject real this black only first future brave world order
space    P(13,12) = 6,227,020,800 orderings, 389,188,800 checksum-valid
rate     ~35,000 orderings/sec on four cores  (2x run 1)
covered  63,665,280 orderings = 1.0%, no match; paused, checkpointed
```

**Run 3 — the revised set.** `candidates.BEST_12`, which swaps the display
words for `one` (section 2) and drops the weakest. Twelve words is a *single*
subset, so this run is exhaustive rather than a sample and completes in about
four hours:

```
pool     moon tower food real subject one future this first black only world
space    479,001,600 orderings, 29,937,600 checksum-valid
full     ~3.8 hours on four cores; checkpointed
```

**Run 4 — brainwallet, lengths 3-6.** Exhausted, no match (section 3).

> **All five runs below assume a 12-word phrase, which section 3 shows is
> wrong.** They are kept as an honest record of what was spent and of the
> engine's measured throughput, not as progress toward the answer.

**Run 5 — `BEST_12` as an Electrum standard seed. COMPLETE.** The first
exhaustive closure of a twelve-word set in a seed scheme:

```
pool      moon tower food real subject one future this first black only world
space     479,001,600 orderings - all of them
addresses m/0/0, m/0/1, m/1/0, m/1/1
result    11,880 / 11,880 units, 1,869,966 seed-version-valid, no match
time      32.9 minutes on four cores (model predicted 31.4)
```

The run checks itself: the observed seed-version pass rate was **0.003904**
against a predicted **1/256 = 0.003906**. Had units been skipped or the filter
been wrong, that number would not land within 0.05% of theory. The space
really was covered.

**So that set is ruled out as an Electrum standard seed** — with two caveats
worth stating: no passphrase was applied, and only address indices 0 and 1 on
each chain were scanned.

Runs 2 and 3 sample one derivation path each; runs 4 and 5 close their spaces
completely. None has found the key.

## 11. The passphrase hypothesis

BIP-39 and Electrum both support an optional **passphrase** — the "13th word"
— which is mixed into the PBKDF2 salt. It can be any string, so it is not
restricted to the wordlist.

That matters here because the puzzle's own description says the *seed
passphrase* is hidden in the picture, and the single most prominent word in
the artwork, `breathe`, is **not** a BIP-39 word. "Twelve marked words, with
`breathe` as the passphrase" reconciles both facts without needing the hint
list to be wrong.

### One enumeration pass serves every passphrase

Neither the BIP-39 checksum nor the Electrum seed version depends on the
passphrase — both are computed from the words alone. So a single pass can
enumerate, filter, and then try *N* passphrases against each surviving
candidate; only the PBKDF2 repeats. `--passphrases` does this.

For a twelve-word pool on four cores:

| Mode | Filter (once) | Per passphrase | 8 passphrases |
|---|---:|---:|---:|
| BIP-39 (fast path) | 3 min | 3.75 h | 30 h |
| Electrum | 16 min | 15 min | **2.3 h** |

Electrum's 1-in-256 seed-version prefix leaves only 1.87M candidates needing
PBKDF2, against BIP-39's 29.9M — which is why the same passphrase sweep is
thirteen times cheaper there.

### Running

1. **BIP-39, `BEST_12`, passphrase `breathe`** — the prioritised test, ~3.8 h.
2. **Electrum, `BEST_12`, eight passphrases** — chained behind it, ~2.3 h:
   `breathe`, `Breathe`, `BREATHE`, `tuesday`, `Tuesday`, `i can't breathe`,
   `icantbreathe`, `black`.

The engine is tested against a planted target reachable *only* under a
passphrase, and against the same target with the correct passphrase removed
from the list — the second case guards against the passphrase being silently
ignored, which would otherwise produce a false negative across an entire run.

## 12. Open questions

- **Is the phrase 12 words?** Nothing establishes the length. `--length`
  accepts 15/18/21/24, and brainwallet mode accepts any length. A 24-word
  phrase is unsearchable by permutation and would need the word *order* to be
  determined by the image.
- **Is the word *set* right at all?** This is now the binding constraint, not
  the ordering. Six words are securely marked and three more are faint; the
  remaining three of any twelve are guesswork drawn from display text. A
  wrong set makes every ordering search worthless, and there is currently no
  way to test a set except by exhausting its 479M orderings (~4 hours). If the
  runes or the clock ever yield positions, that cost collapses to a single
  derivation per set and the whole problem becomes tractable.
- **What do runes 1 and 2 encode?** Rune 4 is now settled (section 2) and its
  "number X" turned out to be a placeholder, so the remaining numeric hope is
  rune 2's "sum of two numbers". Both runes need a higher-resolution scan
  before the crib method can reach them; the alphabet recovered from rune 4 is
  already in `puzzle/runes.py` and ready to apply. Rune 3 is written
  **mirrored** — flip it before transcribing.
- **Where does a higher-resolution original live?** This is now the single
  highest-value thing to find. Three separate leads — runes 1 and 2, the clock
  hand bearings, and the claimed `breathe` on the Statue's neck — are all
  blocked on resolution rather than on method. The tooling to exploit a better
  scan already exists in this repo.
- **Which numerals do the clock hands point at?** Blocked on resolution and on
  the Great Seal overlapping the dial. A cleaner scan of the original, or the
  artist's source file, would likely settle it immediately.
- **Is there a BIP-39 passphrase?** `--passphrase` is supported. If the image
  hides a 13th-word passphrase, every phrase-only search misses.
- **Is the wallet even on the first address?** The schemes here scan five
  address indices per path. A deposit to a later index would be missed.
- **Was the image ever edited?** The hints mention hidden text under the Statue
  of Liberty's base recovered with error-level analysis. A systematic forensic
  pass over the full-resolution original may hold words nobody has listed.

---

## 13. Verification

Every cryptographic primitive is pinned to a published test vector, and the
search engine is tested against planted targets it must find:

```console
$ ./solve.py selftest
Ran 41 tests in 0.974s
OK
```

Covered: RIPEMD-160 reference vectors; BIP-39 Trezor vectors (entropy →
mnemonic → seed); BIP-32 test vector 1; the canonical
`abandon abandon … about` BIP-44 address chain; Base58Check round-trips; the
`correct horse battery staple` brainwallet; agreement between the fast checksum
filter and full mnemonic validation over 5,000 permutations; and end-to-end
recovery of planted targets on BIP-44, on `m/0/2`, with pinned positions, and
in brainwallet mode.

Derivation was additionally cross-checked against two independent
implementations — Trezor's `mnemonic` and the `bip32` package — over 200 random
mnemonics, with zero disagreements.
