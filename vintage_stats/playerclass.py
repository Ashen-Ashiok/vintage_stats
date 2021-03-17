from vintage_stats import data_processing


class PlayerClass:
    """Holds basic information about each player, player data"""

    def __init__(self, pid, nick):
        self.player_id = pid
        self.nick = nick
        self.player_data = data_processing.get_file_cached_player_stats(self.player_id)
        self.profile_nickname = self.player_data['profile']['personaname']

    def __lt__(self, other):
        return self.profile_nickname < other.profile_nickname

    def __str__(self):
        return '{} (Profile nickname: {}, ID: {})'.format(self.nick, self.profile_nickname, self.player_id)
