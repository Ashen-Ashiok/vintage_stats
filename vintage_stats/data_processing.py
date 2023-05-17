import json
import logging
import filecmp
import os
import time
import pickle
from collections import namedtuple
from pathlib import Path
from datetime import datetime, timedelta
from pprint import pformat

import requests

from vintage_stats.utility import WLRecord, get_days_since_date

logging.basicConfig(level=logging.INFO)

hero_map = None


class CacheHandler:
    response_cache = {}
    requests_count = 0
    hero_map = None

    @staticmethod
    def opendota_request_get(response_str):
        response = requests.get(response_str)
        logging.debug('Uncached req: {}'.format(response_str))
        CacheHandler.requests_count += 1
        return response

    @staticmethod
    def cached_opendota_request_get(response_str):
        if response_str in CacheHandler.response_cache:
            logging.debug('Cached used for req: {}'.format(response_str))
            return CacheHandler.response_cache[response_str]
        else:
            response = requests.get(response_str)
            logging.debug('Cached req: {}'.format(response_str))
            CacheHandler.requests_count += 1
            CacheHandler.response_cache[response_str] = response
            return response

    @staticmethod
    def cached_opendota_request_post(response_str):
        if response_str in CacheHandler.response_cache:
            logging.debug('Cached used for req: {}'.format(response_str))
            return CacheHandler.response_cache[response_str]
        else:
            response = requests.post(response_str)
            logging.debug('Cached req: {}'.format(response_str))
            CacheHandler.requests_count += 1
            CacheHandler.response_cache[response_str] = response
            return response

    @staticmethod
    def opendota_request_post(response_str):
        response = requests.post(response_str)
        logging.debug('Uncached req: {}'.format(response_str))
        CacheHandler.requests_count += 1
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
        data = CacheHandler.cached_opendota_request_get('https://api.opendota.com/api/players/{}'.format(player_id)).json()
        dump_file = open(players_stats_path, 'w')
        json.dump(data, dump_file, indent=4)
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
        data = CacheHandler.cached_opendota_request_get('https://api.opendota.com/api/matches/{}'.format(match_id)).json()
        dump_file = open(match_stats_path, 'w')
        json.dump(data, dump_file, indent=4)
        return data


def get_hero_name(hero_id):
    CacheHandler.hero_map = CacheHandler.cached_opendota_request_get('https://api.opendota.com/api/heroes').json()
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


def get_stack_wl(players_list, exclusive=False, excluded_players=None, _cutoff_date_from=None, _cutoff_date_to=None):
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
        matches_response = CacheHandler.cached_opendota_request_get(response_str)

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
            matches_response = CacheHandler.cached_opendota_request_get(response_str)

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


def request_match_parse(match_id):
    logging.info(f"\trequest_match_parse function for {match_id}")
    requested_set_file_path = Path("parse_requested.pickle")
    parse_requested_set = set()

    if requested_set_file_path.exists():
        logging.info("\trequest_match_parse pickle file exists")
        with requested_set_file_path.open(mode="rb") as requested_set_file:
            parse_requested_set = pickle.load(requested_set_file)
            logging.info("\trequest_match_parse pickle file loaded")
    
    if match_id in parse_requested_set:
        logging.info("\trequest_match_parse match was already requested")
        return None

    response_str = f'https://api.opendota.com/api/request/{match_id}'
    response = CacheHandler.opendota_request_post(response_str)

    parse_requested_set.add(match_id)
    logging.info(f"Sorted requested set: {pformat(sorted(parse_requested_set))}")

    with requested_set_file_path.open(mode="wb") as requested_set_file:
        pickle.dump(parse_requested_set, requested_set_file)
        logging.info("\trequest_match_parse saved to pickle file")

    request_log_path = Path("parse_requested.log")
    if not request_log_path.exists():
        with open('parse_requested.log', 'w'):
            pass
    with open('parse_requested.log', 'a') as parse_log:
        if response:
            parse_log.write(f'\nRequest: {response_str}\nResponse: {response.json()}')
    return response


