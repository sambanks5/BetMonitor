# BetMonitor
Improved live bet monitor & feed for online gambling site.

- Online gambling website had an outdated and errored monitoring program of bets coming through. 
- When a bet is placed, function within the system generates a file containing summary of bet details.
- Old program used to display these files had become obsolete (was made in 2004), odds traders & support staff would not be able to run through bet feed - the 'tree' layout was limiting.
- Auto-generated text files were displaying a lot of unneeded information, traders would struggle to 'at a glance' understand the wager info.
- Finally, the main limitation is that the betting 'database' containing full user, bet and event information is fully encrypted.


Below is the old program used (hidden customer refs):
![image](https://github.com/sambanks5/BetMonitor/assets/121309218/cd0dfb2b-7c0c-4017-906b-2d22b1f1b211)

The solution was to create an updated version of this that would:
- Make it easy for office workers to view the feed of incoming bets
- Produce snapshot reports on the daily activity
- Find and display betting patterns

Process of new bet monitor:
- Loop through folder containing the bet summary text files, read and parse relevant information from each.
- Categorise each file into one of 3 types - a bet, a knockback (wager that was not accepted) and Text Bet request.
- Parsed bet information is stored in a dictionary.

Using the parsed bet info:
- Format and display the relevant data in a 'Bet feed'. 
- Find and display any 'runs' on selections - when you have multiple users within a given timeframe betting on one selection, usually an indicator for incorrect odds.
- Display a feed of bets from 'risk' users.
- 'Search' function allows users to lookup certain clients' activity.
- Create a 'report' of betting activity, returning important info such as total stakes, highest spenders, users with most bets, busiest times of the day etc.
- Modify client account limits directly from the program.

Current UI display (updated 18/11/23: 
![image](https://github.com/sambanks5/BetMonitor/assets/121309218/28c36a66-ecec-4bd6-a311-b8d35c049c92)


Showing knockbacks:

![image](https://github.com/sambanks5/BetMonitor/assets/121309218/8366744d-8f9f-4441-97a5-d24f7b9a5f99)


Other functions:
- ability to generate a 'temporary' user password for first account setup.
- Settings to show/hide text bets, knockbacks and ability to display only high risk bets in the feed.

To do: 
- Implement multithreading for the processing/parsing of bet information.
- Fix error with 'SP' bets not displaying correctly.
- Find way to display tk scrollbar for notebook elements
- Parse additional information

