import player_pool

from constants import FAZY_ID, GRUMPY_ID, KESKOO_ID, SHIFTY_ID, WARELIC_ID, \
    PATCH_ID_7_28A, PATCH_ID_7_28B, PATCH_ID_7_28C

from data_processing import get_requests_count, get_stack_wl
from reports import generate_winrate_report, get_all_stacks_report

vintage_player_map = [{'pid': FAZY_ID, 'nick': 'Fazy'},
                      {'pid': GRUMPY_ID, 'nick': 'Grumpy'},
                      {'pid': KESKOO_ID, 'nick': 'Keskoo'},
                      {'pid': SHIFTY_ID, 'nick': 'Shifty'},
                      {'pid': WARELIC_ID, 'nick': 'Warelic'}]

vintage = player_pool.PlayerPool(vintage_player_map)

for player in vintage:
    print(player)

winrate_report_flag = False
if winrate_report_flag:
    hero_count_threshold = 3
    basic_28b_winrate_report = generate_winrate_report(vintage, threshold=hero_count_threshold)

    print('Solo/party winrate report of 7.28b ranked')
    print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}({}+)'.format('Nickname', 'TW', 'TL', 'SW', 'SL', 'PW', 'PL', 'S%', 'HP',
                                                           hero_count_threshold))
    for player_report in basic_28b_winrate_report:
        solo_percentage = player_report['solo'].get_count() / player_report['total'].get_count()
        hero_count = player_report['hero_count']
        print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{:.2f}\t{}'.format(
            player_report['nick'], player_report['total'].wins, player_report['total'].losses,
            player_report['solo'].wins, player_report['solo'].losses, player_report['party'].wins,
            player_report['party'].losses,
            solo_percentage, hero_count)
        )

# fazy_keskoo_28b_stack_record = get_stack_wl((vintage.get_player('Fazy'), vintage.get_player('Keskoo')), exclusive=True, excluded_players=vintage, patch=PATCH_ID_7_28B)
# print(fazy_keskoo_28b_stack_record)


all_duo_stacks_report = get_all_stacks_report(vintage, 2, True)
all_triple_stacks_report = get_all_stacks_report(vintage, 3, True)

for stack in (all_duo_stacks_report + all_triple_stacks_report):
    print('{} – {}'.format(stack['stack_name'], stack['stack_record']))

print('Requests used: {}'.format(get_requests_count()))
