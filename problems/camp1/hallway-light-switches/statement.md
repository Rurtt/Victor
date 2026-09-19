## Statement

A hallway has $N$ lights, numbered $1$ to $N$ from one end to the other. All lights start **off**.

There are $M$ switches. Switch $i$ is wired to every light in the range $[L_i, R_i]$ (inclusive): pressing switch $i$ **toggles** the state of each light in that range (on becomes off, off becomes on).

Every switch is pressed exactly once, in some order. (The final state of the lights does not depend on the order the switches are pressed, since toggling a light twice always cancels out.)

Determine the final state of every light.

## Input

The first line contains two integers $N$ and $M$.

Each of the next $M$ lines contains two integers $L_i$ and $R_i$, describing one switch.

## Output

Print a single string of length $N$ made of the characters `0` and `1`. The $i$-th character (from the left, 1-indexed) must be `1` if light $i$ is on at the end, or `0` if it is off.

## Constraints

- $1 \le N \le 1{,}000{,}000$
- $1 \le M \le 200{,}000$
- $1 \le L_i \le R_i \le N$

## Sample

### Input
```
5 3
1 3
2 5
3 3
```

### Output
```
10111
```

**Explanation:** Light 1 is covered by switch 1 only (1 toggle → on). Light 2 is covered by switches 1 and 2 (2 toggles → off). Light 3 is covered by all three switches (3 toggles → on). Lights 4 and 5 are covered by switch 2 only (1 toggle each → on).