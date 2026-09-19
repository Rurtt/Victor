## Statement

A new city is being built along a straight road represented as the integer points $0, 1, 2, \dots, L-1$.

There are $N$ signal towers along this road. Tower $i$ broadcasts signal to every integer point $x$ satisfying $l_i \le x < r_i$ (note: the right endpoint is **excluded**).

For each point $x$ on the road, define its *coverage* as the number of towers whose interval contains $x$.

You must find:
1. The maximum coverage value $M$ achieved by any point on the road (points not covered by any tower have coverage $0$).
2. The number of points $x$ (with $0 \le x < L$) whose coverage equals $M$.
3. The smallest such point $x$.

## Input

The first line contains two integers $N$ and $L$.

Each of the next $N$ lines contains two integers $l_i$ and $r_i$ describing tower $i$.

## Output

Output three integers separated by spaces: $M$, the number of points achieving coverage $M$, and the smallest point achieving coverage $M$.

## Constraints

- $1 \le N \le 200000$
- $1 \le L \le 1000000$
- $0 \le l_i < r_i \le L$ for every tower

## Sample

### Input
```
3 10
0 5
2 7
6 8
```

### Output
```
2 3 2
```

### Explanation
Coverage per point (0..9): 1 1 2 2 2 1 1 0 0 0.
The maximum coverage is 2, achieved at points 2, 3, 4 (3 points), and the smallest such point is 2.
