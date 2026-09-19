## Statement

Thanarachan's souvenir shop only has 5-baht coins in the cash register, so every item's price must be **rounded to the nearest multiple of 5 baht** before it is charged to a customer.

The rounding rule is:
- If the price's remainder when divided by 5 is **0, 1, or 2**, round **down** to the nearest multiple of 5.
- If the price's remainder when divided by 5 is **3 or 4**, round **up** to the nearest multiple of 5.

For example:
- A price of `7` baht (remainder `2`) rounds down to `5`.
- A price of `8` baht (remainder `3`) rounds up to `10`.
- A price of `10` baht (remainder `0`) stays `10`.

You are given the prices of `N` items. For each item, print its rounded price. After that, print the **total rounding difference**, defined as:

```
(sum of all rounded prices) - (sum of all original prices)
```

This value can be positive, negative, or zero.

## Input

The first line contains one integer `N`, the number of items.

The next `N` lines each contain one integer `P_i`, the price of the `i`-th item in baht.

## Output

Print `N` lines: the `i`-th line contains the rounded price of the `i`-th item.

On the last line, print the total rounding difference as defined above.

## Constraints

- `1 <= N <= 1000`
- `0 <= P_i <= 1,000,000,000`

## Sample

### Input
```
3
7
8
11
```

### Output
```
5
10
10
-1
```

**Explanation:** `7 -> 5`, `8 -> 10`, `11 -> 10`. The sum of original prices is `26`, the sum of rounded prices is `25`, so the difference is `25 - 26 = -1`.
