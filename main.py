import argparse
import logging
from datetime import datetime, timedelta
import timeago

import vintage_stats.player
from vintage_stats.constants import SAUCE_ID, FAZY_ID, GRUMPY_ID, GWEN_ID, KESKOO_ID, SHIFTY_ID, SHOTTY_ID, TIARIN_ID, \
    WARELIC_ID, GAME_MODES
from vintage_stats.data_processing import get_stack_wl, get_last_matches_map, log_requests_count, \
    format_and_print_winrate_report, request_match_parse, get_mmr_history_table
from vintage_stats.reports import generate_winrate_report, get_all_stacks_report, get_player_activity_report, \
    generate_last_week_report
from vintage_stats.utility import get_last_monday

parser = argparse.ArgumentParser(description='TODO VINTAGE STATS DESC',
                                 epilog='Find more info and latest version on https://github.com/Ashen-Ashiok/vintage_stats')

parser.add_argument("-monrep", "--since-monday-report", help="Print this week (since last Monday) winrates and other stats for Vintage",
                    action="store_true")

parser.add_argument("-report", "--custom-report", help="Print previous month (TODO) winrates and other stats for Vintage",
                    action="store_true")

parser.add_argument("-monitor", "--monitor", help="")

parser.add_argument("-w", "--simple_last_week", action="store_true")

parser.add_argument("--date-from", help="Sets cutoff date from for custom report. Default is 28 days ago.", default='28d')

parser.add_argument("--date-to", help="Sets cutoff date to for custom report. Default is now.", default='now')

parser.add_argument("--HT", help="Threshold for a very played hero. Default is 2.", default='2', type=int)

parser.add_argument("--HCT", help="How many best/worst heroes to show in hero report. Default is 3.", default='3', type=int)

parser.add_argument("-stacks", "--stack-reports", help="Print all duo and trio stack reports", action="store_true")

parser.add_argument("-activity", "--activity-report", help="Print games per week in last 6 months or more", action="store_true")

args = parser.parse_args()

vintage_player_map = [  
                        {'pid': SAUCE_ID, 'nick': 'Sauce'},
                        {'pid': FAZY_ID, 'nick': 'Fazy'},
                        {'pid': GRUMPY_ID, 'nick': 'Grumpy'},
                        {'pid': GWEN_ID, 'nick': 'Gwen'},
                        {'pid': KESKOO_ID, 'nick': 'Keskoo'},
                        {'pid': SHIFTY_ID, 'nick': 'Shifty'},
                        {'pid': SHOTTY_ID, 'nick': 'Shotty'},
                        {'pid': TIARIN_ID, 'nick': 'TiarinHino'},
                        {'pid': WARELIC_ID, 'nick': 'Warelic'},
                    ]

vintage = vintage_stats.player.PlayerPool(vintage_player_map)

#vintage.get_player('Fazy').set_known_mmr_point(6254246860, 5774)
#vintage.get_player('Grumpy').set_known_mmr_point(6255488353, 3900)
#vintage.get_player('Keskoo').set_known_mmr_point(6254967232, 2870)
#vintage.get_player('Shifty').set_known_mmr_point(6188018367, 4380)
#vintage.get_player('Warelic').set_known_mmr_point(6254551215, 3200)

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

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
        result_string = 'WON' if match_data.player_won else 'LOST'
        try:
            solo_string = 'party' if match_data.party_size > 1 else 'solo'
        except TypeError:
            solo_string = 'solo'
        time_played = datetime.fromtimestamp(match_data.start_time)
        time_string = time_played.strftime('%a %H:%M')
        print(match_data.game_mode)
        game_mode_string = GAME_MODES.get(str(match_data.game_mode), "Unknown Mode")
        minutes_ago = int((datetime.now() - time_played).total_seconds() / 60)
        time_ago_string = '{} minutes ago'.format(minutes_ago) if minutes_ago < 120 else timeago.format(time_played,
                                                                                                        datetime.now())
        if not match_data.is_new and post_only_new:
            continue       
        print(f'**{player}** played a {solo_string} {game_mode_string} game as **{match_data.hero_name}**, '
              f'went {match_data.kills}-{match_data.deaths}-{match_data.assists} and **{result_string}**.'
              f' The game started {time_ago_string}. Links:\n'
              f'<https://www.stratz.com/matches/{match_data.match_ID}>,'
              f' <https://www.opendota.com/matches/{match_data.match_ID}>')
        set_for_parse.add(match_data.match_ID)

    for match_id in set_for_parse:
        request_match_parse(match_id).json()

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

log_requests_count()
