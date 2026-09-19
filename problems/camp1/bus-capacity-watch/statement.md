## Statement

A bus starts its route with **0** passengers on board and then visits $N$ stops in order.

At stop $i$ (for $i = 1, \dots, N$), first $\text{off}_i$ passengers get off the bus, and then $\text{board}_i$ passengers get on the bus. It is guaranteed that $\text{off}_i$ never exceeds the number of passengers currently on the bus (so the passenger count never goes negative).

The bus has a capacity limit of $K$ passengers. A stop is called an **overflow stop** if, after the boarding at that stop is finished, the number of passengers on the bus is **strictly greater than** $K$.

Consider the passenger count of the bus at every moment right after finishing the boarding of a stop (there are $N$ such moments), as well as the initial count of $0$ before stop 1. Among all $N+1$ of these counts, let $M$ be the maximum value, and let $F$ be the smallest stop index at which this maximum $M$ is first reached after boarding (if the maximum is only ever the initial value $0$ and every stop's passenger count after boarding is less than $0$... which cannot happen since counts are non-negative — so if $M = 0$, report $F = 0$, meaning the maximum was already achieved before any stop).

Determine $M$, $F$, and the total number of overflow stops.

## Input

The first line contains two integers $N$ and $K$.

Each of the next $N$ lines contains two integers $\text{off}_i$ and $\text{board}_i$, describing stop $i$ in order.

## Output

Print three integers separated by spaces: $M$, $F$, and the number of overflow stops.

## Constraints

- $1 \le N \le 1000$
- $1 \le K \le 10^6$
- $0 \le \text{off}_i, \text{board}_i \le 1000$
- At every stop, $\text{off}_i$ does not exceed the number of passengers currently on the bus (before that stop's alighting).

## Sample

### Input
```
3 4
0 4
1 2
5 5
```

### Output
```
5 2 2
```

### Explanation
Passenger counts: start at 0. After stop 1: 0-0+4=4. After stop 2: 4-1+2=5. After stop 3: 5-5+5=5.
The maximum among {0,4,5,5} is M=5, first reached at stop F=2. Stops with count > K=4 are stop 2 (5) and stop 3 (5), so 2 overflow stops.
