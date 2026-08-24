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
  len 21 confirmed only  : NOT searchable: 18 unresolved, 4.02e+59 phrases
  len 21 + all proposed  : NOT searchable:  6 unresolved, 1.48e+20 phrases
  len 24 confirmed only  : NOT searchable: 21 unresolved, 3.45e+69 phrases
  len 24 + all proposed  : NOT searchable:  9 unresolved, 1.27e+30 phrases
```

Enumeration, not PBKDF2, is the wall. Three unresolved positions is 2048³ ≈
8.6e9 — about an hour to enumerate and five to derive. Four is 2048⁴ ≈ 1.8e13,
roughly three months. **Three unresolved positions is the practical ceiling**,
so the map needs 18 more verified assignments before any search is worth
starting.

That is the whole game now. One more decoded clue is worth more than any
amount of hardware, and no amount of CPU substitutes for it.

## 4. Negative results

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

## 5. Electrum seeds: a whole search space nobody had checked

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

## 6. Why the original script could not have worked

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

## 7. What this toolkit does instead

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

## 8. Recommended search order

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

## 9. Coverage so far

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

## 10. The passphrase hypothesis

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

## 11. Open questions

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

## 12. Verification

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
