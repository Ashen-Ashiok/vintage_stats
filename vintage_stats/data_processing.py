import json
import logging
import filecmp
import os
import random
import time
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from pprint import pformat, pprint

import requests
import timeago

from vintage_stats.constants import GAME_MODES
from vintage_stats.utility import WLRecord, get_days_since_date

logging.basicConfig(level=logging.DEBUG)

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
    def opendota_request_post(request_url):
        logging.info(f"opendota_request_post, url: {request_url}")
        headers = {'content-length': ''}
        response = requests.post(request_url, headers)
        logging.info(f"opendota_request_post, response: {response.json()}")
        logging.debug('Uncached req: {}'.format(request_url))
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
    requests_count_history = 0
    with open('request.log', 'r+') as request_log:
        for line in request_log:
            requests_count_history = int(line)
    with open('request.log', 'w') as request_log:
        logging.info(f"Requests used this run: {get_requests_count()}, requests_count_history: {requests_count_history}.")
        request_log.write('{}'.format(get_requests_count() + requests_count_history))


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
    parse_requested_dict = {}

    if requested_set_file_path.exists():
        logging.info("\trequest_match_parse pickle file exists")
        with requested_set_file_path.open(mode="rb") as requested_file:
            parse_requested_dict = pickle.load(requested_file)
            logging.info("\trequest_match_parse pickle file loaded")

    if match_id in parse_requested_dict and parse_requested_dict[match_id] > 2:
        logging.info("\trequest_match_parse match was already requested 3 times.")
        return None

    response_str = f'https://api.opendota.com/api/request/{match_id}'
    response = CacheHandler.opendota_request_post(response_str)

    if match_id in parse_requested_dict:
        parse_requested_dict[match_id] += 1
    else:
        parse_requested_dict[match_id] = 1
    logging.info(f"Sorted requested dict: {pformat(parse_requested_dict)}")

    with requested_set_file_path.open(mode="wb") as requested_file:
        pickle.dump(parse_requested_dict, requested_file)
        logging.info("\trequest_match_parse saved to pickle file")

    if response:
        logging.info(f"Parse request for match_id {match_id} response: {pformat(response.json())}")
    return response


def get_last_matches_map(players_list, days_threshold=7):
    last_matches_map = {}
    last_matches_map_file_path = Path("lastmatches.json")
    last_matches_map_file_path_temp = Path("lastmatches_new.json")

    is_initial_run = False
    if last_matches_map_file_path.exists():
        with open("lastmatches.json") as last_matches_map_file:
            last_matches_map_old = json.load(last_matches_map_file)
    else:
        is_initial_run = True

    for listed_player in players_list:
        response_str = 'https://api.opendota.com/api/players/{}/matches?significant=0&date={}'.format(
            listed_player.player_id, days_threshold)
        matches_response = CacheHandler.opendota_request_get(response_str)

        if not matches_response:
            logging.error(f"Missing matches response for player {listed_player.nick}. Replaced with previous data.")
            last_matches_map[listed_player.nick] = last_matches_map_old[listed_player.nick]
            last_matches_map[listed_player.nick]['is_new'] = False
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
                logging.info(f"{listed_player.nick} checking id {last_match['match_id']}"
                             f" vs {last_matches_map_old[listed_player.nick]['match_id']}")
                if listed_player.nick in last_matches_map_old \
                        and last_match['match_id'] != last_matches_map_old[listed_player.nick]['match_id']:
                    is_new = True

            match_data = dict(match_id=match_id, player_won=player_won, player_hero=player_hero, kills=kills, deaths=deaths,
                              assists=assists, party_size=party_size, start_time=start_time, game_mode=game_mode, is_new=is_new)
            last_matches_map[listed_player.nick] = match_data

    json.dump(last_matches_map, open(last_matches_map_file_path_temp, "w"), indent=4)

    if is_initial_run:
        json.dump(last_matches_map, open(last_matches_map_file_path, "w"), indent=4)

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
    start_date = datetime.now() - timedelta(days=2 * 365)
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
    for match_record in reversed(match_map[:known_mmr_idx + 1]):
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


