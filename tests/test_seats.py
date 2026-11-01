from movie_agent.seats import Seat, pick_seats

ROWS = "ABCDEFGHIJ"  # A nearest the screen


def hall(taken=(), aisle_after=None, prices=None, cols=12):
    """10 rows x `cols` seats. `taken` holds labels like "E6"; `aisle_after` skips a column number."""
    seats = []
    for r, label in enumerate(ROWS):
        col = 0
        for n in range(1, cols + 1):
            col += 1
            if aisle_after and n == aisle_after + 1:
                col += 1  # physical gap
            seats.append(Seat(label, r, col, f"{label}{n}" not in taken, (prices or {}).get(label)))
    return seats


def labels(block):
    return [f"{s.row}{s.col}" for s in block]


def test_two_seats_middle_rows_centre():
    block = pick_seats(hall(), 2, "middle")
    assert block[0].row in "EFGH"
    assert labels(block) in (["F6", "F7"], ["G6", "G7"])


def test_skips_taken_seats_and_stays_central():
    taken = {f"{r}{c}" for r in "EFGH" for c in (6, 7)}
    block = pick_seats(hall(taken=taken), 2, "middle")
    assert block[0].row in "EFGH"
    assert {s.col for s in block} in ({4, 5}, {8, 9})


def test_block_never_spans_an_aisle():
    # Aisle after seat 6: seats 6 and 7 are not together.
    block = pick_seats(hall(aisle_after=6), 2, "middle")
    cols = [s.col for s in block]
    assert cols[1] - cols[0] == 1


def test_price_cap_pushes_to_cheaper_rows():
    prices = {r: (400 if r in "ABCDE" else 250) for r in ROWS}
    block = pick_seats(hall(prices=prices), 3, "front", max_price=300)
    assert all(s.price <= 300 for s in block)
    assert block[0].row == "F"  # closest to the front band that fits the cap


def test_back_preference():
    assert pick_seats(hall(), 2, "back")[0].row in "HIJ"


def test_none_when_nothing_fits():
    full = hall(taken={f"{r}{c}" for r in ROWS for c in range(1, 13) if c % 2})
    assert pick_seats(full, 2) is None
    assert pick_seats([], 2) is None
    assert pick_seats(hall(), 0) is None
