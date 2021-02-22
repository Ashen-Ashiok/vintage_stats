from datetime import datetime
from data_processing import cached_opendota_request

# PLAYER ID ALIASES
FAZY_ID = 67712324
GRUMPY_ID = 100117588
KESKOO_ID = 119653426
SHIFTY_ID = 171566175
WARELIC_ID = 211310297

# HERO MAP
HERO_MAP = cached_opendota_request('https://api.opendota.com/api/heroes').json()


# PATCH IDs
PATCH_ID_7_28A = 47  # id of patch 7.28 based on https://github.com/odota/dotaconstants/blob/master/json/patch.json
PATCH_ID_7_28B = 471  # custom id
PATCH_ID_7_28C = 472  # custom id


def get_hero_name(hero_id):
    for hero_node in HERO_MAP:
        if int(hero_node['id']) == hero_id:
            return hero_node['localized_name']
    return 'Not Found'


def get_patch_release_time(patch):
    cases = {
        PATCH_ID_7_28A: datetime(2020, 12, 22, 12, 0),
        PATCH_ID_7_28B: datetime(2021, 1, 11, 6, 0),
        PATCH_ID_7_28C: datetime(2021, 2, 20, 3, 0),
    }
    return cases.get(patch, datetime(2020, 12, 1, 0, 0))




