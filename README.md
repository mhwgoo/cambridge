# Cambridge

Cambridge is a terminal version of Cambridge Dictionary.

The dictionary data comes from https://dictionary.cambridge.org

## Screenshots
### Look up a word
![look up a word](/screenshots/word.png)
### Look up a phrase
![look up a phrase](/screenshots/phrase.png)

## Why This
I'm a terminal person tired of pulling out a GUI app or browser, inputting words in the search bar, hitting the search button and then waiting for the result to render with a bunch of unnecessary static files coming along. Not only is the time taken long, but also switching apps back and forth can be annoying. So I wrote this console application with features to my satisfaction.

## Features 
1. Just `camb` and "the word and phrase" you want to search.
2. Takes 0.5 ~ 3 secs including webpage fetching, depending on the network speed. Less than 0.1 secs for the same word's second time search. 
3. No unnecessary info, like ads, quizzes, pics, etc.
4. Fetches the first dictionary on Cambridge without similar dictionaries with similar meanings making people dizzy.
5. If not found, a list of related word suggestions will be displayed.
6. `camb l` to list words you've searched successfully. 
7. `camb l | fzf --preview 'camb {}'`, if you've installed [fzf](https://github.com/junegunn/fzf), you'll get the following magics: 
    - fuzzy finding a word from the word list & instantly previewing the meaning for each word you've found 
    - displaying the whole word list & instantly previewing each word meaning as you scroll through the list
![list words](/screenshots/fzf.png)

## Installation
```python
pip install cambridge
```

## Usage
```bash
camb <word/phrase>               # search a word or phrase. e.g. camb stone
camb <phrase with an apostrophe> # e.g. camb "a stone's throw" OR camb a stone\'s throw
camb <phrase with a slash>       # e.g. camb "have your/its moments" OR camb have your\/its moments 
camb -v <word/phrase>            # search a word or phrase in verbose mode 
camb l                           # list words you've searched successfully 
camb l -d                        # delete a word from the word list
```
