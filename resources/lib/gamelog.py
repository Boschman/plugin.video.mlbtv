# Log watched favorite team games to a Google Sheet via a Google Apps Script web app
import threading

from resources.lib.globals import *


# build the display name for a schedule API game, with a suffix for doubleheader games
def game_display_name(game):
    away = game['teams']['away']['team']
    home = game['teams']['home']['team']
    name = away.get('teamName', away['name']) + ' @ ' + home.get('teamName', home['name'])
    if game.get('doubleHeader', 'N') != 'N':
        name += ' (Game ' + str(game['gameNumber']) + ')'
    return name


# build the sheet row data for a game, or None if it can't be determined
def game_log_data(epg_game, game_type):
    try:
        return {
            'date': epg_game['officialDate'],
            'game': game_display_name(epg_game),
            'type': game_type
        }
    except:
        xbmc.log('MLB game log: unable to build game data')
        return None


# fetch the most recently watched game (by game date) from the sheet
def get_latest_game_log():
    try:
        r = requests.get(GAME_LOG_URL, params={'latest': '1'}, timeout=5)
        return r.json().get('latest')
    except:
        xbmc.log('MLB game log: failed to fetch the latest game')
        return None


# convert seconds to a readable H:MM:SS position for the sheet
def seconds_to_position(seconds):
    return '%d:%02d:%02d' % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


# convert a H:MM:SS position from the sheet back to seconds
def position_to_seconds(position):
    seconds = 0
    try:
        for part in position.split(':'):
            seconds = seconds * 60 + int(part)
    except:
        seconds = 0
    return seconds


def post_game_log(data, status, position=None):
    payload = dict(data)
    payload['status'] = status
    if position is not None:
        payload['position'] = position
    try:
        requests.post(GAME_LOG_URL, json=payload, timeout=10)
        xbmc.log('MLB game log: ' + payload['game'] + ' ' + status)
    except:
        xbmc.log('MLB game log: failed to post to ' + GAME_LOG_URL)


# seconds of anti-spoiler padding appended to the stream, taken from the proxy querystring
def get_pad_seconds(stream_url):
    pad_match = re.search(r'[?&]pad=(\d+)', stream_url)
    if pad_match:
        return int(pad_match.group(1)) * SECONDS_PER_SEGMENT
    return 0


# fetch the favorite team schedule between two dates, skipping rescheduled games
def get_fav_schedule(start_date, end_date):
    url = f'{API_URL}/api/v1/schedule?sportId=1&teamId={getFavTeamId()}&startDate={start_date}&endDate={end_date}&hydrate=team'
    headers = {'User-Agent': UA_PC}
    r = requests.get(url, headers=headers, verify=VERIFY)
    games = []
    for date in r.json().get('dates', []):
        for game in date.get('games', []):
            if 'rescheduleDate' not in game:
                games.append(game)
    return games


# handle selecting the most recently watched game item on the home screen:
# resume an in progress game with its logged play option and position,
# or open the stream selection for the game after a finished one
def game_log_action(game_date, game, game_type, game_status, game_position):
    dialog = xbmcgui.Dialog()
    try:
        if game_status == 'in progress':
            direct_play = 'fav'
            if game_type == 'Condensed Game':
                direct_play = 'condensed'
            for schedule_game in get_fav_schedule(game_date, game_date):
                if game_display_name(schedule_game) == game:
                    play_game(schedule_game, direct_play, position_to_seconds(game_position))
                    return
            dialog.notification(LOCAL_STRING(30452), LOCAL_STRING(30453), ICON, 5000, False)
        else:
            # a doubleheader game number suffix determines where to continue on the same date
            game_number = 1
            number_match = re.search(r'\(Game (\d+)\)$', game)
            if number_match:
                game_number = int(number_match.group(1))
            end_date = (parse(game_date) + timedelta(days=45)).strftime('%Y-%m-%d')
            for schedule_game in get_fav_schedule(game_date, end_date):
                if schedule_game['officialDate'] > game_date or (schedule_game['officialDate'] == game_date and schedule_game.get('gameNumber', 1) > game_number):
                    # the next game hasn't started yet
                    if schedule_game['status']['abstractGameState'] == 'Preview':
                        dialog.notification(LOCAL_STRING(30452), LOCAL_STRING(30454), ICON, 5000, False)
                        return
                    play_game(schedule_game, 'select')
                    return
            dialog.notification(LOCAL_STRING(30452), LOCAL_STRING(30454), ICON, 5000, False)
    except:
        xbmc.log('MLB game log: game log action failed')
        dialog.notification(LOCAL_STRING(30452), LOCAL_STRING(30453), ICON, 5000, False)


# trigger playback for a schedule game: a direct play option or the stream selection dialog
def play_game(schedule_game, direct_play, start_seconds=0):
    name = game_display_name(schedule_game)
    u_params = '&game_pk=' + str(schedule_game['gamePk']) + '&name=' + urllib.quote_plus(name) + '&description=' + urllib.quote_plus(name)
    if direct_play == 'select':
        u = '?mode=103' + u_params
    else:
        u = '?mode=104' + u_params + '&direct_play=' + direct_play
        if start_seconds > 0:
            u += '&start_pos=' + str(start_seconds)
    xbmc.executebuiltin('PlayMedia("plugin://plugin.video.mlbtv/' + u + '")')


# log the game as in progress and watch playback to flip it to finished
def start_watch_monitor(data, pad_seconds=0):
    if data is None:
        return
    # a non-daemon thread keeps the addon script alive until playback stops
    threading.Thread(target=watch_monitor, args=(data, pad_seconds)).start()


def watch_monitor(data, pad_seconds):
    post_game_log(data, 'in progress')

    monitor = xbmc.Monitor()
    player = xbmc.Player()

    # wait up to 60 seconds for our stream to start, ignoring a possibly still playing previous file
    initial_file = get_playing_file(player)
    watched_file = None
    waited = 0
    while not monitor.abortRequested() and waited < 60:
        if xbmc.getCondVisibility('Player.HasMedia'):
            current_file = get_playing_file(player)
            if current_file is not None and current_file != initial_file:
                watched_file = current_file
                break
        monitor.waitForAbort(1)
        waited += 1
    # allow a replay of the exact same file
    if watched_file is None and xbmc.getCondVisibility('Player.HasMedia'):
        watched_file = get_playing_file(player)
    if watched_file is None:
        return

    # track the playback position until our file stops playing
    last_time = 0
    total_time = 0
    while not monitor.abortRequested():
        if not xbmc.getCondVisibility('Player.HasMedia') or get_playing_file(player) != watched_file:
            break
        try:
            if player.getTotalTime() > 0:
                total_time = player.getTotalTime()
            if player.getTime() > 0:
                last_time = player.getTime()
        except:
            pass
        monitor.waitForAbort(2)

    # finished means playback stopped at 95% or later of the real content, excluding padding
    content_time = total_time - pad_seconds
    if content_time > 0 and last_time >= content_time * 0.95:
        post_game_log(data, 'finished')
    # otherwise remember where we stopped so the game can be resumed later
    elif last_time > 0:
        post_game_log(data, 'in progress', seconds_to_position(int(last_time)))


def get_playing_file(player):
    try:
        return player.getPlayingFile()
    except:
        return None
