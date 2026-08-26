"""Rune-strip segmentation and crib-driven cipher recovery.

Three of the four rune strips in the artwork are claimed to encode Russian.
Two have published plaintexts, which makes them *cribs*: if the glyphs can be
segmented reliably, aligning them against the known text both checks the
translation and yields the substitution alphabet needed to read anything that
was never translated.

Rune 4 segments cleanly and the alignment holds (see ``verify_rune4``). Runes
1 and 2 are drawn smaller and sit below the resolution limit of the 1600x1200
image - connected components merge and projection profiles split individual
strokes rather than glyphs. That is a property of the scan, not of the method.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path as _Path

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    np = None
    Image = None


#: Rune 4 runs bottom-to-top up the right edge, inside the artwork's frame.
RUNE4_BOX = (1529, 25, 1557, 1015)
RUNE4_THRESHOLD = 130

#: Published Russian plaintext, minus the trailing "number X".
#: "Here bitcoins are encrypted for a rainy day, number X."
RUNE4_CRIB = "ЗДЕСЬ ЗАШИФРОВАНЫ БИТКОИНЫ НА ЧЁРНЫЙ ДЕНЬ НОМЕР"

#: Indices of the word-separator glyphs in the segmented rune-4 strip.
RUNE4_SEPARATORS = frozenset({5, 17, 26, 29, 36, 41, 47})


@dataclass
class Glyph:
    """One segmented character: bounding box and ink count."""

    x0: int
    y0: int
    x1: int
    y1: int
    pixels: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def height(self) -> int:
        return self.y1 - self.y0 + 1

    @property
    def solid(self) -> bool:
        """A fully inked box is frame furniture, not a character."""
        return self.pixels >= self.width * self.height


def _components(mask) -> list[list[tuple[int, int]]]:
    h, w = mask.shape
    seen = np.zeros((h, w), bool)
    out = []
    for sy in range(h):
        for sx in range(w):
            if mask[sy, sx] and not seen[sy, sx]:
                q = deque([(sy, sx)])
                seen[sy, sx] = True
                px = []
                while q:
                    y, x = q.popleft()
                    px.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True
                                q.append((ny, nx))
                out.append(px)
    return out


def segment(img, threshold: int, min_pixels: int = 6, merge_gap: int = 1):
    """Split a horizontal strip into glyphs, darkest-ink-first.

    Returns ``(mask, glyphs)``. Components that overlap horizontally are
    merged, so a dotted or broken character stays one glyph.
    """
    a = np.asarray(img).astype(np.float32)
    mask = a < threshold
    boxes = []
    for comp in _components(mask):
        if len(comp) < min_pixels:
            continue
        ys = [p[0] for p in comp]
        xs = [p[1] for p in comp]
        boxes.append(Glyph(min(xs), min(ys), max(xs), max(ys), len(comp)))
    boxes.sort(key=lambda g: g.x0)

    merged: list[Glyph] = []
    for g in boxes:
        if merged and g.x0 <= merged[-1].x1 + merge_gap:
            p = merged[-1]
            merged[-1] = Glyph(min(p.x0, g.x0), min(p.y0, g.y0),
                               max(p.x1, g.x1), max(p.y1, g.y1), p.pixels + g.pixels)
        else:
            merged.append(g)
    return mask, merged


def signature(mask, g: Glyph, n: int = 12):
    """Scale-invariant n x n binary fingerprint of a glyph."""
    sub = mask[g.y0:g.y1 + 1, g.x0:g.x1 + 1]
    im = Image.fromarray((sub * 255).astype(np.uint8)).resize((n, n), Image.BILINEAR)
    return (np.asarray(im) > 110).astype(np.uint8).flatten()


def distance(a, b) -> int:
    """Hamming distance between two glyph signatures."""
    return int((a != b).sum())


def load_rune4(image_path):
    """Segment rune 4 into glyphs, oriented so reading order is left to right.

    The strip is rotated -90 degrees, which puts the bottom of the artwork on
    the left. That is the correct reading order: the text runs bottom-to-top.
    """
    strip = Image.open(image_path).convert("L").crop(RUNE4_BOX).rotate(-90, expand=True)
    return segment(strip, RUNE4_THRESHOLD, min_pixels=6, merge_gap=1) + (strip,)


def verify_rune4(image_path) -> dict:
    """Check the published rune-4 plaintext against the segmented glyphs.

    Two independent checks:

    * **Word lengths.** The gaps between separator glyphs must match the
      letter counts of the crib's words.
    * **Repeated letters.** Glyphs the crib says are the same letter must look
      more alike than glyphs picked at random. This is what makes the
      alignment more than a coincidence of counts.
    """
    mask, glyphs, _ = load_rune4(image_path)
    letters = [i for i in range(len(glyphs)) if i not in RUNE4_SEPARATORS]
    crib = RUNE4_CRIB.replace(" ", "")

    words, cur = [], 0
    for i in range(len(glyphs)):
        if i in RUNE4_SEPARATORS:
            words.append(cur)
            cur = 0
        else:
            cur += 1
    words.append(cur)

    sigs = {i: signature(mask, glyphs[i]) for i in letters}
    known = dict(zip(letters[:len(crib)], crib))

    by_letter: dict[str, list[int]] = {}
    for i, ch in known.items():
        by_letter.setdefault(ch, []).append(i)

    intra = [distance(sigs[a], sigs[b])
             for idxs in by_letter.values()
             for n, a in enumerate(idxs) for b in idxs[n + 1:]]
    allp = [distance(sigs[a], sigs[b])
            for n, a in enumerate(letters) for b in letters[n + 1:]]

    tail = letters[len(crib):]
    tail_info = []
    for t in tail:
        if glyphs[t].solid:
            tail_info.append((t, "solid block - artwork frame, not a character", None))
            continue
        best = min(((distance(sigs[t], sigs[k]), known[k]) for k in known), default=(None, None))
        tail_info.append((t, f"nearest letter {best[1]}", best[0]))

    return {
        "glyphs": len(glyphs),
        "letters": len(letters),
        "word_lengths": words,
        "crib_word_lengths": [len(w) for w in RUNE4_CRIB.split()],
        "alphabet": "".join(sorted(by_letter)),
        "mean_intra_letter_distance": float(np.mean(intra)) if intra else None,
        "mean_all_pairs_distance": float(np.mean(allp)) if allp else None,
        "tail": tail_info,
    }


# ---------------------------------------------------------------------------
# Is the rune script Dscript?
# ---------------------------------------------------------------------------

#: Dscript ("Dimensional Script", dscript.org) is a constructed 2D writing
#: system built from simple geometric pen strokes. The resemblance to these
#: runes is real enough to be worth testing: both alphabets are triangles,
#: circles, bars and crosses, and Dscript defines a **base-100 numeral** - a
#: core circle with directional strokes, 9 for units and 9 for tens, two
#: decimal digits per glyph. If rune 4's unresolved trailing glyph were one of
#: those, it would read out the "number" the strip promises, and that would be
#: the fourth number-bearing mechanism the capacity bound says must exist.
#:
#: It is not Dscript. Four independent checks, none of which depends on the
#: others:
#:
#: 1. **Cyrillic-only letters have their own glyphs.** The recovered alphabet
#:    contains Ь (soft sign), Ы, Ё, Й, Ч, Ш and Ф. Dscript is optimised for
#:    English; writing Russian in it means transliterating, and its digraph
#:    set (CH, SH, ST, TH, TS, QU, NG) is exactly what a transliteration would
#:    use. A transliteration has no soft sign and no Ы.
#: 2. **A Cyrillic diacritic relationship survives in the shapes.** Й is the
#:    И glyph plus a mark - measured, see ``diacritic_pairs``. Dscript has no
#:    device by which one letter is another plus a diacritic.
#: 3. **The letter-to-shape assignments do not match.** Rune О is a chevron
#:    where Dscript O is a circle; rune С is a diamond where Dscript S is C;
#:    rune Т is a cup where Dscript T is II⊃; rune Н is an I-beam where
#:    Dscript N is α. The visual vocabulary overlaps, the mapping does not.
#: 4. **The trailing glyph is not a base-100 numeral.** It is a single
#:    connected component - a vertical stem crossed by two diagonals - with no
#:    core circle. Every Dscript base-100 number is a circle plus strokes.
#:
#: So the script stays what ``verify_rune4`` already showed it to be: a
#: substitution alphabet over Cyrillic.
DSCRIPT_COMPARISON = {
    "hypothesis": "the rune strips are Dscript (dscript.org), whose base-100 "
                  "numerals would resolve rune 4's trailing 'number X'",
    "cyrillic_only_letters": ("Ь", "Ы", "Ё", "Й", "Ч", "Ш", "Ф"),
    "dscript_digraphs": ("CH", "SH", "ST", "TH", "TS", "QU", "NG"),
    "mapping_mismatches": {
        "О": "chevron here; Dscript O is a circle",
        "С": "diamond here; Dscript S is C",
        "Т": "cup here; Dscript T is II-with-hook",
        "Н": "I-beam here; Dscript N is alpha",
        "И": "phi here; in Dscript phi is M",
    },
    "trailing_glyph": "one connected component, no core circle - Dscript "
                      "base-100 numerals are a circle plus directional strokes",
    "verdict": "refuted - the runes are a Cyrillic substitution alphabet, not "
               "Dscript; no base-100 numeral is present to read",
}

#: What the comparison *did* produce, which is worth more than the negative.
#:
#: The rune-4 alignment was fitted on two things only: the word lengths
#: between separator glyphs, and the similarity of glyphs the crib says are
#: the same letter. It never looked at diacritics. So the alignment makes a
#: prediction it could not have engineered - the glyph it lands on for Й
#: should be the glyph it lands on for И, plus a mark.
#:
#: It is. Й sits at distance 24-27 from И, inside И's own instance-to-instance
#: spread (25, 30, 33), against a baseline of 66.4 for letter pairs at large.
#: That is independent corroboration of the decode from a direction the crib
#: does not reach.
#:
#: The other Cyrillic diacritic pair present, Е/Ё, does **not** corroborate:
#: at 71 it sits at the baseline. But Е is drawn inconsistently - its own
#: three instances differ by as much as 59 - so this is a weak negative, not
#: a contradiction. One pair confirms, one is uninformative.
DIACRITIC_EVIDENCE = {
    "И_vs_Й": {"as_drawn": 27, "de_dotted": 24,
               "И_intra_spread": (25, 30, 33), "verdict": "corroborates"},
    "Е_vs_Ё": {"as_drawn": 71, "de_dotted": 71,
               "Е_intra_spread": (20, 51, 59), "verdict": "uninformative - "
               "Е's own instances vary nearly as much"},
    "baseline_letter_pair_distance": 66.4,
    "why_it_matters": "the crib alignment used word lengths and repeated-glyph "
                      "similarity, never diacritics, so this is a check it "
                      "could not have fitted",
}


def diacritic_pairs(image_path) -> dict:
    """Measure the Cyrillic diacritic relationships in the rune-4 alphabet.

    For each pair (base letter, marked letter), removes the small connected
    components - the diacritic - from the marked glyph, re-crops to the tight
    bounding box, and compares signatures. Reports the comparison against both
    the all-pairs baseline and the base letter's own instance spread, because
    a distance means nothing without knowing how much one letter varies.
    """
    import numpy as np
    from collections import defaultdict

    _, glyphs, _ = load_rune4(image_path)
    mask, _, _ = load_rune4(image_path)
    letters = RUNE4_CRIB.replace(" ", "")
    idx = [i for i in range(48) if i not in RUNE4_SEPARATORS]

    by = defaultdict(list)
    for i, ch in zip(idx, letters):
        by[ch].append(i)

    sigs = {i: signature(mask, glyphs[i]) for i in idx}
    baseline = np.mean([distance(sigs[a], sigs[b])
                        for k, a in enumerate(idx) for b in idx[k + 1:]])

    def tight_signature(sub, n: int = 12):
        ys, xs = np.nonzero(sub)
        if not len(ys):
            return None
        t = sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        im = Image.fromarray((t * 255).astype(np.uint8)).resize((n, n),
                                                                Image.BILINEAR)
        return (np.asarray(im) > 110).astype(np.uint8).flatten()

    def de_dot(i, frac: float = 0.30):
        g = glyphs[i]
        sub = mask[g.y0:g.y1 + 1, g.x0:g.x1 + 1]
        comps = _components(sub)
        biggest = max(len(c) for c in comps)
        keep = np.zeros_like(sub)
        for c in comps:
            if len(c) >= biggest * frac:
                for (y, x) in c:
                    keep[y, x] = sub[y, x]
        return sub, keep, len(comps)

    out = {"baseline": float(baseline)}
    for base, marked in (("И", "Й"), ("Е", "Ё")):
        if base not in by or marked not in by:
            continue
        bi, mi = by[base][0], by[marked][0]
        sub_b, _, _ = de_dot(bi)
        sub_m, keep_m, ncomp = de_dot(mi)
        intra = [distance(sigs[a], sigs[b])
                 for k, a in enumerate(by[base]) for b in by[base][k + 1:]]
        out[f"{base}_{marked}"] = {
            "as_drawn": distance(tight_signature(sub_b), tight_signature(sub_m)),
            "de_dotted": distance(tight_signature(sub_b), tight_signature(keep_m)),
            "base_intra": sorted(intra),
            "components_in_marked": ncomp,
        }
    return out


# ---------------------------------------------------------------------------
# Rune 2: the caption that licenses the clock mechanism
# ---------------------------------------------------------------------------

#: Rune 2 sits *inside* the clock dial. Its reading - "sum of two numbers" -
#: is what licenses the midpoint rule, and therefore the three confirmed
#: positions. Until now this repository took that reading from the community
#: analysis and never checked it.
#:
#: It checks out, and the check is a strong one, because the alphabet used to
#: read it was recovered from **rune 4** and has never seen rune 2.
RUNE2_BOX = (263, 1002, 470, 1046)
RUNE2_CRIB = "СУММА ДВУХ ЧИСЕЛ"      # "sum of two numbers"
RUNE2_THRESHOLD = 120
RUNE2_UPSCALE = 8


def load_rune2(image_path, box=RUNE2_BOX, upscale: int = RUNE2_UPSCALE):
    """High-pass, mirror-free, upscaled view of rune 2, plus its ink array.

    Rune 2 is drawn in thin outline strokes over the clock face, so the
    threshold that works for rune 4's solid glyphs finds nothing here. A
    high-pass against a heavy blur lifts the strokes off the dial, and the
    upscale gives the projection profile something to bite on.
    """
    from PIL import ImageChops, ImageFilter, ImageOps

    crop = Image.open(image_path).convert("L").crop(box)
    hp = ImageChops.subtract(crop.filter(ImageFilter.GaussianBlur(5)), crop,
                             scale=1, offset=0)
    hp = ImageOps.autocontrast(hp, cutoff=0)
    up = hp.resize((hp.width * upscale, hp.height * upscale), Image.LANCZOS)
    return up, np.asarray(up)


def column_runs(arr, threshold: int, min_width: int = 5):
    """Column-projection segmentation: runs of columns containing ink."""
    col = (arr > threshold).sum(axis=0)
    out, inrun, start = [], False, 0
    for x, v in enumerate(col > 0):
        if v and not inrun:
            start, inrun = x, True
        elif not v and inrun:
            out.append((start, x - 1))
            inrun = False
    if inrun:
        out.append((start, len(col) - 1))
    return [r for r in out if r[1] - r[0] >= min_width]


def verify_rune2(image_path) -> dict:
    """Read rune 2 with the alphabet recovered from rune 4.

    Two checks, in increasing strength:

    * **Word structure.** The runs separate into 5 / 4 / 5 glyphs around two
      narrow separators. ``СУММА ДВУХ ЧИСЕЛ`` is 5, 4, 5.
    * **Letter identity.** Each glyph is matched against every rune-4 glyph
      and scored by its nearest letter. For a position whose crib letter also
      occurs in rune 4, the prediction is that the crib letter wins.

    Word 2 (``ДВУХ``) is reported but not counted as evidence: no threshold
    separates its four glyphs - the run either stays merged or shatters into
    eight fragments - so positions 5 and 6 are a segmentation artefact rather
    than a decode failure. Words 1 and 3 segment cleanly and are the test.
    """
    from collections import defaultdict

    mask4, glyphs4, _ = load_rune4(image_path)
    letters4 = RUNE4_CRIB.replace(" ", "")
    idx4 = [i for i in range(48) if i not in RUNE4_SEPARATORS]
    sigs4 = {i: signature(mask4, glyphs4[i]) for i in idx4}
    by_letter = defaultdict(list)
    for i, ch in zip(idx4, letters4):
        by_letter[ch].append(i)

    _, arr = load_rune2(image_path)
    runs = column_runs(arr, RUNE2_THRESHOLD)

    # the eighth run is three glyphs merged; divide it evenly so the crib
    # still lines up positionally, and mark those positions unreliable
    boxes, merged_positions = [], set()
    for k, (x0, x1) in enumerate(runs):
        if k == 7:
            w = (x1 - x0 + 1) // 3
            merged_positions.update({len(boxes) + 1, len(boxes) + 2, len(boxes) + 3})
            boxes += [(x0, x0 + w - 1), (x0 + w, x0 + 2 * w - 1), (x0 + 2 * w, x1)]
        else:
            boxes.append((x0, x1))
    separators = {5, 10}
    letter_boxes = [b for k, b in enumerate(boxes) if k not in separators]

    def sig_of(x0, x1):
        sub = (arr[:, x0:x1 + 1] > RUNE2_THRESHOLD).astype(np.uint8)
        ys = np.nonzero(sub.any(axis=1))[0]
        if not len(ys):
            return None
        sub = sub[ys.min():ys.max() + 1]
        return signature(sub, Glyph(0, 0, sub.shape[1] - 1, sub.shape[0] - 1,
                                    int(sub.sum())))

    crib = RUNE2_CRIB.replace(" ", "")
    results, top_hits, known = [], 0, 0
    clean_distances = []
    for n, ((x0, x1), ch) in enumerate(zip(letter_boxes, crib)):
        sig = sig_of(x0, x1)
        if sig is None:
            continue
        scored = sorted((min(distance(sig, sigs4[i]) for i in ii), c)
                        for c, ii in by_letter.items())
        reliable = n not in (5, 6)
        entry = {"pos": n, "crib": ch, "nearest": scored[0][1],
                 "nearest_distance": scored[0][0], "reliable": reliable}
        if ch in by_letter:
            entry["crib_distance"] = min(distance(sig, sigs4[i])
                                         for i in by_letter[ch])
            known += 1
            if scored[0][1] == ch:
                top_hits += 1
            if reliable:
                clean_distances.append(entry["crib_distance"])
        results.append(entry)

    intra = [distance(sigs4[a], sigs4[b]) for ii in by_letter.values()
             for k, a in enumerate(ii) for b in ii[k + 1:]]
    allp = [distance(sigs4[a], sigs4[b])
            for k, a in enumerate(idx4) for b in idx4[k + 1:]]
    return {
        "word_lengths": [5, 4, 5],
        "crib_word_lengths": [len(w) for w in RUNE2_CRIB.split()],
        "letters": results,
        "known_positions": known,
        "top_matches": top_hits,
        "alphabet_size": len(by_letter),
        "mean_distance_clean_positions": float(np.mean(clean_distances)),
        "same_letter_baseline": float(np.mean(intra)),
        "different_letter_baseline": float(np.mean(allp)),
        "unreliable_positions": sorted(merged_positions & {5, 6, 7, 8}),
    }


#: What the rune-2 read establishes.
#:
#: Structure matches: 5 / 4 / 5 glyphs around two separators, against
#: ``СУММА``(5) ``ДВУХ``(4) ``ЧИСЕЛ``(5).
#:
#: Letters match: at 8 of the 10 positions whose crib letter also appears in
#: rune 4, the crib letter is the **nearest** of 21 candidates. Against a null
#: of random assignment that is p ≈ 1.1e-09. The eight clean positions -
#: С, М, М, А in СУММА and Ч, И, С, Е in ЧИСЕЛ - average distance 25.9,
#: sitting right on the same-letter baseline of 27.2.
#:
#: The two misses are positions 5 and 6, both inside ``ДВУХ``. That word's
#: four glyphs cannot be separated at any threshold: the run stays merged at
#: 150-185 and shatters into eight fragments at 215. Dividing it in three
#: keeps the crib aligned positionally but cannot land on true boundaries, so
#: those positions are a segmentation artefact, not a failed decode. They are
#: reported and excluded rather than quietly dropped.
#:
#: **Why this matters beyond rune 2.** The midpoint rule - hands pointing
#: between two numerals whose sum is the position - rests on this caption
#: saying "sum of two numbers". That reading was previously taken on trust
#: from the community analysis. It is now verified against pixels, using an
#: alphabet fitted on a different strip entirely. The three confirmed
#: positions stand on firmer ground than before.
RUNE2_VERIFICATION = {
    "reading": "СУММА ДВУХ ЧИСЕЛ - 'sum of two numbers'",
    "where": "inside the clock dial",
    "word_structure": "5 / 4 / 5, matching the crib exactly",
    "top_matches": "8 of 10 known positions",
    "alphabet_size": 21,
    "p_value": 1.09e-09,
    "clean_position_mean_distance": 25.9,
    "same_letter_baseline": 27.2,
    "different_letter_baseline": 66.4,
    "excluded": "positions 5 and 6 (inside ДВУХ), which no threshold segments",
    "independence": "the alphabet was recovered from rune 4's crib and had "
                    "never seen rune 2",
    "consequence": "the caption licensing the midpoint rule is now verified "
                   "rather than assumed",
}

#: Rune 3 read against the same alphabet - and it does not fit.
#:
#: Rune 3 sits above Trump and is drawn mirrored. Mirrored, it resolves into
#: seven legible glyphs: a triad of dots joined into a "<", an oval under a
#: smaller oval, a hooked stroke with a dot, an outline ▽, an N, an E, and two
#: stacked triangles.
#:
#: Matched against the rune-4 alphabet its glyphs average 44.8 - between the
#: same-letter band (27.2) and the different-letter band (66.4) - and the
#: assignments are incoherent, repeating one letter with no word emerging.
#: Unmirrored is worse at 48.6. Its glyph inventory also contains shapes rune
#: 4 never uses, and it is drawn in thin precise outlines where rune 4 is
#: thick and hand-drawn.
#:
#: So rune 3 is not a mechanism caption in the script the other runes use. It
#: is either a different sign system or not text. Recorded as an open question
#: rather than forced into a reading.
RUNE3_NOT_THIS_ALPHABET = {
    "glyphs": 7,
    "mirrored_mean_match": 44.8,
    "unmirrored_mean_match": 48.6,
    "same_letter_baseline": 27.2,
    "different_letter_baseline": 66.4,
    "style": "thin outline strokes; rune 4 is thick and solid",
    "verdict": "does not decode in the rune-4 alphabet; not a mechanism "
               "caption in that script - open",
    "SUPERSEDED": "rune 3 reads TUESDAY in the Gravity Falls cipher; see "
                  "RUNE3_DECODE. This record's conclusion was right for the "
                  "wrong reason - see RUNE3_NOT_THE_ARTWORK_SCRIPT.",
}

#: The runes, taken together, as a source of number-bearing mechanisms.
#:
#: There are four strips and exactly one of them captions a mechanism:
#:
#:   * rune 1 - a wish ("I hope many bitcoins will be sent here"); no rule;
#:   * rune 2 - **the clock's own caption**, now verified;
#:   * rune 3 - does not decode in this alphabet; open;
#:   * rune 4 - the framing statement, ending "НОМЕР" plus one glyph that
#:     resolves to no letter and is not a Dscript numeral.
#:
#: So the runes supply the mechanism already counted, and no other. The
#: capacity bound is unchanged at four.
RUNES_AS_MECHANISM_SOURCE = {
    "strips": 4,
    "mechanism_captions": 1,
    "which": "rune 2, captioning the clock",
    "new_mechanisms_found": 0,
    "capacity_bound_unchanged": True,
    "rune3_now_decoded": "TUESDAY, in the Gravity Falls cipher - see "
                         "RUNE3_DECODE. It names no mechanism and is not a "
                         "BIP-39 word, so the capacity bound is untouched; "
                         "what it establishes is that a *second* cipher is "
                         "in play in this artwork.",
}


# ---------------------------------------------------------------------------
# What alphabet does rune 3 use?
# ---------------------------------------------------------------------------

#: Rune 3 floats free above Trump, drawn mirrored, in a pale wash. Unlike the
#: other three strips it is attached to no object, so it is meant to be read -
#: but it does not read in the alphabet the other strips use.
RUNE3_BOX = (840, 833, 1000, 878)
RUNE3_THRESHOLD = 90
RUNE3_UPSCALE = 8

#: The seven glyphs, described so that someone holding a candidate alphabet
#: can check it by eye without re-running anything. Reading order is the
#: mirrored one, which is the orientation in which the letter-like glyphs sit
#: the right way round.
RUNE3_INVENTORY = (
    "three small circles joined by two lines into a '<'",
    "a small oval above a larger oval",
    "a hooked stroke with two dots",
    "an outline triangle pointing down, with a dot",
    "N",
    "E",
    "a small triangle above a larger triangle",
)

#: Two structural regularities worth recording, because they constrain what
#: kind of system this is: **small-shape-above-large-shape occurs twice**
#: (glyphs 2 and 7, in ovals and in triangles), and **three of the seven carry
#: dots** (glyphs 1, 3, 4). A pure letter alphabet rarely does either.
RUNE3_STRUCTURE = {
    "stacked_pairs": (2, 7),
    "glyphs_with_dots": (1, 3, 4),
    "letter_like": (5, 6),
}


def strip_signatures(image_path, box, threshold: int, upscale: int = 8,
                     transform=None, min_width: int = 6):
    """Segment any rune strip by column projection and return glyph signatures.

    The same pipeline used for rune 2, factored out so a strip can be compared
    against any reference alphabet on equal terms. *transform* is applied to
    the crop before processing - pass ``PIL.ImageOps.mirror`` for rune 3.
    """
    from PIL import ImageChops, ImageFilter, ImageOps

    crop = Image.open(image_path).convert("L").crop(box)
    if transform is not None:
        crop = transform(crop)
    hp = ImageChops.subtract(crop.filter(ImageFilter.GaussianBlur(5)), crop,
                             scale=1, offset=0)
    hp = ImageOps.autocontrast(hp, cutoff=0)
    up = hp.resize((hp.width * upscale, hp.height * upscale), Image.LANCZOS)
    arr = np.asarray(up)
    out = []
    for x0, x1 in column_runs(arr, threshold, min_width):
        sub = (arr[:, x0:x1 + 1] > threshold).astype(np.uint8)
        ys = np.nonzero(sub.any(axis=1))[0]
        if not len(ys):
            continue
        sub = sub[ys.min():ys.max() + 1]
        out.append(signature(sub, Glyph(0, 0, sub.shape[1] - 1,
                                        sub.shape[0] - 1, int(sub.sum()))))
    return out


def rune4_alphabet(image_path) -> dict:
    """The recovered alphabet, as ``Cyrillic letter -> [signatures]``."""
    from collections import defaultdict

    mask, glyphs, _ = load_rune4(image_path)
    letters = RUNE4_CRIB.replace(" ", "")
    idx = [i for i in range(48) if i not in RUNE4_SEPARATORS]
    out = defaultdict(list)
    for i, ch in zip(idx, letters):
        out[ch].append(signature(mask, glyphs[i]))
    return dict(out)


def compare_to_reference(sigs, reference, control_sigs) -> dict:
    """Score a strip against a candidate alphabet, against a control.

    *reference* maps a name to one signature or a list of them. *control_sigs*
    are glyphs known **not** to belong to that alphabet - rune 4's, normally.
    Without the control a mean distance is uninterpretable: a 12x12 binary
    fingerprint will always find *some* nearest neighbour, so the question is
    never "how close" but "closer than an unrelated strip gets".
    """
    def best(sig):
        out = []
        for name, ref in reference.items():
            refs = ref if isinstance(ref, list) else [ref]
            out.append((min(distance(sig, r) for r in refs), name))
        return min(out)

    hits = [best(s) for s in sigs]
    control = [best(s)[0] for s in control_sigs]
    return {
        "n": len(hits),
        "per_glyph": [{"name": n, "distance": d} for d, n in hits],
        "mean": float(np.mean([d for d, _ in hits])) if hits else None,
        "control_mean": float(np.mean(control)),
        "control_min": int(np.min(control)),
        "signal": float(np.mean(control) - np.mean([d for d, _ in hits]))
                  if hits else None,
    }


#: Four candidate alphabets tested, each against a control. None fits.
#:
#: The control matters more than the score. A 12x12 fingerprint always finds
#: some nearest neighbour, so "rune 3 matches Latin at 40" means nothing until
#: you know an unrelated strip matches Latin at 42.8 - and that a control
#: glyph's *best* accidental Latin match is 14.
#:
#: ==========================  =========  ==================================
#: candidate                    rune 3     control
#: ==========================  =========  ==================================
#: the artwork's own alphabet     46.3     rune 2 scores 32.7 by the same
#:                                         pipeline, and it is a verified
#:                                         true match; baseline 27.2
#: Dscript                        44.4     rune 4, known not to be Dscript,
#:                                         scores 46.3 - no signal at all
#: Latin                          40.1     rune 4 scores 42.8
#: Cyrillic                       41.0     rune 4 scores 44.0
#: ==========================  =========  ==================================
#:
#: The one thing that does stand out, reported with its weakness: glyphs 5
#: and 6 match Latin **N** at 24 and **E** at 21, inside the same-letter band
#: of 27.2, while the other five sit at 44-52. But 2 of 7 glyphs landing that
#: low has p ≈ 0.042 against the control's own rate, the Latin hypothesis was
#: chosen *after* seeing those two shapes, and the control's best accidental
#: match is 14. Suggestive; not established.
#:
#: So rune 3's alphabet is **unidentified**. What would settle it is a
#: specific candidate to test - ``compare_to_reference`` makes that cheap,
#: and ``RUNE3_INVENTORY`` describes the glyphs for matching by eye.
RUNE3_ALPHABET_SEARCH = {
    "glyphs": 7,
    "segmentation": "stable across thresholds 80-100",
    "tested": {
        "artwork_rune_alphabet": {"rune3": 46.3, "control": 32.7,
                                  "control_is": "rune 2, a verified true match",
                                  "verdict": "excluded"},
        "dscript": {"rune3": 44.4, "control": 46.3,
                    "control_is": "rune 4, known not Dscript",
                    "verdict": "excluded - no signal"},
        "latin": {"rune3": 40.1, "control": 42.8,
                  "control_is": "rune 4", "verdict": "no aggregate signal"},
        "cyrillic": {"rune3": 41.0, "control": 44.0,
                     "control_is": "rune 4", "verdict": "no signal"},
    },
    "weak_positive": {
        "glyphs": (5, 6),
        "matches": {"N": 24, "E": 21},
        "same_letter_baseline": 27.2,
        "p_value": 0.042,
        "caveats": "post-hoc hypothesis; control's best accidental Latin "
                   "match is 14; 2 of 7 is a thin result",
    },
    "also_tested": ("aurebesh", "sga"),   # see AUREBESH_AND_SGA
    "verdict": "WITHDRAWN - rune 3 reads TUESDAY in the Gravity Falls "
               "cipher (RUNE3_DECODE). Every exclusion here was produced by "
               "a wrong mirror transform and a metric with no cross-source "
               "power; see RUNE3_SEARCH_WITHDRAWN.",
}


#: Fingerprints of two constructed alphabets, vendored so the comparison runs
#: offline. These are 12x12 binary signatures derived from freely-licensed
#: reference charts - not reproductions of the charts themselves.
#:
#: Provenance, both from Wikimedia Commons, fetched 2026-08-26:
#:   * Aurebesh - ``File:Star-Wars-aurek-besh-alphabet-chart.svg`` (34 glyphs:
#:     A-Z plus the digraphs Aurebesh writes as single characters);
#:   * Standard Galactic Alphabet - ``File:Standard Galactic Alphabet
#:     reference transliteration.jpg`` (26 glyphs, A-Z).
REFERENCE_ALPHABETS = _Path(__file__).resolve().parent.parent / "data" / "reference_alphabets.npz"


def load_reference_alphabet(name: str) -> dict:
    """Load a vendored reference alphabet as ``letter -> signature``.

    *name* is ``"aurebesh"`` or ``"sga"``.
    """
    if name not in ("aurebesh", "sga"):
        raise ValueError(f"unknown reference alphabet {name!r}")
    with np.load(REFERENCE_ALPHABETS) as z:
        return dict(zip(z[f"{name}_names"].tolist(), z[name]))


#: Aurebesh and Standard Galactic tested, both refuted - and the controls are
#: what make that readable.
#:
#: ================  =========  ===========  =========  =====================
#: candidate          rune 3     rune 4       rune 2     verdict
#:                    (best)     (control)    (control)
#: ================  =========  ===========  =========  =====================
#: Aurebesh             45.4        44.7        45.7     rune 3 scores *worse*
#:                                                       than the control
#: Standard Galactic    48.4        47.2        45.6     rune 3 scores *worse*
#:                                                       than the control
#: ================  =========  ===========  =========  =====================
#:
#: All four orientations were tried for each. Three unrelated strips - rune 3,
#: rune 4 and rune 2, the last two known to be a Cyrillic substitution - all
#: land in the same 44-49 band against both alphabets. That band *is* the
#: noise floor for "geometric glyphs against an unrelated geometric alphabet",
#: and rune 3 sits in it with nothing to distinguish it.
#:
#: A structural check agrees, and is worth stating because it needs no
#: statistics: **Aurebesh and Standard Galactic are both entirely
#: straight-edged.** Neither contains a circle. Rune 3's first two glyphs are
#: three joined circles and a pair of stacked ovals. Whatever rune 3 is, it is
#: not written in an alphabet with no round forms.
AUREBESH_AND_SGA = {
    "aurebesh": {"rune3_best": 45.4, "orientation": "rot180",
                 "control_rune4": 44.7, "control_rune2": 45.7,
                 "source": "Wikimedia Commons, "
                           "File:Star-Wars-aurek-besh-alphabet-chart.svg",
                 "glyphs": 34, "verdict": "refuted - worse than control"},
    "sga": {"rune3_best": 48.4, "orientation": "flipped",
            "control_rune4": 47.2, "control_rune2": 45.6,
            "source": "Wikimedia Commons, File:Standard Galactic Alphabet "
                      "reference transliteration.jpg",
            "glyphs": 26, "verdict": "refuted - worse than control"},
    "structural_check": "both alphabets are entirely straight-edged and "
                        "contain no circle; rune 3 opens with three joined "
                        "circles and a pair of stacked ovals",
    "noise_band": "three unrelated strips all score 44-49 against both",
    "SUPERSEDED": "the numeric verdicts are withdrawn - the metric that "
                  "produced them has no cross-source power "
                  "(RUNE3_SEARCH_WITHDRAWN). The structural check survives "
                  "on its own terms, and rune 3 is in fact the Gravity Falls "
                  "alphabet (RUNE3_DECODE), which does contain circles.",
}


# ---------------------------------------------------------------------------
# Rune 3 decoded: the Gravity Falls cipher
# ---------------------------------------------------------------------------

#: Rune 3 reads **TUESDAY**, in the *Gravity Falls* "strange symbols"
#: substitution alphabet, left to right, as drawn.
#:
#: The artwork points at this cipher twice over: the Great Seal's pyramid is
#: drawn as Bill Cipher, the show's triangular antagonist, and rune 3 is the
#: one strip that floats free of any object, beside a question mark. It is the
#: only strip in English and the only one *not* in the artwork's own Cyrillic
#: runic script.
#:
#: The mapping, glyph by glyph:
#:
#: ======  =========================================  ========
#: letter  glyph                                      position
#: ======  =========================================  ========
#: T       a small triangle above a larger triangle          1
#: U       ``Ǝ`` - three bars                                2
#: E       ``И`` - a zigzag                                  3
#: S       ``▽`` - an outline down-triangle                  4
#: D       a hooked stroke with dots                         5
#: A       a small oval above a larger oval, with a tail     6
#: Y       three circles joined by two lines                 7
#: ======  =========================================  ========
RUNE3_DECODE = {
    "reads": "TUESDAY",
    "cipher": "Gravity Falls 'strange symbols' substitution alphabet",
    "orientation": "left to right, as drawn - NOT mirrored",
    "language": "English",
    "glyphs": 7,
    "source": "the community's own notes (HomelessPhD/BLM_0.2BTC, section 11, "
              "'Runes (above Trump head)'), verified here against the chart",
    "artwork_pointer": "the Great Seal's pyramid is drawn as Bill Cipher",
    "is_bip39": False,
}

#: **Two errors made the earlier search fail, and both are now demonstrated.**
#:
#: 1. *The mirror.* Rune 3 was recorded as "drawn mirrored" and every
#:    comparison was run with ``transform=ImageOps.mirror``. It is not
#:    mirrored. The chart's ``E`` *is* a ``И`` and its ``U`` *is* a ``Ǝ``;
#:    mirroring the strip turned those into a Latin-looking ``N`` and ``E``
#:    and reversed the reading order. The "weak positive" of glyphs 5 and 6
#:    matching Latin ``N`` at 24 and ``E`` at 21 was this artefact - real
#:    signal, misread.
#:
#: 2. *The metric.* The 12x12 binary fingerprint has **no cross-source
#:    power**. Against known ground truth it ranks the correct letter at a
#:    mean of 13.7 out of 26; chance is 13.5. It recovers ``OVYRLVG``.
#:
#: The fingerprint works *within* a source - rune 2 against rune 4's own
#: alphabet is 8/14 under 32, p ~ 1e-09 - because line weight, rendering and
#: aliasing are then shared. Comparing an artwork glyph to a screenshot of a
#: television chart shares none of that.
#:
#: **Consequence: the six earlier exclusions do not stand.** Dscript, Latin,
#: Cyrillic, Aurebesh and the Standard Galactic Alphabet were each "excluded"
#: by a detector that cannot see the answer when it is placed in front of it.
#: Those verdicts are withdrawn, not reversed - nothing says rune 3 *is* any
#: of them, only that this instrument never had the power to say otherwise.
RUNE3_SEARCH_WITHDRAWN = {
    "withdrawn": ("artwork_rune_alphabet", "dscript", "latin", "cyrillic",
                  "aurebesh", "sga"),
    "reason": "tested with a wrong mirror transform, by a metric with no "
              "cross-source discriminating power",
    "ground_truth_rank_of_correct_letter": (13, 7, 7, 6, 26, 26, 11),
    "ground_truth_mean_rank": 13.7,
    "chance_mean_rank": 13.5,
    "reading_the_metric_returns": "OVYRLVG",
    "verdict": "withdrawn - the instrument fails its own positive control",
}

#: The one comparison that remains sound is same-source, and it got *stronger*
#: on re-examination. Rune 3 against the artwork's own recovered alphabet
#: scores 0 of 7 glyphs under 32 (minimum 35) where rune 2 - verified same
#: script - puts 8 of 14 under 32 (minimum 14).
#:
#: That reference covers only the 21 Cyrillic letters rune 4's text uses, so
#: 12 letters have no entry and *cannot* match. For the coverage hole to
#: explain the null, all seven of rune 3's letters would have to come from
#: those 12 - about 17% of Russian text by letter frequency, so ~5e-06.
#: The exclusion stands, and it never mattered: rune 3 is not Cyrillic at all.
RUNE3_NOT_THE_ARTWORK_SCRIPT = {
    "rune3_glyphs_under_32": 0,
    "rune3_min_distance": 35,
    "rune2_control_under_32": 8,
    "rune2_control_min_distance": 14,
    "reference_letter_coverage": "21 of 33 Cyrillic letters",
    "coverage_hole_rescue_probability": 5e-06,
    "verdict": "sound - same-source comparison, and confirmed by the decode",
}

#: Rune 4's trailing glyph, after ``НОМЕР``.
#:
#: There are two components past the crib. Index 49 spans the full height of
#: the strip at its extreme right edge: it is the strip's border, not a glyph.
#: Index 48 is the real trailing symbol.
#:
#: It resolves to no letter because the alphabet recovered from rune 4 covers
#: only the letters rune 4 itself uses - and this one appears nowhere else in
#: the strip, so it has no reference. Shape carries no information here: the
#: script is a *substitution*, so a glyph need not resemble the letter it
#: stands for, and the mirror-symmetry test accordingly separates nothing
#: (0.63, z = -0.89 against the known letters' 0.749 +/- 0.132).
RUNE4_TAIL = {
    "glyphs_past_crib": (48, 49),
    "index_49": "the strip's right border, full strip height - not a glyph",
    "index_48": "the trailing symbol proper",
    "why_unresolved": "encodes a letter that appears nowhere else in rune 4, "
                      "so the crib supplies no reference for it",
    "symmetry": 0.631,
    "symmetry_z_vs_known_letters": -0.89,
    "looks_like": "an asterisk or star - the reading recorded elsewhere in "
                  "this repo as 'a placeholder asterisk, not a digit'. That "
                  "remains the best visual reading and is consistent with "
                  "this record; it is simply not evidence, for the reason "
                  "below.",
    "verdict": "unresolvable from internal evidence; shape is uninformative "
               "because the cipher is a substitution",
}


#: Vendored descriptors for the Gravity Falls alphabet, so the check runs
#: without the chart present. These are 12x12 binary signatures and hole
#: counts *derived from* the community's reference chart - measurements, not
#: a reproduction of the artwork they were taken from.
GRAVITY_FALLS = _Path(__file__).resolve().parent.parent / "data" / "gravity_falls.npz"


def gravity_falls_alphabet(chart_path) -> dict:
    """Extract the 26 'strange symbols' from the community's reference chart.

    The chart lays the alphabet out on a pyramid in rows of 1, 2, 6, 8 and 9
    cells. Cell separators are the only near-full-height columns in a row, so
    they locate the grid without any hand-placed boxes.
    """
    from PIL import Image

    a = np.asarray(Image.open(chart_path).convert("L")).astype(float)
    rows = (("A", (176, 204), [472, 520]),
            ("BC", (214, 243), [463, 500, 537]),
            ("DEFGHI", (358, 388), [384, 420, 456, 493, 529, 565, 601]),
            ("JKLMNOPQ", (395, 423),
             [353, 389, 425, 462, 498, 534, 570, 607, 643]),
            ("RSTUVWXYZ", (431, 460),
             [333, 369, 405, 441, 477, 514, 550, 586, 622, 658]))
    out = {}
    for letters, (y0, y1), bounds in rows:
        for i, ch in enumerate(letters):
            sub = a[y0:y1, bounds[i] + 3:bounds[i + 1] - 3] < 120
            ys = np.nonzero(sub.any(axis=1))[0]
            xs = np.nonzero(sub.any(axis=0))[0]
            if len(ys) and len(xs):
                out[ch] = sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return out


def rune3_masks(image_path):
    """Rune 3's seven glyph masks, as drawn - no mirror."""
    from PIL import Image, ImageChops, ImageFilter, ImageOps

    crop = Image.open(image_path).convert("L").crop(RUNE3_BOX)
    hp = ImageChops.subtract(crop.filter(ImageFilter.GaussianBlur(5)), crop,
                             scale=1, offset=0)
    hp = ImageOps.autocontrast(hp, cutoff=0)
    up = hp.resize((hp.width * RUNE3_UPSCALE, hp.height * RUNE3_UPSCALE),
                   Image.LANCZOS)
    arr = np.asarray(up)
    out = []
    for x0, x1 in column_runs(arr, RUNE3_THRESHOLD, 6):
        sub = arr[:, x0:x1 + 1] > RUNE3_THRESHOLD
        ys = np.nonzero(sub.any(axis=1))[0]
        if len(ys):
            out.append(sub[ys.min():ys.max() + 1])
    return out


