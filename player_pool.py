from player import PlayerClass


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
        for item in sorted(self.player_dict.values()):
            yield item

    def remove(self, player):
        self.player_dict.pop(player, None)