def get_last_matches_map(players_list, days_threshold=7):
    last_matches_map = {}
    last_matches_map_file_path = Path("lastmatches.json")
    last_matches_map_file_path_temp = Path("lastmatches_new.json")
    last_matches_map_file_path_debug = Path("debug")
    MatchData = namedtuple('MatchData', ['match_ID', 'player_won', 'hero_name', 'kills', 'deaths',
                                         'assists', 'party_size', 'start_time', 'is_new', 'game_mode'])

    is_initial_run = False
    if last_matches_map_file_path.exists():
        with open("lastmatches.json") as last_matches_map_file:
            last_matches_map_old = json.load(last_matches_map_file)
            for listed_player_nick in last_matches_map_old:
                if last_matches_map_old[listed_player_nick]:
                    match_data = MatchData(**(last_matches_map_old[listed_player_nick]))
                    last_matches_map_old[listed_player_nick] = match_data
    else:
        is_initial_run = True

    for listed_player in players_list:
        response_str = 'https://api.opendota.com/api/players/{}/matches?significant=0&date={}'.format(
            listed_player.player_id, days_threshold)
        matches_response = CacheHandler.opendota_request_get(response_str)
    
        if not matches_response:
            logging.error(f"Missing matches response for player {listed_player.nick}. Replaced with previous data.")
            match_data_old = MatchData(**(last_matches_map_old[listed_player.nick]))
            last_matches_map[listed_player.nick] = match_data_old
            continue

        logging.debug(listed_player)
        if matches_response.json()[:1]:
            last_match = matches_response.json()[:1][0]
            game_mode = last_match['game_mode']
            kills = last_match['kills']
            deaths = last_match['deaths']
            assists = last_match['assists']
            party_size = last_match['party_size']
            match_id = last_match['match_id']
            player_won = check_victory(last_match)
            player_hero = get_hero_name(last_match['hero_id'])
            start_time = last_match['start_time']

            is_new = False
            if is_initial_run:
                is_new = True
            else:
                if listed_player.nick in last_matches_map_old \
                        and last_match['match_id'] != last_matches_map_old[listed_player.nick].match_ID:
                    is_new = True

            match_data = MatchData(match_id, player_won, player_hero, kills, deaths, assists, party_size, start_time,
                                   game_mode=game_mode, is_new=is_new)
            match_data_dict = match_data._asdict()
            last_matches_map[listed_player.nick] = match_data_dict

    json.dump(last_matches_map, open(last_matches_map_file_path_temp, "w"), indent=4)
    check = filecmp.cmp('lastmatches.json', 'lastmatches_new.json')
    if not check:
        logging.info(f"Lastmatches files differed, saving a copy of the old.")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        os.rename('lastmatches.json', f'lastmatches_{timestamp}.json')
        os.rename('lastmatches_new.json', 'lastmatches.json')
    else:
        logging.info(f"Lastmatches files were identical, keeping only one.")
        os.remove("lastmatches.json")
        os.rename('lastmatches_new.json', 'lastmatches.json')

    for listed_player_nick in last_matches_map:
        match_data = MatchData(**(last_matches_map[listed_player_nick]))
        last_matches_map[listed_player_nick] = match_data

    logging.info(f"Is_new: {is_new}, is_initial_run: {is_initial_run}")

    if not is_initial_run:
        for player in last_matches_map:
            current_match_ID = last_matches_map[player].match_ID
            try:
                previous_match_ID = last_matches_map_old[player].match_ID
            except KeyError:
                logging.error(f"Previous match missing for {player}, dumping map to debug/lastmatches_{int(time.time())}.json")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                json.dump(last_matches_map, open(last_matches_map_file_path_debug / f"lastmatches_{timestamp}_error_new.json", "w"), indent=4)
                json.dump(last_matches_map_old, open(last_matches_map_file_path_debug / f"lastmatches_{timestamp}_error_old.json", "w"), indent=4)
                continue
            if current_match_ID == previous_match_ID:
                last_matches_map[listed_player_nick] = match_data
                last_matches_map[player] = last_matches_map[player]._replace(is_new=False)

    return last_matches_map


