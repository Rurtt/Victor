## Statement

Mint runs a bakery and has baked $N$ buns, numbered $1$ to $N$. The $i$-th bun has price $A_i$ baht.

Mint wants to put buns into gift boxes, two buns per box. A box is called *lucky* if the sum of the prices of the two buns inside it is divisible by a magic number $K$.

Mint wants to know: among all $\binom{N}{2}$ possible ways to choose two different buns $i < j$, how many of those pairs would form a lucky box, i.e. how many pairs satisfy
$$(A_i + A_j) \bmod K = 0?$$

## Input

The first line contains two integers $N$ and $K$.

The second line contains $N$ integers $A_1, A_2, \ldots, A_N$.

## Output

Print a single integer: the number of pairs $(i, j)$ with $1 \le i < j \le N$ such that $(A_i + A_j) \bmod K = 0$.

## Constraints

- $2 \le N \le 2 \times 10^5$
- $2 \le K \le 10^5$
- $1 \le A_i \le 10^9$
- All values in the input are integers.

## Sample

### Sample Input 1
```
5 3
1 2 3 4 5
```

### Sample Output 1
```
4
```

The lucky pairs are $(1,2)$, $(1,5)$, $(2,4)$, and $(4,5)$, since $1+2=3$, $1+5=6$, $2+4=6$, and $4+5=9$ are all divisible by $3$.
