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
        xbmc.log('MLB game log: unable to build game data', xbmc.LOGINFO)
        return None


# fetch the most recently watched game (by game date) from the sheet
def get_latest_game_log():
    try:
        r = requests.get(GAME_LOG_URL, params={'latest': '1'}, timeout=15)
        return r.json().get('latest')
    except:
        xbmc.log('MLB game log: failed to fetch the latest game', xbmc.LOGINFO)
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
        requests.post(GAME_LOG_URL, json=payload, timeout=15)
        xbmc.log('MLB game log: ' + payload['game'] + ' ' + status, xbmc.LOGINFO)
    except:
        xbmc.log('MLB game log: failed to post to ' + GAME_LOG_URL, xbmc.LOGINFO)


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
    r = requests.get(url, headers=headers, verify=VERIFY, timeout=10)
    games = []
    for date in r.json().get('dates', []):
        for game in date.get('games', []):
            if 'rescheduleDate' not in game:
                games.append(game)
    return games


# build the home screen item for the most recently watched game:
# a playable item that resumes an in progress game with its logged play option and position,
# or opens the stream selection for the game after a finished one
# returns a (label, url_params, is_playable) tuple, or None if there is no log entry
def get_game_log_item(latest):
    if latest is None:
        return None
    try:
        label = LOCAL_STRING(30451) + ': ' + latest['date'] + ' (' + latest['type'] + ', ' + latest['status'] + ')'
    except:
        xbmc.log('MLB game log: malformed latest game data', xbmc.LOGINFO)
        return None
    try:
        if latest['status'] == 'in progress':
            for schedule_game in get_fav_schedule(latest['date'], latest['date']):
                if game_display_name(schedule_game) == latest['game']:
                    direct_play = 'fav'
                    if latest['type'] == 'Condensed Game':
                        direct_play = 'condensed'
                    u = '?mode=104' + play_params(schedule_game) + '&spoiler=' + game_log_spoiler(latest['date']) + '&direct_play=' + direct_play
                    start_seconds = position_to_seconds(latest.get('position', ''))
                    if start_seconds > 0:
                        u += '&start_pos=' + str(start_seconds)
                    return (label, u, True)
        else:
            next_game = find_next_fav_game(latest['date'], latest['game'])
            if next_game is not None and next_game['status']['abstractGameState'] != 'Preview':
                return (label, '?mode=103' + play_params(next_game) + '&spoiler=' + game_log_spoiler(next_game['officialDate']), True)
    except:
        xbmc.log('MLB game log: unable to build a playable home screen item', xbmc.LOGINFO)
    # no playable action, show an informational item
    return (label, '?mode=999', False)


# whether the favorite team plays again on the same date after the given game,
# which only a doubleheader game number suffix in the name can tell us
def has_later_fav_game(game_date, game):
    number_match = re.search(r'\(Game (\d+)\)$', game)
    if number_match is None:
        return False
    game_number = int(number_match.group(1))
    for schedule_game in get_fav_schedule(game_date, game_date):
        if schedule_game.get('gameNumber', 1) > game_number:
            return True
    return False


# favorite team division standings rows for the most recently watched game, dated so they
# can never spoil what is left to watch: the game date once that date has been watched to
# the end, otherwise the day before, since the game itself or the rest of a doubleheader
# day is still unwatched
def get_game_log_standings(latest):
    if latest is None or SHOW_STANDINGS != 'true':
        return []
    try:
        game_date = latest['date']
        if latest['status'] == 'finished' and not has_later_fav_game(game_date, latest['game']):
            standings_date = game_date
        else:
            standings_date = (stringToDate(game_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        standings = get_fav_division_standings(game_date[:4], standings_date)
        if standings is not None:
            return get_standings_rows(standings, standings_date)
    except:
        xbmc.log('MLB game log: unable to build the standings rows', xbmc.LOGINFO)
    return []


# spoiler flag for a favorite team game, matching the games list logic,
# so direct play streams take the same (proxied) route as manual play
def game_log_spoiler(game_day):
    spoiler = 'True'
    today = localToEastern()
    if NO_SPOILERS == '1' or NO_SPOILERS == '2' or (NO_SPOILERS == '3' and game_day == today) or (NO_SPOILERS == '4' and game_day < today):
        spoiler = 'False'
    return spoiler


# find the first favorite team game after the given one, minding doubleheaders
def find_next_fav_game(game_date, game):
    # a doubleheader game number suffix determines where to continue on the same date
    game_number = 1
    number_match = re.search(r'\(Game (\d+)\)$', game)
    if number_match:
        game_number = int(number_match.group(1))
    end_date = (parse(game_date) + timedelta(days=45)).strftime('%Y-%m-%d')
    for schedule_game in get_fav_schedule(game_date, end_date):
        if schedule_game['officialDate'] > game_date or (schedule_game['officialDate'] == game_date and schedule_game.get('gameNumber', 1) > game_number):
            return schedule_game
    return None


def play_params(schedule_game):
    name = game_display_name(schedule_game)
    return '&game_pk=' + str(schedule_game['gamePk']) + '&name=' + urllib.quote_plus(name) + '&description=' + urllib.quote_plus(name)


# log the game as in progress and watch playback to flip it to finished
def start_watch_monitor(data, pad_seconds=0, seek_seconds=0):
    if data is None:
        return
    # a non-daemon thread keeps the addon script alive until playback stops
    threading.Thread(target=watch_monitor, args=(data, pad_seconds, seek_seconds)).start()


def watch_monitor(data, pad_seconds, seek_seconds=0):
    post_game_log(data, 'in progress')

    monitor = xbmc.Monitor()
    player = xbmc.Player()

    # wait up to 60 seconds for playback to actually roll
    # our own item replaced any previous playback, so a rolling video is ours
    started = False
    waited = 0
    while not monitor.abortRequested() and waited < 60:
        try:
            if player.isPlayingVideo() and player.getTime() > 0:
                started = True
                break
        except:
            pass
        monitor.waitForAbort(1)
        waited += 1
    if not started:
        return
    watched_file = get_playing_file(player)
    if watched_file is None:
        return

    # jump to the requested resume position once playback is actually under way,
    # retrying since a seek during stream open is silently dropped
    if seek_seconds > 0:
        seek_wait = 0
        while not monitor.abortRequested() and seek_wait < 30 and xbmc.getCondVisibility('Player.HasMedia'):
            current_time = 0
            try:
                if player.isPlayingVideo():
                    current_time = player.getTime()
            except:
                pass
            # the seek landed once the position is at or past the target
            if current_time > seek_seconds - 30:
                break
            # only seek while playback is rolling
            if current_time > 0:
                try:
                    player.seekTime(seek_seconds)
                except:
                    pass
            monitor.waitForAbort(2)
            seek_wait += 1

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
