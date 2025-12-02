# GoodLinks2Insta - sync saved links from GoodLinks

GoodLinks2Insta automatically syncs saved links from GoodLinks to your Instapaper account. This tool bridges the gap between GoodLinks (Apple-optimized) and Instapaper (better integration ecosystem). 

GoodLinks is a great read later app, but only in the Apple ecosystem. Instapaper does not seem great at all, but has lots of integrations. 

## Requirements

- macOS
- [uv](https://github.com/astral-sh/uv)
- GoodLinks app
- Instapaper account

## Setup

```bash
# Clone/download this repo, then:
./sync.py init
```

This creates a config at `~/Library/Application Support/goodlinks2insta/config.json`.

## Usage

```bash
./sync.py              # sync new links
./sync.py status       # show sync status
./sync.py sync -n      # dry run (show what would sync)
./sync.py reset        # reset state (re-sync everything)
```

## Background Sync (every 3 hours)

```bash
cp com.elidickinson.goodlinks2insta.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.elidickinson.goodlinks2insta.plist
```

**Note**: The launchd plist file assumes `uv` is located at `/opt/homebrew/bin/uv`. If your `uv` installation is elsewhere, you'll need to update the path in the plist file. To find your uv location, run:

```bash
which uv
```

Then edit the plist file and replace `/opt/homebrew/bin/uv` with the output from the `which` command.

Logs: `~/Library/Logs/goodlinks2insta.log`

To uninstall:
```bash
launchctl unload ~/Library/LaunchAgents/com.elidickinson.goodlinks2insta.plist
rm ~/Library/LaunchAgents/com.elidickinson.goodlinks2insta.plist
```

## Config

Edit `~/Library/Application Support/goodlinks2insta/config.json`:

```json
{
  "username": "your@email.com",
  "password": "...",
  "launch_goodlinks": true,
  "log_file": "~/Library/Logs/goodlinks2insta.log"
}
```

Set `launch_goodlinks` to `false` if you don't want the script to open GoodLinks when it's not running.
