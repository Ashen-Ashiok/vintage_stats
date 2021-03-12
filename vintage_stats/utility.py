from datetime import datetime, timedelta

from vintage_stats.constants import *


class WLRecord:
    """Holds wins/losses record, able to provide basic statistics (games count, winrate)"""

    def __init__(self, wins, losses):
        self.wins = wins
        self.losses = losses

    def __add__(self, other):
        new_wins = self.wins + other.wins
        new_losses = self.losses + other.losses
        return WLRecord(new_wins, new_losses)

    def add_match(self, player_won):
        if player_won:
            self.wins = self.wins + 1
        else:
            self.losses = self.losses + 1

    def __str__(self):
        return '{}–{}'.format(self.wins, self.losses)

    def get_count(self):
        return self.losses + self.wins

    def get_record_goodness(self):
        count = self.wins + self.losses
        net = self.wins - self.losses
        return net * 100 + count

    def get_winrate(self):
        try:
            return 100 * self.wins / (self.losses + self.wins)
        except ZeroDivisionError:
            return 0


def get_days_since_date(date):
    """Ensures at least 1 day at minimum without corrupting the date itself."""
    seconds_since_cutoff = (datetime.now() - date).total_seconds()
    return int(seconds_since_cutoff / 86400)


def get_last_monday():
    """Used for reports that are cut off by a start of a week"""
    time_now = datetime.now()
    last_monday = time_now - timedelta(days=time_now.weekday()) - timedelta(hours=time_now.hour,
                                                                            minutes=time_now.minute,
                                                                            seconds=time_now.second)
    return last_monday


def get_patch_release_time(patch):
    """Helper class for converting patch IDs into patch release dates"""
    cases = {
        PATCH_ID_7_28A: datetime(2020, 12, 22, 12, 0),
        PATCH_ID_7_28B: datetime(2021, 1, 11, 6, 0),
        PATCH_ID_7_28C: datetime(2021, 2, 20, 3, 0),
    }
    return cases.get(patch, datetime(2020, 12, 1, 0, 0))
