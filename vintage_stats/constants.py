from datetime import datetime

# PLAYER ID ALIASES
FAZY_ID = 67712324
GRUMPY_ID = 100117588
KESKOO_ID = 119653426
SHIFTY_ID = 171566175
WARELIC_ID = 211310297


class DotaPatch:
    def __init__(self, name, release_time):
        self.name = name
        self.release_time = release_time

    def __str__(self):
        string_datetime = self.release_time.strftime('%d-%b-Y %H:%M')
        return f'(version {self.name} (released on {string_datetime})'


v728a = DotaPatch('7.28a', datetime(2020, 12, 22, 12, 0))
v728b = DotaPatch('7.28b', datetime(2021, 1, 11, 6, 0))
v728c = DotaPatch('7.28c', datetime(2021, 2, 20, 3, 0))

VERSIONS = {'7.28a': v728a,
            '7.28b': v728b,
            '7.28c': v728c}
