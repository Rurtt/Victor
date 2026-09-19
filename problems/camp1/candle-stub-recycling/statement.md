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

**Explanation for the first case:** Start with 5 candles and 0 stubs, $K=2$.
- Burn the 5 starting candles → total burned = 5, stubs = 5. Melt stubs into new candles as long as at least $K=2$ are available: 5 stubs make 2 new candles, leaving 1 stub over.
- Burn those 2 new candles → total burned = 7, stubs = 1 (leftover) + 2 (just produced) = 3. Melt: 3 stubs make 1 new candle, leaving 1 stub over.
- Burn that candle → total burned = 8, stubs = 1 (leftover) + 1 (just produced) = 2. Melt: 2 stubs make 1 new candle, leaving 0 stubs over.
- Burn that candle → total burned = 9, stubs = 0 + 1 = 1. Now only 1 stub remains (fewer than $K=2$) and there are no candles left to burn, so the process stops.

Final total burned = **9**.
