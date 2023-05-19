import argparse
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import timeago

import vintage_stats.player
from vintage_stats.constants import SAUCE_ID, FAZY_ID, GRUMPY_ID, GWEN_ID, KESKOO_ID, SHIFTY_ID, SHOTTY_ID, TIARIN_ID, \
    WARELIC_ID, GAME_MODES
from vintage_stats.data_processing import get_stack_wl, get_last_matches_map, log_requests_count, \
    format_and_print_winrate_report, request_match_parse, get_mmr_history_table, get_player_match_history, CacheHandler, \
    get_hero_name, \
    save_player_match_history, handle_recent_matches_file, check_victory
from vintage_stats.reports import generate_winrate_report, get_all_stacks_report, get_player_activity_report, \
    generate_last_week_report
from vintage_stats.utility import get_last_monday

# region args
parser = argparse.ArgumentParser(description='TODO VINTAGE STATS DESC',
                                 epilog='Find more info and latest version on https://github.com/Ashen-Ashiok/vintage_stats')

parser.add_argument("--HCT", help="How many best/worst heroes to show in hero report. Default is 3.", default='3',
                    type=int)
parser.add_argument("--HT", help="Threshold for a very played hero. Default is 2.", default='2', type=int)
parser.add_argument("--date-from", help="Sets cutoff date from for custom report. Default is 28 days ago.",
                    default='28d')
parser.add_argument("--date-to", help="Sets cutoff date to for custom report. Default is now.", default='now')
parser.add_argument("-activity", "--activity-report", help="Print games per week in last 6 months or more",
                    action="store_true")
parser.add_argument("-monitor", "--monitor", help="")
parser.add_argument("-monrep", "--since-monday-report", help="Print this week (since last Monday) report for Vintage",
                    action="store_true")
parser.add_argument("-report", "--custom-report", help="Print a custom report for Vintage", action="store_true")
parser.add_argument("-stacks", "--stack-reports", help="Print all duo and trio stack reports", action="store_true")
parser.add_argument("-w", "--simple_last_week", action="store_true")
parser.add_argument("-t", "--monitor_updated", action="store_true")

args = parser.parse_args()
# endregion args

vintage_player_map = [
    {'pid': FAZY_ID, 'nick': 'Fazy'},
    {'pid': GRUMPY_ID, 'nick': 'Grumpy'},
    {'pid': GWEN_ID, 'nick': 'Gwen'},
    {'pid': KESKOO_ID, 'nick': 'Keskoo'},
    {'pid': SHIFTY_ID, 'nick': 'Shifty'},
    {'pid': SHOTTY_ID, 'nick': 'Shotty'},
    {'pid': TIARIN_ID, 'nick': 'TiarinHino'},
    {'pid': WARELIC_ID, 'nick': 'Warelic'},
]

vintage_test_player_map = [
    {'pid': FAZY_ID, 'nick': 'Fazy'},
    {'pid': GWEN_ID, 'nick': 'Gwen'},
    {'pid': KESKOO_ID, 'nick': 'Keskoo'},
    {'pid': SHIFTY_ID, 'nick': 'Shifty'},
    {'pid': SHOTTY_ID, 'nick': 'Shotty'},
    {'pid': TIARIN_ID, 'nick': 'TiarinHino'},
    {'pid': WARELIC_ID, 'nick': 'Warelic'},
]

vintage = vintage_stats.player.PlayerPool(vintage_player_map)
vintage_test = vintage_stats.player.PlayerPool(vintage_test_player_map)
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


