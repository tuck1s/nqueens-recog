"""Stepwise human-like solver for the N-Queens (queensgame) puzzle.

Instead of backtracking exhaustively, this module applies a sequence of
logical elimination rules — the same techniques a human would use — and
prints a trace of each deduction as it works.

Rule names are based upon (and extend) https://www.caterbum.com/blog/linkedin-queens-game-solver:

  1. **Region singleton** — a region (or row, or column) has been narrowed
      to exactly one candidate cell; place the queen there.  This is the
      terminal action that rules 2–6 work toward by eliminating candidates.
  2. **Region forced row/col** — all candidates for a region fall on the
      same row (or column); claim that line and eliminate every other
      region's candidates on it.
  3. **Squeeze** — when a row's (or column's) active candidates span ≤ 2
      cells, the queen placed there will always diagonally attack the overlap
      zone in both adjacent rows (or columns); eliminate candidates there.
      E.g. two candidates in consecutive columns eliminate 2 cells in each
      adjacent row; three consecutive candidates eliminate 1 cell each.
  4. **Shadow** — for each colour, find every cell (outside that colour's
      region) that is attacked by all of the colour's active candidates —
      same row, same column, or diagonally adjacent.  Since the colour's
      queen must land on one of those candidates, every shadowed cell is
      certain to be blocked and can be eliminated.  Generalises Squeeze to
      arbitrary region shapes (L-shapes, 2×2, 2×3, 3×3 blocks, …).
  5. **N-group** (generalised from caterbum: "triple-check") — when k regions
      together have all their candidates confined to exactly k rows (or
      columns), those lines are reserved; eliminate any other region's
      candidates on them.
  6. **X-Wing** — when c colours have all their candidates within the union
      of a rows R and b columns C (a+b=c), those c queens must collectively
      claim every row in R and every column in C; eliminate other colours'
      candidates from those rows and columns.  The typical case is c=4,
      a=b=2 (two pairs of colours forming a cross pattern).
  7. **Y-Wing** — a generalised X-Wing that accounts for queens forced into
      row/column intersections.
  8. **Elimination** — if placing a queen at a candidate cell would leave
      some other region with no remaining candidates at all, that cell is
      ruled out (one-step lookahead).
  9. **Lookahead** — starting with smaller regions, trial-place a queen in every
      candidate cell; remove any candidate that leads to a contradiction.
  10. **Search** — last resort: pick the most-constrained region, guess,
      and recurse with backtracking.

The trace uses plain text so it can be piped or saved alongside the solutions produced by ``--solve``.
"""

import time
from itertools import combinations
from .solver import is_diagonally_adjacent

# Helper to print (row, col) - now begins from R1C1
def row_str(r: int) -> str:
    return 'R'+str(r+1)

def col_str(c: int) -> str:
    return 'C'+str(c+1)

def row_col_str(r: int, c: int) -> str:
    return f"({row_str(r)},{col_str(c)})"

