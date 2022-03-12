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
camb <word/phrase>                    # search a word or phrase. e.g. camb stone
camb <word/phrase with an apostrophe> # e.g. camb "a stone's throw" OR camb a stone\'s throw
camb -v <word/phrase>                 # search a word or phrase in verbose mode 
camb l                                # list words you've searched successfully 
camb l -d                             # delete a word from words' list
```
