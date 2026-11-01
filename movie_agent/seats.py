"""Seat choice by a fixed score, decided before the show opens so picking takes milliseconds.

The booker (phase 4) turns the site's seat map into `Seat`s; this module never touches the page.
"""

from dataclasses import dataclass

# Fraction of the hall, 0.0 = row nearest the screen, 1.0 = last row.
ROW_BANDS = {
    "front": (0.0, 0.35),
    "middle": (0.4, 0.75),
    "back": (0.7, 1.0),
    "any": (0.0, 1.0),
}


@dataclass(frozen=True)
class Seat:
    row: str  # label printed on the site, e.g. "H"
    row_index: int  # 0 = nearest the screen
    col: int  # physical column; a gap in numbers means an aisle
    available: bool
    price: int | None = None


def pick_seats(seats: list[Seat], n: int, pref: str = "middle", max_price: int | None = None) -> list[Seat] | None:
    """Best block of `n` side-by-side free seats, or None if no block fits.

    Ranking: inside the preferred row band first, then closest to the centre
    column, then closest to the middle of the band.
    """
    if n < 1 or not seats:
        return None
    lo, hi = ROW_BANDS[pref]
    last_row = max(s.row_index for s in seats) or 1
    centre = (min(s.col for s in seats) + max(s.col for s in seats)) / 2
    ideal = (lo + hi) / 2

    best, best_key = None, None
    for row_index in sorted({s.row_index for s in seats}):
        frac = row_index / last_row
        band_miss = max(lo - frac, 0, frac - hi)
        row = sorted((s for s in seats if s.row_index == row_index), key=lambda s: s.col)
        for i in range(len(row) - n + 1):
            block = row[i : i + n]
            if not all(_ok(s, max_price) for s in block):
                continue
            if block[-1].col - block[0].col != n - 1:  # aisle or missing seat inside the block
                continue
            mid = (block[0].col + block[-1].col) / 2
            key = (band_miss, abs(mid - centre), abs(frac - ideal))
            if best_key is None or key < best_key:
                best, best_key = block, key
    return best


def _ok(seat: Seat, max_price: int | None) -> bool:
    return seat.available and (max_price is None or seat.price is None or seat.price <= max_price)
