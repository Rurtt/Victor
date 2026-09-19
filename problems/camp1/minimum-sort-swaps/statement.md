## Statement

You are given an array of $n$ **distinct** integers. In one operation you may swap the values at any two positions of the array.

Find the **minimum** number of swap operations needed to rearrange the array into strictly increasing order.

## Input

The first line contains a single integer $n$.

The second line contains $n$ integers $a_1, a_2, \dots, a_n$ — the array.

## Output

Print a single integer: the minimum number of swaps required to sort the array in increasing order.

## Constraints

- $1 \le n \le 200000$
- $-10^9 \le a_i \le 10^9$
- All $a_i$ are distinct.

## Sample

### Sample 1

Input:
```
4
4 3 1 2
```

Output:
```
3
```

Explanation: Swap positions (0-indexed) 0 and 2: `1 3 4 2`. Swap positions 1 and 3: `1 2 4 3`. Swap positions 2 and 3: `1 2 3 4`. This takes 3 swaps, and no sequence of fewer swaps can sort the array.

### Sample 2

Input:
```
5
1 2 3 4 5
```

Output:
```
0
```
