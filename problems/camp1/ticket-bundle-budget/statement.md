## Statement

A ticket booth sells `n` tickets, each with its own price. A customer wants to buy exactly **two** different tickets (a "bundle"), and the total price of the bundle must fall within their budget window: at least `L` baht and at most `R` baht.

Given the list of ticket prices, count how many distinct bundles (pairs of tickets, chosen by position — two tickets with the same price but different positions count as different bundles) have a total price `T` satisfying `L <= T <= R`.

Formally, count the number of index pairs `(i, j)` with `1 <= i < j <= n` such that `L <= price[i] + price[j] <= R`.

## Input

The first line contains three integers `n`, `L`, and `R`.

The second line contains `n` integers `price[1], price[2], ..., price[n]`.

## Output

Print a single integer: the number of bundles whose total price is within the budget window `[L, R]`.

## Constraints

- `2 <= n <= 100000`
- `1 <= L <= R <= 2000000000`
- `1 <= price[i] <= 1000000000` for every `i`

## Sample

### Input
```
5 4 6
3 1 4 1 5
```

### Output
```
6
```

(The pair sums, over all `C(5,2)=10` pairs, are: 4, 7, 4, 8, 5, 9, 2, 6, 5, 6. Six of these — 4, 4, 5, 6, 5, 6 — lie between 4 and 6 inclusive.)
