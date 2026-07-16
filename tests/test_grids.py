"""Tests for color-based grid recognition against the example images in ./img."""

import sys
import os
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nqueens_recog.display import print_board
from nqueens_recog.grid_reader import Grid, Tile, read_grid
from nqueens_recog.__main__ import main
from nqueens_recog.palette import PALETTE, grid_to_letters
from nqueens_recog.url_reader import is_community_level_url, read_community_level, _parse_color_regions
from nqueens_recog.solver import solve
from nqueens_recog.stepwise import solve_stepwise

IMG_DIR = Path(__file__).parent.parent / "img"
PUZZLE_687   = IMG_DIR / "puzzle-687.png"
PUZZLE_589   = IMG_DIR / "puzzle-589.png"
PUZZLE_657   = IMG_DIR / "puzzle-657-bad-cropping.png"

# ---------------------------------------------------------------------------
# puzzle-687.png — Grid method tests
# ---------------------------------------------------------------------------

class TestPuzzle687:
    @pytest.fixture(scope="class")
    def grid(self):
        return read_grid(str(PUZZLE_687))

    def test_color_index_grid(self, grid):
        cig = grid.color_index_grid()
        n = grid.rows
        assert len(cig) == n
        assert all(len(row) == n for row in cig)
        assert all(0 <= v < n for row in cig for v in row)


# ---------------------------------------------------------------------------
# Expected letter grid for puzzle-687.png  (standard test image)
# Uses the default game palette; colours mapped via nearest-RGB matching.
# Correct the rows below if the colour assignments need adjusting.
# ---------------------------------------------------------------------------
# Disable annoying spell checker in the expected letter grid
# cspell: disable

def test_puzzle_687_letter_map():
    grid = read_grid(str(PUZZLE_687))
    result = grid_to_letters(grid)
    expected = [
        "EBBEEELOOOLEEGEEE",
        "BBBBEOOJAJOEPEEEE",
        "BBBBOIAAFAAOEEEEE",
        "EBBLOADCCCDOOLEEG",
        "EGEOOACCCCCAJOEEE",
        "EEOOADFCQCFDAOOEE",
        "EEGOJACCCCCAJOEGE",
        "EEELOAICCCCIOLEEE",
        "GEEEOPAAQADAOEEEE",
        "EEEEEOOJAJOOPEEEE",
        "HEEEEELOQOLEEEEEE",
        "HHHHHEHEFEEEHEHHE",
        "HHNNNNNHQHHHHHNNN",
        "NNMMNNMNNNNNNHNMM",
        "NMMMMMMMQMMNNNMMM",
        "MMMKMMMMMMMMKMMMM",
        "KMMKKKMMQMKMKKMMM",
    ]
    assert result == expected


def test_puzzle_589_letter_map():
    grid = read_grid(str(PUZZLE_589))
    result = grid_to_letters(grid)
    expected = [
        "EEEEIIIJJJJ",
        "EIIAKKKFIII",
        "AAAAAIIFFJJ",
        "IIIAKKKFIII",
        "IIIAKKKKIII",
        "IIKKKKKDKKI",
        "CCCCIDDDDHB",
        "HHHCKKKHHHB",
        "HHHIKKKDHHB",
        "GHHIKKKDIHB",
        "GGGGIIIDIBB",
    ]
    assert result == expected


def test_puzzle_657_letter_map():
    """18x18 puzzle with UI chrome above and below the grid."""
    grid = read_grid(str(PUZZLE_657))
    result = grid_to_letters(grid)
    expected = [
        "OONKKKKKKKKKKKKKOO",
        "ONNNKKKKKKKKKKKKKO",
        "KKNKKQQQQQQQQKKKKK",
        "KKKKQLLLLGLLLQKKKK",
        "KKKQLLLFLLJLGLQKKK",
        "KKQLLLILLLLLLHLQKK",
        "KKQALLLLRRLJLLLQKK",
        "KKQLBLLRRRRLLLLQKP",
        "KKQLLLRRRRRRLDLQKP",
        "KKQLLLRRRRRRLLLQKK",
        "KKQLLCLRRRRLLLLQKK",
        "KKQLLLLLRRLLLLBQKK",
        "KKQLDLLLHLLGLLLQKK",
        "KKKQLCLGLLALLLQKKK",
        "KKKKQLLLILLFLQKKKK",
        "KKKKKQQQQQQQQKKKEO",
        "OKMMKKKKKKKKKKKEEE",
        "OOOMKKKKKKKKKKKOEO",
    ]
    assert result == expected

# cspell: enable


# ---------------------------------------------------------------------------
# url_reader: unit tests (no network required)
# ---------------------------------------------------------------------------

