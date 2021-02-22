from data_processing import cached_opendota_request


class WLRecord:
    """Holds wins/losses record, able to provide basic statistics (games count, winrate)"""

    def __init__(self, wins, losses):
        self.wins = wins
        self.losses = losses

    def __add__(self, other):
        new_wins = self.wins + other.wins
        new_losses = self.losses + other.losses
        return WLRecord(new_wins, new_losses)

    def __str__(self):
        return '{}–{}'.format(self.wins, self.losses)

    def get_count(self):
        return self.losses + self.wins

    def get_winrate(self):
        try:
            return 100 * self.wins / (self.losses + self.wins)
        except ZeroDivisionError:
            return 0


class Player:
    """Holds basic information about each player, player data"""

    def __init__(self, pid, nick):
        self.player_id = pid
        self.nick = nick
        self.player_data = cached_opendota_request('https://api.opendota.com/api/players/{}'.format(self.player_id)).json()
        self.profile_nickname = self.player_data['profile']['personaname']

    def __lt__(self, other):
        return self.profile_nickname < other.profile_nickname

    def __str__(self):
        return '{} (Profile nickname: {}, ID: {})'.format(self.nick, self.profile_nickname, self.player_id)
