## Statement

A traffic light repeats a fixed cycle forever, starting at time `0`. During each cycle it is:

- **Red** for the first `R` seconds of the cycle,
- then **Green** for the next `G` seconds,
- then **Yellow** for the last `Y` seconds,

after which the cycle repeats (back to Red) with total cycle length `R + G + Y` seconds.

More precisely, at time `0` the light turns Red. If `c = R + G + Y` is the cycle length and `t` is a non-negative integer number of seconds since time `0`, let `r = t mod c` (the number of seconds elapsed within the current cycle, where `r = 0` means the cycle has just started). Then the color at time `t` is:

- **Red** if `0 <= r < R`
- **Green** if `R <= r < R + G`
- **Yellow** if `R + G <= r < R + G + Y`

You are given `R`, `G`, `Y`, and `Q` query times. For each query time `t`, output the color of the light at that time.

## Input

The first line contains four integers `R`, `G`, `Y`, `Q`.

Each of the next `Q` lines contains a single integer `t`, the query time in seconds.

## Output

Print `Q` lines. The `i`-th line must contain the color (`Red`, `Green`, or `Yellow`) of the light at the `i`-th query time.

## Constraints

- `1 <= R, G, Y <= 10^9`
- `1 <= Q <= 200000`
- `0 <= t <= 10^18` for every query

## Sample

### Input
```
2 3 1 5
0
1
2
4
6
```

### Output
```
Red
Red
Green
Green
Red
```
