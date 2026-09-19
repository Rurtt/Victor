## Statement

You are given a sentence `S` made of one or more **words** separated by single spaces. Each word consists only of English letters (uppercase or lowercase).

For every word in the sentence, apply the following rule:

- The **first** and **last** character of the word are always kept as they are.
- Every character **strictly between** the first and last character that is a vowel (`a`, `e`, `i`, `o`, `u`, case-insensitive) is **removed**.
- All other characters between the first and last (non-vowels) are kept, in their original order.
- If a word has length 1 or 2, it is left completely unchanged (there is nothing "strictly between" its first and last character).

Print the resulting sentence, with the transformed words separated by single spaces, in the same order as the original.

### Input

A single line containing the sentence `S`.

### Output

A single line containing the transformed sentence.

### Constraints

- `1 <= length of S <= 5000`
- `S` consists of uppercase and lowercase English letters and single spaces.
- `S` has no leading or trailing spaces and no two consecutive spaces.
- `S` contains at least one word (at least one letter).

### Sample

Input:
```
Hello World Programming
```

Output:
```
Hllo Wrld Prgrmmng
```
