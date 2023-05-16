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
    format_and_print_winrate_report, request_match_parse, get_mmr_history_table, get_player_match_history, CacheHandler, get_hero_name, \
    save_player_match_history
from vintage_stats.reports import generate_winrate_report, get_all_stacks_report, get_player_activity_report, \
    generate_last_week_report
from vintage_stats.utility import get_last_monday

# region args
parser = argparse.ArgumentParser(description='TODO VINTAGE STATS DESC',
                                 epilog='Find more info and latest version on https://github.com/Ashen-Ashiok/vintage_stats')

parser.add_argument("--HCT", help="How many best/worst heroes to show in hero report. Default is 3.", default='3', type=int)
parser.add_argument("--HT", help="Threshold for a very played hero. Default is 2.", default='2', type=int)
parser.add_argument("--date-from", help="Sets cutoff date from for custom report. Default is 28 days ago.", default='28d')
parser.add_argument("--date-to", help="Sets cutoff date to for custom report. Default is now.", default='now')
parser.add_argument("-activity", "--activity-report", help="Print games per week in last 6 months or more", action="store_true")
parser.add_argument("-monitor", "--monitor", help="")
parser.add_argument("-monrep", "--since-monday-report", help="Print this week (since last Monday) report for Vintage", action="store_true")
parser.add_argument("-report", "--custom-report", help="Print a custom report for Vintage", action="store_true")
parser.add_argument("-stacks", "--stack-reports", help="Print all duo and trio stack reports", action="store_true")
parser.add_argument("-w", "--simple_last_week", action="store_true")
parser.add_argument("-t", "--test", action="store_true")

args = parser.parse_args()
# endregion args

vintage_player_map = [  
                        {'pid': SAUCE_ID, 'nick': 'Boneal'},
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
    if args.test:
        match_history_dir_path = Path("match_histories")

        for player in vintage_test:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            player_recent_matches_path = match_history_dir_path / f"{player.player_id}_recent_{timestamp}.json"
            logging.info(f"Getting recentMatches for player {player}.")
            with player_recent_matches_path.open(mode="w", encoding="utf-8") as player_recent_matches_file:
                response_str = f"https://api.opendota.com/api/players/{player.player_id}/recentMatches"
                try:
                    recent_matches = CacheHandler.opendota_request_get(response_str).json()
                except Exception as e:
                    logging.error(f"Could not get recentMatches for player {player}, skipping in this cycle, error: {e}.")
                    continue

                if not recent_matches:
                    logging.error(f"Could not get recentMatches for player {player}, skipping in this cycle, error: {e}.")
                    continue

                logging.info(f"Saving recentMatches for player {player} to file {player_recent_matches_path}")
                json.dump(recent_matches, player_recent_matches_file, indent=4)

                logging.info(f"Getting matchHistory for player {player}.")
                match_history = get_player_match_history(player)

                # print("\nMATCH HISTORY (LOADED DATA)")
                for idx, match in enumerate(match_history):
                    print(f"{idx}: match_ID: {match['match_id']}, hero: {get_hero_name(match['hero_id'])}, is_parsed: "
                          f"{match['version']}")

                # print("\nNEWLY SCANNED RECENT MATCHES")
                meet_index = 0
                for idx, match in enumerate(recent_matches):
                    print(f"{idx}: match_ID: {match['match_id']}, hero: {get_hero_name(match['hero_id'])}, is_parsed: "
                          f"{match['version']}")
                    if match['match_id'] == match_history[0]['match_id']:
                        meet_index = idx

                new_matches = [x['match_id'] for x in recent_matches[:meet_index]]
                print(f"\nFound the sync between history and new recent matches, it is match with ID: "
                      f"{recent_matches[meet_index]['match_id']}\n"
                      f"New matches are: {new_matches}")

                for item in recent_matches[:meet_index]:
                    match_history.insert(0, item)

                for item in match_history:
                    if not item['version']:
                        item['version'] = 'requested'
                        request_match_parse(item['match_id'])

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
        return

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
            time_string = time_played.strftime('%a %H:%M')
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

        print(f'played_heroes_threshold:{player_heroes_threshold}, best_worst_heroes_count: {best_worst_heroes_count}, games_for_hero_report: {games_for_hero_report}')
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

        format_and_print_winrate_report(last_week_winrate_report, player_heroes_threshold, games_for_hero_report, best_worst_heroes_count)

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
