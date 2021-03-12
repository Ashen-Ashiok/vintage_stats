import itertools
import logging
from datetime import datetime

from vintage_stats.constants import *
from vintage_stats.data_processing import cached_opendota_request, check_victory, get_stack_wl
from vintage_stats.utility import WLRecord
from vintage_stats.utility import get_patch_release_time


def generate_winrate_report(players_list, patch=PATCH_ID_7_28A, threshold=0, _cutoff_date_from=None, _cutoff_date_to=None):
    full_report = []
    cutoff_date_from = get_patch_release_time(patch)
    cutoff_date_to = datetime.now()

    if _cutoff_date_from is not None:
        cutoff_date_from = _cutoff_date_from

    if _cutoff_date_to is not None:
        cutoff_date_to = _cutoff_date_to

    seconds_since_cutoff = (datetime.now() - cutoff_date_from).total_seconds()
    days_since_cutoff = int(seconds_since_cutoff / 86400)
    logging.debug('Detected patch with date {}, days ago: {}'.format(cutoff_date_from, days_since_cutoff))

    for listed_player in players_list:
        response_str = 'https://api.opendota.com/api/players/{}/matches?lobby_type=7&date={}'.format(
            listed_player.player_id, days_since_cutoff)

        matches_response = cached_opendota_request(response_str)

        solo_wins = solo_losses = party_wins = party_losses = 0
        hero_pool = {}
        for match in matches_response.json():
            match_datetime = datetime.fromtimestamp(match['start_time'])

            if match_datetime < cutoff_date_from or match_datetime > cutoff_date_to:
                continue
            player_won = check_victory(match)
            if match['hero_id'] not in hero_pool:
                if player_won:
                    hero_pool[match['hero_id']] = WLRecord(1, 0)
                else:
                    hero_pool[match['hero_id']] = WLRecord(0, 1)
            else:
                hero_pool[match['hero_id']].add_match(player_won)

            if player_won:
                if not match['party_size']:
                    solo_wins = solo_wins + 1
                else:
                    if int(match['party_size']) > 1:
                        party_wins = party_wins + 1
                    else:
                        solo_wins = solo_wins + 1
            else:
                if not match['party_size']:
                    solo_losses = solo_losses + 1
                else:
                    if int(match['party_size']) > 1:
                        party_losses = party_losses + 1
                    else:
                        solo_losses = solo_losses + 1

        solo_record = WLRecord(solo_wins, solo_losses)
        party_record = WLRecord(party_wins, party_losses)

        hero_count_once = 0
        hero_count_more = 0
        hero_more_total_record = WLRecord(0, 0)

        best_heroes_list = []
        for hero in hero_pool:
            hero_id_record_tuple = (hero, hero_pool[hero])
            best_heroes_list.append(hero_id_record_tuple)

        best_heroes_list.sort(key=lambda x: x[1].get_record_goodness(), reverse=True)

        for hero in hero_pool:
            if hero_pool[hero]:
                hero_count_once = hero_count_once + 1
            if hero_pool[hero].get_count() > threshold:
                hero_count_more = hero_count_more + 1
                hero_more_total_record += hero_pool[hero]

        player_record = {'nick': listed_player.nick,
                         'total': solo_record + party_record,
                         'solo': solo_record,
                         'party': party_record,
                         'hero_count': hero_count_once,
                         'hero_count_more': hero_count_more,
                         'hero_more_record': hero_more_total_record,
                         'best_heroes': best_heroes_list
                         }
        full_report.append(player_record)

    return full_report


def get_all_stacks_report(player_pool, player_count=2, exclusive=False, patch=PATCH_ID_7_28B):
    all_possible_stacks = itertools.combinations(player_pool.get_player_list(), player_count)

    full_report = []
    for stack in all_possible_stacks:
        stack_record = get_stack_wl(stack, exclusive, player_pool, patch)
        sorted_stack_nicknames = sorted(player.nick for player in stack)
        stack_name = ''
        for index, nick in enumerate(sorted_stack_nicknames):
            if index == 0:
                stack_name += nick
            else:
                stack_name += ', ' + nick
        full_report.append({"stack_name": stack_name, "stack_record": stack_record})
    return full_report
