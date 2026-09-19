## Statement

You are given a starting number $N$. You repeat the following operation until $N$ becomes $0$:

- If $N$ is even, divide it by $2$.
- If $N$ is odd, subtract $1$ from it.

Each application of this rule (whether a division or a subtraction) counts as **one step**.

You are given $Q$ starting numbers. For each one, output how many steps are needed to reduce it to $0$.

## Input

The first line contains a single integer $Q$, the number of queries.

Each of the next $Q$ lines contains a single integer $N$, the starting number for that query.

## Output

Output $Q$ lines. The $i$-th line should contain a single integer: the number of steps needed to reduce the $i$-th $N$ to $0$.

## Constraints

- $1 \le Q \le 100000$
- $1 \le N \le 10^9$

## Sample

### Input
```
3
6
7
1
```

### Output
```
4
5
1
```

Explanation for $N=6$: $6 \to 3 \to 2 \to 1 \to 0$, which takes 4 steps.

Explanation for $N=7$: $7 \to 6 \to 3 \to 2 \to 1 \to 0$, which takes 5 steps.

Explanation for $N=1$: $1 \to 0$, which takes 1 step.
