import argparse
import logging
from datetime import datetime, timedelta
import timeago

from vintage_stats import player_pool
from vintage_stats.constants import FAZY_ID, GRUMPY_ID, KESKOO_ID, SHIFTY_ID, WARELIC_ID, \
    PATCH_ID_7_28B, PATCH_ID_7_28C
from vintage_stats.data_processing import get_stack_wl, get_last_matches_map, log_requests_count, \
    format_and_print_winrate_report
from vintage_stats.reports import generate_winrate_report, get_all_stacks_report
from vintage_stats.utility import get_last_monday

parser = argparse.ArgumentParser(description='TODO VINTAGE STATS DESC',
                                 epilog='Find more info and latest version on https://github.com/Ashen-Ashiok/vintage_stats')

parser.add_argument("-monrep", "--since-monday-report", help="Print this week (since last Monday) winrates and other stats for Vintage",
                    action="store_true")

parser.add_argument("-report", "--custom-report", help="Print previous month (TODO) winrates and other stats for Vintage", action="store_true")

parser.add_argument("-monitor", "--monitor", help="")

parser.add_argument("--date-from", help="Sets cutoff date from for custom report. Default is 28 days ago.", default='28d')

parser.add_argument("--date-to", help="Sets cutoff date to for custom report. Default is now.", default='now')

parser.add_argument("--hct", help="Hero count threshold for custom report. Default is 3.", default='3', type=int)

parser.add_argument("-examples", "--testing-examples", help="EXAMPLES LOL", action="store_true")
args = parser.parse_args()

vintage_player_map = [{'pid': FAZY_ID, 'nick': 'Fazy'},
                      {'pid': GRUMPY_ID, 'nick': 'Grumpy'},
                      {'pid': KESKOO_ID, 'nick': 'Keskoo'},
                      {'pid': SHIFTY_ID, 'nick': 'Shifty'},
                      {'pid': WARELIC_ID, 'nick': 'Warelic'}]

vintage = player_pool.PlayerPool(vintage_player_map)
logging.basicConfig()
logging.getLogger().setLevel(logging.ERROR)

if args.monitor:
    post_only_new = True
    if args.monitor == 'all':
        post_only_new = False
    if args.monitor == 'new':
        post_only_new = True
    last_matches_map = get_last_matches_map(vintage)

    for player in last_matches_map:
        match_data = last_matches_map[player]
        result_string = 'WON' if match_data.player_won else 'LOST'
        solo_string = 'party' if match_data.party_size > 1 else 'solo'
        time_played = datetime.fromtimestamp(match_data.start_time)
        time_string = time_played.strftime('%a %H:%M')
        minutes_ago = int((datetime.now() - time_played).total_seconds() / 60)
        time_ago_string = '{} minutes ago'.format(minutes_ago) if minutes_ago < 120 else timeago.format(time_played, datetime.now())
        if not match_data.is_new and post_only_new:
            continue
        new_string = '** NEW!**' if match_data.is_new else ''
        print('**{}** played {} game as **{}**, went {}-{}-{} and **{}**. The game started {}. Links:\n'
              '<https://www.stratz.com/matches/{}>, <https://www.opendota.com/matches/{}>'.format(
                player, solo_string, match_data.hero_name, match_data.kills,
                match_data.deaths, match_data.assists, result_string, time_ago_string,
                match_data.match_ID, match_data.match_ID))

if args.since_monday_report:
    hero_count_threshold = 2
    best_heroes_threshold = 3
    date_from = get_last_monday()
    date_to = datetime.now()
    last_week_winrate_report = generate_winrate_report(vintage, hero_count_threshold=hero_count_threshold,
                                                       _cutoff_date_from=date_from, _cutoff_date_to=date_to)

    format_and_print_winrate_report(last_week_winrate_report, hero_count_threshold, best_heroes_threshold)

if args.custom_report:
    best_heroes_threshold = args.hct
    date_from = datetime.now() - timedelta(days=28)
    date_to = datetime.now()
    if args.date_to != 'now':
        date_to = datetime.fromisoformat(args.date_to)
    if args.date_from != '28d':
        date_from = datetime.fromisoformat(args.date_from)

    last_week_winrate_report = generate_winrate_report(vintage, hero_count_threshold=best_heroes_threshold,
                                                       _cutoff_date_from=date_from, _cutoff_date_to=date_to)

    print("Printing Vintage winrate report for time period from {} to {}, hero threshold set to {}.".format(date_from.strftime('%d-%b-%y'), date_to.strftime(
        '%d-%b-%y'), best_heroes_threshold))
    format_and_print_winrate_report(last_week_winrate_report, best_heroes_threshold, best_heroes_threshold)

if args.testing_examples:
    all_duo_stacks_report = get_all_stacks_report(vintage, 2, True, _cutoff_date_from=datetime(2021, 2, 14, 0, 0, 0),
                                                  _cutoff_date_to=datetime(2021, 3, 14, 23, 59, 59))
    for stack in all_duo_stacks_report:
        print('{}\t{}'.format(stack['stack_name'], stack['stack_record']))
    exit()

    fazy_shifty_28b_stack_record = get_stack_wl((vintage.get_player('Fazy'),
                                                 vintage.get_player('Shifty')),
                                                exclusive=False, patch=PATCH_ID_7_28B)
    print(fazy_shifty_28b_stack_record)

    fazy_keskoo_28b_stack_record = get_stack_wl((vintage.get_player('Fazy'),
                                                 vintage.get_player('Keskoo')),
                                                exclusive=True, excluded_players=vintage, patch=PATCH_ID_7_28B)
    print(fazy_keskoo_28b_stack_record)
    all_triple_stacks_report = get_all_stacks_report(vintage, 3, True)

    for stack in (all_duo_stacks_report + all_triple_stacks_report):
        print('{} – {}'.format(stack['stack_name'], stack['stack_record']))

log_requests_count()
