# CLAUDE.md

Personal fork of the MLB.TV Kodi video addon (Kodi 20+, Python 3 via the xbmc modules).

## Architecture

- `main.py`: entry point, dispatches on the `mode` URL parameter (100s: listings/streams, 999: no-op for label items).
- `service.py`: background service running a local HLS proxy on `127.0.0.1:43670` that strips subtitle/ad tags (inputstream.adaptive chokes on them) and appends anti-spoiler padding via `?pad=N`.
- `resources/lib/globals.py`: settings, constants, shared helpers, imported everywhere with `*`.
- `resources/lib/mlb.py`: menus and `stream_select()` (the "Choose stream" dialog, favorite team and condensed play options).
- `resources/lib/mlbmonitor.py`: playback monitors (commercial skip markers, overlays, game changer).
- `resources/lib/gamelog.py`: logs watched favorite team games to a Google Sheet via the Apps Script in `resources/gamelog.gs` (see README for setup). When `gamelog.gs` changes, the sheet owner must redeploy it manually (Manage deployments > New version).
- `resources/settings.xml` (old format) + `resources/language/resource.language.en_gb/strings.po`: settings and label strings; use the next free `#304xx` id.

## Workflow

- No test suite; verify with `python3 -m py_compile` on changed files.
- Pushing to `main` auto-publishes through the "Publish Kodi repository" GitHub Action; the version is stamped `9999.<date>.<run_number>`. Never bump `addon.xml` manually. Testing in Kodi requires commit + push, since the addon installs from the published repo.

## Kodi gotchas (learned the hard way)

- Never start playback from a directory handler (PlayMedia during a folder click crashes Kodi 20 with "two concurrent busydialogs"); add a directly playable item (`IsPlayable=true`, `isFolder=False`) instead.
- A `ResumeTime` start offset stalls inputstream.adaptive on MLB archive streams; seek with `player.seekTime()` once playback rolls.
- `Player().getPlayingFile()` keeps returning the plugin URL, so detect stream start with `isPlayingVideo() and getTime() > 0`, not a filename change.
- Direct-play paths must pass the same `spoiler` flag the games list computes, so streams take the proxied route.
- `xbmc.log()` defaults to debug level, invisible in normal logs; log diagnostics with `xbmc.LOGINFO`.