def main():
    if args.monitor_updated:
        total_new_matches = 0
        matches_to_post = []

        for player in vintage_test:
            # region get recent matches
            logging.info(f"Getting recentMatches for player {player.nick} from API.")
            response_str = f"https://api.opendota.com/api/players/{player.player_id}/recentMatches"
            try:
                recent_matches = CacheHandler.opendota_request_get(response_str).json()
            except Exception as e:
                logging.error(f"Could not get recentMatches for player {player.nick}, skipping in this cycle, error: {e}.")
                continue

            if not recent_matches:
                logging.error(f"Could not get recentMatches for player {player.nick}, skipping in this cycle, error: {e}.")
                continue

            handle_recent_matches_file(recent_matches, player)
            logging.info(f"Finished getting recentMatches, length: {len(recent_matches)} for player {player.nick}.")
            # endregion

            logging.info(f"Getting matchHistory for player {player.nick}.")
            match_history = get_player_match_history(player)
            logging.info(f"Finished getting matchHistory for player {player.nick}, length: {len(match_history)}.")

            common_history_point = 0
            for idx, match in enumerate(recent_matches):
                if match['match_id'] == match_history[0]['match_id']:
                    common_history_point = idx

            # If common history point is 0, there are no new matches
            if common_history_point:
                new_matches = [x['match_id'] for x in recent_matches[:common_history_point]]

                for match in recent_matches[:common_history_point]:
                    if match['version'] and match['version'] != 'requested':
                        matches_to_post.append([True, player, match])
                    else:
                        matches_to_post.append([True, player, match])

                total_new_matches += len(new_matches)
                logging.info(f"Found the sync between history and new recent matches, it is match with ID: "
                             f"{recent_matches[common_history_point]['match_id']}")
                logging.info(f"New matches are: {new_matches}")

                for item in recent_matches[:common_history_point]:
                    logging.info(f"Adding match with ID: {item['match_id']} to matchHistory of player {player}.")
                    match_history.insert(0, item)

            # Update older matches in match history if recentMatches has more
            update_flag = False
            logging.info(f"Checking for new data for player history of player {player.nick}")
            for idx, history_match in enumerate(match_history[common_history_point:20]):
                matching_recent_match = recent_matches[idx+common_history_point]
                if matching_recent_match['match_id'] != history_match['match_id']:
                    logging.error(f"Mismatch between match ID order of history and recent matches, idx {idx},"
                                  f" history match ID {history_match['match_id']},"
                                  f" recent match ID {matching_recent_match['match_id']}.")
                    break

                if len(history_match) <= len(matching_recent_match) and matching_recent_match['version'] \
                        and matching_recent_match['version'] != "requested" and history_match != matching_recent_match:

                    if history_match['version'] == 'requested' or not history_match['version']:
                        matches_to_post.append([True, player, matching_recent_match])

                    match_history[idx+common_history_point] = matching_recent_match
                    logging.info(f"Extended info for match ID {history_match['match_id']} based on data from "
                                 f"recentMatches.")
                    update_flag = True
            logging.info(f"\nRequesting matches to be parsed for player {player.nick}.")

            def get_match_data_from_recent_matches(match_id, recent_matches):
                for match in recent_matches:
                    if match['match_id'] == match_id:
                        return match
                return None

            request_count = 0
            for item in match_history:
                if item['version'] == 'requested':
                    recent_match = get_match_data_from_recent_matches(item['match_id'], recent_matches)
                    if recent_match and recent_match['version'] and recent_match['version'] != 'requested':
                        item['version'] = recent_match['version']

                if not item['version']:
                    item['version'] = 'requested'
                    request_match_parse(item['match_id'])
                    request_count += 1

            logging.info(f"Request count: {request_count}, common_history_point: {common_history_point} for player {player.nick}")

            if update_flag or request_count or common_history_point:
                logging.info(f"Saving extended matchHistory for player {player.nick}.")
                save_player_match_history(player, match_history)

        # iterate through recentMatches matchID list, compare to the newest match in MatchHistory
        # when you find it, take any newer matches and append them to MatchHistory and:
        # check if they are parsed:
        #   NOT PARSED - send parse request, don't add to ToBePostedMatchGroup
        #   ARE PARSED - extract player specific info (hero, KDA, STREAK, that byz) and add it to ToBePostedMatchGroup
        # every match in MatchHistory is either parsed or we sent a request, never a duplicate request
        # PART 2
        # after you are done with every player, save MatchHistory to file, keep a few old copies (10 maybe)
        # if ToBePostedMatchGroup contains at least one object:
        # figure out if multiple players were in the same match
        # create postings, send to bot
        # log request count
        new_matches_string = "no new matches."
        if total_new_matches:
            new_matches_string = f"found {total_new_matches} new matches!"

        for match_listing in matches_to_post:
            is_parsed = match_listing[0]
            player = match_listing[1]
            match = match_listing[2]
            solo_string = 'party ' if match.party_size > 1 else 'solo '
            game_mode_string = GAME_MODES.get(str(match.game_mode), "Unknown Mode")
            player_hero = get_hero_name(match['hero_id'])
            time_played = datetime.fromtimestamp(match_data['start_time'])
            minutes_ago = int((datetime.now() - time_played).total_seconds() / 60)

            time_ago_string = '{} minutes ago'.format(minutes_ago) if minutes_ago < 120 else timeago.format(time_played,
                                                                                                datetime.now())
            # Post matches that are new and parsed
            if is_parsed:
                result_string = 'WON' if check_victory(match) else 'LOST'
                print(f"**{player.nick}** played a {solo_string}{game_mode_string} game as **{player_hero}**, "
              f"went {match['kills']}-{match['deaths']}-{match['assists']} and **{result_string}**."
              f" The game started {time_ago_string}. Links:\n"
              f"<https://www.stratz.com/matches/{match['match_id']}>,"
              f" <https://www.opendota.com/matches/{match['match_id']}>")      
            else:
                print(f"Detected a new match {match['match_id']} for player {player.nick} but it is not parsed yet.")

        logging.info(f"Monitor run finished, {new_matches_string}")

    if args.monitor:
        post_only_new = True
        if args.monitor == 'all':
            post_only_new = False
        if args.monitor == 'new':
            post_only_new = True

        last_matches_map = get_last_matches_map(vintage)

        set_for_parse = set()

        for player in last_matches_map:
            match_data = last_matches_map[player]
            if match_data.is_new:
                set_for_parse.add(match_data.match_ID)

        for match_id in set_for_parse:
            request_match_parse(match_id).json()

        for player in last_matches_map:
            match_data = last_matches_map[player]
            result_string = 'WON' if match_data.player_won else 'LOST'
            try:
                solo_string = 'party ' if match_data.party_size > 1 else 'solo '
            except TypeError:
                solo_string = ''
            time_played = datetime.fromtimestamp(match_data.start_time)
            game_mode_string = GAME_MODES.get(str(match_data.game_mode), "Unknown Mode")
            minutes_ago = int((datetime.now() - time_played).total_seconds() / 60)
            time_ago_string = '{} minutes ago'.format(minutes_ago) if minutes_ago < 120 else timeago.format(time_played,
                                                                                                            datetime.now())
            if not match_data.is_new and post_only_new:
                continue

            print(f'**{player}** played a {solo_string}{game_mode_string} game as **{match_data.hero_name}**, '
                  f'went {match_data.kills}-{match_data.deaths}-{match_data.assists} and **{result_string}**.'
                  f' The game started {time_ago_string}. Links:\n'
                  f'<https://www.stratz.com/matches/{match_data.match_ID}>,'
                  f' <https://www.opendota.com/matches/{match_data.match_ID}>')

    # region archived
    if args.simple_last_week:
        last_week_simple_report = generate_last_week_report(vintage)
        for player in last_week_simple_report:
            if player['total'].get_count() == 0:
                continue
            print(f"**{player['nick']}** played {player['total'].get_count()} games and went **{player['total']}**.\n"
                  f"{player['solo'].get_count()} were solo games while {player['party'].get_count()} were party games.")

    if args.since_monday_report:
        hero_count_threshold = 2
        best_heroes_threshold = 1
        date_from = get_last_monday()
        date_to = datetime.now()
        last_week_winrate_report = generate_winrate_report(vintage, hero_count_threshold=hero_count_threshold,
                                                           _cutoff_date_from=date_from, _cutoff_date_to=date_to)

        format_and_print_winrate_report(last_week_winrate_report, hero_count_threshold, best_heroes_threshold)

    if args.custom_report:
        # Amount of games needed on a hero for it to show up in the Winrate (X+ games) column
        player_heroes_threshold = args.HT
        # Amount of heroes to show in the best/worst heroes column
        best_worst_heroes_count = args.HCT
        # Amount of games needed on a hero for it to show up in the best/worst heroes column (there is also win/loss difference condition though)
        games_for_hero_report = 2

        print(
            f'played_heroes_threshold:{player_heroes_threshold}, best_worst_heroes_count: {best_worst_heroes_count}, games_for_hero_report: {games_for_hero_report}')
        date_from = datetime.now() - timedelta(days=28)
        date_to = datetime.now()
        if args.date_to != 'now':
            date_to = datetime.fromisoformat(args.date_to)
        if args.date_from != '28d':
            date_from = datetime.fromisoformat(args.date_from)

        last_week_winrate_report = generate_winrate_report(vintage, hero_count_threshold=player_heroes_threshold,
                                                           _cutoff_date_from=date_from, _cutoff_date_to=date_to)

        print("Printing Vintage winrate report for time period from {} to {}, hero threshold set to {}.".format(
            date_from.strftime('%d-%b-%y'), date_to.strftime('%d-%b-%y'), player_heroes_threshold))

        format_and_print_winrate_report(last_week_winrate_report, player_heroes_threshold, games_for_hero_report,
                                        best_worst_heroes_count)

    if args.stack_reports:
        date_from = datetime.now() - timedelta(days=28)
        date_to = datetime.now()
        if args.date_to != 'now':
            date_to = datetime.fromisoformat(args.date_to)
        if args.date_from != '28d':
            date_from = datetime.fromisoformat(args.date_from)

        all_duo_stacks_report = get_all_stacks_report(vintage, 2, exclusive=True, _cutoff_date_from=date_from,
                                                      _cutoff_date_to=date_to)
        all_triple_stacks_report = get_all_stacks_report(vintage, 3, exclusive=True, _cutoff_date_from=date_from,
                                                         _cutoff_date_to=date_to)

        for stack in (all_duo_stacks_report + all_triple_stacks_report):
            print(f'{stack["stack_name"]}\t{stack["stack_record"].wins}\t{stack["stack_record"].losses}')

    if args.activity_report:
        date_from = datetime.fromisoformat('2019-01-03')
        date_to = datetime.now()
        get_player_activity_report(vintage, date_from, date_to)
    # endregion archived
    log_requests_count()


if __name__ == '__main__':
    main()