def update_player_match_history(player, recent_matches, previous_match_history, common_history_point):
    # Update older matches in match history if recentMatches has more
    update_flag = False
    logging.info(f"Checking for new data for player history of player {player.nick}")
    for idx, history_match in enumerate(previous_match_history[common_history_point:20]):
        matching_recent_match = recent_matches[idx + common_history_point]
        if matching_recent_match['match_id'] != history_match['match_id']:
            logging.error(f"Mismatch between match ID order of history and recent matches, idx {idx},"
                          f" history match ID {history_match['match_id']},"
                          f" recent match ID {matching_recent_match['match_id']}.")
            break

        if len(history_match) <= len(matching_recent_match) and matching_recent_match['version'] \
                and matching_recent_match['version'] != "requested" and history_match != matching_recent_match:

            previous_match_history[idx + common_history_point] = matching_recent_match
            logging.info(f"Extended info for match ID {history_match['match_id']} based on data from "
                         f"recentMatches.")
            update_flag = True

    def get_match_data_from_recent_matches(match_id, recent_matches):
        for match in recent_matches:
            if match['match_id'] == match_id:
                return match
        return None

    request_count = 0
    for item in previous_match_history:
        if item['version'] == 'requested':
            recent_match = get_match_data_from_recent_matches(item['match_id'], recent_matches)
            if recent_match and recent_match['version'] and recent_match['version'] != 'requested':
                item['version'] = recent_match['version']

        if not item['version']:
            logging.info(f"Requesting match {item['match_id']} to be parsed for player {player.nick}.")
            item['version'] = 'requested'
            request_match_parse(item['match_id'])
            request_count += 1

    logging.info(f"Request count: {request_count}, common_history_point: {common_history_point} for player {player.nick}")

    if update_flag or request_count or common_history_point:
        logging.info(f"Saving extended matchHistory for player {player.nick}.")
        save_player_match_history(player, previous_match_history)


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
        logging.info(f"Comparing {player_recent_matches_path} and {player_recent_matches_path_archive}.")
        check = filecmp.cmp(player_recent_matches_path, player_recent_matches_path_archive)
        if check:
            logging.info(f"Match history for player {player} identical, removing the copy.")
            os.remove(player_recent_matches_path_archive)
        else:
            logging.info(f"Match history for player {player} differed, keeping a copy.")


def get_match_history_difference(player, recent_matches, previous_match_history, match_id_to_match_listing):
    common_history_point = 0
    for idx, match in enumerate(recent_matches):
        if match['match_id'] == previous_match_history[0]['match_id']:
            common_history_point = idx

    # If common history point is 0, there are no new matches
    if common_history_point:
        new_matches = [x['match_id'] for x in recent_matches[:common_history_point]]

        for match in recent_matches[:common_history_point]:
            if match['match_id'] not in match_id_to_match_listing:
                match_id_to_match_listing[match['match_id']] = MatchListing(player, match)
            else:
                match_id_to_match_listing[match['match_id']].add_match(player, match)

        logging.info(f"Found the sync between history and new recent matches, it is match with ID: "
                     f"{recent_matches[common_history_point]['match_id']}")
        logging.info(f"New matches are: {new_matches}")

        for item in recent_matches[:common_history_point]:
            logging.info(f"Adding match with ID: {item['match_id']} to matchHistory of player {player}.")
            previous_match_history.insert(0, item)

    return match_id_to_match_listing, common_history_point


