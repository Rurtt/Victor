## Statement

A **digit sum machine** takes a number and repeatedly replaces it with the sum of its digits, until only a single digit (0-9) remains.

For example, starting from `9875`:
- Step 1: `9+8+7+5 = 29`
- Step 2: `2+9 = 11`
- Step 3: `1+1 = 2`

Since `2` is a single digit, the machine stops. It took **3** steps, and the final digit is **2**.

Given a starting number $N$, determine how many steps the machine performs and what the final single digit is.

If $N$ itself is already a single digit (0-9), the machine performs **0** steps and the final digit is $N$ itself.

## Input

A single line containing one integer $N$.

## Output

Print two integers separated by a single space: the number of steps the machine performs, followed by the final single digit.

## Constraints

- $1 \le N \le 10^{18}$

## Sample 1

### Input
```
9875
```

### Output
```
3 2
```

## Sample 2

### Input
```
7
```

### Output
```
0 7
```
