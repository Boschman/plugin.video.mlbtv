[![GitHub release](https://img.shields.io/github/release/eracknaphobia/plugin.video.mlbtv.svg)](https://github.com/eracknaphobia/plugin.video.mlbtv/releases)
![License](https://img.shields.io/badge/license-GPL%20(%3E%3D%202)-orange)
[![Contributors](https://img.shields.io/github/contributors/eracknaphobia/plugin.video.mlbtv.svg)](https://github.com/eracknaphobia/plugin.video.mlbtv/graphs/contributors)

Watch MLB tv in KODI

## Game log Google Sheet

The addon can log watched games of your favorite team to a Google Sheet.
It logs a row when you pick "Play [favorite team]" or "Play Condensed Game"
from the stream selection dialog (condensed games only when your favorite team
is playing). The sheet is kept sorted with the most recent game date at the
top and each row holds:

| Column    | Contents                                                                  |
|-----------|---------------------------------------------------------------------------|
| Game date | The official game date (YYYY-MM-DD)                                       |
| Game      | For instance "Red Sox @ Yankees", with a "(Game 2)" suffix for doubleheaders |
| Type      | Full Game or Condensed Game                                               |
| Status    | "in progress" or "finished"                                               |
| Position  | Where you stopped (H:MM:SS) in an unfinished game, cleared once finished  |

The status starts as "in progress" and changes to "finished" once you stop
playback at 95% or later of the actual broadcast (anti-spoiler stream padding
is excluded). Each game has one row: resuming a game later updates the
existing row, and replaying a finished game resets it to "in progress" until
you finish it again.

While a game log URL is set, the addon home screen also shows a
"Most recently watched game" item at the top with the game date, type and
status of the most recent game in the sheet (by game date, not by when you
watched it). Selecting the item continues where you left off:

- Status "in progress": plays that game again with the logged play option
  (the favorite team feed for a Full Game, or the condensed game), resuming
  from the logged position.
- Status "finished": opens the stream selection dialog for your favorite
  team's next game after that date (including game 2 of a doubleheader).
  If that game hasn't started yet, a notification is shown instead.

### Setting up the Google Sheet connection

Google requires authentication for direct API writes, so the addon posts to a
small Apps Script web app attached to your sheet instead. One-time setup:

1. Create a new Google Sheet at https://sheets.new (any name is fine, the
   addon writes to the first tab). You don't need to add a header row, the
   script creates it on first use.
2. In the sheet, go to Extensions > Apps Script. An editor opens with an
   empty `Code.gs` file.
3. Replace its contents with the contents of
   [resources/gamelog.gs](resources/gamelog.gs) and save (Ctrl+S / Cmd+S).
4. Click Deploy > New deployment, click the gear icon and choose type
   "Web app". Configure it as:
   - Description: anything, for instance "MLB.TV game log"
   - Execute as: **Me**
   - Who has access: **Anyone** (not "Anyone with a Google account", that
     returns a login page instead of accepting the addon's requests)
5. Click Deploy. Google asks you to authorize the script: choose your
   account, click "Advanced" and "Go to ... (unsafe)" if an unverified app
   warning appears, and allow access. This is your own script, the warning
   only means Google hasn't reviewed it.
6. Copy the shown web app URL. It looks like
   `https://script.google.com/macros/s/.../exec` and must end in `/exec`.
7. In Kodi, open the addon settings and paste the URL into
   "Game log URL (Google Apps Script web app)". Make sure your favorite
   team is set in the same settings category, otherwise nothing is logged.

To verify the connection, open the web app URL in a browser: it should show
"MLB.TV game log endpoint is working." Then play a favorite team game from
the stream selection dialog and the row should appear in the sheet within a
few seconds.

Notes:

- Leave the addon setting empty to disable game logging.
- If you later change the script, Deploy > Manage deployments > edit (pencil
  icon) > Version: "New version" > Deploy. The URL stays the same. Creating
  a new deployment instead gives a new URL, which you would have to copy to
  Kodi again.
- If Kodi is killed while watching, the row correctly stays "in progress";
  the status only flips to "finished" when playback is stopped normally.

