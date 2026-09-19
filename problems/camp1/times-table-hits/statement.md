## Statement

Consider a multiplication table with $N$ rows and $N$ columns, where the cell in row $i$ and column $j$ (for $1 \le i, j \le N$) contains the value $i \times j$.

You are given $Q$ queries. Each query gives an integer $K$, and you must determine how many cells of the table contain the value $K$ (that is, how many pairs $(i, j)$ with $1 \le i, j \le N$ satisfy $i \times j = K$).

## Input

The first line contains two integers $N$ and $Q$.

Each of the next $Q$ lines contains a single integer $K$, describing one query.

## Output

Output $Q$ lines. The $i$-th line should contain the number of cells in the table equal to the $i$-th query's value.

## Constraints

- $1 \le N \le 2000$
- $1 \le Q \le 2000$
- $1 \le K \le N \times N$

## Sample

### Input
```
4 3
6
16
5
```

### Output
```
2
1
0
```

### Explanation
The 4x4 multiplication table is:
```
1  2  3  4
2  4  6  8
3  6  9  12
4  8  12 16
```
The value 6 appears at (2,3) and (3,2), so the answer is 2. The value 16 appears only at (4,4), so the answer is 1. The value 5 never appears, so the answer is 0.
