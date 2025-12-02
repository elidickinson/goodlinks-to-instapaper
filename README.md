# GoodLinks2Insta - sync saved links from GoodLinks to Instapaper

GoodLinks2Insta automatically syncs saved links from GoodLinks to your Instapaper account. This tool bridges the gap between GoodLinks (Apple-optimized) and Instapaper (better integration ecosystem).

This is an unofficial app and not endorsed by GoodLinks or Instapaper.

## Installation

```bash
# Clone the repository
git clone https://github.com/elidickinson/goodlinks-to-instapaper.git
cd goodlinks-to-instapaper

# Install as a uv tool
uv tool install .
```

After installation, you can run `goodlinks2insta` from anywhere:

```bash
goodlinks2insta init
goodlinks2insta sync
goodlinks2insta status
```

## Requirements

- macOS
- [uv](https://github.com/astral-sh/uv)
- GoodLinks app
- Instapaper account

## Installing uv on macOS

If you don't have uv installed, you can install it with:

```bash
# Using Homebrew (recommended)
brew install uv

# Or using the official installer
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify the installation:
```bash
uv --version
```

## Setup

```bash
# Initialize config with your Instapaper credentials
goodlinks2insta init
```

This creates a config at `~/Library/Application Support/goodlinks2insta/config.json`.

## Usage

```bash
goodlinks2insta              # sync new links
goodlinks2insta status       # show sync status
goodlinks2insta sync -n      # dry run (show what would sync)
goodlinks2insta reset        # reset state (re-sync everything)
```

## Background Sync (every 3 hours)

To set up automatic syncing every 3 hours, the plist file is already in your cloned repository:

### 1. Edit the plist file (if needed)

Open `com.sidget.goodlinks2insta.plist` (it's already in your cloned repository) and configure the paths:

- The UV path is already set to `/opt/homebrew/bin/uv` for Homebrew installations
  - If you installed uv elsewhere, replace this with the output from `which uv`
- The command is already set to `goodlinks2insta` (the installed uv tool)

### 2. Install the launch agent

```bash
cp com.sidget.goodlinks2insta.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sidget.goodlinks2insta.plist
```

**The plist file is already configured for most Homebrew users:**
```xml
<array>
    <string>/opt/homebrew/bin/uv</string>
    <string>tool</string>
    <string>run</string>
    <string>goodlinks2insta</string>
    <string>sync</string>
    <string>--quiet</string>
</array>
```

If you're not using Homebrew, update the UV path accordingly before copying the file.

Logs: `~/Library/Logs/goodlinks2insta.log`

To uninstall the background sync:
```bash
launchctl unload ~/Library/LaunchAgents/com.sidget.goodlinks2insta.plist
rm ~/Library/LaunchAgents/com.sidget.goodlinks2insta.plist
```

**Important**: Use the uv tool command structure:
`/opt/homebrew/bin/uv tool run goodlinks2insta sync --quiet`

Since `goodlinks2insta` is installed as a uv tool, it's available on your PATH and can be called directly from anywhere.

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

Set `launch_goodlinks` to `false` if you don't want the script to automatically open GoodLinks when it's not running.

## Uninstalling the tool

If you installed with `uv tool install`:

```bash
uv tool uninstall goodlinks2insta
```
