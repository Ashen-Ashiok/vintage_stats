import json
import logging
import requests
from pathlib import Path


logging.basicConfig(level=logging.ERROR)
requests_count = 0
response_cache = {}


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


def get_requests_count():
    global requests_count
    return requests_count


def get_mmr_change(player_won, was_party):
    sign = 1 if player_won else -1
    return (20 + int((not was_party) * 10)) * sign



