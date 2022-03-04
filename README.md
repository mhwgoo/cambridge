# Cambridge

Cambridge is a terminal version of Cambridge Dictionary. The dictionary data comes from https://dictionary.cambridge.org.

## Screenshots
### Look up a word
![look up a word](/screenshots/word.png)
### Look up a phrase
![look up a phrase](/screenshots/phrase.png)

## Why This
I'm a terminal person tired of pulling out a dict app or browser, inputting words in the search bar, hitting the search button and waiting the result to render with a bunch of unnecessary static files coming along. Not only time taken is long, but also switching apps back and forth is annoying. So I wrote this console application with features to my satisfaction.

## Feature Highlights
1. **EASY**: Only one positional argument, which can be a word, or a phrase of multiple words.
2. **FAST**: It usually takes 0.5 ~ 3 secs including the time for webpage fetching, depending on your network speed.
3. **NEAT**: No unnecessary info, like ads, quizzes, pics, etc.
4. **DIRECT**: Only the first dictionary that Cambridge Organization displays on its website without too many similar dictionaries making people dizzy as the website does.
5. **CONSIDERATE**. If not found, a list of related word suggestions will be displayed.
![not found](/screenshots/not_found.png)

## Installation
```python
pip install cambridge
```

## Usage
```bash
camb <the word/phrase you want to look up>     # e.g. camb stone
camb <the word/phase with an apostrophe>       # e.g. camb "a stone's throw"
camb <the word/phase with an apostrophe>       # e.g. camb a stone\'s throw
camb -d <the word/phrase you want to look up>  # switch to debug mode to inspect problems if any
```
