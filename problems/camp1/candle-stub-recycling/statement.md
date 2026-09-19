## Statement

A shop starts with $N$ new candles. Every candle, once lit, burns all the way down and leaves behind exactly one **stub**.

The shopkeeper recycles stubs: whenever she has collected $K$ stubs, she melts them together to form **one brand-new candle**, which can then be lit and burned just like any other candle (leaving yet another stub when it finishes). Leftover stubs (fewer than $K$) are kept and combined with stubs produced later.

She keeps lighting every candle she has (new or recycled) until no more candles can be produced, i.e. until the number of unmelted stubs is smaller than $K$ and there are no candles left to burn.

Given $N$ and $K$, determine the **total number of candles that get burned** (counting the original $N$ candles as well as every recycled one).

You are given $T$ independent scenarios; answer each one.

## Input

The first line contains a single integer $T$, the number of scenarios.

Each of the next $T$ lines contains two integers $N$ and $K$, describing one scenario.

## Output

For each scenario, output a single line containing the total number of candles burned.

## Constraints

- $1 \le T \le 100000$
- $1 \le N \le 10^{18}$
- $2 \le K \le 10^{18}$

## Sample

### Input
```
3
5 2
4 4
1 5
```

### Output
```
9
5
1
```

**Explanation for the first case:** Start with 5 candles and 0 stubs.
- Burn 5 candles → 5 stubs. Melt 4 of them into 1 new candle (1 stub left over). Total burned so far: 5.
- Burn that 1 new candle → 2 stubs total. Melt 2 into 1 new candle (0 left over). Total burned: 6.
- Burn that candle → 1 stub. Not enough to melt (need 2). Total burned: 7.

Wait — let's redo carefully with $K=2$: stubs accumulate one at a time and are melted as soon as 2 are available, so:
5 burned → 5 stubs → melt into 2 new candles (1 stub left, 2 candles produced) → burn 2 → total 7, stubs = 1+2 = 3 → melt into 1 candle (1 stub left) → burn 1 → total 8, stubs = 1+1 = 2 → melt into 1 candle (0 left) → burn 1 → total 9, stubs = 1 → stop (stub count 1 < K=2, no candles left to burn). Final total = **9**.