class MatchListing:
    """Holds information about a match in format that allows easy printing out.
    All the involved tracked players and their respective match data."""

    def __init__(self, player, player_match_data):
        self.is_vintage_party = False
        self.players = [player]
        self.player_match_data = [player_match_data]

    def add_match(self, player, player_match_data):
        self.is_vintage_party = True
        self.players.append(player)
        self.player_match_data.append(player_match_data)

    def get_common_data(self):
        return self.player_match_data[0]

    def print_listing(self):
        listing_string = ""

        if self.is_vintage_party:
            players_involved = self.players
            player_match_data = self.player_match_data

            match_generic = player_match_data[0]
            player_string = f"{get_random_positive_phrase(0.7).capitalize()}"
            player_string += f", {get_random_positive_phrase(0.7)}".join([f"**{player.nick}**" for player in players_involved[:-1]])
            player_string += f" and {get_random_positive_phrase(0.7)}**{players_involved[-1].nick}**"
            player_string.capitalize()
            game_mode_string = GAME_MODES.get(str(match_generic['game_mode']), "Unknown Mode")

            ownage_total = 0.0
            for match in player_match_data:
                ownage_total += (match['kills'] + match['assists'])/(match['deaths'] or 0.5)
            ownage_rating = ownage_total / len(players_involved)

            result_string = 'WON' if check_victory(match_generic) else 'LOST'
            logging.info(f"ownage_rating: {ownage_rating}")
            if check_victory(match_generic):
                result_string = 'WON'
                if 5.0 <= ownage_rating < 7.5:
                    result_string = 'OWNED'
                elif 7.5 <= ownage_rating < 10.0:
                    result_string = 'TOTALLY OWNED'
                elif ownage_rating >= 10:
                    result_string = 'ABSOLUTELY STOMPED'
            time_played = datetime.fromtimestamp(match_generic['start_time'])
            minutes_ago = int((datetime.now() - time_played).total_seconds() / 60)
            game_duration = int(match_generic['duration']/60)
            time_ago_string = '{} minutes ago'.format(minutes_ago) if minutes_ago < 120 else timeago.format(time_played,
                                                                                                            datetime.now())
            print(f"------------------------------------------\n"
                  f"{player_string} played a {game_mode_string} game **together** and **{result_string}**.")
            for idx, player in enumerate(self.players):
                match = self.player_match_data[idx]
                player_hero = get_hero_name(match['hero_id'])
                print(f"**{player.nick}** played **{player_hero}** and went **{match['kills']}-{match['deaths']}-{match['assists']}**.")
            print(f"The game started {time_ago_string} and lasted {game_duration:.0f} minutes."
                  f"\nLink: <https://www.stratz.com/matches/{match_generic['match_id']}>")
        else:
            player = self.players[0]
            match = self.player_match_data[0]
            ownage_rating = (match['kills'] + match['assists'])/match['deaths']
            game_mode_string = GAME_MODES.get(str(match['game_mode']), "Unknown Mode")
            result_string = 'WON' if check_victory(match) else 'LOST'
            if result_string == 'WON' and ownage_rating > 4.0:
                result_string = 'TOTALLY OWNED'
            time_played = datetime.fromtimestamp(match['start_time'])
            minutes_ago = int((datetime.now() - time_played).total_seconds() / 60)
            player_hero = get_hero_name(match['hero_id'])
            game_duration = int(match['duration'] / 60)
            time_ago_string = '{} minutes ago'.format(minutes_ago) if minutes_ago < 120 else timeago.format(time_played,
                                                                                                            datetime.now())
            print(f"------------------------------------------\n"
                  f"{get_random_positive_phrase().capitalize()}**{player.nick}** played a {game_mode_string} game **solo** and *"
                  f"*{result_string}**.")
            print(f"**{player.nick}** played **{player_hero}** and went **{match['kills']}-{match['deaths']}-{match['assists']}**.")
            print(f"The game started {time_ago_string} and lasted {game_duration:.0f} minutes. Link: <https://www.stratz.com/matches/{match['match_id']}>")
        return listing_string


def get_random_positive_phrase(chance=0.50):
    random.seed()
    if random.random() > chance:
        return ""

    phrase_list = ["admirable", "amazing", "astonishing", "attractive", "awesome", "beautiful", "breathtaking", "brilliant", "cool",
                   "dazzling", "delightful", "elite", "epic", "esteemed", "excellent", "exceptional", "fabulous", "fearless", "fearsome",
                   "formidable", "glorious", "godlike", "gorgeous", "handsome", "illustrious", "imba", "incredible", "ingenious",
                   "inspiring", "leet", "magnificent", "marvelous", "mind-blowing", "miraculous", "ninja", "number one", "outstanding",
                   "overpowered", "pro gamer", "remarkable", "robot", "spectacular", "superb", "terrific", "too fucking good", "top-notch",
                   "totally radical", "very clutch", "wonderful", "wondrous", "exquisite", "dashing", "majestic", "sublime", "captivating",
                   "phenomenal", "unbelievable", "unbeatable", "supreme", "masterful", "astounding", "unrivaled", "impressive",
                   "awe-inspiring", "extraordinary", "unparalleled", "thrilling", "perfect player", "striking", "peerless", "unprecedented",
                   "legendary", "sensational", "absolute god", "madly skilled", "slayer", "insane"]
    phrase = random.choice(phrase_list)
    phrase += " "

    return phrase

