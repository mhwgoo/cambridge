# Cambridge
`cambridge` is a terminal version of Cambridge Dictionary, with its data from https://dictionary.cambridge.org

By default, it is English to English translation. For English to Chinese, add '-c' or '--chinese' option.

Also supports the Merriam-Webster Dictionary. Webster has no foreign language translation in itself.

## Screenshots
#### Look up Cambridge Dictionary (screenshot on DARK terminal background)
![look up a word in Cambridge Dictionary](/screenshots/cambridge.png)

#### Look up Merriam-Webster Dictionary (screenshot on LIGHT terminal background)
![look up a word in Merriam-Webster Dictionary](/screenshots/webster.png)

## Why This
I'm a terminal person tired of pulling out a GUI app or browser, inputting words in the search bar, hitting the search button and then waiting for the result to render with a bunch of unnecessary static files coming along. Not only is the time taken long, but also switching apps back and forth can be annoying. So I wrote this console application with features to my satisfaction.

## Highlights
1. `camb <word/phrase>` to initiate the lookup in Cambridge Dictionary by default
2. `-w` option to enable looking up in Merriam-Webster Dictionary
3. less than 2s taken to do all the work for the word, including fetching, parsing, printing, and writing cache
4. less than 0.1s for the same word's later search by retrieving cache
5. only the first dictionary from Cambridge (assuming the optimal) to avoid being confused by multiple dictionaries
6. a list of suggestions will be given, if not found
7. `camb l` to list cached words and phrases
8. support displaying spellcheck suggestion list, cache list, Webster's word of the day list by `fzf`
9. if `fzf` not installed, no worries, printing of the aforementioned lists on terminal has been beautified
10. well tuned to dark, light, blueish, grayish, `gruvbox` terminal colorschemes

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
For looking up a dictionary. Options can be put before or after `<word/phrase>`.
```bash
camb <word/phrase>      # look up a word/phrase in Cambridge Dictionary
camb <word/phrase> -w   # look up a word/phrase in Merriam-Webster Dictionary
camb <word/phrase> -c   # look up a word/phrase in Cambridge with Chinese translation

camb <phrase with "'" > # camb "a stone's throw" | camb a stone\'s throw
camb <phrase with "/" > # camb "have your/its moments" | camb have your\/its moments

camb <word/phrase> -d   # look up a word/phrase in debug mode
camb <word/phrase> -f   # look up a word/phrase afresh without using cache
camb <word/phrase> -n   # look up a word/phrase without showing suggestions if not found
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

## TO-DOS
* [x] input a new word/phrase when spelling suggestions are not satisfactory without restarting a new command line
* [ ] check a particular expression against all cached sentence examples, if found, we can confidently use it like that in our speaking or writing
* [ ] split and accumulate all sentences from a whole bulk of cache as independent Corpus, then we can use this Corpus outside this program
* [x] strengthen 'Word of the Day' functionality from Webster
