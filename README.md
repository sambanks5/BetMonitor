# Bet Monitor
Live bet monitor & feed built for online gambling operator. SRC Code not provided here for security. 

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

20/03/2024 - Update to feed now shows colours for each bet. Colours are identifiers depending on the user/bet. Red - Risk client/bet or watchlist, Purple - New Registration, Green - Good client/bet
08/06/2024 - Added 'Staff Feed' for logging notices for staff on live activity. Additionally, added bottom panel 'Next 3' races for Horses and Greyhounds, so staff can see what is coming up and the race 'Status'

Bet Viewer UI:

User data and any other sensitive data has been blanked out, hence gaps. 

![image](https://github.com/user-attachments/assets/802d9ccb-9255-4fef-a680-849d57a2fe68)
![image](https://github.com/user-attachments/assets/958737de-9bd8-43dd-a418-890fa9d64aae)
![image](https://github.com/user-attachments/assets/b5dea8b7-ab72-4e47-b2df-21e2f79ca092)
![image](https://github.com/user-attachments/assets/258713b8-e964-4f7f-a3a7-0101611ce933)
![image](https://github.com/user-attachments/assets/7199be27-e30e-400b-bb1e-18448cc9fca3)


# Bet Processor

Bet Processor UI:

User data and any other sensitive data has been blanked out, hence gaps. 

![image](https://github.com/user-attachments/assets/b8e3def8-de9b-47f7-85d8-9bf8c389ca13)
  
  A simple UI containing a scroll text widget outputting processed bets, button to set the folder containing bet files and 'reprocess' button to delete and re-process all bet files from the folder in case of error.


Data sources (updated 06/04/2024)
![External Sources](https://github.com/user-attachments/assets/169e8616-2c45-4b9c-8192-5a95c1ebf7df)

