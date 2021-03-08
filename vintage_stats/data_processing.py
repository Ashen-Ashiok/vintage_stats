import json
import logging
import requests
from pathlib import Path
from vintage_stats.utility import get_patch_release_time, get_days_since_date, WLRecord
from vintage_stats.constants import PATCH_ID_7_28A, PATCH_ID_7_28B, PATCH_ID_7_28C

logging.basicConfig(level=logging.ERROR)
requests_count = 0
response_cache = {}
hero_map = None


def add_request_count():
    global requests_count
    requests_count = requests_count + 1


def cached_opendota_request(response_str):
    global response_cache
    if response_str in response_cache:
        logging.debug('Cached used for req: {}'.format(response_str))
        return response_cache[response_str]
    else:
        response = requests.get(response_str)
        logging.debug('Cached req: {}'.format(response_str))
        add_request_count()
        response_cache[response_str] = response
        return response


def check_victory(player_match_data):
    rad_win = bool(player_match_data['radiant_win'])
    player_on_dire = int(player_match_data['player_slot']) > 127
    player_won = (rad_win and not player_on_dire) or (not rad_win and player_on_dire)
    return player_won


def get_file_cached_match_stats(match_id):
    data_folder_path = Path('.', 'data', 'matches')
    data_folder_path.mkdir(parents=True, exist_ok=True)
    match_stats_path = Path(data_folder_path, str(match_id) + '_data.json')
    if Path.is_file(match_stats_path):
        with open(match_stats_path) as match_file:
            data = json.load(match_file)
            response_cache['https://api.opendota.com/api/matches/{}'.format(match_id)] = data
            return data
    else:
        data = cached_opendota_request('https://api.opendota.com/api/matches/{}'.format(match_id)).json()
        dump_file = open(match_stats_path, 'w')
        json.dump(data, dump_file)
        return data


def get_hero_name(hero_id):
    global hero_map
    hero_map = cached_opendota_request('https://api.opendota.com/api/heroes').json()
    for hero_node in hero_map:
        if int(hero_node['id']) == hero_id:
            return hero_node['localized_name']
    return 'Not Found'


def get_mmr_change(player_won, was_party):
    sign = 1 if player_won else -1
    return (20 + int((not was_party) * 10)) * sign


def get_requests_count():
    global requests_count
    return requests_count


def get_stack_wl(players_list, exclusive=False, excluded_players=None, patch=PATCH_ID_7_28B):
    """Assumes players on players_list are on the same team. Removes players in player_list from excluded_players"""
    if len(players_list) <= 1:
        logging.debug('Stack needs to have at least 2 members.')
        return None
    if excluded_players is not None:
        excluded_players_copy = excluded_players.get_player_list().copy()
    else:
        excluded_players_copy = None
    if exclusive:
        for player in players_list:
            excluded_players_copy.remove(player)

    cutoff_date = get_patch_release_time(patch)
    days_since_cutoff = get_days_since_date(cutoff_date)

    match_sets = []
    result_map = {}

    # Find set of played matches for each player, track down its result and then intersect those sets
    # thus gaining only matches that all players played
    for player in players_list:
        response_str = 'https://api.opendota.com/api/players/{}/matches?lobby_type=7&date={}'.format(
            player.player_id, days_since_cutoff)
        matches_response = cached_opendota_request(response_str)

        player_matches_set = set()
        for match in matches_response.json():
            player_matches_set.add(int(match['match_id']))
            check_victory(match)
            result_map[match['match_id']] = check_victory(match)
        match_sets.append(player_matches_set)

    excluded_matches_set = set()
    if exclusive:
        for player in excluded_players_copy:
            response_str = 'https://api.opendota.com/api/players/{}/matches?lobby_type=7&date={}'.format(
                player.player_id, days_since_cutoff)
            matches_response = cached_opendota_request(response_str)

            for match in matches_response.json():
                excluded_matches_set.add(int(match['match_id']))

    stacked_matches_set = set.intersection(*match_sets) - excluded_matches_set

    wins = losses = 0
    for match in stacked_matches_set:
        if result_map[match]:
            wins = wins + 1
        else:
            losses = losses + 1
    stack_record = WLRecord(wins, losses)

    return stack_record