def format_and_print_winrate_report(data_report, _hero_count_threshold, _heroes_threshold, heroes_count=3, list_all_heroes=False):
    # For logic behind these numbers, look at get_record_goodness()
    worst_hero_goodness_threshold = -100
    best_hero_goodness_threshold = 100
    print(f'Nickname\tTotal G\tTotal W\tTotal L\tSolo W\tSolo L\tParty W\tParty L\tSolo %'
          f'\tBest hero\tHeroes played\tHeroes played X+ times\tHPX+ wins\tHPX+ losses'
          f'\tWorst heroes\t Threshold {_hero_count_threshold}')
    for player_report in data_report:
        try:
            solo_percentage = player_report['solo'].get_count() / player_report['total'].get_count() * 100
        except ZeroDivisionError:
            solo_percentage = 100
        heroes = player_report['best_heroes']

        best_heroes_string = 'Not enough games played.'
        no_good_heroes_flag = True
        count = 0
        for best_hero in heroes:
            if count >= heroes_count:
                break
            if best_hero[1].get_count() >= _heroes_threshold and best_hero[1].get_record_goodness() > best_hero_goodness_threshold:
                no_good_heroes_flag = False
                best_hero_name = get_hero_name(best_hero[0])
                best_hero_record = best_hero[1]
                if best_heroes_string == 'Not enough games played.':
                    best_heroes_string = f'="{best_hero_name} ({best_hero_record})"'
                else:
                    best_heroes_string += f' & CHAR(10) & "{best_hero_name} ({best_hero_record})"'
                count += 1

        if no_good_heroes_flag:
            best_heroes_string = 'No such heroes.'

        worst_heroes_string = 'Not enough games played.'
        no_bad_heroes_flag = True
        count = 0
        for worst_hero in reversed(heroes):
            if count >= heroes_count:
                break
            if worst_hero[1].get_count() >= _heroes_threshold and worst_hero[1].get_record_goodness() < worst_hero_goodness_threshold:
                no_bad_heroes_flag = False
                worst_hero_name = get_hero_name(worst_hero[0])
                worst_hero_record = worst_hero[1]
                if worst_heroes_string == 'Not enough games played.':
                    worst_heroes_string = f'="{worst_hero_name} ({worst_hero_record})"'
                else:
                    worst_heroes_string += f' & CHAR(10) & "{worst_hero_name} ({worst_hero_record})"'
                count += 1

        if no_bad_heroes_flag:
            worst_heroes_string = 'No such heroes.'

        print(f'{player_report["nick"]}\t{player_report["total"].get_count()}'
              f'\t{player_report["total"].wins}\t{player_report["total"].losses}'
              f'\t{player_report["solo"].wins}\t{player_report["solo"].losses}'
              f'\t{player_report["party"].wins}\t{player_report["party"].losses}\t{solo_percentage:.2f}%'
              f'\t{best_heroes_string}\t{player_report["hero_count"]}\t{player_report["hero_count_more"]}'
              f'\t{player_report["hero_more_record"].wins}\t{player_report["hero_more_record"].losses}\t{worst_heroes_string}')

    if list_all_heroes:
        for player_report in data_report:
            print(f'--- {player_report["nick"]} ---')
            heroes = player_report['best_heroes']
            for hero in heroes:
                print(f'\t{get_hero_name(hero[0])}: {hero[1]}')


def get_mmr_history_table(player, match_id_with_known_mmr, known_mmr_amount, _start_date_string=None, _end_date_string=None):
    start_date = datetime.now() - timedelta(days=2*365)
    end_date = datetime.now()
    if _start_date_string:
        start_date = datetime.fromisoformat(_start_date_string)
    if _end_date_string:
        end_date = datetime.fromisoformat(_end_date_string)
    response_str = 'https://api.opendota.com/api/players/{}/matches?lobby_type=7&date={}'.format(
        player.player_id, get_days_since_date(start_date))
    matches_response = CacheHandler.cached_opendota_request_get(response_str)

    match_map = []
    known_mmr_idx = None
    used_idx = 0

    for match in matches_response.json():
        match_datetime = datetime.fromtimestamp(match['start_time'])
        if match_datetime < start_date:
            continue
        if match_datetime > end_date:
            continue

        match_id = int(match['match_id'])
        if match['party_size'] is None:
            was_party = False
        else:
            was_party = int(match['party_size']) > 1

        player_won = check_victory(match)
        mmr_change = get_mmr_change(player_won, was_party)
        mmr_after = None

        if match_id == match_id_with_known_mmr:
            mmr_after = known_mmr_amount
            known_mmr_idx = used_idx
        match_record = {"match_id": match_id,
                        "mmr_after": mmr_after,
                        "won": player_won,
                        "party": was_party,
                        "mmr_change": mmr_change,
                        "start_time": match_datetime,
                        "start_time_string": match_datetime.strftime('%d-%b-%Y')}
        used_idx = used_idx + 1
        match_map.append(match_record)

    if match_map is None or known_mmr_idx is None:
        return []

    prev_mmr = None
    prev_change = None

    # Iterate from the known point to the past
    # Match map from Opendota data is from newest to latest
    for match_record in match_map[known_mmr_idx:]:
        if match_record['mmr_after']:
            prev_mmr = match_record['mmr_after']
            prev_change = match_record['mmr_change']
        if prev_mmr and prev_change and not match_record['mmr_after']:
            match_record['mmr_after'] = prev_mmr - prev_change
            prev_mmr = prev_mmr - prev_change
            prev_change = match_record['mmr_change']

    # Iterate from the known point to the present
    for match_record in reversed(match_map[:known_mmr_idx+1]):
        if match_record['mmr_after']:
            prev_mmr = match_record['mmr_after']
            prev_change = match_record['mmr_change']
        if prev_mmr and prev_change and not match_record['mmr_after']:
            match_record['mmr_after'] = prev_mmr + prev_change
            prev_mmr = prev_mmr + prev_change
            prev_change = match_record['mmr_change']

    return list(reversed(match_map))