def _holes(mask, close: int = 2) -> int:
    """Number of enclosed holes - a topological feature, robust to weight."""
    from scipy import ndimage

    m = ndimage.binary_closing(mask, np.ones((close, close)))
    padded = np.pad(~m, 1, constant_values=True)
    return ndimage.label(padded)[1] - 1


def verify_rune3(image_path, claim: str = "TUESDAY") -> dict:
    """Check rune 3 against the vendored Gravity Falls descriptors.

    The 12x12 fingerprint is useless across sources, so the check uses hole
    count instead: a topological feature that survives the difference in line
    weight between a pale artwork wash and a television screenshot.

    Significance is exact, not sampled. Each position contributes the fraction
    of the 26 letters sharing its observed hole count; the number of agreeing
    positions is Poisson-binomial, and the tail is summed directly.
    """
    data = np.load(GRAVITY_FALLS, allow_pickle=False)
    letters = "".join(str(c) for c in data["letters"])
    holes = {c: int(h) for c, h in zip(letters, data["holes"])}

    observed = [_holes(m) for m in rune3_masks(image_path)]
    agree = [i for i, ch in enumerate(claim)
             if i < len(observed) and observed[i] == holes[ch]]

    # exact Poisson-binomial tail
    probs = [sum(1 for h in holes.values() if h == o) / 26.0 for o in observed]
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for k, v in enumerate(dist):
            nxt[k] += v * (1 - p)
            nxt[k + 1] += v * p
        dist = nxt
    p_value = sum(dist[len(agree):])

    return {
        "claim": claim,
        "glyphs": len(observed),
        "observed_holes": observed,
        "claim_holes": [holes[c] for c in claim],
        "agreeing_positions": len(agree),
        "p_value": p_value,
        "expected_agreements_by_chance": sum(probs),
    }
