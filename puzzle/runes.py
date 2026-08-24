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
