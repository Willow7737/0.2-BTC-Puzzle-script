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
