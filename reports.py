from constants import *
from data_processing import cached_opendota_request, check_victory
import logging
from player import WLRecord


def generate_winrate_report(players_list, patch=PATCH_ID_7_28B, threshold=5):
    full_report = []
    for listed_player in players_list:
        cutoff_date = get_patch_release_time(patch)
        seconds_since_cutoff = (datetime.now() - cutoff_date).total_seconds()
        days_since_cutoff = int(seconds_since_cutoff/86400)
        logging.debug('Detected patch with date {}, days ago: {}'.format(cutoff_date, days_since_cutoff))

        response_str = 'https://api.opendota.com/api/players/{}/matches?lobby_type=7&date={}'.format(listed_player.player_id, days_since_cutoff)

        matches_response = cached_opendota_request(response_str)

        solo_wins = solo_losses = party_wins = party_losses = 0
        hero_pool = []
        for match in matches_response.json():
            match_datetime = datetime.fromtimestamp(match['start_time'])

            if match_datetime < cutoff_date:
                continue
            player_won = check_victory(match)
            if match['hero_id'] not in hero_pool:
                hero_pool.append(match['hero_id'])

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

        player_record = {'nick': listed_player.nick,
                         'total': solo_record + party_record,
                         'solo': solo_record,
                         'party': party_record,
                         'hero_count': len(hero_pool)
                         }
        full_report.append(player_record)

    return full_report
