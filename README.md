# Bet Monitor
Live bet monitor & feed built for online gambling operator.
Potential employers are welcome to enquire and I can give live demonstrations.


- Previous monitoring program outdated, errored and unhelpful.
- When a bet is placed, function within the system generates a file containing summary of bet details.
- Old program used to display these files had become obsolete (2004), odds traders & support staff would not be able to run through bet feed - the 'tree' layout was limiting.
- Auto-generated text files were displaying a lot of unneeded information, traders would struggle to 'at a glance' understand the wager info.
- Finally, the main limitation is that the betting 'database' containing full user, bet and event information is fully encrypted.






Below is the old program used (hidden customer refs):
![image](https://github.com/sambanks5/BetMonitor/assets/121309218/cd0dfb2b-7c0c-4017-906b-2d22b1f1b211)

The solution was to create an updated version of this that would:
- Display a feed of live incoming wagers, making it easy to 'scan' through and get a snapshot of current betting activity. Bets categorised and displayed in colours as per bet 'risk'. Additionally, filter the feed by 5 variables (Client, Unit Stk, Risk Category, Selection and Sport).
- Display a feed of 'Runs on selections', for staff to see selections (events) that have taken above x number of bets in the last x total number of bets. For identifying selections where we may have a higher than market average odds or finding groups of linked clients betting on the same selection.
- Produce snapshot report on daily activity and staff activity.
- Screen daily user activity for signs of trading/arbing/other high risk activity.
- Screen daily user activity for signs of Irresponsible Gambling.
- Apply 'factoring' (increasing or decreasing max stakes, restricting certain sports or price types) to certain client accounts using internal and Pipedrive API.
- Internal staff tracker for what racing events need checking for updates.
- Display of the 'Next 3' Horse and Greyhound races to go off, for staff to keep up with days main events.
- Staff notification 'feed' so the office can keep up with what everyone else is doing, avoiding duplicated work and allowing for better efficiency. Additionally, notifications display for daily milestones and notices.
- View up to 30 days of previous databases of betting activity, usually for support purposes.
- Other various QoL improvements for office staff

  
# Bet Viewer
# Not displaying real data - in test mode to show function of the UI.  

![image](https://github.com/user-attachments/assets/a5d99c6c-2f35-492f-8c39-cd6a0fba2b84)


# Bet Feed
- Main module of the tool displaying a live feed of incoming bets, knockbacks and SMS bet requests. 
- Colours to signify client 'Risk', as well as to make it easier to get 'at a glance' a snapshot of activity.
- If users are backing certain selections that are current plays on Matched Betting sites, it will signify this next to the wager. 
- Filtering options also available as to alter the live feed output, and to assist with clients' queries wanting clarity on their recent activity.

# Activity Status
- Shows current bets/knockbacks/knockback%. Displays comparrison to the values at the same time the previous day (can be altered to compare to previous week)
- Also displays current turnover/profit/profit%, breakdown of clients by type and bet take per sport.

# Bet Runs
- An important module for in-house traders, allowing them to view live which selections have been taking the most action in the last X number of bets.
- Selections taking lots of wagers in a short period can be telling, and means action to alter the price must be taken.
- Uses same colourscheme as in the Bet Feed for outlining clients by risk.
  
# Race Updation
- Small module to help traders keep on top of manual checks on liabilities for racing.
  
# Staff Feed
- Staff Feed is a live feed of staff activity, assisting communication and efficiency.
- It will occasionally kick out news information on sporting events from API's, as well as company notices or reminders that are important to tend to.
- A points system is in place, whereby staff are awarded a score for work done, and a fun ceremony at the end of each month to award the best traders.
  
# Reporting
- Reporting module that can output Daily, Monthly reports on betting activity.
- 'Screeners' to find trading activity, as well as outline any users showing signs of irresponsible gambling for compliance teams.
- A Staff Report to show who's been working the hardest, as well as some other fun info on staff activity.
  
# Factoring Log, Freebet Log, Popup Log
- Apply and log changes to client account terms, apply and log Freebets, and display responsible gambling popups to certain clients from the tool.
  
# Client Reporting & Modifications
- Center for making changes to client account terms, applying freebets and showing responsible gambling popups to certain clients.
- All links to various API for processing and notifying clients via email.
  

# Live Events
- Displays all current live events and their last manual check on liabilities for tracking.
  
# Next 3 Races
- Shows next 3 Horses and Greyhound races that are due to go off, and their current status.
- Helps to track what's coming up, and assist customer service taking phone bets.
- Can switch between UK/IRISH Racing and ALL (inc. international)
  
# Bet Processor

Bet Processor UI:

User data and any other sensitive data has been blanked out, hence gaps. 

![image](https://github.com/user-attachments/assets/b8e3def8-de9b-47f7-85d8-9bf8c389ca13)
  
  A simple UI containing a scroll text widget outputting processed bets, button to set the folder containing bet files and 'reprocess' button to delete and re-process all bet files from the folder in case of error.