_MINIMAL_TS = """\
import {{ turquoiseBlue }} from "../colors";

const level = {{
  path: "/community-level/1",
  size: 3,
  colorRegions: [
    ["A", "A", "B"],
    ["A", "C", "B"],
    ["C", "C", "B"],
  ],
  regionColors: {{
    A: turquoiseBlue,
  }},
  solutionsCount: 1,
}};

export default level;
"""


class TestIsCommunityLevelUrl:
    def test_valid(self):
        assert is_community_level_url(
            "https://queensgame.vercel.app/community-level/657"
        )

    def test_rejects_image_path(self):
        assert not is_community_level_url("img/puzzle-687.png")

    def test_rejects_other_url(self):
        assert not is_community_level_url("https://example.com/community-level/1")


class TestParseColorRegions:
    def test_returns_correct_shape(self):
        rows = _parse_color_regions(_MINIMAL_TS, "1")
        assert len(rows) == 3
        assert all(len(r) == 3 for r in rows)

    def test_returns_correct_letters(self):
        rows = _parse_color_regions(_MINIMAL_TS, "1")
        assert rows[0] == ["A", "A", "B"]
        assert rows[1] == ["A", "C", "B"]
        assert rows[2] == ["C", "C", "B"]

    def test_raises_on_missing_size(self):
        bad = _MINIMAL_TS.replace("size: 3,", "")
        with pytest.raises(ValueError, match="size"):
            _parse_color_regions(bad, "1")

    def test_raises_on_missing_block(self):
        bad = _MINIMAL_TS.replace("colorRegions", "gridData")
        with pytest.raises(ValueError, match="colorRegions"):
            _parse_color_regions(bad, "1")

    def test_raises_on_wrong_cell_count(self):
        bad = _MINIMAL_TS.replace('size: 3,', 'size: 4,')
        with pytest.raises(ValueError, match="expected"):
            _parse_color_regions(bad, "1")


# ---------------------------------------------------------------------------
# Cross-validation: image recognition vs. authoritative URL data
# Run with:  pytest --network
# ---------------------------------------------------------------------------

_COMMUNITY_LEVELS = {
    "589": PUZZLE_589,
    "657": PUZZLE_657,
    "687": PUZZLE_687,
}


@pytest.mark.network
@pytest.mark.parametrize("level_id,image_path", _COMMUNITY_LEVELS.items())
def test_image_matches_community_level(level_id: str, image_path: Path) -> None:
    """Image recognition output must exactly match the authoritative level data."""
    url = f"https://queensgame.vercel.app/community-level/{level_id}"
    url_rows = read_community_level(url)
    expected = ["".join(r) for r in url_rows]

    img_rows = grid_to_letters(read_grid(str(image_path)))

    assert img_rows == expected, (
        f"Level {level_id}: image recognition differs from community-level data.\n"
        + "\n".join(
            f"  row {i}: img={img!r}  url={url_r!r}"
            for i, (img, url_r) in enumerate(zip(img_rows, expected))
            if img != url_r
        )
    )


# ---------------------------------------------------------------------------
# Solver: each puzzle must have exactly one solution
# Board is built from local image recognition (no network required).
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("image_path,label,expected_cols", [
    (PUZZLE_589, "589", [10, 1, 5, 8, 6, 2, 7, 4, 9, 11, 3]),
    (PUZZLE_687, "687", [14, 3, 6, 4, 12, 7, 5, 8, 11, 13, 10, 17, 2, 15, 9, 16, 1]),
    (PUZZLE_657, "657", [16, 2, 13, 10, 8, 14, 12, 18, 7, 4, 6, 15, 5, 11, 9, 17, 3, 1]),
])
def test_solver_finds_one_solution(image_path: Path, label: str, expected_cols: list[int]) -> None:
    """Solver must find exactly one solution for each sample puzzle."""
    board = [list(row) for row in grid_to_letters(read_grid(str(image_path)))]
    solutions = solve(board)
    assert len(solutions) == 1, (
        f"Puzzle {label}: expected 1 solution, got {len(solutions)}"
    )
    cols = [x + 1 for x, _ in solutions[0]]
    assert cols == expected_cols, (
        f"Puzzle {label}: solution {cols} != expected {expected_cols}"
    )


# ---------------------------------------------------------------------------
# Stepwise solver helpers
# ---------------------------------------------------------------------------

def _assert_matches_solver(board: list[list[str]], stepwise_result: dict[int, int] | None) -> None:
    """Cross-validate: stepwise result must agree with the unique exhaustive solution."""
    solutions = solve(board, quiet=True)
    if len(solutions) != 1:
        return  # only cross-validate when there is exactly one solution
    expected = {y: x for x, y in solutions[0]}
    assert stepwise_result == expected, (
        f"stepwise={stepwise_result} != solver={expected}"
    )


# ---------------------------------------------------------------------------
# Stepwise solver: X-Wing rule
# ---------------------------------------------------------------------------