def solve_stepwise(
    board: list[list[str]], quiet: bool = False, verbose: bool = False,
    timestamps: bool = False, x_wing_max: int = 6,
    lookahead_max_cands: int | None = None,
) -> dict[int, int] | None:
    """Apply elimination rules to *board*, printing a trace of each step.

    Returns a ``{row: col}`` dict (0-indexed) when the puzzle is solved by
    deduction alone, or ``None`` if the rules were insufficient.

    When *verbose* is ``True``, the board state is printed after each rule
    fires, showing region letters for active candidates, ``X`` for eliminated
    cells, and 👑 for placed queens.
    """
    n = len(board)
    t0 = time.monotonic()
    candidates: list[list[bool]] = [[True] * n for _ in range(n)]
    queens: dict[int, int] = {}
    colours = sorted({board[r][c] for r in range(n) for c in range(n)})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    pending_trace: list[str] = []

    def out(msg: str) -> None:
        if quiet:
            return
        lines = msg.splitlines() or [msg]
        if timestamps:
            prefix = f"{time.monotonic() - t0:.1f}s: "
            for line in lines:
                pending_trace.append(prefix + line if line else line)
        else:
            pending_trace.extend(lines)

    def flush_trace() -> None:
        if quiet or not pending_trace:
            pending_trace.clear()
            return
        for line in pending_trace:
            print(line)
        pending_trace.clear()

    # Snapshot of candidates at the last show_board call, used to highlight new eliminations.
    _prev_candidates: list[list[bool]] = [row[:] for row in candidates]

    def show_board() -> None:
        nonlocal _prev_candidates
        if not verbose:
            _prev_candidates = [row[:] for row in candidates]
            return
        from .display import print_board
        q_list = [(c, r) for r, c in queens.items()]
        newly = {
            (c, r)
            for r in range(n)
            for c in range(n)
            if _prev_candidates[r][c] and not candidates[r][c]
        }
        _prev_candidates = [row[:] for row in candidates]
        print_board(board, queens=q_list, candidates=candidates, newly_eliminated=newly)

    def colour_at(r: int, c: int) -> str:
        return board[r][c]

    region_of: dict[str, list[tuple[int, int]]] = {
        colour: [(r, c) for r in range(n) for c in range(n) if board[r][c] == colour]
        for colour in colours
    }

    def region_cells(colour: str) -> list[tuple[int, int]]:
        return region_of[colour]

    solved_colours: set[str] = set()

    def colour_is_solved(colour: str) -> bool:
        return colour in solved_colours

    def active_for_colour(colour: str) -> list[tuple[int, int]]:
        return [(r, c) for r, c in region_cells(colour) if candidates[r][c]]

    def active_in_row(r: int) -> list[int]:
        return [c for c in range(n) if candidates[r][c]]

    def active_in_col(c: int) -> list[int]:
        return [r for r in range(n) if candidates[r][c]]

    def eliminate(r: int, c: int, *, trace: bool = True) -> None:
        if candidates[r][c]:
            candidates[r][c] = False
            if trace:
                out(f"  eliminate {row_col_str(r, c)} [{colour_at(r, c)}]") # updated

    def place_queen(r: int, c: int, reason: str) -> None:
        queens[r] = c
        colour = colour_at(r, c)
        solved_colours.add(colour)
        elim = 0
        for cc in range(n):
            if cc != c and candidates[r][cc]:
                candidates[r][cc] = False
                elim += 1
        for rr in range(n):
            if rr != r and candidates[rr][c]:
                candidates[rr][c] = False
                elim += 1
        for rr, cc in region_cells(colour):
            if (rr != r or cc != c) and candidates[rr][cc]:
                candidates[rr][cc] = False
                elim += 1
        placed = [(c, r)]
        for rr in range(n):
            for cc in range(n):
                if is_diagonally_adjacent(cc, rr, placed) and candidates[rr][cc]:
                    candidates[rr][cc] = False
                    elim += 1
        out(f"  QUEEN {row_col_str(r, c)} [{colour}]: {reason}: eliminating row {row_str(r)}, col {col_str(c)}, region [{colour}], diagonal adjacents → {elim} cell(s)") # updated

    # ------------------------------------------------------------------
    # Rule — Region / row / col singleton
    # ------------------------------------------------------------------

    def rule_singleton() -> bool:
        """Place a queen wherever exactly one candidate remains."""
        changed = False
        for colour in colours:
            if colour_is_solved(colour):
                continue
            cands = active_for_colour(colour)
            if len(cands) == 1:
                r, c = cands[0]
                if r not in queens:
                    place_queen(r, c, f"region singleton [{colour}]")
                    changed = True
        for r in range(n):
            if r in queens:
                continue
            cands = active_in_row(r)
            if len(cands) == 1:
                place_queen(r, cands[0], f"row {row_str(r)} singleton")
                changed = True
        for c in range(n):
            if c in queens.values():
                continue
            cands = active_in_col(c)
            if len(cands) == 1:
                r = cands[0]
                if r not in queens:
                    place_queen(r, c, f"col {col_str(c)} singleton")
                    changed = True
        return changed

    # ------------------------------------------------------------------
    # Rule — Region forced row / col
    # ------------------------------------------------------------------

    def rule_forced_row_col() -> bool:
        """Claim a line when all of a region's candidates lie on it."""
        changed = False
        for colour in colours:
            if colour_is_solved(colour):
                continue
            cands = active_for_colour(colour)
            if len(cands) <= 1:
                continue
            rows = {r for r, _ in cands}
            if len(rows) == 1:
                r = next(iter(rows))
                count = sum(
                    1 for cc in range(n)
                    if board[r][cc] != colour and candidates[r][cc]
                )
                if count:
                    for cc in range(n):
                        if board[r][cc] != colour:
                            eliminate(r, cc, trace=False)
                    out(f"  forced: [{colour}] confined to row {row_str(r)} → {count} cell(s) eliminated") # updated
                    changed = True
            cols = {c for _, c in cands}
            if len(cols) == 1:
                col = next(iter(cols))
                count = sum(
                    1 for rr in range(n)
                    if board[rr][col] != colour and candidates[rr][col]
                )
                if count:
                    for rr in range(n):
                        if board[rr][col] != colour:
                            eliminate(rr, col, trace=False)
                    out(f"  forced: [{colour}] confined to col {col_str(col)} → {count} cell(s) eliminated") # updated
                    changed = True
        return changed

    # ------------------------------------------------------------------
    # Rule — Squeeze
    # ------------------------------------------------------------------

    def rule_squeeze() -> bool:
        """Eliminate in adjacent rows/cols when a line's candidates have a narrow span.

        If a row's active candidates span columns [c_min, c_max] with
        c_max - c_min ≤ 2, the queen placed there will definitely attack every
        column in [c_max-1, c_min+1] of the immediately adjacent rows,
        regardless of which candidate is chosen.  Those candidates are eliminated.

        The symmetric rule applies to columns: when a column's candidates have
        r_max − r_min ≤ 2 (i.e. confined to 2 or 3 consecutive rows), every
        row in [r_max-1, r_min+1] of the immediately adjacent columns is
        eliminated.

        Note: unlike rule_shadow, this rule is colour-agnostic — it fires based
        on the geometric spread of all candidates in a line, regardless of which
        colour regions they belong to.
        """
        # Row perspective
        for r in range(n):
            if r in queens:
                continue
            active_cols = active_in_row(r)
            if len(active_cols) < 2:
                continue
            c_min, c_max = min(active_cols), max(active_cols)
            if c_max - c_min > 2:
                continue
            # Guaranteed attack zone in adjacent rows: cols [c_max-1 .. c_min+1]
            count = 0
            for adj_r in (r - 1, r + 1):
                if adj_r < 0 or adj_r >= n:
                    continue
                for cc in range(c_max - 1, c_min + 2):
                    if 0 <= cc < n and candidates[adj_r][cc]:
                        eliminate(adj_r, cc, trace=False)
                        count += 1
            if count:
                out(f"  squeeze: {row_str(r)} cols {col_str(c_min)}–{col_str(c_max)} → {count} cell(s) eliminated in adjacent rows") # updated
                return True
        # Column perspective
        for c in range(n):
            if c in queens.values():
                continue
            active_rows = active_in_col(c)
            if len(active_rows) < 2:
                continue
            r_min, r_max = min(active_rows), max(active_rows)
            if r_max - r_min > 2:
                continue
            # Guaranteed attack zone in adjacent cols: rows [r_max-1 .. r_min+1]
            count = 0
            for adj_c in (c - 1, c + 1):
                if adj_c < 0 or adj_c >= n:
                    continue
                for rr in range(r_max - 1, r_min + 2):
                    if 0 <= rr < n and candidates[rr][adj_c]:
                        eliminate(rr, adj_c, trace=False)
                        count += 1
            if count:
                out(f"  squeeze: col {col_str(c)} rows {row_str(r_min)}–{row_str(r_max)} → {count} cell(s) eliminated in adjacent cols") # updated
                return True
        return False

    # ------------------------------------------------------------------
    # Rule — Shadow
    # ------------------------------------------------------------------

    def rule_shadow() -> bool:
        """Eliminate cells in the universal attack shadow of each colour.

        For each unsolved colour C, a non-C cell is eliminated if it is
        attacked (same row, same column, or diagonally adjacent) by every
        active candidate of C.  Since C's queen must occupy one of those
        candidates, such cells are guaranteed to be blocked.
        """
        for colour in colours:
            if colour_is_solved(colour):
                continue
            cands = active_for_colour(colour)
            if len(cands) < 2:
                continue
            cand_set = set(cands)
            count = 0
            for r in range(n):
                for c in range(n):
                    if not candidates[r][c] or (r, c) in cand_set:
                        continue
                    if all(
                        r == pr or c == pc or
                        (abs(r - pr) == 1 and abs(c - pc) == 1)
                        for pr, pc in cands
                    ):
                        eliminate(r, c, trace=False)
                        count += 1
            if count:
                out(f"  shadow: [{colour}] ({len(cands)} candidates) → {count} cell(s) eliminated") # no update needed
                return True
        return False

    # ------------------------------------------------------------------
    # Rule — N-group (generalised triple-check)
    # ------------------------------------------------------------------

    def rule_n_group() -> bool:
        """Eliminate when k regions' candidates are confined to exactly k lines.

        At each group size k (ascending) two complementary perspectives are tried:

          Colour perspective (k ≥ 2): k colours whose candidates span exactly k
            rows/cols → eliminate other colours' candidates from those lines.
          Line perspective  (k ≥ 1): k rows/cols whose candidates come from
            exactly k colours → eliminate those colours' candidates elsewhere.

        Starting with the line perspective at k=1 catches the case where a
        single row or column is entirely one colour, e.g. a bottom row that is
        all-J immediately tells us J must go there.
        """
        unsolved = [c for c in colours if not colour_is_solved(c)]
        cands_by_colour: dict[str, list[tuple[int, int]]] = {
            c: active_for_colour(c) for c in unsolved
        }
        unsolved_set = set(unsolved)
        free_rows = [r for r in range(n) if r not in queens]
        free_cols = [c for c in range(n) if c not in queens.values()]
        # Precompute which unsolved colours appear in each free row / col.
        colours_in_row: dict[int, set[str]] = {
            r: {board[r][c] for c in range(n)
                if candidates[r][c] and board[r][c] in unsolved_set}
            for r in free_rows
        }
        colours_in_col: dict[int, set[str]] = {
            col: {board[r][col] for r in range(n)
                  if candidates[r][col] and board[r][col] in unsolved_set}
            for col in free_cols
        }

        for k in range(1, len(unsolved)):
            # ----------------------------------------------------------
            # Line perspective: k rows/cols exclusive to exactly k colours
            # ----------------------------------------------------------
            for row_group in combinations(free_rows, k):
                colours_here: set[str] = set()
                for r in row_group:
                    colours_here |= colours_in_row[r]
                    if len(colours_here) > k:
                        break
                if len(colours_here) == k:
                    row_set = set(row_group)
                    count = sum(
                        1 for colour in colours_here
                        for r2, c2 in cands_by_colour[colour]
                        if r2 not in row_set
                    )
                    if count:
                        for colour in colours_here:
                            for r2, c2 in cands_by_colour[colour]:
                                if r2 not in row_set:
                                    eliminate(r2, c2, trace=False)
                        rows_str_formatted = ",".join(str(row_str(r)) for r in sorted(row_group))
                        clabel = "{" + ",".join(sorted(colours_here)) + "}"
                        out(f"  n-group: rows {{{rows_str_formatted}}} exclusive to {clabel} → {count} cell(s) eliminated") # updated
                        return True
            for col_group in combinations(free_cols, k):
                colours_here = set()
                for c in col_group:
                    colours_here |= colours_in_col[c]
                    if len(colours_here) > k:
                        break
                if len(colours_here) == k:
                    col_set = set(col_group)
                    count = sum(
                        1 for colour in colours_here
                        for r2, c2 in cands_by_colour[colour]
                        if c2 not in col_set
                    )
                    if count:
                        for colour in colours_here:
                            for r2, c2 in cands_by_colour[colour]:
                                if c2 not in col_set:
                                    eliminate(r2, c2, trace=False)
                        cols_str_formatted = ",".join(col_str(c) for c in sorted(col_group))
                        clabel = "{" + ",".join(sorted(colours_here)) + "}"
                        out(f"  n-group: cols {{{cols_str_formatted}}} exclusive to {clabel} → {count} cell(s) eliminated") # updated
                        return True

            if k < 2:
                continue  # colour perspective starts at k=2 (k=1 is forced-row/col)

            # ----------------------------------------------------------
            # Colour perspective: k colours confined to exactly k rows/cols
            # ----------------------------------------------------------
            for group in combinations(unsolved, k):
                group_set = set(group)
                label = "{" + ",".join(sorted(group_set)) + "}"
                rows: set[int] = set()
                for colour in group:
                    rows.update(r for r, _ in cands_by_colour[colour])
                if len(rows) == k:
                    count = sum(
                        1 for r in rows for cc in range(n)
                        if board[r][cc] not in group_set and candidates[r][cc]
                    )
                    if count:
                        for r in rows:
                            for cc in range(n):
                                if board[r][cc] not in group_set:
                                    eliminate(r, cc, trace=False)
                        rows_str_formatted = ",".join(row_str(r) for r in sorted(rows))
                        out(f"  n-group: {label} claims rows {rows_str_formatted} → {count} cell(s) eliminated") # updated
                        return True
                cols: set[int] = set()
                for colour in group:
                    cols.update(c for _, c in cands_by_colour[colour])
                if len(cols) == k:
                    count = sum(
                        1 for col in cols for rr in range(n)
                        if board[rr][col] not in group_set and candidates[rr][col]
                    )
                    if count:
                        for col in cols:
                            for rr in range(n):
                                if board[rr][col] not in group_set:
                                    eliminate(rr, col, trace=False)
                        cols_str_formatted = ",".join(col_str(c) for c in sorted(cols))
                        out(f"  n-group: {label} claims cols {cols_str_formatted} → {count} cell(s) eliminated") # updated
                        return True
        return False

    # ------------------------------------------------------------------
    # Rule — X-Wing
    # ------------------------------------------------------------------

    def rule_x_wing() -> bool:
        """Eliminate when c colors are confined to a rows ∪ b columns (a+b=c).

        If every active candidate of a set of c colours lies within the union
        of some a rows R and b columns C (where a+b=c), the c queens must
        collectively claim all a rows and all b columns.  Therefore no other
        colour can place its queen in any of those rows or columns.

        This captures the community "X-Wing" technique (typically c=4, a=b=2)
        and generalises it to any (a, b) split.
        """
        unsolved = [col for col in colours if not colour_is_solved(col)]
        cands_by = {col: active_for_colour(col) for col in unsolved}
        rows_by = {
            col: frozenset(r for r, _ in cands)
            for col, cands in cands_by.items()
        }
        cols_by = {
            col: frozenset(c for _, c in cands)
            for col, cands in cands_by.items()
        }
        # Search group size c up to min(n-1, x_wing_max).  The "inversion" argument —
        # that a size-c x-wing implies the complement (size n-c) would fire
        # first — is unsound: the complement colours' candidates aren't yet
        # confined to the complementary rows/cols until *after* the x-wing
        # eliminates from them.  Level 452 (7x7, size-4 x-wing with no
        # size-3 equivalent) is a concrete counterexample.
        max_c = min(len(unsolved), n - 1, x_wing_max)
        if max_c < 2:
            return False

        seen_hits: set[tuple[frozenset[str], frozenset[int], frozenset[int]]] = set()
        out(f"  x-wing scan from size 2 up to {max_c}...") # no update needed
        flush_trace()
        for c in range(2, max_c + 1):
            scan_count = 0
            for group in combinations(unsolved, c):
                scan_count += 1

                # Cheap pre-screen: choose only feasible (a, b) split range from
                # group row/col coverage before expensive cell-level checks.
                group_rows: set[int] = set()
                group_cols: set[int] = set()
                for col in group:
                    group_rows.update(rows_by[col])
                    group_cols.update(cols_by[col])
                if not group_rows:
                    continue
                a_min = max(1, c - len(group_cols))
                a_max = min(c - 1, len(group_rows))
                if a_min > a_max:
                    continue

                cell_set: set[tuple[int, int]] = set()
                for col in group:
                    cell_set.update(cands_by[col])
                if not cell_set:
                    continue
                rows_used = sorted(group_rows)
                group_set = set(group)
                label = "{" + ",".join(sorted(group_set)) + "}"

                for a in range(a_min, a_max + 1):
                    b = c - a
                    for row_subset in combinations(rows_used, a):
                        row_set = set(row_subset)
                        needed_cols = frozenset(
                            cc for r2, cc in cell_set if r2 not in row_set
                        )
                        if len(needed_cols) != b:
                            continue
                        rows_frozen = frozenset(row_subset)
                        hit_key = (frozenset(group_set), rows_frozen, needed_cols)
                        if hit_key in seen_hits:
                            continue
                        seen_hits.add(hit_key)

                        # X-Wing confirmed — build elimination set from R and C
                        elim_cells: set[tuple[int, int]] = set()
                        for r2 in row_subset:
                            for cc in range(n):
                                if board[r2][cc] not in group_set and candidates[r2][cc]:
                                    elim_cells.add((r2, cc))
                        for cc in needed_cols:
                            for r2 in range(n):
                                if board[r2][cc] not in group_set and candidates[r2][cc]:
                                    elim_cells.add((r2, cc))
                        # Group candidates at corner intersections (row_subset ∩ needed_cols)
                        # are also invalid: the b queens outside row_subset must each claim
                        # one of the b cols in needed_cols, exhausting all of them, so the
                        # a queens inside row_subset cannot use any col from needed_cols.
                        for r2 in row_subset:
                            for cc in needed_cols:
                                if board[r2][cc] in group_set and candidates[r2][cc]:
                                    elim_cells.add((r2, cc))

                        if not elim_cells:
                            continue
                        for r2, cc in elim_cells:
                            eliminate(r2, cc, trace=False)

                        rows_formatted_str = ",".join(row_str(r2) for r2 in sorted(rows_frozen))
                        cols_formatted_str = ",".join(col_str(cc) for cc in sorted(needed_cols))
                        out(f"    x-wing scan: size {c} → 1 hit after {scan_count} group(s)") # no update needed
                        out(f"  x-wing: size {c} {label} confined to rows {{{rows_formatted_str}}} ∪ cols {{{cols_formatted_str}}} → {len(elim_cells)} cell(s) eliminated") # updated
                        return True
            out(f"    x-wing scan: size {c} → 0 hit(s) after {scan_count} group(s)") # no update needed
            flush_trace()

        return False

    # ------------------------------------------------------------------
    # Rule — Y-Wing (generalised X-Wing)
    # ------------------------------------------------------------------

    def rule_y_wing_isolated_union() -> bool:
        """Lock colours to R ∩ C when R ∪ C admits only those colours.

        Let ``R`` contain ``a`` rows and ``C`` contain ``b`` columns.  If the
        union has candidates from exactly ``k`` colours, its ``a + b`` line
        queens require at least ``a + b - k`` placements in ``R ∩ C``.  When
        exactly that many colours can occupy the intersection, they must do
        so, and their candidates outside it can be removed.
        """
        unsolved = [col for col in colours if not colour_is_solved(col)]
        free_rows = [r for r in range(n) if r not in queens]
        free_cols = [c for c in range(n) if c not in queens.values()]
        max_dim = min(len(unsolved), n - 1, x_wing_max)
        max_span = min(len(free_rows) + len(free_cols), x_wing_max + 1)
        if max_dim < 2:
            return False

        for a in range(1, min(len(free_rows), max_dim, max_span - 1) + 1):
            for b in range(1, min(len(free_cols), max_dim, max_span - a) + 1):
                for row_group in combinations(free_rows, a):
                    row_set = set(row_group)
                    for col_group in combinations(free_cols, b):
                        col_set = set(col_group)
                        union_colours = {
                            board[r2][c2]
                            for r2 in range(n)
                            for c2 in range(n)
                            if candidates[r2][c2]
                            and (r2 in row_set or c2 in col_set)
                        }
                        # Every candidate in the union must belong to one of
                        # the k colours; a non-positive bound is ordinary
                        # X-Wing territory rather than a forced intersection.
                        k = len(union_colours)
                        forced = a + b - k
                        if k > x_wing_max or forced <= 0 or forced > min(a, b):
                            continue

                        intersection_colours = {
                            board[r2][c2]
                            for r2 in row_set for c2 in col_set
                            if candidates[r2][c2]
                        }
                        if len(intersection_colours) != forced:
                            continue

                        elim_cells = {
                            (r2, c2)
                            for colour in intersection_colours
                            for r2, c2 in active_for_colour(colour)
                            if r2 not in row_set or c2 not in col_set
                        }
                        if not elim_cells:
                            continue
                        for r2, c2 in elim_cells:
                            eliminate(r2, c2, trace=False)

                        rows_str = ",".join(row_str(r2) for r2 in sorted(row_set))
                        cols_str = ",".join(col_str(c2) for c2 in sorted(col_set))
                        label = "{" + ",".join(sorted(intersection_colours)) + "}"
                        out(
                            f"  y-wing (isolated): {label} forced into intersection "
                            f"of rows {{{rows_str}}} and cols {{{cols_str}}} "
                            f"→ {len(elim_cells)} cell(s) eliminated"
                        )
                        return True
        return False

    def rule_y_wing_forced_intersections() -> bool:
        """Claim R ∪ C when colours already locked in R ∩ C reduce capacity.

        Colours confined to ``R ∩ C`` consume one row and one column each.
        If precisely ``|R| + |C| - locked`` colours are confined to ``R ∪ C``,
        they saturate the union, so all other colours can be eliminated from it.
        """
        unsolved = [col for col in colours if not colour_is_solved(col)]
        cands_by = {colour: active_for_colour(colour) for colour in unsolved}
        free_rows = [r for r in range(n) if r not in queens]
        free_cols = [c for c in range(n) if c not in queens.values()]
        max_dim = min(len(unsolved), n - 1, x_wing_max)
        max_span = min(len(free_rows) + len(free_cols), x_wing_max + 1)
        if max_dim < 2:
            return False

        for a in range(1, min(len(free_rows), max_dim, max_span - 1) + 1):
            for b in range(1, min(len(free_cols), max_dim, max_span - a) + 1):
                for row_group in combinations(free_rows, a):
                    row_set = set(row_group)
                    for col_group in combinations(free_cols, b):
                        col_set = set(col_group)
                        intersection_colours = {
                            colour for colour, cands in cands_by.items()
                            if cands and all(r2 in row_set and c2 in col_set for r2, c2 in cands)
                        }
                        locked = len(intersection_colours)
                        if not locked:
                            continue
                        target = a + b - locked
                        if target <= 0 or target > x_wing_max:
                            continue
                        union_colours = {
                            colour for colour, cands in cands_by.items()
                            if cands and all(r2 in row_set or c2 in col_set for r2, c2 in cands)
                        }
                        if len(union_colours) != target:
                            continue

                        elim_cells = {
                            (r2, c2)
                            for r2 in range(n) for c2 in range(n)
                            if candidates[r2][c2]
                            and (r2 in row_set or c2 in col_set)
                            and board[r2][c2] not in union_colours
                        }
                        if not elim_cells:
                            continue
                        for r2, c2 in elim_cells:
                            eliminate(r2, c2, trace=False)

                        rows_str = ",".join(row_str(r2) for r2 in sorted(row_set))
                        cols_str = ",".join(col_str(c2) for c2 in sorted(col_set))
                        label = "{" + ",".join(sorted(union_colours)) + "}"
                        out(
                            f"  y-wing (forced intersection): size {target} "
                            f"(locked={locked}) {label} confined to rows {{{rows_str}}} "
                            f"∪ cols {{{cols_str}}} → {len(elim_cells)} cell(s) eliminated"
                        )
                        return True
        return False

    # ------------------------------------------------------------------
    # Simulation helpers — shared by rules 5–9
    # ------------------------------------------------------------------

    def _sim_place(sc: list[list[bool]], sq: dict[int, int], r_t: int, c_t: int) -> None:
        """Apply placement effects to a simulation state (sc, sq) in place."""
        col = board[r_t][c_t]
        sq[r_t] = c_t
        for cc in range(n):
            if cc != c_t:
                sc[r_t][cc] = False
        for rr in range(n):
            if rr != r_t:
                sc[rr][c_t] = False
        for rr, cc in region_cells(col):
            sc[rr][cc] = False
        pl = [(c_t, r_t)]
        for rr in range(n):
            for cc in range(n):
                if is_diagonally_adjacent(cc, rr, pl):
                    sc[rr][cc] = False

    def _sim_active(
        sc: list[list[bool]], sq: dict[int, int], col: str
    ) -> list[tuple[int, int]]:
        return [(r, c) for r, c in region_cells(col) if r not in sq and sc[r][c]]

    def _sim_solved(sq: dict[int, int], col: str) -> bool:
        return any(board[r][sq[r]] == col for r in sq)

    def _contradiction(sc: list[list[bool]], sq: dict[int, int]) -> bool:
        occ_cols = set(sq.values())
        # Any unsolved colour with no candidates
        if any(not _sim_solved(sq, col) and not _sim_active(sc, sq, col) for col in colours):
            return True
        # Any row without a queen and no remaining candidates
        if any(r not in sq and not any(sc[r][c] for c in range(n)) for r in range(n)):
            return True
        # Any column without a queen and no remaining candidates
        if any(c not in occ_cols and not any(sc[r][c] for r in range(n)) for c in range(n)):
            return True
        return False

    def _propagate_sim(sc: list[list[bool]], sq: dict[int, int]) -> bool:
        """Apply rules 1, 2, and 4 (singleton, forced row/col, N-group) until stable. Returns False if contradicted."""
        if _contradiction(sc, sq):
            return False
        while len(sq) < n:
            prog = False
            occ_cols = set(sq.values())
            # Singletons
            for col in colours:
                if _sim_solved(sq, col):
                    continue
                ca = _sim_active(sc, sq, col)
                if len(ca) == 1:
                    r2, c2 = ca[0]
                    if r2 not in sq:
                        _sim_place(sc, sq, r2, c2)
                        prog = True
            for r2 in range(n):
                if r2 in sq:
                    continue
                ca = [c2 for c2 in range(n) if sc[r2][c2]]
                if len(ca) == 1:
                    _sim_place(sc, sq, r2, ca[0])
                    prog = True
            for c2 in range(n):
                if c2 in occ_cols:
                    continue
                ca = [r2 for r2 in range(n) if sc[r2][c2]]
                if len(ca) == 1 and ca[0] not in sq:
                    _sim_place(sc, sq, ca[0], c2)
                    prog = True
            if _contradiction(sc, sq):
                return False
            if prog:
                continue
            # Forced row/col
            for col in colours:
                if _sim_solved(sq, col):
                    continue
                ca = _sim_active(sc, sq, col)
                if len(ca) <= 1:
                    continue
                rs = {r2 for r2, _ in ca}
                if len(rs) == 1:
                    r2 = next(iter(rs))
                    for c2 in range(n):
                        if board[r2][c2] != col and sc[r2][c2]:
                            sc[r2][c2] = False
                            prog = True
                cs = {c2 for _, c2 in ca}
                if len(cs) == 1:
                    c2 = next(iter(cs))
                    for r2 in range(n):
                        if board[r2][c2] != col and sc[r2][c2]:
                            sc[r2][c2] = False
                            prog = True
            if _contradiction(sc, sq):
                return False
            if prog:
                continue
            # N-group (both perspectives)
            un2 = [col for col in colours if not _sim_solved(sq, col)]
            if not un2:
                break
            cbc2 = {col: _sim_active(sc, sq, col) for col in un2}
            uset2 = set(un2)
            fr2 = [r2 for r2 in range(n) if r2 not in sq]
            fc2 = [c2 for c2 in range(n) if c2 not in occ_cols]
            cir2 = {
                r2: {board[r2][c2] for c2 in range(n)
                     if sc[r2][c2] and board[r2][c2] in uset2}
                for r2 in fr2
            }
            cic2 = {
                c2: {board[r2][c2] for r2 in range(n)
                     if sc[r2][c2] and board[r2][c2] in uset2}
                for c2 in fc2
            }
            r3p = False
            for k in range(1, len(un2)):
                if r3p:
                    break
                for rg in combinations(fr2, k):
                    ch: set[str] = set()
                    for r2 in rg:
                        ch |= cir2[r2]
                        if len(ch) > k:
                            break
                    if len(ch) == k:
                        rs2 = set(rg)
                        for col in ch:
                            for r2, c2 in cbc2[col]:
                                if r2 not in rs2 and sc[r2][c2]:
                                    sc[r2][c2] = False
                                    r3p = True
                if r3p:
                    break
                for cg in combinations(fc2, k):
                    ch = set()
                    for c2 in cg:
                        ch |= cic2[c2]
                        if len(ch) > k:
                            break
                    if len(ch) == k:
                        cs2 = set(cg)
                        for col in ch:
                            for r2, c2 in cbc2[col]:
                                if c2 not in cs2 and sc[r2][c2]:
                                    sc[r2][c2] = False
                                    r3p = True
                if r3p:
                    break
                if k >= 2:
                    for grp in combinations(un2, k):
                        gs = set(grp)
                        rows3 = {r2 for col in grp for r2, _ in cbc2[col]}
                        if len(rows3) == k:
                            for r2 in rows3:
                                for c2 in range(n):
                                    if board[r2][c2] not in gs and sc[r2][c2]:
                                        sc[r2][c2] = False
                                        r3p = True
                        cols3 = {c2 for col in grp for _, c2 in cbc2[col]}
                        if len(cols3) == k:
                            for c2 in cols3:
                                for r2 in range(n):
                                    if board[r2][c2] not in gs and sc[r2][c2]:
                                        sc[r2][c2] = False
                                        r3p = True
            prog = r3p
            if _contradiction(sc, sq):
                return False
            if not prog:
                break
        return not _contradiction(sc, sq)

    def _backtrack(
        sc: list[list[bool]], sq: dict[int, int], depth: int = 0
    ) -> tuple[dict[int, int] | None, list[str]]:
        """Recursive backtracking with rules 1–3 propagation at each node.

        Returns ``(result, lines)`` where *lines* is the buffered trace output.
        Each ``try`` line includes the immediate deduction chain from propagation.
        Leaf failures are collapsed to a single ``try … → ✗`` line.
        """
        if not _propagate_sim(sc, sq):
            return None, []
        if len(sq) == n:
            return dict(sq), []
        un = [col for col in colours if not _sim_solved(sq, col)]
        best_colour = min(un, key=lambda col: len(_sim_active(sc, sq, col)))
        pad = "  " * (depth + 2)
        lines: list[str] = []
        for r_t, c_t in _sim_active(sc, sq, best_colour):
            nsc = [row[:] for row in sc]
            nsq = dict(sq)
            _sim_place(nsc, nsq, r_t, c_t)
            sq_placed = dict(nsq)  # state after placing, before propagation
            prop_ok = _propagate_sim(nsc, nsq)
            deduced = [
                f"{board[r2][nsq[r2]]}{row_col_str(r2, nsq[r2])}"
                for r2 in nsq if r2 not in sq_placed
            ]
            if deduced:
                chain = " → " + ", ".join(deduced)
            else:
                chain = ""
            if not prop_ok:
                occ_cols = set(nsq.values())
                reason = "empty"
                for colour2 in colours:
                    if not _sim_solved(nsq, colour2) and not _sim_active(nsc, nsq, colour2):
                        reason = f"[{colour2}] empty ✗"
                        break
                if reason == "empty":
                    for r2 in range(n):
                        if r2 not in nsq and not any(nsc[r2][c2] for c2 in range(n)):
                            reason = f"row {row_str(r2)} empty ✗" # updated
                            break
                if reason == "empty":
                    for c2 in range(n):
                        if c2 not in occ_cols and not any(nsc[r2][c2] for r2 in range(n)):
                            reason = f"col {col_str(c2)} empty ✗" # updated
                            break
                lines.append(f"{pad}try {row_col_str(r_t, c_t)} [{best_colour}]{chain} → {reason}")
                continue
            if len(nsq) == n:
                lines.append(f"{pad}try {row_col_str(r_t, c_t)} [{best_colour}]{chain}")
                return dict(nsq), lines
            # nsc/nsq already propagated; recursive call's initial propagation is a no-op
            result, child_lines = _backtrack(nsc, nsq, depth + 1)
            if result is not None:
                lines.append(f"{pad}try {row_col_str(r_t, c_t)} [{best_colour}]{chain}")
                lines.extend(child_lines)
                return result, lines
            if child_lines:
                lines.append(f"{pad}try {row_col_str(r_t, c_t)} [{best_colour}]{chain}")
                lines.extend(child_lines)
                lines.append(f"{pad}✗ {row_col_str(r_t, c_t)}")
            else:
                lines.append(f"{pad}try {row_col_str(r_t, c_t)} [{best_colour}]{chain} → ✗")
        return None, lines

    def _solve_sim(
        sc: list[list[bool]], sq: dict[int, int]
    ) -> list[str] | None:
        """Solve silently. Returns None if solvable; a short failure-witness otherwise.

        The witness is the first contradicting branch: a list of queen labels
        (e.g. ``['E(3,1)', '[D]\u2205']``) showing why the position has no solution.
        """
        if not _propagate_sim(sc, sq):
            occ_cols = set(sq.values())
            for colour2 in colours:
                if not _sim_solved(sq, colour2) and not _sim_active(sc, sq, colour2):
                    return [f"[{colour2}] empty"]
            for r2 in range(n):
                if r2 not in sq and not any(sc[r2][c2] for c2 in range(n)):
                    return [f"row {row_str(r2)} empty"]
            for c2 in range(n):
                if c2 not in occ_cols and not any(sc[r2][c2] for r2 in range(n)):
                    return [f"col {col_str(c2)} empty"]
            return ["empty"]
        if len(sq) == n:
            return None
        un = [col for col in colours if not _sim_solved(sq, col)]
        best = min(un, key=lambda col: len(_sim_active(sc, sq, col)))
        first_fail: list[str] | None = None
        for r_t, c_t in _sim_active(sc, sq, best):
            nsc = [row[:] for row in sc]
            nsq = dict(sq)
            _sim_place(nsc, nsq, r_t, c_t)
            result = _solve_sim(nsc, nsq)
            if result is None:
                return None  # found a solution
            if first_fail is None:
                first_fail = [f"{board[r_t][c_t]}({r_t},{c_t})"] + result
        return first_fail if first_fail is not None else ["empty"]


    # ------------------------------------------------------------------
    # Rule — Elimination
    # ------------------------------------------------------------------

    def rule_elimination() -> bool:
        """Eliminate if placement immediately strands another region (no propagation)."""
        for colour in colours:
            if colour_is_solved(colour):
                continue
            for r, c in active_for_colour(colour):
                sc = [row[:] for row in candidates]
                sq = dict(queens)
                _sim_place(sc, sq, r, c)
                for colour2 in colours:
                    if colour2 == colour or _sim_solved(sq, colour2):
                        continue
                    if not _sim_active(sc, sq, colour2):
                        eliminate(r, c, trace=False)
                        out(f"  eliminate: {row_col_str(r, c)} [{colour}]: immediately strands [{colour2}] → 1 cell eliminated") # updated
                        return True
        return False

    # ------------------------------------------------------------------
    # Rule — Lookahead
    # ------------------------------------------------------------------

    def rule_lookahead() -> bool:
        """Eliminate candidates that lead to a contradiction after full propagation.

        Colours are tried shortest-list-first.  For the first colour where any
        candidate contradicts, all contradicting candidates are eliminated and
        the full attempt list (ok and failed) is printed.  Safe candidates are
        left untouched.
        """
        unsolved = [col for col in colours if not colour_is_solved(col)]
        changed = False
        multi_colour_mode = lookahead_max_cands is not None
        for colour in sorted(unsolved, key=lambda col: len(active_for_colour(col))):
            if lookahead_max_cands is not None and len(active_for_colour(colour)) > lookahead_max_cands:
                continue
            attempts: list[tuple[int, int, list[str], bool, list[str]]] = []
            for r, c in active_for_colour(colour):
                sc = [row[:] for row in candidates]
                sq = dict(queens)
                _sim_place(sc, sq, r, c)
                sq_after_trial = dict(sq)
                prop_ok = _propagate_sim(sc, sq)  # capture forced moves for the deduced chain
                deduced = [
                    f"{board[r2][sq[r2]]}{row_col_str(r2, sq[r2])}"
                    for r2 in sq  # insertion order = propagation order
                    if r2 not in sq_after_trial
                ] # updated
                bt_lines: list[str] = []
                if not prop_ok:
                    # Enrich the chain with why propagation failed
                    occ_cols = set(sq.values())
                    for colour2 in colours:
                        if not _sim_solved(sq, colour2) and not _sim_active(sc, sq, colour2):
                            deduced.append(f"[{colour2}] empty")
                            break
                    else:
                        for r2 in range(n):
                            if r2 not in sq and not any(sc[r2][c2] for c2 in range(n)):
                                deduced.append(f"row {row_str(r2)} empty")
                                break
                        else:
                            for c2 in range(n):
                                if c2 not in occ_cols and not any(sc[r2][c2] for r2 in range(n)):
                                    deduced.append(f"col{col_str(c2)} empty")
                                    break
                    ok = False
                else:
                    if verbose:
                        # Full backtrack trace so every dead-end branch is visible
                        result_bt, bt_lines = _backtrack(sc, sq, depth=1)
                        ok = result_bt is not None
                    else:
                        witness = _solve_sim(sc, sq)  # full silent search from propagated state
                        ok = witness is None
                        if not ok and witness:
                            deduced.extend(witness)
                attempts.append((r, c, deduced, not ok, bt_lines))
            contradictions = [(r, c) for r, c, _, contra, _ in attempts if contra]
            if contradictions:
                for r, c in contradictions:
                    eliminate(r, c, trace=False)
                lines = []
                for ar, ac, achain, acontra, abt in attempts:
                    ch = " → " + ", ".join(achain) if achain else ""
                    verdict = "✗ eliminated" if acontra else "ok"
                    lines.append(f"    try {row_col_str(ar,ac)}{ch} → {verdict}")
                    lines.extend(abt)
                out(f"  lookahead [{colour}] ({len(attempts)} candidates):\n" + "\n".join(lines))
                changed = True
                if not multi_colour_mode:
                    return True
        return changed

    # ------------------------------------------------------------------
    # Rule — Search
    # ------------------------------------------------------------------

    def rule_search() -> bool:
        """Last resort: backtracking search from the current state."""
        un = [col for col in colours if not colour_is_solved(col)]
        best = min(un, key=lambda col: len(active_for_colour(col)))
        out(f"  search [{best}] ({len(active_for_colour(best))} cands):")
        sc = [row[:] for row in candidates]
        sq = dict(queens)
        result, lines = _backtrack(sc, sq, depth=0)
        for line in lines:
            out(line)
        if result is None:
            out("  search: exhausted — no solution")
            return False
        for r_t in sorted(result):
            if r_t not in queens:
                place_queen(r_t, result[r_t], "search")
        return True

    # ------------------------------------------------------------------
    # Main loop — apply rules in priority order, restart on any change
    # ------------------------------------------------------------------

    global rule_functions
    rule_functions = [
        rule_singleton,
        rule_forced_row_col,
        rule_squeeze,
        rule_shadow,
        rule_n_group,
        rule_x_wing,
        rule_y_wing_isolated_union,
        rule_y_wing_forced_intersections,
        rule_elimination,
        rule_lookahead,
        rule_search,
    ]
    rules_used: list[str] = []
    while len(queens) < n:
        for rule_func in rule_functions:
            changed = rule_func()
            flush_trace()
            if changed:
                rules_used.append(rule_name(rule_func))
                show_board()
                break
        else:
            break

    if len(queens) == n:
        out(f"Solved: {n} queens placed.")
        flush_trace()
        return dict(queens), rules_used

    out(f"Stuck: {len(queens)}/{n} queens placed.")
    flush_trace()
    return None, rules_used


def rule_name(func) -> str:
    """Return the canonical rule name for a rule function (without 'rule_' prefix), mapping some names for backward compatibility."""
    mapped_names = {
        "forced_row_col": "forced",
    }
    n = getattr(func, "__name__", str(func))
    # Remove 'rule_' prefix if present
    name = n[5:] if n.startswith("rule_") else n
    # Use mapped name if present
    if name in mapped_names:
        name = mapped_names[name]
    # Replace underscores with dashes
    return name.replace("_", "-")


def compact_rules_used(rules_used: list[str]) -> list[str]:
    """Return unique rule names in the order declared in rule_functions """
    # Use the canonical names from rule_functions order
    declared = [rule_name(f) for f in rule_functions]
    seen = set()
    compacted = []
    for name in declared:
        if name in rules_used and name not in seen:
            compacted.append(name)
            seen.add(name)
    return compacted
