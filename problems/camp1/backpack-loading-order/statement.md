## Statement

You are packing a backpack that can carry a total weight of at most `W`.

You have `N` items, numbered `1` to `N` in the order you must consider them. Item `i` has weight `w[i]`.

You go through the items **in order from item 1 to item N**. For each item, you try to add it to the backpack:
- If adding the item's weight to the backpack's current total weight would **not exceed** `W`, you put it in the backpack (the current total weight increases by `w[i]`).
- Otherwise, you **skip** that item (it is left behind) and move on to consider the next item.

Note that even after skipping an item, you keep considering the remaining items — a later, lighter item may still fit even if an earlier, heavier one didn't.

After considering all `N` items, determine:
1. How many items ended up in the backpack.
2. The total weight of the items in the backpack.
3. The remaining free capacity of the backpack (`W` minus the total weight packed).

## Input

The first line contains two integers `N` and `W`.

The second line contains `N` integers `w[1], w[2], ..., w[N]`, the weights of the items in order.

## Output

Print three integers separated by spaces: the number of items packed, the total weight packed, and the remaining free capacity.

## Constraints

- `1 <= N <= 1000`
- `1 <= W <= 100000`
- `1 <= w[i] <= 100000` for every item

## Sample

### Input
```
5 10
4 3 5 2 1
```

### Output
```
4 10 0
```

### Explanation
Start with 0 packed.
- Item 1 (weight 4): 0+4=4 <= 10, pack it. Total = 4.
- Item 2 (weight 3): 4+3=7 <= 10, pack it. Total = 7.
- Item 3 (weight 5): 7+5=12 > 10, skip it. Total stays 7.
- Item 4 (weight 2): 7+2=9 <= 10, pack it. Total = 9.
- Item 5 (weight 1): 9+1=10 <= 10, pack it. Total = 10.

4 items packed, total weight 10, remaining capacity 0.
