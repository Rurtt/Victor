## Statement

There are $N$ candies and $K$ children sitting in a circle, numbered $1$ to $K$. Candies are handed out one at a time, starting with child $1$, then child $2$, and so on up to child $K$, then wrapping back around to child $1$ again, continuing in this order until all $N$ candies have been given out (some children may end up with $0$ candies if $K > N$).

For each child from $1$ to $K$, determine how many candies they receive in total.

## Input

A single line containing two integers:

```
N K
```

## Output

Print $K$ integers separated by single spaces: the number of candies child $1$, child $2$, ..., child $K$ receives, in that order.

## Constraints

- $1 \le N \le 10^9$
- $1 \le K \le 10^5$

## Sample 1

### Input
```
7 3
```

### Output
```
3 2 2
```

Explanation: candies go to children in order 1,2,3,1,2,3,1. Child 1 receives 3 candies, children 2 and 3 each receive 2.

## Sample 2

### Input
```
2 5
```

### Output
```
1 1 0 0 0
```
