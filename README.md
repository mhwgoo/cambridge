# Cambridge

Cambridge is a terminal version of Cambridge Dictionary. The dictionary data comes from https://dictionary.cambridge.org.

## Screenshots
### Look up a word
![look up a word](/screenshots/word.png)
### Look up a phrase
![look up a phrase](/screenshots/phrase.png)

## Why This
Since I spend most time of my day using terminal, I'm tired of pulling out a dict app or browser, inputting words in its search bar, and hitting search button. Not only time taken is long, but also switching apps back and forth is annoying. 

Therefore, I wrote this terminal app with features to my satisfaction.

## Feature Highlights
1. **SIMPLE**. Only one positional argument following 4-character endpoint prompt `camb`. The argument can be a word, or a phrase of multiple words.
2. **FAST**. It usually takes 0.5 ~ 3 secs, occasionally 5 secs at most with the lousy network service by my network supplier(parsing and displaying takes less than 0.4 secs). Much faster than fetching the same content by web browser under the same network within the same time period.
3. **ESSENTIAL**. No excessive info to distract from essential meanings and usage, like ads, quizzes, pics, and other useless data.
4. **ONE DICT**. Not many dictionaries with similar definitions take too much space and time and make people dizzy. Only the first and the most important dictionary Cambridge Organization displays on its website. It can absolutely meets our needs, clear and to the point.
5. **CONSIDERATE**. If not found, in stead of showing nothing, a list of related word suggestions is displayed where you may find there was a typo in your word input or a slight variation of it will fit.
![not found](/screenshots/not_found.png)

## Installation
```python
pip install cambridge
```

## Usage
```bash
camb <the word/phrase you want to look up>  # e.g. camb stone
camb <the word/phase with an apostrophe>    # e.g. camb "a stone's throw"
camb <the word/phase with an apostrophe>    # e.g. camb a stone\'s throw
```



