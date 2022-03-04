# Cambridge

Cambridge is a terminal version of Cambridge Dictionary.

The dictionary data comes from https://dictionary.cambridge.org.

## Screenshots
### Look up a word
![look up a word](/screenshots/word.png)
### Look up a phrase
![look up a phrase](/screenshots/phrase.png)

## Why This
I'm a terminal person tired of pulling out a GUI app or browser, inputting words in the search bar, hitting the search button and then waiting for the result to render with a bunch of unnecessary static files coming along. Not only is the time taken long, but also switching apps back and forth can be annoying. So I wrote this console application with features to my satisfaction.

## Feature Highlights
1. **EASY**: Only needs one positional argument, which can be a word or a phrase.
2. **FAST**: It usually takes 0.5 ~ 3 secs including the time for webpage fetching, depending on the network speed.
3. **NEAT**: No unnecessary info, like ads, quizzes, pics, etc.
4. **DIRECT**: It fetches the first dictionary on the Cambridge Organization webpage without similar dictionaries with similar meanings making people dizzy.
5. **CONSIDERATE**: If not found, a list of related word suggestions will be displayed.
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