def test_stepwise_y_wing_isolated_union_fires(capsys) -> None:
    """An isolated union locks the only possible intersection colour."""
    board = [
        list("AAEBCC"),
        list("ABBBCE"),
        list("BFCFFC"),
        list("DCDFCD"),
        list("DAEACD"),
        list("CDBCFA"),
    ]
    result, rules = solve_stepwise(board, x_wing_max=4)
    assert result is not None
    _assert_matches_solver(board, result)
    assert "y-wing-isolated-union" in rules
    assert "y-wing (isolated):" in capsys.readouterr().out


def test_stepwise_y_wing_isolated_union_counts_column_side_colours() -> None:
    """Regression: colours seen only in the selected columns must count in R ∪ C.

    This board is a one-cell mutation of the isolated-union fixture. It keeps the
    puzzle uniquely solvable, but introduces a colour in the relevant column side
    of the union so the isolated-union bound no longer applies.
    """
    board = [
        list("ABEBCC"),
        list("ABBBCE"),
        list("BFCFFC"),
        list("DCDFCD"),
        list("DAEACD"),
        list("CDBCFA"),
    ]
    result, rules = solve_stepwise(board, x_wing_max=4, quiet=True)
    assert result is not None
    _assert_matches_solver(board, result)
    assert "y-wing-isolated-union" not in rules


def test_stepwise_y_wing_forced_intersection_fires(capsys) -> None:
    """Intersection-confined colours reduce a union's available capacity."""
    board = [
        list("BAFFBE"),
        list("DDBBAF"),
        list("CACDBC"),
        list("DAACCB"),
        list("AFECDA"),
        list("BCDDFE"),
    ]
    result, rules = solve_stepwise(board, x_wing_max=4)
    assert result is not None
    _assert_matches_solver(board, result)
    assert "y-wing-forced-intersections" in rules
    assert "y-wing (forced intersection):" in capsys.readouterr().out

def test_stepwise_x_wing_fires(capsys) -> None:
    """{A,B} cells are confined to row-0 ∪ col-0, forcing rule_x_wing to fire.

    A candidates: (0,0), (0,1), (1,0)  — not in row 0 ⟹ col 0
    B candidates: (0,2), (0,3), (2,0)  — not in row 0 ⟹ col 0
    X-Wing (c=2, a=1, b=1): row {0} ∪ col {0} covers all {A,B} cells.
    Expected eliminations: C(3,0) [non-group in col 0] + A(0,0) [intersection].
    """
    board = [
        ["A", "A", "B", "B"],
        ["A", "C", "C", "C"],
        ["B", "D", "D", "D"],
        ["C", "C", "D", "D"],
    ]
    result = solve_stepwise(board)
    assert result is not None
    _assert_matches_solver(board, result)
    assert "x-wing:" in capsys.readouterr().out


def test_stepwise_verbose_show_board(capsys) -> None:
    """verbose=True causes show_board() to call print_board after each rule step."""
    board = [
        ["A", "A", "B", "B"],
        ["A", "C", "C", "C"],
        ["B", "D", "D", "D"],
        ["C", "C", "D", "D"],
    ]
    result = solve_stepwise(board, verbose=True)
    assert result is not None
    out = capsys.readouterr().out
    assert "\033[" in out  # ANSI escape codes emitted by print_board


