import json
import logging
from collections import namedtuple
from pathlib import Path
from datetime import datetime, timedelta

import requests

from vintage_stats.constants import VERSIONS
from vintage_stats.utility import WLRecord, get_days_since_date

logging.basicConfig(level=logging.ERROR)

hero_map = None


class CacheHandler:
    response_cache = {}
    requests_count = 0
    hero_map = None

    @staticmethod
    def cached_opendota_request(response_str):
        if response_str in CacheHandler.response_cache:
            logging.debug('Cached used for req: {}'.format(response_str))
            return CacheHandler.response_cache[response_str]
        else:
            response = requests.get(response_str)
            logging.debug('Cached req: {}'.format(response_str))
            CacheHandler.requests_count += 1
            CacheHandler.response_cache[response_str] = response
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
            CacheHandler.response_cache['https://api.opendota.com/api/players/{}'.format(player_id)] = data
            return data
    else:
        data = CacheHandler.cached_opendota_request('https://api.opendota.com/api/players/{}'.format(player_id)).json()
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
            CacheHandler.response_cache['https://api.opendota.com/api/matches/{}'.format(match_id)] = data
            return data
    else:
        data = CacheHandler.cached_opendota_request('https://api.opendota.com/api/matches/{}'.format(match_id)).json()
        dump_file = open(match_stats_path, 'w')
        json.dump(data, dump_file)
        return data


def get_hero_name(hero_id):
    CacheHandler.hero_map = CacheHandler.cached_opendota_request('https://api.opendota.com/api/heroes').json()
    for hero_node in CacheHandler.hero_map:
        if int(hero_node['id']) == hero_id:
            return hero_node['localized_name']
    return 'Not Found'


def get_mmr_change(player_won, was_party):
    sign = 1 if player_won else -1
    return (20 + int((not was_party) * 10)) * sign


def get_requests_count():
    return CacheHandler.requests_count


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


def get_stack_wl(players_list, exclusive=False, excluded_players=None, patch=None, _cutoff_date_from=None, _cutoff_date_to=None):
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

    # Default values
    cutoff_date_from = datetime.now() - timedelta(days=28)
    cutoff_date_to = datetime.now()

    if patch in VERSIONS:
        cutoff_date_from = VERSIONS[patch].release_time

    if _cutoff_date_from is not None:
        cutoff_date_from = _cutoff_date_from

    if _cutoff_date_to is not None:
        cutoff_date_to = _cutoff_date_to

    days_since_cutoff = get_days_since_date(cutoff_date_from)

    match_sets = []
    result_map = {}

    # Find set of played matches for each player, track down its result and then intersect those sets
    # thus gaining only matches that all players played
    for player in players_list:
        response_str = 'https://api.opendota.com/api/players/{}/matches?lobby_type=7&date={}'.format(
            player.player_id, days_since_cutoff)
        matches_response = CacheHandler.cached_opendota_request(response_str)

        player_matches_set = set()
        for match in matches_response.json():
            match_datetime = datetime.fromtimestamp(match['start_time'])
            if match_datetime < cutoff_date_from or match_datetime > cutoff_date_to:
                continue
            player_matches_set.add(int(match['match_id']))
            check_victory(match)
            result_map[match['match_id']] = check_victory(match)
        match_sets.append(player_matches_set)

    excluded_matches_set = set()
    if exclusive:
        for player in excluded_players_copy:
            response_str = 'https://api.opendota.com/api/players/{}/matches?lobby_type=7&date={}'.format(
                player.player_id, days_since_cutoff)
            matches_response = CacheHandler.cached_opendota_request(response_str)

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
    MatchData = namedtuple('MatchData', ['match_ID', 'player_won', 'hero_name', 'kills', 'deaths',
                                         'assists', 'party_size', 'start_time', 'is_new'])

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
        matches_response = CacheHandler.cached_opendota_request(response_str)

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


def format_and_print_winrate_report(data_report, _hero_count_threshold, _best_heroes_threshold, heroes_count=3):
    print(f'Nickname\tSolo W\tSolo L\tParty W\tParty L\tSolo %'
          f'\tBest hero\tHeroes played\tHeroes played X+ times\tHPX+ wins\tHPX+ losses'
          f'\tWorst heroes\t Threshold {_hero_count_threshold}')
    for player_report in data_report:
        try:
            solo_percentage = player_report['solo'].get_count() / player_report['total'].get_count() * 100
        except ZeroDivisionError:
            solo_percentage = 100
        best_heroes = player_report['best_heroes']

        best_heroes_string = 'Not enough games played.'
        count = 0
        for best_hero in best_heroes:
            if count >= heroes_count:
                break
            if best_hero[1].get_count() >= _best_heroes_threshold and best_hero[1].get_record_goodness() >= 4:
                best_hero_name = get_hero_name(best_hero[0])
                best_hero_record = best_hero[1]
                if best_heroes_string == 'Not enough games played.':
                    best_heroes_string = f'="{best_hero_name} ({best_hero_record})"'
                else:
                    best_heroes_string += f' & CHAR(10) & "{best_hero_name} ({best_hero_record})"'
                count += 1

        worst_heroes_string = 'Not enough games played.'
        count = 0
        for worst_hero in reversed(best_heroes):
            if count >= heroes_count:
                break
            if worst_hero[1].get_count() > 1 and worst_hero[1].get_record_goodness() < 0:
                worst_hero_name = get_hero_name(worst_hero[0])
                worst_hero_record = worst_hero[1]
                if worst_heroes_string == 'Not enough games played.':
                    worst_heroes_string = f'="{worst_hero_name} ({worst_hero_record})"'
                else:
                    worst_heroes_string += f' & CHAR(10) & "{worst_hero_name} ({worst_hero_record})"'
                count += 1

        for hero in best_heroes:
            logging.debug(f'{get_hero_name(hero[0])} - {hero[1]}')

        print(f'{player_report["nick"]}\t{player_report["solo"].wins}\t{player_report["solo"].losses}'
              f'\t{player_report["party"].wins}\t{player_report["party"].losses}\t{solo_percentage:.2f}%'
              f'\t{best_heroes_string}\t{player_report["hero_count"]}\t{player_report["hero_count_more"]}'
              f'\t{player_report["hero_more_record"].wins}\t{player_report["hero_more_record"].losses}\t{worst_heroes_string}')

