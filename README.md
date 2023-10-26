# BetMonitor
Side project - live bet monitor and feed for an online gambling website.

- Online gambling company had an outdated and errored monitoring program of bets coming through from their online website. 
- When a customer places an online bet, a function within the system generates a text file with a summary of bet details.
- The old program used to display these files had become obsolete (was made in 2004), odds traders & support stadd in the office would not be able to quickly run through the betting feed - the 'tree' layout was limiting for users and would only display the bet number, time and username. For staff to be able to pick out betting patterns, and keep track of users' bets, the design of the old program made tasks much more difficult & tedious.
- The generated text files when bets are placed online were displaying a lot of unneeded information, meaning traders would struggle to 'at a glance' understand the wager.
- Finally, the main limitation is that the company 'database' containing full user, bet and event information is fully encrypted. Unfortunately then it's not possible to retrieve bet information this way. 


Below is the old program used (Removed customer refs for privacy):
![image](https://github.com/sambanks5/BetMonitor/assets/121309218/cd0dfb2b-7c0c-4017-906b-2d22b1f1b211)

The solution was to create an updated version of this that would:
- Make it easy for office workers to view the feed of incoming bets
- Produce snapshot reports on the daily online activity
- Find and display betting patterns

Process of new bet monitor:
- Loop through files in folder containing the bet summary (.bww) files, read and parse relevant information from each.
- Categorise each file into one of 3 types - obviously the main one is a placed bet, some are wager 'knockbacks' which are notifications of a refused online wager by the system and some files are text bets, where a user will text through their bet request. 
- Parsed bet information is stored in a dictionary using the unique bet no. as the key, and a list of bet details such as selection, odds, unit stake etc as the value.

Using the dictionary of bet info:
- Format and display the relevant data in a 'Bet feed', in a way that makes it easy for staff to glance through to get a full picture of live betting activity.
- Find and display any 'runs' on selections - when you have multiple users within a short timeframe betting on one selection, it can be an indicator for incorrect odds or some other issue.
- Display a feed of bets from 'high risk' users.
- 'Search' function allows users to lookup certain clients & display a feed of their bets
- Create a daily 'report' of betting activity, returning important daily info such as total stakes, highest spenders, users with most bets, busiest times of the day & more. 

Current UI display: 

![image](https://github.com/sambanks5/BetMonitor/assets/121309218/1521fb89-6bce-443d-bc13-7cc165d7b3e9)

To note - 'report' is displaying test data. 

Showing knockbacks in feed:

![image](https://github.com/sambanks5/BetMonitor/assets/121309218/8366744d-8f9f-4441-97a5-d24f7b9a5f99)


Other functions:
- ability to generate a 'temporary' user password for first account setup.
- Settings to show/hide text bets, knockbacks and ability to display only high risk bets in the feed.

Known issues to fix:
- Currently program is refreshing for new data every 20s. At end of the day when there is a lot of data, it can be slow to update as its looping through 2000+ bets. Need to make this function more efficient by checking bets have not already been added to dictionary.
- Bets placed at 'SP' are sometimes not being displayed. Easy fix.
- Tkinter scrollbar not showing for Notebook elements (report)
- Remove irrelevent information from knockbacks
- Comment code
