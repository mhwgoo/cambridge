# Cambridge

Cambridge is a terminal version of Cambridge Dictionary.

The dictionary data comes from https://dictionary.cambridge.org

If you're not satisfied with the result, you can try with `-w` flag to look up the word in Merriam-Webster Dictionary.

## Screenshots
![look up a word](/screenshots/word.png)

## Why This
I'm a terminal person tired of pulling out a GUI app or browser, inputting words in the search bar, hitting the search button and then waiting for the result to render with a bunch of unnecessary static files coming along. Not only is the time taken long, but also switching apps back and forth can be annoying. So I wrote this console application with features to my satisfaction.

## Features 
1. `camb <word/phrase>` to look it up in Cambridge Dictionary by default. 
2. `-w` flag to fetch Merriam-Webster Dictionary. 
3. Less than 2s taken to do all the work for the word, including fetching, parsing, printing, and writing cache. 
4. Less than 0.1s for the same word's later search. 
5. Fetch the first dictionary from Cambridge, avoiding confuses by multiple dictionaries.
6. If not found, a list of related suggestions will be displayed.
7. `camb l` to list words and phrases you've found before. 

## With `fzf`
`camb l | fzf --preview 'camb {}'`, if [fzf](https://github.com/junegunn/fzf) has been installed, you'll get a taste of the `fzf` magic: 
1. Display the whole word list
2. Fuzzy find a word from the word list & preview its meaning instantly 
3. preview each word definition instantly as you scroll through the list
4. `alias cambl="camb l | fzf --preview 'camb {}'"` can be added in your `bashrc` for convenience
![list words](/screenshots/fzf.png)

## Installation
```python
pip install cambridge
```

## Usage
```bash
camb <word/phrase>  e.g. camb value  # look up a word/phrase in Cambridge Dictionary
camb <word/phrase> -v                # look up a word/phrase in verbose/debug mode
camb <word/phrase> -w                # look up a word/phrase in Merriam-Webster Dictionary
camb <word/phrase> -f                # look up a word/phrase afresh without using cache

camb l                               # list words found before in alphabetical order
camb l -t                            # list words found before in reverse chronological order
camb l -r                            # list 20 words from the word list randomly 
camb l -d                            # delete a word from the word list

camb <phrase with an apostrophe>     # camb "a stone's throw" | camb a stone\'s throw
camb <phrase with a slash>           # camb "have your/its moments" | camb have your\/its moments
```
