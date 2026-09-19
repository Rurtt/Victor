## Statement

A farmer owns $N$ rectangular plots of land arranged in a row. The $i$-th plot has width $a_i$ meters.

For every pair of plots $(i, j)$ with $i < j$, the farmer wants to build a shared fence made of identical square tiles that exactly cover both plot widths without cutting any tile. The largest possible tile side length for the pair $(i, j)$ is $\gcd(a_i, a_j)$ (the greatest common divisor of $a_i$ and $a_j$).

Compute the sum, over **all** pairs $i < j$, of $\gcd(a_i, a_j)$.

## Input

The first line contains one integer $N$, the number of plots.

The second line contains $N$ integers $a_1, a_2, \dots, a_N$, the widths of the plots.

## Output

Print a single integer: the sum of $\gcd(a_i, a_j)$ over all pairs $1 \le i < j \le N$.

If $N = 1$ there are no pairs, so the answer is $0$.

## Constraints

- $1 \le N \le 3000$
- $1 \le a_i \le 10^9$

## Sample

### Input
```
4
12 18 24 30
```

### Output
```
42
```

Explanation: the six pairwise gcds are gcd(12,18)=6, gcd(12,24)=12, gcd(12,30)=6, gcd(18,24)=6, gcd(18,30)=6, gcd(24,30)=6. Their sum is 6+12+6+6+6+6=42.