def get_player_match_history(player):
    logging.info(f"get_player_match_history for {player}")
    match_history_dir_path = Path("match_histories")
    player_history_path = match_history_dir_path / f"{player.player_id}_history.json"
    player_history = None

    if player_history_path.exists():
        history_file_error = False
        with player_history_path.open(mode="r") as player_history_file:
            logging.info(f"get_player_match_history file exists for {player}")
            
            try:
                player_history = json.load(player_history_file)
            except Exception as e:
                logging.error(f"get_player_match_history file loading error: {e}")
                history_file_error = True

            if not player_history or not isinstance(player_history, list) or not player_history[0]['match_id']:
                history_file_error = True
        
        if history_file_error:
            logging.error(f"get_player_match_history existing file is invalid for {player}")

            with player_history_path.open(mode="w") as player_history_file:
                player_history_file.truncate(0)
                response_str = f"https://api.opendota.com/api/players/{player.player_id}/matches?significant=0&date=60"
                player_history = CacheHandler.opendota_request_get(response_str).json()
                # trim to 40 games
                if len(player_history) > 40:
                    player_history = player_history[:40]
                json.dump(player_history, player_history_file, indent=4)

        return player_history
    else:
        with player_history_path.open(mode="w") as player_history_file:
            logging.info(f"get_player_match_history file does not exist for {player}")
            response_str = f"https://api.opendota.com/api/players/{player.player_id}/matches?significant=0&date=60"
            player_history = CacheHandler.opendota_request_get(response_str).json()
            # trim to 40 games
            if len(player_history) > 40:
                player_history = player_history[:40]
            json.dump(player_history, player_history_file, indent=4)
            return player_history


def save_player_match_history(player, match_history):
    logging.info(f"save_player_match_history for {player}")
    match_history_dir_path = Path("match_histories")
    player_history_path = match_history_dir_path / f"{player.player_id}_history.json"
    player_history_path_old = match_history_dir_path / f"{player.player_id}_history_old.json"

    if player_history_path.exists():
        os.rename(player_history_path, player_history_path_old)

    with player_history_path.open(mode="w") as player_history_file:
        player_history = match_history
        # trim to 40 games
        if len(player_history) > 40:
            player_history = player_history[:40]
        json.dump(player_history, player_history_file, indent=4)
        logging.info(f"save_player_match_history succesful for {player}")
        if player_history_path_old.exists():
            check = filecmp.cmp(player_history_path, player_history_path_old)
            if not check:
                logging.info(f"Match history for player {player} differed, saving a copy.")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.rename(player_history_path_old, f"match_histories/{player.player_id}_history_old_{timestamp}.json")
        return True


def handle_recent_matches_file(response_json, player):
    match_history_dir_path = Path("match_histories")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    player_recent_matches_path = match_history_dir_path / f"{player.player_id}_recentMatches.json"
    player_recent_matches_path_archive = match_history_dir_path / f"{player.player_id}_recentMatches_{timestamp}.json"

    if player_recent_matches_path.exists():
        os.rename(player_recent_matches_path, player_recent_matches_path_archive)

    with player_recent_matches_path.open(mode="w") as player_recent_matches_file:
        recent_matches = response_json
        json.dump(recent_matches, player_recent_matches_file, indent=4)
        logging.info(f"Saving recentMatches for player {player} to file {player_recent_matches_path}")

    if player_recent_matches_path_archive.exists():
        logging.info(f"Comparing\n{player_recent_matches_path}\n{player_recent_matches_path_archive}")
        check = filecmp.cmp(player_recent_matches_path, player_recent_matches_path_archive)
        if check:
            logging.info(f"Match history for player {player} identical, removing the copy.")
            os.remove(player_recent_matches_path_archive)
        else:
            logging.info(f"Match history for player {player} differed, keeping a copy.")

