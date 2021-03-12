import argparse
import logging
from datetime import datetime

from vintage_stats import player_pool
from vintage_stats.constants import FAZY_ID, GRUMPY_ID, KESKOO_ID, SHIFTY_ID, WARELIC_ID, \
    PATCH_ID_7_28B, PATCH_ID_7_28C
from vintage_stats.data_processing import get_requests_count, get_stack_wl, get_hero_name, get_last_matches_map, log_requests_count
from vintage_stats.reports import generate_winrate_report, get_all_stacks_report
from vintage_stats.utility import get_last_monday

parser = argparse.ArgumentParser(description='TODO VINTAGE STATS DESC',
                                 epilog='Find more info and latest version on https://github.com/Ashen-Ashiok/vintage_stats')

parser.add_argument("-wwr", "--week-win-report", help="Print this week (since last Monday) winrates and other stats for Vintage",
                    action="store_true")
parser.add_argument("-monitor", "--monitor", help="",
                    action="store_true")
parser.add_argument("-onlynew", "--only_new", help="",
                    action="store_true")
parser.add_argument("-mrep", "--monthly-report", help="Print previous month (TODO) winrates and other stats for Vintage",
                    action="store_true")
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
    last_matches_map = get_last_matches_map(vintage)
    post_only_new = False
    if args.only_new:
        post_only_new = True
    for player in last_matches_map:
        match_data = last_matches_map[player]
        result_string = 'WON' if match_data.player_won else 'LOST'
        solo_string = 'party' if match_data.party_size > 1 else 'solo'
        time_string = datetime.fromtimestamp(match_data.start_time).strftime('%a %dth %H:%M')
        if not match_data.is_new:
            continue
        new_string = 'NEW\t' if match_data.is_new else 'OLD\t'
        print('{}{} played {} game (ID {}) as {}, {}-{}-{} and {}. Played on {}'.format(new_string, player, solo_string, match_data.match_ID,
                                                                                        match_data.hero_name, match_data.kills,
                                                                                        match_data.deaths, match_data.assists,
                                                                                        result_string, time_string))

if args.week_win_report:
    hero_count_threshold = 2
    last_week_winrate_report = generate_winrate_report(vintage, patch=PATCH_ID_7_28C, threshold=hero_count_threshold,
                                                       _cutoff_date_from=get_last_monday())

    print('Solo/party winrate report of last monday ranked')
    print('Nickname\tSolo W\tSolo L\tParty W\tParty L\tSolo %'
          '\tBest hero\tHeroes played\tHeroes played X+ times\tHPX+ wins\tHPX+ losses\t Threshold {}'.format(hero_count_threshold))
    for player_report in last_week_winrate_report:
        try:
            solo_percentage = player_report['solo'].get_count() / player_report['total'].get_count() * 100
        except ZeroDivisionError:
            solo_percentage = 100
        best_heroes = player_report['best_heroes']
        best_heroes_string = 'No games played.'
        if best_heroes:
            best_heroes_string = '{} ({})'.format(get_hero_name(best_heroes[0][0]), best_heroes[0][1])

        print('{}\t{}\t{}\t{}\t{}\t{:.2f}%\t{}\t{}\t{}\t{}\t{}'.format(
            player_report['nick'], player_report['solo'].wins, player_report['solo'].losses,
            player_report['party'].wins, player_report['party'].losses, solo_percentage,
            best_heroes_string,
            player_report['hero_count'], player_report['hero_count_more'],
            player_report['hero_more_record'].wins, player_report['hero_more_record'].losses)
        )

if args.monthly_report:
    hero_count_threshold = 3
    last_week_winrate_report = generate_winrate_report(vintage, patch=PATCH_ID_7_28C, threshold=hero_count_threshold,
                                                       _cutoff_date_from=datetime(2021, 1, 1, 0, 0, 0),
                                                       _cutoff_date_to=datetime(2021, 2, 1, 0, 0, 0))

    print('Solo/party winrate report of the last full month, ranked')
    print('Nickname\tSolo W\tSolo L\tParty W\tParty L\tSolo %'
          '\tBest hero\tHeroes played\tHeroes played X+ times\tHPX+ wins\tHPX+ losses\t Threshold {}'.format(hero_count_threshold))
    for player_report in last_week_winrate_report:
        try:
            solo_percentage = player_report['solo'].get_count() / player_report['total'].get_count() * 100
        except ZeroDivisionError:
            solo_percentage = 100
        best_heroes = player_report['best_heroes']

        print('{}\t{}\t{}\t{}\t{}\t{:.2f}%\t{} ({}), {} ({}), {} ({})\t{}\t{}\t{}\t{}'.format(
            player_report['nick'], player_report['solo'].wins, player_report['solo'].losses,
            player_report['party'].wins, player_report['party'].losses, solo_percentage,
            get_hero_name(best_heroes[0][0]), best_heroes[0][1],
            get_hero_name(best_heroes[1][0]), best_heroes[1][1],
            get_hero_name(best_heroes[2][0]), best_heroes[2][1],
            player_report['hero_count'], player_report['hero_count_more'],
            player_report['hero_more_record'].wins, player_report['hero_more_record'].losses)
        )

if args.testing_examples:
    fazy_shifty_28b_stack_record = get_stack_wl((vintage.get_player('Fazy'),
                                                 vintage.get_player('Shifty')),
                                                exclusive=False, patch=PATCH_ID_7_28B)
    print(fazy_shifty_28b_stack_record)

    fazy_keskoo_28b_stack_record = get_stack_wl((vintage.get_player('Fazy'),
                                                 vintage.get_player('Keskoo')),
                                                exclusive=True, excluded_players=vintage, patch=PATCH_ID_7_28B)
    print(fazy_keskoo_28b_stack_record)

    all_duo_stacks_report = get_all_stacks_report(vintage, 2, True)
    all_triple_stacks_report = get_all_stacks_report(vintage, 3, True)

    for stack in (all_duo_stacks_report + all_triple_stacks_report):
        print('{} – {}'.format(stack['stack_name'], stack['stack_record']))

log_requests_count()
