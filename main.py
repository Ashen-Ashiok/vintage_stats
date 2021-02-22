from player_pool import PlayerPool

from constants import *
from data_processing import get_requests_count
from reports import generate_winrate_report

vintage_player_map = [{'pid': FAZY_ID, 'nick': 'Fazy'},
                      {'pid': GRUMPY_ID, 'nick': 'Grumpy'},
                      {'pid': KESKOO_ID, 'nick': 'Keskoo'},
                      {'pid': SHIFTY_ID, 'nick': 'Shifty'},
                      {'pid': WARELIC_ID, 'nick': 'Warelic'}]

vintage = PlayerPool(vintage_player_map)

# print(vintage.get_player('Fazy').profile_nickname)

for player in vintage:
    print(player)

basic_28b_winrate_report = generate_winrate_report(vintage)

print('Solo/party winrate report of 7.28b ranked')
print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}'.format('Nickname', 'TW', 'TL', 'SW', 'SL', 'PW', 'PL', 'S%', 'HP'))
for player_report in basic_28b_winrate_report:
    solo_percentage = player_report['solo'].get_count() / player_report['total'].get_count()
    hero_count = player_report['hero_count']
    print('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{:.2f}\t{}'.format(
        player_report['nick'], player_report['total'].wins, player_report['total'].losses,
        player_report['solo'].wins, player_report['solo'].losses, player_report['party'].wins, player_report['party'].losses,
        solo_percentage, hero_count)
    )

print('Requests used: {}'.format(get_requests_count()))
