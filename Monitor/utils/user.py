USER_NAMES = {
    'GB': 'George B',
    'GM': 'George M',
    'JP': 'Jon',
    'DF': 'Dave',
    'SB': 'Sam',
    'JJ': 'Joji',
    'AE': 'Arch',
    'EK': 'Ed',
    'VO': 'Victor',
    'MF': 'Mark'
}

_user = ""

def get_user():
    global _user
    return _user

def set_user(value):
    global _user
    _user = value