# Cambridge

Cambridge is a terminal version of Cambridge Dictionary. Its dictionary data comes from https://dictionary.cambridge.org.

## Screenshots
![Search for a word](/screenshots/word.png)

![Search for a phrase](/screenshots/phrase.png)

## Why This
Since I spend most time of my day using terminal, I'm tired of pulling out a dict app or browser, inputting words in its search bar, and hitting search button. Not only time taken is long, but also switching apps back and forth is annoying. 

Therefore, I wrote this terminal app with features to my satisfaction.

## Feature Highlights
1. **SIMPLE**. Only one argument `-w`. You can simply look up a word, or a phrase by typing multiple words.
2. **FAST**. It usually takes 1 ~ 5 secs with the lousy network service by my network supplier(parsing and displaying takes less than 0.4 secs). Much faster than fetching the same content by web browser under the same network within the same time period.
3. **ESSENTIAL**. No excessive info to distract from essential meanings and usage, like ads, quizzes, pics, and other useless data.
4. **ONE DICT**. Not many dictionaries with similar definitions take too much space and time and make people dizzy. Only the first and the most important dictionary Cambridge Organization displays on its website. It can absolutely meets our needs, clear and to the point.
5. **CONSIDERATE**. If not found, in stead of simply showing nothing, a related word suggestions page is fetched. Then you'll find maybe there was a typo or a slight variation will fit.
![Search for one word](/screenshots/not_found.png)

## Installation
```python
pip install cambridge
```

## Usage
```bash
cambridge -w <the word/phrase you want to search>  
```



