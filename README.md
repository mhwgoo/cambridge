# Cambridge
`cambridge` is a terminal version of Cambridge Dictionary, whose source is from https://dictionary.cambridge.org; also supports the Merriam-Webster Dictionary as backup.

## Screenshots
#### Look up Cambridge Dictionary (screenshot on DARK terminal background)
![look up a word in Cambridge Dictionary](/screenshots/cambridge.png)

#### Look up Merriam-Webster Dictionary (screenshot on LIGHT terminal background)
![look up a word in Merriam-Webster Dictionary](/screenshots/webster.png)

## Highlights
1. `camb <word/phrase>` to look up in Cambridge Dictionary by default
2. `camb -c <word/phrase>` to look up in Cambridge Dictionary with additional Chinese translation
3. `camb -w <word/phrase>` to look up in Merriam-Webster Dictionary
4. **support concurrent searching multiple words from one dictionary, or multiple words from different dictionaries**
5. less than 2s taken to do all the work for the word, including fetching, parsing, printing, and writing cache
6. less than 0.1s for the same word's later search by retrieving cache
7. only the first dictionary from Cambridge (assuming the optimal) to avoid being confused by multiple dictionaries
8. a list of suggestions will be given, if not found
9. `camb l` to list cached words and phrases
10. support checking "Word of the Day" from Merriam-Webster Dictionary
11. support displaying spellcheck suggestion list, cache list, Webster's all of word of the days by `fzf`
12. if `fzf` not installed, the aforementioned lists have been formatted elaborately
13. well tuned to dark, light, blueish, grayish, `gruvbox` terminal colorschemes

## Install & Uninstall
```bash
pip install cambridge
pip uninstall -r requirements.txt -y
rm -rf $HOME/.cache/cambridge
rm -rf $HOME/.cache/fakeua

# within the project
make install
make uninstall
make clean_cache
```

## Usages
#### Command `s` (hidden)
For looking up words/phrases in a dictionary or multiple dictionaries.
```bash
camb <word/phrase>, <word/phrase>, ...     # look up words/phrases in Cambridge Dictionary
camb -w <word/phrase>, <word/phrase>, ...  # look up words/phrases in Merriam-Webster Dictionary
camb -c <word/phrase>, <word/phrase>, ...  # look up words/phrases in Cambridge with Chinese translation
camb <w/p>, <w/p>, ... -w <w/p>, <w/p>, ... -c <w/p>, <w/p>, ... # concurrent searching

# Additional Options
--debug   # look up words/phrases in debug mode
-f        # look up words/phrases afresh without using cache
-n        # look up words/phrases without showing suggestions if not found

# Special Characters on Terminal
# phrase with "'":
camb "a stone's throw" | camb a stone\'s throw

# phrase with "/":
camb "have your/its moments" | camb have your\/its moments
```

#### Command `l`
For listing and deleting items in the cache.
```bash
camb l                  # list alphabetically ordered words/phrases you've found before
camb l -t               # list words/phrases in reverse chronological order
camb l -r               # list 20 words/phrases from the word list randomly
camb l -d               # delete one or more words/phrases(separated by ", ") from the list
```

#### Command `wod`
For displaying 'Word of the Day' in the Merriam Webster Dictionary
```bash
camb wod                # list today's Word of the Day from Merriam-Webster Dictionary
camb wod -l             # list all words of the day
```

#### General options
```bash
camb -h, --help         # show this help message and exit
camb -v, --version      # print the current version of the program
```