def test_stepwise_ngroup_row_line_perspective(capsys) -> None:
    """Row-line n-group: row 4 is entirely colour E, so E must be placed there.

    Board rows 0-3 form a cyclic Latin square; row 4 is all E.  No region
    has only one cell (no singleton), no colour is confined to a single
    row/col (no forced_row_col), rows span all five columns (no squeeze),
    and the diagonal scatter of A-D cells means shadow never fires.
    Therefore rule_n_group fires first:
      colours_in_row[4] == {E} and E has four candidates outside row 4
      → n-group ROW line eliminates E from rows 0-3.
    """
    board = [
        ["A", "B", "C", "D", "E"],
        ["B", "C", "D", "E", "A"],
        ["C", "D", "E", "A", "B"],
        ["D", "E", "A", "B", "C"],
        ["E", "E", "E", "E", "E"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "n-group: rows" in out      # rule_n_group row line perspective


def test_stepwise_singleton_paths_and_stuck(capsys) -> None:
    """Region singleton, squeeze, row singleton, and the stuck path.

    A has exactly one cell → region singleton fires first.  Placing A(0,0)
    eliminates all of B's candidates (row 0 + diagonal), leaving no valid
    solution.  Before search gives up the trace visits:
      region singleton → A(0,0)
      squeeze          → row 1 (cols 2–3) eliminates in adjacent rows
      row singleton    → D placed (only candidate remaining in row 2)
      row singleton    → C placed (only candidate remaining in row 3)
      search exhausted → solve_stepwise returns None  (stuck path)
    """
    board = [
        ["A", "B", "B", "B"],
        ["C", "B", "C", "C"],
        ["C", "D", "D", "C"],
        ["C", "D", "D", "C"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result[0] is None                # stuck path → return None
    assert "region singleton" in out        # rule_singleton region branch
    assert "squeeze:" in out               # rule_squeeze fires
    assert "row R3 singleton" in out        # rule_singleton row branch
    assert "row R4 singleton" in out        # rule_singleton row branch


# ---------------------------------------------------------------------------
# Stepwise solver: community levels (boards embedded; no network at test time)
# ---------------------------------------------------------------------------

def test_stepwise_ngroup_colour_perspective(capsys) -> None:
    """Community level 150 (7×7): shadow and forced row/col solve without backtracking.

    shadow eliminates candidates for B, C, E before forced col fires for D and B.
    Board is fully solvable by deduction alone.
    Source: https://queensgame.vercel.app/community-level/150
    """
    board = [
        ["A", "A", "C", "C", "A", "A", "F"],
        ["A", "D", "D", "C", "A", "F", "F"],
        ["A", "D", "C", "C", "A", "A", "F"],
        ["G", "A", "C", "A", "A", "A", "A"],
        ["G", "A", "C", "E", "E", "B", "B"],
        ["G", "A", "A", "A", "E", "A", "B"],
        ["G", "G", "G", "A", "A", "A", "A"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result[0] is not None
    _assert_matches_solver(board, result[0])
    assert "shadow:" in out             # rule_shadow fires
    assert "confined to col" in out     # rule_forced_row_col col branch


def test_stepwise_shadow_l_shape(capsys) -> None:
    """Community level 578 (8×8): shadow fires on four corner regions simultaneously.

    The board has four compact corner regions whose candidates each jointly
    attack one interior cell, producing a symmetric pattern of eliminations:

      F triangle top-left  (0,0),(0,1),(1,0)        → eliminates (1,1)
      E L-shape  top-right (0,5),(0,6),(0,7),(1,7)  → eliminates (1,6)
      G L-shape  bot-left  (5,0),(6,0),(7,0),(7,1),(7,2) → eliminates (6,1)
      H triangle bot-right (6,7),(7,6),(7,7)         → eliminates (6,6)

    In every case every candidate attacks the target via row, col, or diagonal
    adjacency, so rule_shadow fires for each colour.
    Source: https://queensgame.vercel.app/community-level/578
    """
    board = [
        ["F", "F", "A", "A", "A", "E", "E", "E"],
        ["F", "A", "A", "C", "A", "A", "A", "E"],
        ["A", "A", "C", "C", "D", "D", "A", "E"],
        ["A", "C", "C", "C", "C", "C", "A", "A"],
        ["A", "A", "B", "B", "C", "C", "C", "A"],
        ["G", "A", "B", "B", "B", "B", "A", "A"],
        ["G", "A", "A", "A", "B", "A", "A", "H"],
        ["G", "G", "G", "A", "A", "A", "H", "H"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result[0] is not None
    _assert_matches_solver(board, result[0])
    assert "shadow: [E]" in out     # L-shape eliminates (1,6)
    assert "shadow: [F]" in out     # triangle eliminates (1,1)
    assert "shadow: [G]" in out     # L-shape eliminates (6,1)
    assert "shadow: [H]" in out     # triangle eliminates (6,6)


def test_stepwise_forced_ngroup_col_lookahead(capsys) -> None:
    """Community level 113 (7×7): forced row/col and n-group col line fire.

    After A is placed as region singleton:
      forced row  → B confined to row 1, D confined to row 2
      n-group col → cols {6} exclusive to E; cols {5} exclusive to F
      forced col  → C confined to col 1
      search      → resolves the remaining queens
    Source: https://queensgame.vercel.app/community-level/113
    """
    board = [
        ["A", "B", "B", "B", "D", "E", "E"],
        ["C", "B", "B", "B", "D", "F", "E"],
        ["C", "D", "D", "D", "D", "F", "E"],
        ["C", "C", "C", "G", "F", "F", "E"],
        ["C", "C", "C", "G", "E", "F", "E"],
        ["C", "G", "G", "G", "E", "F", "E"],
        ["C", "G", "G", "G", "E", "E", "E"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "confined to row" in out     # rule_forced_row_col row branch
    assert "confined to col" in out     # rule_forced_row_col col branch
    assert "n-group: cols" in out       # rule_n_group col line perspective


def test_stepwise_colour_perspective_and_lookahead_large(capsys) -> None:
    """Community level 114 (11×11): n-group colour perspective on a larger board.

    {B,K} candidates span rows {8,9} → claims those rows.
    {H,J} candidates span cols {0,1} → claims those cols.
    Search resolves the remaining queens.
    Source: https://queensgame.vercel.app/community-level/114
    """
    board = [
        ["H", "H", "D", "D", "D", "D", "D", "D", "I", "I", "I"],
        ["H", "H", "F", "F", "D", "D", "D", "F", "F", "I", "I"],
        ["H", "F", "G", "G", "F", "D", "F", "G", "G", "F", "I"],
        ["H", "F", "G", "G", "G", "F", "G", "G", "G", "F", "I"],
        ["H", "F", "C", "C", "C", "C", "C", "C", "C", "F", "I"],
        ["H", "H", "F", "C", "C", "C", "C", "C", "F", "I", "A"],
        ["A", "A", "A", "F", "E", "E", "E", "F", "A", "A", "A"],
        ["J", "J", "A", "A", "F", "F", "F", "E", "E", "B", "B"],
        ["G", "K", "K", "K", "K", "F", "B", "B", "B", "B", "G"],
        ["G", "K", "K", "K", "K", "B", "B", "B", "B", "B", "G"],
        ["G", "G", "G", "G", "G", "G", "G", "G", "G", "G", "G"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "claims rows" in out     # rule_n_group colour perspective (rows)
    assert "claims cols" in out     # rule_n_group colour perspective (cols)
    assert "search" in out           # search resolves remaining queens


@pytest.mark.slow
def test_stepwise_lookahead_10x10(capsys) -> None:
    """Community level 108 (10×10): search resolves after deduction rules stall.

    Source: https://queensgame.vercel.app/community-level/108
    """
    board = [
        ["E", "D", "D", "D", "D", "C", "A", "A", "A", "A"],
        ["E", "D", "C", "C", "C", "C", "A", "A", "A", "A"],
        ["E", "D", "D", "D", "D", "C", "B", "B", "A", "B"],
        ["E", "E", "E", "E", "D", "D", "B", "B", "A", "B"],
        ["F", "F", "F", "E", "D", "B", "B", "B", "B", "B"],
        ["F", "E", "E", "E", "D", "H", "H", "I", "I", "J"],
        ["F", "E", "F", "F", "F", "H", "H", "I", "I", "J"],
        ["F", "F", "F", "G", "F", "F", "H", "I", "I", "J"],
        ["G", "G", "G", "G", "F", "F", "H", "J", "J", "J"],
        ["H", "H", "H", "H", "H", "H", "H", "J", "J", "J"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "search" in out           # search resolves remaining queens


def test_stepwise_xwing_with_lookahead(capsys) -> None:
    """Community level 578 (8×8): forced row, n-group colour perspective, and x-wing all fire.

    D candidates are confined to row 2 → forced row fires.
    {E,F} candidates span exactly rows {0,1} → n-group claims those rows.
    x-wing fires twice; search resolves the remaining queens.
    Source: https://queensgame.vercel.app/community-level/578
    """
    board = [
        ["F", "F", "A", "A", "A", "E", "E", "E"],
        ["F", "A", "A", "C", "A", "A", "A", "E"],
        ["A", "A", "C", "C", "D", "D", "A", "E"],
        ["A", "C", "C", "C", "C", "C", "A", "A"],
        ["A", "A", "B", "B", "C", "C", "C", "A"],
        ["G", "A", "B", "B", "B", "B", "A", "A"],
        ["G", "A", "A", "A", "B", "A", "A", "H"],
        ["G", "G", "G", "A", "A", "A", "H", "H"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result[0] is not None
    _assert_matches_solver(board, result[0])
    assert "confined to row" in out     # rule_forced_row_col row branch
    assert "claims rows" in out         # rule_n_group colour perspective (rows)
    assert "x-wing:" in out             # rule_x_wing fires


def test_stepwise_345_first_xwing_per_pass(capsys) -> None:
    """Community level 345 (7x7): apply the first X-Wing found each pass.

    rule_x_wing scans size 2..N and short-circuits on the first valid hit,
    then returns so other rules can run before the next x-wing scan.
    Source: https://queensgame.vercel.app/community-level/345
    """
    board = [
        ["B", "B", "G", "B", "B", "B", "B"],
        ["B", "A", "A", "F", "A", "C", "B"],
        ["B", "A", "A", "A", "A", "A", "C"],
        ["B", "G", "A", "E", "A", "A", "B"],
        ["F", "A", "A", "A", "A", "D", "B"],
        ["B", "A", "A", "A", "A", "A", "B"],
        ["B", "B", "E", "B", "D", "B", "B"],
    ]
    result = solve_stepwise(board, verbose=True, timestamps=True, x_wing_max=9)
    out = capsys.readouterr().out
    assert result[0] is not None
    _assert_matches_solver(board, result[0])

    # First-hit-per-pass: expect the earliest available hit at each scan.
    l2 = "x-wing: size 2 {E,G}"
    l3 = "x-wing: size 3 {D,E,F}"
    l5 = "x-wing: size 5 {A,B,C,F,G}"
    for line in [l2, l3, l5]:
        assert line in out
    assert out.count("x-wing:") >= 3
    assert out.index(l2) < out.index(l3) < out.index(l5)


@pytest.mark.slow
def test_stepwise_641_no_search(capsys) -> None:
    """Community level 641 (18×18): solved entirely by deduction — no backtracking.

    Key rule firings:
      forced row/col → M confined to row 15, N to row 14, R to col 3
      n-group colour perspective → {A,B,J,K,L,P,R} claims rows 0–6
      x-wing → {A,B,C,D} confined to rows {0,17} ∪ cols {0,17}
      shadow → [E] and [F] each eliminate one cell
      x-wing → {E,I,J,K} confined to rows {1,16} ∪ cols {1,16}
      n-group line perspective → col 7 exclusive to G; cols {5,8,9} to {F,M,O}
    Source: https://queensgame.vercel.app/community-level/641
    """
    board = [
        ["A","A","A","E","E","E","E","E","E","E","B","B","B","B","B","B","B","B"],
        ["A","K","K","K","K","O","O","O","O","L","L","L","L","L","J","J","J","B"],
        ["A","K","L","R","O","O","H","H","O","O","O","P","P","L","L","L","J","E"],
        ["A","K","L","R","O","H","H","H","H","H","O","O","P","P","P","L","J","E"],
        ["E","K","L","R","O","O","O","O","H","H","H","O","O","P","P","L","J","E"],
        ["E","K","L","O","G","G","G","O","O","O","H","H","O","O","P","L","Q","E"],
        ["E","K","L","O","O","O","G","G","G","O","O","H","H","O","O","Q","Q","E"],
        ["E","Q","Q","O","F","F","O","G","G","G","O","O","H","H","O","O","Q","E"],
        ["E","Q","Q","O","F","F","O","G","G","G","G","O","O","H","H","O","Q","E"],
        ["E","Q","O","G","O","O","G","G","G","O","O","G","O","H","H","O","O","E"],
        ["E","Q","O","G","G","G","G","G","O","F","F","O","O","O","H","H","O","E"],
        ["E","E","O","G","G","G","G","G","O","F","F","O","G","O","H","H","O","D"],
        ["E","E","O","G","G","G","G","G","G","O","O","G","G","O","H","O","O","D"],
        ["E","O","G","G","O","O","G","G","G","G","G","G","G","O","O","O","I","D"],
        ["E","O","G","O","F","F","O","G","O","O","O","O","O","N","N","N","I","D"],
        ["C","O","G","O","F","O","O","O","M","M","M","M","M","M","M","N","I","D"],
        ["C","O","O","O","O","E","E","I","I","I","I","I","I","I","I","I","I","D"],
        ["C","C","C","C","C","C","E","E","E","E","E","E","E","E","E","D","D","D"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result[0])
    assert "search" not in out          # solved purely by deduction
    assert "confined to row" in out     # rule_forced_row_col
    assert "x-wing:" in out             # rule_x_wing fires
    assert "n-group:" in out            # rule_n_group fires
    assert "shadow:" in out             # rule_shadow fires


# ---------------------------------------------------------------------------
# Solver unit tests (no images needed)
# ---------------------------------------------------------------------------

class TestSolveUnit:
    # 1×1 board: trivially one solution
    _1x1 = [["A"]]

    # 2×2 board: no solution – diagonal adjacency blocks all placements
    _2x2_nosol = [["A", "B"], ["A", "B"]]

    # 4×4 board with exactly 2 known solutions
    _4x4 = [
        ["A", "A", "B", "B"],
        ["A", "A", "B", "B"],
        ["C", "C", "D", "D"],
        ["C", "C", "D", "D"],
    ]

    def test_1x1_one_solution(self):
        sols = solve(self._1x1, quiet=True)
        assert sols == [[(0, 0)]]

    def test_no_solution(self):
        sols = solve(self._2x2_nosol, quiet=True)
        assert sols == []

    def test_4x4_two_solutions(self):
        sols = solve(self._4x4, quiet=True)
        assert len(sols) == 2
        assert [(1, 0), (3, 1), (0, 2), (2, 3)] in sols
        assert [(2, 0), (0, 1), (3, 2), (1, 3)] in sols

# ---------------------------------------------------------------------------
# display.print_board unit tests
# ---------------------------------------------------------------------------

class TestPrintBoard:
    _board = [["A", "B"], ["C", "D"]]

    def test_no_queens_shows_letters(self, capsys):
        print_board(self._board)
        out = capsys.readouterr().out
        assert "A" in out and "B" in out

    def test_queens_shows_crown(self, capsys):
        print_board(self._board, queens=[(0, 0), (1, 1)])
        out = capsys.readouterr().out
        assert "\U0001f451" in out

    def test_unknown_color_uses_fallback(self, capsys):
        board = [["Z"]]  # 'Z' not in PALETTE
        print_board(board)
        out = capsys.readouterr().out
        assert "\033[" in out  # ANSI escape still produced with fallback colour


# ---------------------------------------------------------------------------
# url_reader.read_community_level: mock network tests
# ---------------------------------------------------------------------------

class TestReadCommunityLevelMocked:
    _valid_url = "https://queensgame.vercel.app/community-level/1"
    @pytest.mark.slow
    def test_retries_and_raises_on_429(self):
        from urllib.error import HTTPError
        # Simulate HTTP 429 for all attempts
        def raise_429(*a, **k):
            raise HTTPError(url='u', code=429, msg='Too Many Requests', hdrs=None, fp=None)
        with patch("nqueens_recog.url_reader.urllib.request.urlopen", side_effect=raise_429):
            with pytest.raises(RuntimeError, match="Rate limited by GitHub.*429"):
                read_community_level(self._valid_url)

    @pytest.mark.slow
    def test_retries_and_raises_on_403(self):
        from urllib.error import HTTPError
        # Simulate HTTP 403 for all attempts
        def raise_403(*a, **k):
            raise HTTPError(url='u', code=403, msg='Forbidden', hdrs=None, fp=None)
        with patch("nqueens_recog.url_reader.urllib.request.urlopen", side_effect=raise_403):
            with pytest.raises(RuntimeError, match="Rate limited by GitHub.*403"):
                read_community_level(self._valid_url)


class TestReadCommunityLevelInfoMocked:
    _valid_url = "https://queensgame.vercel.app/community-level/1"
    _fake_ts_full = (
        "const level = {\n"
        "  size: 2,\n"
        "  colorRegions: [\n"
        '    ["A", "B"],\n'
        '    ["B", "A"],\n'
        "  ],\n"
        "  regionColors: {},\n"
        "  solutionsCount: 42,\n"
        '  createdBy: "alice",\n'
        "};\n"
    )
    _fake_ts_missing = (
        "const level = {\n"
        "  size: 2,\n"
        "  colorRegions: [\n"
        '    ["A", "B"],\n'
        '    ["B", "A"],\n'
        "  ],\n"
        "  regionColors: {},\n"
        "};\n"
    )

    def test_returns_full_info(self):
        from nqueens_recog.url_reader import read_community_level_info
        class _FakeResp:
            def read(self):
                return TestReadCommunityLevelInfoMocked._fake_ts_full.encode()
            def __enter__(self): return self
            def __exit__(self, *_): pass
        with patch("nqueens_recog.url_reader.urllib.request.urlopen", return_value=_FakeResp()):
            board, solutions_count, created_by = read_community_level_info(self._valid_url)
        assert board == [["A", "B"], ["B", "A"]]
        assert solutions_count == 42
        assert created_by == "alice"

    def test_returns_info_with_missing_fields(self):
        from nqueens_recog.url_reader import read_community_level_info
        class _FakeResp:
            def read(self):
                return TestReadCommunityLevelInfoMocked._fake_ts_missing.encode()
            def __enter__(self): return self
            def __exit__(self, *_): pass
        with patch("nqueens_recog.url_reader.urllib.request.urlopen", return_value=_FakeResp()):
            board, solutions_count, created_by = read_community_level_info(self._valid_url)
        assert board == [["A", "B"], ["B", "A"]]
        assert solutions_count == 0
        assert created_by == ""

    _valid_url = "https://queensgame.vercel.app/community-level/1"
    _fake_ts = (
        "const level = {\n"
        "  size: 2,\n"
        "  colorRegions: [\n"
        '    ["A", "B"],\n'
        '    ["B", "A"],\n'
        "  ],\n"
        "  regionColors: {},\n"
        "};\n"
    )

    def test_raises_on_bad_url(self):
        with pytest.raises(ValueError, match="Unrecognised URL"):
            read_community_level("https://example.com/not-a-level")

    def test_raises_runtime_on_network_error(self):
        with patch("nqueens_recog.url_reader.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = URLError("connection refused")
            with pytest.raises(RuntimeError, match="Could not fetch"):
                read_community_level(self._valid_url)

    def test_returns_grid_on_success(self):
        fake_ts = self._fake_ts

        class _FakeResp:
            def read(self):
                return fake_ts.encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        with patch("nqueens_recog.url_reader.urllib.request.urlopen", return_value=_FakeResp()):
            result = read_community_level(self._valid_url)
        assert result == [["A", "B"], ["B", "A"]]


# ---------------------------------------------------------------------------
# palette.grid_to_letters: unknown-colour fallback
# ---------------------------------------------------------------------------

class TestGridToLettersUnknown:
    def test_unknown_rgb_gets_lowercase_letter(self):
        tile = Tile(row=0, col=0, color_rgb=(1, 2, 3))  # far outside all palette colours
        grid = Grid(tiles=[[tile]], rows=1, cols=1)
        result = grid_to_letters(grid)
        assert result[0][0].islower()

    def test_two_unknown_colors_get_distinct_letters(self):
        t1 = Tile(row=0, col=0, color_rgb=(1, 2, 3))
        t2 = Tile(row=0, col=1, color_rgb=(4, 5, 6))
        grid = Grid(tiles=[[t1, t2]], rows=1, cols=2)
        result = grid_to_letters(grid)
        assert result[0][0] != result[0][1]
        assert result[0][0].islower() and result[0][1].islower()


# ---------------------------------------------------------------------------
# __main__.main(): CLI entry point
# ---------------------------------------------------------------------------

_SIMPLE_BOARD_STR = ["AB", "BA"]  # grid_to_letters returns list of strings


class TestMain:
    """Tests for the CLI entry point in __main__.main()."""

    def test_image_path_prints_grid_size(self, capsys):
        with patch("sys.argv", ["nqueens-recog", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.grid_reader.read_grid"), \
             patch("nqueens_recog.palette.grid_to_letters", return_value=_SIMPLE_BOARD_STR):
            main()
        assert "2 \u00d7 2" in capsys.readouterr().out

    def test_url_path_success(self, capsys):
        with patch("sys.argv", ["nqueens-recog", "https://queensgame.vercel.app/community-level/1"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=True), \
             patch("nqueens_recog.__main__.read_community_level", return_value=[["A", "B"], ["B", "A"]]):
            main()
        assert "2 \u00d7 2" in capsys.readouterr().out

    def test_url_value_error_exits(self):
        with patch("sys.argv", ["nqueens-recog", "https://queensgame.vercel.app/community-level/1"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=True), \
             patch("nqueens_recog.__main__.read_community_level", side_effect=ValueError("bad")):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_url_runtime_error_exits(self):
        with patch("sys.argv", ["nqueens-recog", "https://queensgame.vercel.app/community-level/1"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=True), \
             patch("nqueens_recog.__main__.read_community_level", side_effect=RuntimeError("net")):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_non_square_board_exits(self):
        with patch("sys.argv", ["nqueens-recog", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.grid_reader.read_grid"), \
             patch("nqueens_recog.palette.grid_to_letters", return_value=["AB", "B"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_wrong_color_count_exits(self):
        with patch("sys.argv", ["nqueens-recog", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.grid_reader.read_grid"), \
             patch("nqueens_recog.palette.grid_to_letters", return_value=["AA", "AA"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_verbose_flag_prints_board(self, capsys):
        with patch("sys.argv", ["nqueens-recog", "--verbose", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.grid_reader.read_grid"), \
             patch("nqueens_recog.palette.grid_to_letters", return_value=_SIMPLE_BOARD_STR):
            main()
        assert "\033[" in capsys.readouterr().out

    def test_solve_flag_prints_total(self, capsys):
        with patch("sys.argv", ["nqueens-recog", "--solve", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.grid_reader.read_grid"), \
             patch("nqueens_recog.palette.grid_to_letters", return_value=_SIMPLE_BOARD_STR):
            main()
        assert "Total solutions found:" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# grid_reader internal helpers: edge-case coverage
# ---------------------------------------------------------------------------


class TestGridReaderInternals:
    def test_read_grid_raises_for_nonsquare(self, tmp_path):
        """read_grid raises ValueError when detected row/col counts differ."""
        import numpy as np
        import cv2
        img = np.full((100, 150, 3), 200, dtype=np.uint8)
        p = tmp_path / "fake.png"
        cv2.imwrite(str(p), img)
        with patch(
            "nqueens_recog.grid_reader._line_positions",
            side_effect=[[20, 50, 80], [30, 60]],  # 4 rows, 3 cols
        ):
            with pytest.raises(ValueError, match="not square"):
                read_grid(str(p))


# ---------------------------------------------------------------------------
# Stepwise solver: rules 1-3 must be sufficient for sample puzzles
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("image_path,label,expected_cols", [
    (PUZZLE_589, "589", [10, 1, 5, 8, 6, 2, 7, 4, 9, 11, 3]),
    (PUZZLE_687, "687", [14, 3, 6, 4, 12, 7, 5, 8, 11, 13, 10, 17, 2, 15, 9, 16, 1]),
    (PUZZLE_657, "657", [16, 2, 13, 10, 8, 14, 12, 18, 7, 4, 6, 15, 5, 11, 9, 17, 3, 1]),
])
def test_stepwise_solves_puzzle(image_path: Path, label: str, expected_cols: list[int]) -> None:
    """All rules must fully solve each sample puzzle."""
    board = [list(row) for row in grid_to_letters(read_grid(str(image_path)))]
    result = solve_stepwise(board, quiet=True)
    assert result[0] is not None, f"Puzzle {label}: stepwise solver got stuck"
    cols = [result[0][r] + 1 for r in range(len(board))]
    assert cols == expected_cols, (
        f"Puzzle {label}: stepwise solution {cols} != expected {expected_cols}"
    )
