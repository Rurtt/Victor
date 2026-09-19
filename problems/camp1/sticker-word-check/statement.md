## Statement

You have one sticker sheet containing lowercase English letters. The sheet is described by a string $S$: it has as many stickers of a letter as that letter appears in $S$.

You want to spell out several words using the stickers. To spell a word, for every letter in the word you need one sticker of that exact letter, and the sheet must contain **at least** as many stickers of that letter as the word needs. (Assume the sheet is never used up — each word is checked independently against the same, unchanged sheet.)

For each of $N$ query words, determine whether it can be spelled using the stickers on the sheet.

## Input

The input consists of:

- Line 1: the string $S$ (the sticker sheet).
- Line 2: an integer $N$, the number of query words.
- The next $N$ lines: one word each.

## Output

Print $N$ lines. For the $i$-th query word, print `YES` if it can be spelled using the sticker sheet, otherwise print `NO`.

## Constraints

- $1 \le |S| \le 1000$
- $1 \le N \le 1000$
- $1 \le |\text{word}| \le 1000$ for every query word
- $S$ and every query word consist only of lowercase English letters (`a`-`z`).

## Sample

### Sample Input
```
aabbbc
3
abc
bbbb
ccc
```

### Sample Output
```
YES
NO
NO
```

Explanation: the sheet `aabbbc` has counts a:2, b:3, c:1.
- `abc` needs a:1, b:1, c:1 — all available — `YES`.
- `bbbb` needs b:4, but only 3 are available — `NO`.
- `ccc` needs c:3, but only 1 is available — `NO`.
