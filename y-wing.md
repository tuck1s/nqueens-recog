# Y-Wing: a generalised X-Wing

This note records the two Y-Wing deductions proposed in [issue #4](https://github.com/tuck1s/nqueens-recog/issues/4), together with the implementation details used by the stepwise solver. It maps directly onto the geometry table in [README.md](README.md#large-x-wings) — see the note at the end of each section below for which table rows each deduction produces.

Let `R` be a selected set of rows, `C` a selected set of columns, and `I = R × C` their crossing cells. Every row and every column receives exactly one queen, so — by inclusion-exclusion on "queens whose row is in `R`" and "queens whose column is in `C`" — the number of queens in their union is:

$$
|Q(R \cup C)| = |R| + |C| - |Q(I)|.
$$

This holds unconditionally; it's just counting, not a Y-Wing-specific claim.

Ordinary X-Wing is the case where `k` colours are confined to `R ∪ C` and `k = |R| + |C|`. Substituting into the formula above gives `|Q(I)| ≥ 0`, so X-Wing claims all the selected lines but says nothing about the intersection. Y-Wing looks at what happens when `k < |R| + |C|` instead — i.e. *fewer* colours than lines — which forces queens into the intersection and unlocks two further deductions.

## 1. Isolated union: forcing colours into the intersection

Suppose every remaining candidate in `R ∪ C` belongs to one of exactly `k` colours. Since no other colour has a candidate there, at most `k` queens can land in `R ∪ C`: `|Q(R ∪ C)| ≤ k`. Substituting into the opening formula:

$$
|Q(I)| = |R| + |C| - |Q(R \cup C)| \ge |R| + |C| - k.
$$

So at least `forced = |R| + |C| - k` queens must sit in `I`. If precisely `forced` distinct colours have *any* candidate in `I`, pigeonhole forces the conclusion: those are the only colours that could supply the required queens, so each of them must place its queen inside `I`. Their candidates outside `I` can therefore be eliminated.

The implementation deliberately checks that *all* candidate cells in the union have one of the `k` colours (not just some), then locks the exact set of colours that must occupy the intersection.

**Worked example.** Take `R = {row 2, row 3}`, `C = {col 2, col 3}`, so `I` is the 2×2 block at their crossing. Suppose every remaining candidate in rows 2–3 and columns 2–3 belongs to one of `k = 3` colours (A, B, C) — four lines, three colours. Then `forced = 2 + 2 - 3 = 1`: at least one queen must land somewhere in `I`. If only colour A has a candidate inside `I`, A is the only colour that *can* supply that forced queen — so A must place there, and every other A-candidate outside `I` can be eliminated.

*README mapping:* this is the deduction behind every row whose Elimination effect says "colours also grouped from \[the] intersection\[s]" — the `k=2`, `k=3`, and the general `k≥4` rows all describe this same forcing argument at different sizes.

## 2. Forced intersection: discarding colours from the union

Some colours can already be *completely* confined to `I` (all their candidates lie inside it, not just some). Because each queen occupies a distinct row and column, if `locked` such colours exist they necessarily consume `locked` distinct rows of `R` and `locked` distinct columns of `C` between them.

Since `|Q(I)| ≥ locked`, the opening formula gives an upper bound on the union: `|Q(R ∪ C)| = |R| + |C| - |Q(I)| ≤ |R| + |C| - locked`. Call this remaining capacity `target = |R| + |C| - locked`. If precisely `target` colours (the `locked` ones plus any others) have *all* their candidates confined to `R ∪ C`, those colours alone already account for the full capacity — there is no room left for a queen of any other colour to land there. Any other colour's candidates within the selected rows and columns can therefore be eliminated.

**Worked example, continuing the one above.** Suppose a fourth colour, D, turns out to have every candidate confined to `I` (so `locked = 1`). The union's capacity shrinks to `target = 2 + 2 - 1 = 3`. If exactly three colours — say A, D, and one more, E — have all their candidates confined to rows {2,3} ∪ columns {2,3}, they fill that capacity exactly. Any other colour's candidate anywhere in rows 2–3 or columns 2–3 can be eliminated, even outside `I`.

*README mapping:* this is what the "Non-colours eliminated from lines" wording describes, and it's what lets the `k ≥ 4` row's crossing-point elimination reach cases where `|R| = 1` or `|C| = 1` — the "degenerate" cross — without needing a separate table row for that shape: whether the crossing-point elimination is achieved via §1 (forcing) or §2 (discarding) depends on what's already locked elsewhere on the board, not on the shape alone. That's why the table only needs one row per `(k, R, C)` geometry rather than one per mechanism.

## Solver behaviour

Both checks run after ordinary X-Wing, so the less expensive rule gets the first opportunity to simplify the board. Their search is bounded by `--x-wing-max`: it considers at most that many colours and at most one more selected line (a Y-Wing needs at least one forced intersection). This keeps the additional combinations tractable.

The trace names are:

```
y-wing (isolated): {…} forced into intersection of rows {…} and cols {…}
y-wing (forced intersection): size … (locked=…) {…} confined to rows {…} ∪ cols {…}
```

The original issue calls these deductions "Y-Wing"; this name is used here as project terminology, rather than the similarly named Sudoku pattern.
