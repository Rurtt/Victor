## Statement

The POSN camp has exactly $2N$ programmers attending a hackathon. Programmer $i$ has a skill rating $a_i$.

The camp organizer wants to split all $2N$ programmers into exactly $N$ teams of $2$ people each (every programmer belongs to exactly one team). To keep teams balanced, the organizer defines the *imbalance* of a team as the absolute difference between the skill ratings of its two members.

The organizer wants to choose how to split the programmers into teams so that the **sum of imbalances over all $N$ teams is as small as possible**.

Given the skill ratings, output this minimum possible total imbalance.

## Input

The first line contains one integer $N$.

The second line contains $2N$ integers $a_1, a_2, \ldots, a_{2N}$ — the skill ratings of the programmers.

## Output

Print a single integer — the minimum possible sum of imbalances over all valid ways to split the $2N$ programmers into $N$ teams of $2$.

## Constraints

- $1 \le N \le 100000$
- $1 \le a_i \le 10^9$ for every $i$

## Sample

### Sample 1

Input:
```
2
1 4 2 8
```

Output:
```
5
```

Explanation: Sort the ratings to get $1, 2, 4, 8$. Pairing $(1,2)$ and $(4,8)$ gives imbalance $1 + 4 = 5$, which is the minimum possible. (Pairing $(1,4)$ and $(2,8)$ gives $3+6=9$, and pairing $(1,8)$ and $(2,4)$ gives $7+2=9$, both worse.)

### Sample 2

Input:
```
3
5 5 5 5 5 5
```

Output:
```
0
```
