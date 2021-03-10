import argparse
from vintage_stats import player_pool

from vintage_stats.constants import FAZY_ID, GRUMPY_ID, KESKOO_ID, SHIFTY_ID, WARELIC_ID, \
    PATCH_ID_7_28A, PATCH_ID_7_28B, PATCH_ID_7_28C

from vintage_stats.data_processing import get_requests_count, get_stack_wl, get_hero_name
from vintage_stats.reports import generate_winrate_report, get_all_stacks_report

from vintage_stats.utility import get_last_monday

parser = argparse.ArgumentParser(
    description="""
TODO VINTAGE STATS DESC""",
    epilog="""Find more info and latest version on https://github.com/Ashen-Ashiok/vintage_stats""",
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("-wwr", "--week-win-report", help="Print this week (since last Monday) winrates and other stats for Vintage", action="store_true")
parser.add_argument("-examples", "--testing-examples", help="EXAMPLES LOL", action="store_true")
args = parser.parse_args()

vintage_player_map = [{'pid': FAZY_ID, 'nick': 'Fazy'},
                      {'pid': GRUMPY_ID, 'nick': 'Grumpy'},
                      {'pid': KESKOO_ID, 'nick': 'Keskoo'},
                      {'pid': SHIFTY_ID, 'nick': 'Shifty'},
                      {'pid': WARELIC_ID, 'nick': 'Warelic'}]

vintage = player_pool.PlayerPool(vintage_player_map)

if args.week_win_report:
    hero_count_threshold = 2
    last_week_winrate_report = generate_winrate_report(vintage, patch=PATCH_ID_7_28C, threshold=hero_count_threshold,
                                                       _cutoff_date=get_last_monday())

    print('Solo/party winrate report of last monday ranked')
    print('Nickname\tSolo W\tSolo L\tParty W\tParty L\tSolo %'
          '\tBest hero\tHeroes played\tHeroes played X+ times\tHPX+ wins\tHPX+ losses\t Threshold {}'.format(hero_count_threshold))
    for player_report in last_week_winrate_report:
        try:
            solo_percentage = player_report['solo'].get_count() / player_report['total'].get_count()
        except ZeroDivisionError:
            solo_percentage = 1
        print('{}\t{}\t{}\t{}\t{}\t{:.2f}%\t{} ({}–{}, {:.2f})\t{}\t{}\t{}\t{}'.format(
            player_report['nick'], player_report['solo'].wins, player_report['solo'].losses,
            player_report['party'].wins, player_report['party'].losses, solo_percentage,
            get_hero_name(player_report['best_hero_id']), player_report['best_hero_record'].wins, player_report['best_hero_record'].losses,
            player_report['best_hero_record'].get_winrate(), player_report['hero_count'], player_report['hero_count_more'],
            player_report['hero_more_record'].wins, player_report['hero_more_record'].losses)
        )
exit()
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

print('Requests used: {}'.format(get_requests_count()))
