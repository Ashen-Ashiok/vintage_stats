from vintage_stats import data_processing


class PlayerClass:
    """Holds basic information about each player, player data"""

    def __init__(self, pid, nick, match_id=None, mmr_amount=None):
        self.player_id = pid
        self.nick = nick
        self.player_data = data_processing.get_file_cached_player_stats(self.player_id)
        self.profile_nickname = self.player_data['profile']['personaname']
        self.known_mmr = {
            "match_id": match_id,
            "mmr_amount": mmr_amount
        }

    def __lt__(self, other):
        return self.profile_nickname < other.profile_nickname

    def __str__(self):
        return '{} (Profile nickname: {}, ID: {})'.format(self.nick, self.profile_nickname, self.player_id)

    def set_known_mmr_point(self, match_id, mmr_amount):
        self.known_mmr = {
            "match_id": match_id,
            "mmr_amount": mmr_amount
        }


class PlayerPool:
    """Holds a list of players"""
    def __init__(self, input_player_map):
        self.player_dict = {}
        for player_mapping in input_player_map:
            player = PlayerClass(player_mapping['pid'], player_mapping['nick'])
            self.player_dict[player_mapping['nick']] = player

    def get_player(self, nick):
        return self.player_dict[nick]

    def get_player_list(self):
        return list(self.player_dict.values())

    def __iter__(self):
        for item in sorted(self.player_dict.values(), key=lambda player: player.nick):
            yield item

    def remove(self, player):
        self.player_dict.pop(player, None)
