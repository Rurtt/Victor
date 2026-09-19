## Statement

You are given a string S consisting of uppercase English letters.

Scan the string from left to right and split it into maximal runs of identical consecutive characters. For example, the string `AAABCCDAA` splits into the runs `AAA`, `B`, `CC`, `D`, `AA`.

For each run, produce a piece of output as follows:
- If the run has length 1 (a single character with no repeats), output just that character.
- If the run has length 2 or more, output the character followed by the run's length written as a decimal number (with no leading zeros).

Concatenate the pieces for all runs, in order, to form the squeezed string. Print this squeezed string.

## Input

A single line containing the string S.

## Output

Print a single line: the squeezed string obtained as described above.

## Constraints

- 1 <= |S| <= 1000
- S consists only of uppercase English letters (A-Z).

## Sample

### Sample Input 1
```
AAABCCDAA
```

### Sample Output 1
```
A3BC2DA2
```

### Sample Input 2
```
ABCDE
```

### Sample Output 2
```
ABCDE
```