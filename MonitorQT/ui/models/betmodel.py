from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex

class BetItem:
    def __init__(self, bet_dict):
        self.bet_dict = bet_dict
        self.expanded = False  # Track expanded state if you want collapsible cards

class BetListModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.bets = []
        
    def rowCount(self, parent=QModelIndex()):
        return len(self.bets)
        
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.bets)):
            return None
            
        bet = self.bets[index.row()]
        
        if role == Qt.DisplayRole:
            return bet.bet_dict
        elif role == Qt.UserRole:
            return bet
            
        return None
        
    def setBets(self, bet_list, column_names):
        self.beginResetModel()
        self.bets = [BetItem(dict(zip(column_names, bet))) for bet in bet_list]
        self.endResetModel()
        
    def getBet(self, index):
        if 0 <= index < len(self.bets):
            return self.bets[index].bet_dict
        return None