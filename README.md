# BetMonitor
Live bet monitor and feed for an online gambling website.

Online gambling company had an outdated and errored monitoring program of bets coming through from their online website. 
When a customer places an online bet, the system generates a text file with a summary of bet details. 
The original program used to display these files had become obsolete (was made in 2007), betting traders in the office would not be able to quickly run through the betting feed - it was using a 'tree' layout meaning you could not see the full bet information unless the bet number was clicked. Additionally, the generated text files were displaying a lot of unneeded information, meaning traders would struggle to 'at a glance' understand the wager. 

Below is the old program used (Removed customer Refs):
![image](https://github.com/sambanks5/BetMonitor/assets/121309218/cd0dfb2b-7c0c-4017-906b-2d22b1f1b211)

The solution was to create an updated version of this that would:
- Make it easy for office workers to view the feed of incoming bets
- Produce snapshot reports on the daily online activity
- Find and display betting patterns

Using Python, I have written a program which does this. 

Process of new bet monitor:
- Loop through the folder containing the bet summary files, read and parse relevant information from each.
- Parsed bet information is stored in a dictionary using the unique bet no. as the key, and for the value a list of bet details such as selection, odds, unit stake etc.
- The folder also contains files which notify of wager 'knockbacks' 


not finished..
