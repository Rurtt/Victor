## Statement

A secret message was encoded using a simple substitution cipher: every letter in the original lowercase message was shifted forward in the alphabet by exactly `k` positions, wrapping around from `z` back to `a` (for example, with `k = 2`, `'a'` becomes `'c'`, and `'z'` becomes `'b'`).

You are given the shift amount `k` and the encoded message `s`. Recover and print the original message.

Formally, if a letter of the original message is the `i`-th letter of the alphabet (0-indexed, so `'a'` is `0`), then the corresponding letter of `s` is the `((i + k) mod 26)`-th letter of the alphabet. Your task is to reverse this transformation for every character of `s`.

## Input

The input consists of two lines:
- Line 1: an integer `k`.
- Line 2: a string `s` consisting only of lowercase English letters — the encoded message.

## Output

Print a single line containing the decoded (original) message.

## Constraints

- `0 <= k <= 25`
- `1 <= |s| <= 100000`
- `s` consists only of lowercase English letters (`a`-`z`).

## Sample 1

### Input
```
3
defghij
```

### Output
```
abcdefg
```

## Sample 2

### Input
```
0
hello
```

### Output
```
hello
```
