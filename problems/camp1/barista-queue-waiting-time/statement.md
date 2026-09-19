## Statement

A single barista at a coffee shop serves customers **one at a time**. The $i$-th customer needs $t_i$ minutes to be served (once the barista starts on them, they finish $t_i$ minutes later, with no breaks in between).

The barista gets to choose the **order** in which to serve the customers. A customer's *waiting time* is the total number of minutes that pass before the barista starts serving them — that is, the sum of the service times of every customer served strictly before them. (The very first customer served has waiting time $0$.)

The barista wants to choose an order that minimizes the **total waiting time**, i.e. the sum of the waiting times of all $N$ customers.

Given the service times, output the minimum possible total waiting time.

## Input

The first line contains a single integer $N$, the number of customers.

The second line contains $N$ integers $t_1, t_2, \ldots, t_N$, the service time of each customer.

## Output

Output a single integer: the minimum possible total waiting time, over all orders in which the barista could serve the customers.

## Constraints

- $1 \le N \le 2 \times 10^5$
- $1 \le t_i \le 10^6$

## Sample

### Sample 1

Input:
```
4
4 2 5 1
```

Output:
```
11
```

Explanation: Serving in order $1, 2, 4, 5$ gives waiting times $0, 1, 3, 7$, which sum to $11$. No other order achieves a smaller total.
