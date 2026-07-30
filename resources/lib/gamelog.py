# Log watched favorite team games to a Google Sheet via a Google Apps Script web app
import threading

from resources.lib.globals import *


# build the sheet row data for a game, or None if it can't be determined
def game_log_data(epg_game, game_type):
    try:
        away = epg_game['teams']['away']['team']
        home = epg_game['teams']['home']['team']
        game = away.get('teamName', away['name']) + ' @ ' + home.get('teamName', home['name'])
        # distinguish doubleheader games
        if epg_game.get('doubleHeader', 'N') != 'N':
            game += ' (Game ' + str(epg_game['gameNumber']) + ')'
        return {
            'date': epg_game['officialDate'],
            'game': game,
            'type': game_type
        }
    except:
        xbmc.log('MLB game log: unable to build game data')
        return None


def post_game_log(data, status):
    payload = dict(data)
    payload['status'] = status
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


def get_playing_file(player):
    try:
        return player.getPlayingFile()
    except:
        return None
