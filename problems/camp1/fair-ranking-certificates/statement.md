## Statement

A tournament organizer has scores for $N$ contestants and wants to print a
ranking certificate for each of them, in the original input order.

The organizer uses **standard competition ranking** (also called "1224"
ranking): the contestant(s) with the highest score get rank $1$. If $k$
contestants are tied for a rank, the next distinct (lower) score group gets
rank $k+1$... more precisely, a contestant's rank equals **one plus the
number of contestants with a strictly greater score**.

For example, with scores $50, 60, 60, 40, 60$:
- Three contestants have score $60$ (the highest), so each gets rank $1$.
- One contestant has score $50$; three contestants (all the $60$s) beat it, so its rank is $4$.
- One contestant has score $40$; four contestants beat it, so its rank is $5$.

Given the scores of all contestants, output the rank of each contestant, in
the same order they were given in the input.

## Input

The first line contains a single integer $N$, the number of contestants.

The second line contains $N$ integers $s_1, s_2, \dots, s_N$, the score of
each contestant.

## Output

Print $N$ integers separated by single spaces on one line: the rank of
contestant $1$, contestant $2$, ..., contestant $N$, in that order.

## Constraints

- $1 \le N \le 200000$
- $0 \le s_i \le 10^9$

## Sample

### Sample Input
```
5
50 60 60 40 60
```

### Sample Output
```
4 1 1 5 1
```
