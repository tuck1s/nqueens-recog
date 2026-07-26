# nqueens-recog

[![CI](https://github.com/tuck1s/nqueens-recog/actions/workflows/ci.yml/badge.svg)](https://github.com/tuck1s/nqueens-recog/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tuck1s/nqueens-recog/graph/badge.svg)](https://codecov.io/gh/tuck1s/nqueens-recog)

For results, see [the results index](https://tuck1s.github.io/nqueens-recog/).

Detect and parse a colour grid from an N-Queens puzzle, either from a
[community-level URL](https://queensgame.vercel.app/community-level/657) or
from a screenshot/image file.

**URL mode** fetches the level's TypeScript source directly from the
[queens-game GitHub repo](https://github.com/samimsu/queens-game), giving an
exact, lossless letter grid with no image processing.

**Image mode** uses OpenCV for perspective correction and gradient-based grid
line detection, then k-means colour quantisation to assign each cell to one
of the *n* region colours. No OCR is used; recognition is purely colour-based.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

> **Note:** By popular demand, cell locations are mapped for text output e.g. to (R1,C1) for the top left cell. Code internals still use Python 0-based lists.

## Run

```bash
nqueens-recog https://queensgame.vercel.app/community-level/657
nqueens-recog img/puzzle-687.png
```

Prints `Grid: N × N, N colours`. Add `-v` / `--verbose` to also show the
coloured board (ANSI background per region, region letter in each cell).

## Stepwise solver

`--stepwise` applies human-like logical elimination rules and prints a trace
of each deduction, rather than backtracking exhaustively:

```bash
nqueens-recog https://queensgame.vercel.app/community-level/705 --stepwise
```

Add `-v` / `--verbose` to also render the board state after each rule fires,
showing region letters for active candidates, `✖` for eliminated cells, and
👑 for placed queens (newly-eliminated cells are highlighted in red).

Add `--timestamps` to prefix trace lines with elapsed time:

```bash
nqueens-recog https://queensgame.vercel.app/community-level/705 --stepwise --timestamps
# 0.2s:   forced: [A] confined to row 1 → 3 cell(s) eliminated
```

Add `--x-wing-max N` to cap how large X-Wing groups are scanned. If omitted,
the default is `6`. Larger values increase runtimes a lot.

```bash
# Default: scans up to size 6
nqueens-recog https://queensgame.vercel.app/community-level/705 --stepwise

# Explicit cap
nqueens-recog https://queensgame.vercel.app/community-level/705 --stepwise --x-wing-max 4
```

Add `--lookahead-max-cands N` to limit lookahead to colours with at most `N`
active candidates. When set, lookahead processes all eligible colours in the
same pass (instead of stopping after the first contradictory colour).

```bash
# Only run lookahead for colours with <= 5 active candidates
nqueens-recog https://queensgame.vercel.app/community-level/734 --stepwise --lookahead-max-cands 5
```

X-Wing scans ascending from size 2 up to the cap, printing a progress line per size, e.g.:
```
x-wing scan from size 2 up to 6...
  x-wing scan: size 2 → 0 hit(s) after 28 group(s)
  x-wing scan: size 3 → 0 hit(s) after 56 group(s)
  x-wing scan: size 4 → 1 hit after 35 group(s)
```
The first valid hit found is applied immediately and the rule returns (no further scanning that pass).

Ten rules are applied in order of increasing cost:

1. **Region singleton** — a region/row/column narrowed to one cell; place the queen.
2. **Region forced row/col** — all candidates for a region share a row or column; claim it.
3. **Squeeze** — a row/col's candidates span ≤ 2 cells, so the queen always diagonally attacks the overlap zone in adjacent rows/cols.
4. **Shadow** — eliminate any cell attacked by *all* candidates of a colour.
5. **N-group** — k regions whose candidates are confined to k rows/cols; reserve those lines.
6. **X-Wing** — c colours whose candidates fit within a rows + b columns (a+b=c); scan sizes 2 upward, apply the first valid hit found, then return to other rules.
7. **Y-Wing** — a generalised X-Wing that uses colours forced into row/column intersections; see [y-wing.md](y-wing.md).
8. **Elimination** — placing a queen at a candidate leaves another region empty; rule it out.
9. **Lookahead** — trial-place a queen in every candidate of a colour; by default stop after the first contradictory colour. With `--lookahead-max-cands N`, consider all colours with ≤ N candidates in the same pass.
10. **Search** — last resort: pick the most-constrained region, guess, and backtrack.

### What is X-Wing?

From [jess334](https://github.com/jess334)'s explanation across levels [593](https://queensgame.vercel.app/community-level/593), [600](https://queensgame.vercel.app/community-level/600), [641](https://queensgame.vercel.app/community-level/641):


Suppose you have $k$ colours (regions) whose candidates are all confined to the union of a set of rows $R$ and columns $C$, where $|R| + |C| = k$. This forms a cross or "#" shape on the board.

Because each colour must be placed in a unique row and column:

- At least $|C|$ of the queens must be placed in rows outside $R$, so their columns must be in $C$ (using up all those columns).
- The remaining $|R|$ queens are placed in rows $R$ (using up all those rows).

All $|R|$ rows and all $|C|$ columns will be claimed by these $k$ colours. Therefore, any candidate in those rows or columns that is not one of the $k$ colours can be eliminated. This works for various geometries:

| $k$ | `R` | `C` | Shape | Elimination effect | Note |
|-|-|-|-|-|-|
| 2 | 1 | 1 | 1 row, 1 col | Non-colours eliminated from lines; colours also grouped from the intersection | This overlaps the region forced row/col rule |
| 3 | 1 | 2 | 1 row, 2 cols | Non-colours eliminated from lines; colours also grouped from intersections | True X-Wing starts at k=3 |
| 3 | 2 | 1 | 2 rows, 1 col | Non-colours eliminated from lines; colours also grouped from intersections | |
| 4 | 2 | 2 | 2 rows, 2 cols (cross) | Non-colours eliminated from lines; all 4 colours _also eliminated from crossing-points_ | **Classic X-Wing (cross/#)** |
| ≥4 | ≥1 | ≥1 | R rows, C cols (cross) | Non-colours eliminated from lines; all k colours _also eliminated from crossing-points_ | Larger shapes |

**Generalisation for $k \geq 4$:**
- If $k$ colours are confined to $|R|$ rows and $|C|$ columns with $|R| + |C| = k$:
   - All those rows and columns are claimed for those colours (eliminate other colours from those lines).
   - All $|R| \times |C|$ intersections (crossing-points) are also eliminated for the $k$ colours. This holds even when either dimension is one: the queens outside the selected rows must exhaust the selected columns (and vice versa).

#### Large X-wings

Some large X-wings can be found by changing the solver to look for largest-first.
These are not given by the current stepwise code, as it looks for smaller X-wings first and uses the first found one.

|Level|Size|
|-|-|
|587|9|
|641|9|
|674|9|

There are many levels with size 8 X-wings. At time of writing: 273, 538, 583, 589, 600, 601, 623, 636, 647, 674.

## Batch stepwise solver

This script looks for any unsolved community levels, printing solution output as HTML. The HTML uses fixed-width coloured cells so the board renders cleanly in any browser regardless of font. Also an index.html is created/updated as an easy way to view the solutions in a browser.

Each level is solved once. The generated trace is captured and converted to HTML via `aha` (no second solver run). In batch mode, `--verbose` mirrors that same trace to stdout as it is produced.

**Run the batch stepwise solver from the project root:**

```bash
python chk_stepwise.py --help

# Auto mode (default) - solve all missing and new levels
python chk_stepwise.py
python chk_stepwise.py --timestamps                # Include elapsed prefixes in stepwise traces

# Range mode (specify both --first and --last):
python chk_stepwise.py --first 1 --last 100             # Levels 1–100, rate 2/s
python chk_stepwise.py --first 578 --last 642 --rate 0  # Unlimited rate
python chk_stepwise.py --first 578 --last 642 --x-wing-max 4
python chk_stepwise.py --first 734 --last 734 --lookahead-max-cands 5
```

**Arguments:**

- `--first N`   — First level number (inclusive). Must be used with `--last`.
- `--last N`    — Last level number (inclusive). Must be used with `--first`.
- `--rate R`    — Submissions per second; 0 = unlimited (default: 2).
- `--timestamps` — Pass through to stepwise runs so generated traces are prefixed with elapsed time.
- `--x-wing-max N` — Pass through to stepwise X-Wing scanning cap (default: 6). Larger values can increase runtimes significantly.
- `--lookahead-max-cands N` — Pass through to stepwise lookahead candidate cap. When set, lookahead considers all eligible colours (≤ N candidates) in one pass.
- `--verbose` — Mirror the live stepwise trace to stdout during batch processing (HTML is still written from the captured trace).

> \[!WARNING]
> Previous `--workers` option removed, as there are [weird Python multiprocessing bugs](https://sqlpey.com/python/solved-how-to-overcome-python-multiprocessing-crashes-on-macos/) with MacOS.

If neither --first nor --last is given, auto mode will:
   - Detect all missing levels in the existing index and solve them.
   - Continue probing for new levels over HTTP until a 404 is returned.
   - Update all_solutions/index.html with all results.

For each level it:

1. Fetches the board and reads `solutionsCount` and `createdBy` from the TypeScript source.
2. Runs the stepwise solver and captures its trace.
3. Validates the result; reports any invalid or stuck solution on stderr with a `!! ` prefix.
4. Prints elapsed time and which deduction rules were used.
5. Writes `all_solutions/level_N.html` with a `Level N — by <creator>` browser title (requires `aha`: `brew install aha`).
6. Writes `all_solutions/index.html` — a summary table (level, multi-solution flag, creator, runtime, rules used).

Example output:

```
=== Level 640 ===
  Board: 6×6, solutionsCount=1, createdBy=colby_hurst
  Stepwise: ok [stepwise 0.002s] — rules used: singleton, forced, squeeze, shadow, n-group
  Written: all_solutions/level_640.html
=== Level 641 ===
  Board: 18×18, solutionsCount=1, createdBy=Jess
  Stepwise: ok [stepwise 0.041s] — rules used: singleton, forced, squeeze, shadow, n-group, x-wing
  Written: all_solutions/level_641.html
Written: all_solutions/index.html
```

### Running under PyPy - not recommended

OpenCV is not available for PyPy, so the image-recognition is not possible either.

## Test

Run tests from the project root with the virtual environment activated:

```bash
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pytest
pytest --slow
pytest --network
```

If you see import errors, make sure you are running pytest from the root directory (where README.md is located) and that your virtual environment is active. This ensures all local imports and dependencies are resolved correctly.

## Project layout

```
chk_stepwise.py     # batch stepwise solver script (HTML output for all levels)
src/nqueens_recog/
   grid_reader.py   # image → Grid (perspective correct, line detect, k-means)
   palette.py       # queensgame colour palette and nearest-colour matching
   display.py       # ANSI terminal board renderer (letter view and queen view)
   url_reader.py    # community-level URL → letter grid (fetches GitHub TS source)
   solver.py        # backtracking solver; prints spoiler line + coloured board
   __main__.py      # entry point: nqueens-recog <url_or_image> [--solve [-v]] [--stepwise [--timestamps] [--x-wing-max N] [--lookahead-max-cands N]]
img/
   puzzle-*.png     # sample puzzle images (test fixtures)
tests/
   test_*.py        # pytest cases
```

## How the image recognition works

1. **Perspective correction** — find the four-corner contour of the grid and
   warp it to a rectangle.
1. **Border stripping** — locate the bounding box of dark (grid-line) pixels
   to remove the surrounding cream/white border.
1. **Grid line detection** — project gradient magnitudes along each axis and
   find peaks to locate row and column boundaries.
1. **Squareness check** — raise `ValueError` if the number of detected rows
   differs from the number of columns.
1. **Colour sampling** — take the median colour of the inner 60 % of each cell.
1. **K-means quantisation** — cluster the *n²* samples into *n* canonical
   colours (one per region).
1. **Palette matching** — map each canonical colour to its nearest letter in
   the queensgame default palette by squared RGB distance.

## Recursive solver (obsolete-ish)

As an alternative to `--stepwise`, use `--solve` to run the basic backtracking solver and print the spoiler line of
1-based column positions (one per row).

> \[!NOTE]
> This is slow on large and complex levels. See "stepwise" solver below.

```
> Solution: 16, 2, 13, 10, 8, 14, 12, 18, 7, 4, 6, 15, 5, 11, 9, 17, 3, 1
Total solutions found: 1
```

`-v` and `--solve` are independent — combine them to show both the coloured
grid and the solved board with queen markers:

```bash
nqueens-recog https://queensgame.vercel.app/community-level/657 --solve -v
```

`python -m nqueens_recog <url_or_image>` also works if the package is not installed.
