import json
import logging
from collections import namedtuple
from pathlib import Path

import requests

from vintage_stats.constants import PATCH_ID_7_28B
from vintage_stats.utility import get_patch_release_time, get_days_since_date, WLRecord

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


def get_file_cached_player_stats(player_id):
    data_folder_path = Path('.', 'data', 'players')
    data_folder_path.mkdir(parents=True, exist_ok=True)
    players_stats_path = Path(data_folder_path, str(player_id) + '_data.json')

    if Path.is_file(players_stats_path):
        with open(players_stats_path) as match_file:
            data = json.load(match_file)
            response_cache['https://api.opendota.com/api/players/{}'.format(player_id)] = data
            return data
    else:
        data = cached_opendota_request('https://api.opendota.com/api/players/{}'.format(player_id)).json()
        dump_file = open(players_stats_path, 'w')
        json.dump(data, dump_file)
        return data


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


def log_requests_count():
    request_log_path = Path("request.log")
    if not request_log_path.exists():
        with open('request.log', 'w') as request_log:
            request_log.write('0')
    requests_used_today = 0
    with open('request.log', 'r+') as request_log:
        for line in request_log:
            requests_used_today = int(line)
    with open('request.log', 'w') as request_log:
        request_log.write('{}'.format(get_requests_count() + requests_used_today))


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


def get_last_matches_map(players_list):
    last_matches_map = {}
    threshold_in_days = 7
    last_matches_map_file_path = Path("lastmatches.json")
    MatchData = namedtuple('MatchData', ['match_ID', 'player_won', 'hero_name', 'kills', 'deaths', 'assists', 'party_size', 'start_time', 'is_new'])

    is_initial_run = False
    if last_matches_map_file_path.exists():
        with open("lastmatches.json") as last_matches_map_file:
            last_matches_map_old = json.load(last_matches_map_file)
            for listed_player_nick in last_matches_map_old:
                match_data = MatchData(**(last_matches_map_old[listed_player_nick]))
                last_matches_map_old[listed_player_nick] = match_data
    else:
        is_initial_run = True

    for listed_player in players_list:
        response_str = 'https://api.opendota.com/api/players/{}/matches?lobby_type=7&date={}'.format(
            listed_player.player_id, threshold_in_days)
        matches_response = cached_opendota_request(response_str)

        for match in matches_response.json()[:1]:
            kills = match['kills']
            deaths = match['deaths']
            assists = match['assists']
            party_size = match['party_size']
            match_id = match['match_id']
            player_won = check_victory(match)
            player_hero = get_hero_name(match['hero_id'])
            time = match['start_time']
            match_data = MatchData(match_id, player_won, player_hero, kills, deaths, assists, party_size, time, is_new=not is_initial_run)
            match_data_dict = match_data._asdict()
            last_matches_map[listed_player.nick] = match_data_dict
    json.dump(last_matches_map, open(last_matches_map_file_path, "w"))

    for listed_player_nick in last_matches_map:
        match_data = MatchData(**(last_matches_map[listed_player_nick]))
        last_matches_map[listed_player_nick] = match_data

    if not is_initial_run:
        for player in last_matches_map:
            current_match_ID = last_matches_map[player].match_ID
            previous_match_ID = last_matches_map_old[player].match_ID
            if current_match_ID == previous_match_ID:
                last_matches_map[listed_player_nick] = match_data
                last_matches_map[player] = last_matches_map[player]._replace(is_new=False)

    return last_matches_map
