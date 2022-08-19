# Cambridge

Cambridge is a terminal version of Cambridge Dictionary.

The dictionary data comes from https://dictionary.cambridge.org

If you're not satisfied with the result, you can try with "-w" flag to look up the word in Merriam-Webster Dictionary.

## Screenshots
![look up a word](/screenshots/word.png)

## Why This
I'm a terminal person tired of pulling out a GUI app or browser, inputting words in the search bar, hitting the search button and then waiting for the result to render with a bunch of unnecessary static files coming along. Not only is the time taken long, but also switching apps back and forth can be annoying. So I wrote this console application with features to my satisfaction.

## Features 
1. `camb <word/phrase>` to look up what you need. 
2. Takes < 2s for the first time, including fetching, parsing, printing, and writing cache. 
3. Less than 0.1s for the same term's later search. 
4. Fetches the first dictionary on Cambridge, avoiding confuses by multiple dictionaries.
5. If not found, a list of related suggestions will be displayed.
6. `camb l` to list words and phrases you've found before. 

## With `fzf`
`camb l | fzf --preview 'camb {}'`, if you've installed [fzf](https://github.com/junegunn/fzf), you'll get the following magics: 
1. fuzzy finding a word from the word list & instantly previewing its meaning 
2. displaying the whole word list & instantly previewing each word meaning as you scroll through the list
![list words](/screenshots/fzf.png)
3. You can also add `alias cambl="camb l | fzf --preview 'camb {}'"` in your shell config for convenience

## Installation
```python
pip install cambridge
```

## Usage
```bash
camb <word/phrase>     e.g. camb pertinent  # look up a word/phrase in Cambridge Dictionary
camb <word/phrase> -v                       # look up a word/phrase in verbose/debug mode
camb <word/phrase> -w                       # look up a word/phrase in Merriam-Webster Dictionary
camb <word/phrase> -f                       # look up a word/phrase afresh without using cache

camb l                                      # list words found before in alphabetical order
camb l -t                                   # list words found before in reverse chronological order
camb l -r                                   # list 20 words from the word list randomly 
camb l -d                                   # delete a word from the word list

camb <phrase with an apostrophe>            # camb "a stone's throw" | camb a stone\'s throw
camb <phrase with a slash>                  # camb "have your/its moments" | camb have your\/its moments
```
