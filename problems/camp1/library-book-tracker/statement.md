## Statement

A small library has $n$ books, numbered from $1$ to $n$. At the beginning, every book is **available**.

The librarian processes $q$ events, one after another. Each event is one of the following three types, given as a command word followed by a book number $x$:

- `BORROW x` — Someone wants to borrow book $x$.
  - If book $x$ is currently available, it becomes borrowed, and you must print `OK`.
  - If book $x$ is already borrowed, nothing changes, and you must print `ALREADY BORROWED`.
- `RETURN x` — Someone wants to return book $x$.
  - If book $x$ is currently borrowed, it becomes available, and you must print `OK`.
  - If book $x$ is already available, nothing changes, and you must print `ALREADY AVAILABLE`.
- `STATUS x` — Someone asks for the current status of book $x$, without changing anything.
  - Print `AVAILABLE` if book $x$ is currently available.
  - Print `BORROWED` if book $x$ is currently borrowed.

Process the events in order and report the required output for each one.

## Input

The first line contains two integers $n$ and $q$.

Each of the next $q$ lines contains an event in one of the formats:
```
BORROW x
RETURN x
STATUS x
```

## Output

Print $q$ lines. The $i$-th line must contain the result of processing the $i$-th event, exactly as described above (`OK`, `ALREADY BORROWED`, `ALREADY AVAILABLE`, `AVAILABLE`, or `BORROWED`).

## Constraints

- $1 \le n \le 1000$
- $1 \le q \le 2000$
- $1 \le x \le n$ for every event
- The command word is always one of `BORROW`, `RETURN`, `STATUS`

## Sample

### Input
```
3 6
BORROW 1
BORROW 1
STATUS 1
RETURN 1
RETURN 1
STATUS 1
```

### Output
```
OK
ALREADY BORROWED
BORROWED
OK
ALREADY AVAILABLE
AVAILABLE
```
