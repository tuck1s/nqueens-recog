# Y-Wing: a generalised X-Wing

This note records the two Y-Wing deductions proposed in [issue #4](https://github.com/tuck1s/nqueens-recog/issues/4), together with the implementation details used by the stepwise solver.

Let `R` be a selected set of rows, `C` a selected set of columns, and `I = R × C` their crossing cells. Every row and column must receive one queen, so the number of queens in their union is:

$$
|Q(R \cup C)| = |R| + |C| - |Q(I)|.
$$

Ordinary X-Wing is the case where `k` colours are confined to `R ∪ C` and `k = |R| + |C|`. It claims all the selected lines. Y-Wing also uses the information supplied by queens that must occupy the crossing cells.

## 1. Forcing intersections by limited colours

Suppose candidates in `R ∪ C` belong to exactly `k` colours. Since all selected rows and columns require queens, at least

$$
|R| + |C| - k
$$

queens must be in `I`. If precisely that many distinct colours have candidates in `I`, those colours must occupy the intersection. Their candidates outside `I` can therefore be eliminated.

The implementation deliberately checks that *all candidate cells* in the union have one of the `k` colours. It then locks the exact set of colours that can occur at the intersection.

## 2. Discarding colours through forced intersections

Some colours can already be completely confined to `I`. If `locked` colours are confined there, they consume `locked` rows and `locked` columns. The remaining capacity of the union is:

$$
|R| + |C| - locked.
$$

If exactly that many colours have all their candidates in `R ∪ C` (including the locked colours), they saturate the union. Every other colour can be eliminated from the selected rows and columns.

This is the capacity reduction described in the issue. It is not a guess: each intersection-confined colour must place a queen in a distinct selected row and column.

## Solver behaviour

Both checks run after ordinary X-Wing, so the less expensive rule gets the first opportunity to simplify the board. Their search is bounded by `--x-wing-max`: it considers at most that many colours and at most one more selected line (a Y-Wing needs at least one forced intersection). This keeps the additional combinations tractable.

The trace names are:

```
y-wing (isolated): {…} forced into intersection of rows {…} and cols {…}
y-wing (forced intersection): size … (locked=…) {…} confined to rows {…} ∪ cols {…}
```

The original issue calls these deductions “Y-Wing”; this name is used here as project terminology, rather than the similarly named Sudoku pattern.
