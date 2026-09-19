## Statement

A company has a single meeting room that can be booked during a workday that runs from time `0` to time `L` (an integer number of minutes).

During the day, `N` meetings were booked in this room. The `i`-th meeting occupies the room during the time interval `[s_i, e_i)` (it starts at minute `s_i` and ends at minute `e_i`). Because bookings were made independently by different people, some meetings may **overlap** or even be nested inside one another, and they are **not** given in any particular order.

Whenever two or more booked intervals overlap or touch (share at least one instant of time), the room is considered occupied for the entire union of those intervals without any gap. The room is **free** at every moment of the day (between `0` and `L`) that is not covered by any meeting.

Compute:
1. The **total amount of free time** in the room during the day.
2. The length of the **longest single continuous stretch** of free time during the day.

If the room has no free time at all, both answers are `0`.

## Input

The first line contains two integers `N` and `L`.
Each of the next `N` lines contains two integers `s_i` and `e_i` — the start and end time of the `i`-th meeting.

## Output

Print two integers separated by a space: the total free time during the day, and the length of the longest continuous free stretch.

## Constraints

- `1 <= N <= 200000`
- `1 <= L <= 10^9`
- `0 <= s_i < e_i <= L`

## Sample

### Input
```
3 10
1 3
2 5
7 8
```

### Output
```
5 2
```

(The meetings `[1,3)` and `[2,5)` merge into `[1,5)`. The occupied stretches are `[1,5)` and `[7,8)`. The free stretches are `[0,1)` of length 1, `[5,7)` of length 2, and `[8,10)` of length 2. Total free time is `1+2+2=5`, and the longest free stretch has length `2`.)
