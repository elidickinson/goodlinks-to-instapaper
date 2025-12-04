#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""
GoodLinks to Instapaper Sync

Syncs all links from GoodLinks to your Instapaper account.

How it works:
1. Queries GoodLinks via AppleScript to get all saved links
2. Compares against a state file to find new links
3. Adds new links to Instapaper via Simple API (HTTP Basic Auth)
4. Updates state file to track what's been synced

Config: ~/Library/Application Support/goodlinks2insta/config.json
  {
    "username": "...",
    "password": "...",
    "launch_goodlinks": true,
    "log_file": "~/Library/Logs/goodlinks2insta.log"
  }

State: ~/Library/Application Support/goodlinks2insta/synced.json
"""

import argparse
import getpass
import json
import logging
import subprocess
import sys
import time

from pathlib import Path

import requests

APP_DIR = Path("~/Library/Application Support/goodlinks2insta").expanduser()
STATE_FILE = APP_DIR / "synced.json"
CONFIG_FILE = APP_DIR / "config.json"
DEFAULT_LOG_FILE = Path("~/Library/Logs/goodlinks2insta.log").expanduser()

log = logging.getLogger("goodlinks2insta")


def setup_logging(quiet: bool, log_file: Path | None):
    """Configure logging for interactive or background mode."""
    log.setLevel(logging.DEBUG)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        log.addHandler(file_handler)

    if not quiet:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(console_handler)


def is_goodlinks_running():
    """Check if GoodLinks is currently running."""
    result = subprocess.run(["pgrep", "-x", "GoodLinks"], capture_output=True)
    return result.returncode == 0


def launch_goodlinks():
    """Launch GoodLinks app."""
    subprocess.run(["open", "-a", "GoodLinks"], check=True)
    time.sleep(2)


def quit_goodlinks():
    """Quit GoodLinks app gracefully."""
    script = 'tell application "GoodLinks" to quit'
    try:
        subprocess.run(["osascript", "-e", script], check=True)
    except subprocess.CalledProcessError as e:
        log.debug(f"GoodLinks quit command failed: {e}")


def ensure_goodlinks_running(launch_if_needed: bool) -> bool:
    """Ensure GoodLinks is running. Returns True if ready, False if not."""
    if is_goodlinks_running():
        return True

    if launch_if_needed:
        log.info("Launching GoodLinks...")
        launch_goodlinks()
        if is_goodlinks_running():
            return True
        else:
            log.error("GoodLinks failed to start")
            return False

    log.warning(
        "GoodLinks is not running and launch_goodlinks is disabled in config\n"
        "Either start GoodLinks manually or set 'launch_goodlinks': true in config"
    )
    return False


def get_goodlinks():
    """Get all links from GoodLinks via AppleScript."""
    script = """
    tell application "GoodLinks"
        set output to ""
        set allLinks to every link
        repeat with l in allLinks
            set output to output & id of l & "\t" & url of l & "\t" & title of l & "\\n"
        end repeat
        return output
    end tell
    """
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        if "No such process" in result.stderr or "not running" in result.stderr:
            raise RuntimeError(
                "Cannot connect to GoodLinks - is the app installed and running?\n"
                "GoodLinks must be running in the background to sync links"
            )
        else:
            raise RuntimeError(f"AppleScript failed: {result.stderr}")

    links = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("\t")
            if len(parts) >= 3:
                links.append({"id": parts[0], "url": parts[1], "title": parts[2]})
    return links


def load_synced_ids():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_synced_ids(ids):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(list(ids)))


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Config file not found: {CONFIG_FILE}\n"
            f"Run '{sys.argv[0]} init' to create it"
        )
    config = json.loads(CONFIG_FILE.read_text())
    # Apply defaults
    config.setdefault("launch_goodlinks", True)
    config.setdefault("log_file", str(DEFAULT_LOG_FILE))
    return config


def cmd_init(args):
    """Initialize config file with Instapaper credentials."""
    APP_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists() and not args.force:
        print(f"Config already exists: {CONFIG_FILE}")
        print("Use --force to overwrite")
        return

    print("Enter your Instapaper credentials:")
    print("  Note: Use your Instapaper email and password you use to log in")
    username = input("  Email: ").strip()
    password = getpass.getpass("  Password: ").strip()

    if not username or not password:
        print("Error: Instapaper email and password are both required")
        print("  Make sure you've entered both fields and try again")
        sys.exit(1)

    config = {
        "username": username,
        "password": password,
        "launch_goodlinks": True,
        "log_file": str(DEFAULT_LOG_FILE),
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    CONFIG_FILE.chmod(0o600)
    print(f"Config saved to {CONFIG_FILE}")


def add_to_instapaper(url, title, username, password, max_retries=3):
    """Add URL to Instapaper via Simple API with timeout and retry."""
    timeout = 30

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                "https://www.instapaper.com/api/add",
                auth=(username, password),
                data={"url": url, "title": title},
                timeout=timeout,
            )

            if resp.status_code == 201:
                return True
            elif resp.status_code == 403:
                raise RuntimeError(
                    "Instapaper authentication failed - check your email and password\n"
                    "Run 'goodlinks2insta init' to update your credentials"
                )
            elif resp.status_code == 400:
                # Bad request - likely invalid URL, don't retry
                return False
            elif resp.status_code >= 500:
                # Server error - retry with exponential backoff
                if attempt < max_retries:
                    wait_time = 2**attempt  # 2, 4, 8 seconds
                    log.warning(
                        f"Server error (status {resp.status_code}), retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    log.error(
                        f"Max retries reached for server error (status {resp.status_code})"
                    )
                    return False
            else:
                # Other client errors - don't retry
                log.warning(
                    f"Instapaper returned status {resp.status_code} - skipping this link"
                )
                return False

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait_time = 2**attempt
                log.warning(f"Request timeout, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                log.error("Max retries reached for timeout")
                return False

        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                wait_time = 2**attempt
                log.warning(f"Connection error, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                log.error("Max retries reached for connection error")
                return False

        except requests.RequestException as e:
            # Other network errors - don't retry
            log.error(f"Network error adding {url}: {e}")
            return False

    return False


def cmd_sync(args):
    """Sync new links from GoodLinks to Instapaper."""
    config = load_config()

    # Setup logging
    log_file = Path(config["log_file"]).expanduser() if config.get("log_file") else None
    setup_logging(quiet=args.quiet, log_file=log_file)

    log.info("Starting sync")

    # Check if GoodLinks was already running
    was_running = is_goodlinks_running()

    # Ensure GoodLinks is running
    if not ensure_goodlinks_running(config.get("launch_goodlinks", True)):
        log.error("GoodLinks not running, skipping sync")
        return

    try:
        username = config["username"]
        password = config["password"]

        links = get_goodlinks()
        synced = load_synced_ids()
        to_sync = [l for l in links if l["id"] not in synced]

        log.info(f"Found {len(to_sync)} new links to sync (of {len(links)} total)")

        if args.dry_run:
            for link in to_sync:
                log.info(f"  Would sync: {link['title'][:70]}")
            log.info(f"Would sync {len(to_sync)} links")
            return

        if not to_sync:
            log.info("Nothing to sync")
            return

        new_count = 0
        failed_count = 0
        for i, link in enumerate(to_sync, 1):
            title_short = link["title"][:60]
            if add_to_instapaper(
                link["url"], link["title"], username, password, max_retries=args.max_retries
            ):
                synced.add(link["id"])
                new_count += 1
                log.info(f"[{i}/{len(to_sync)}] {title_short}... ok")
            else:
                failed_count += 1
                log.warning(f"[{i}/{len(to_sync)}] {title_short}... FAILED")
            # Save progress periodically
            if i % 10 == 0:
                save_synced_ids(synced)

        save_synced_ids(synced)
        log.info(f"Done: {new_count} synced, {failed_count} failed")

    finally:
        # Close GoodLinks if we opened it
        if not was_running:
            log.info("Closing GoodLinks")
            try:
                quit_goodlinks()
            except Exception as e:
                log.warning(f"Failed to close GoodLinks: {e}")


def cmd_status(args):
    """Show sync status."""
    links = get_goodlinks()
    synced = load_synced_ids()
    unsynced = [l for l in links if l["id"] not in synced]

    print(f"GoodLinks: {len(links)} links")
    print(f"Synced:    {len(synced)}")
    print(f"Pending:   {len(unsynced)}")

    if unsynced:
        print("\nPending links:")
        for link in unsynced[:10]:
            print(f"  - {link['title'][:60]}")
        if len(unsynced) > 10:
            print(f"  ... and {len(unsynced) - 10} more")


def cmd_reset(args):
    """Reset sync state (mark all as unsynced)."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print("Sync state reset")
    else:
        print("No sync state to reset")


def main():
    parser = argparse.ArgumentParser(
        description="Sync GoodLinks to Instapaper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # init command
    init_parser = subparsers.add_parser(
        "init", help="initialize config with credentials"
    )
    init_parser.add_argument(
        "-f", "--force", action="store_true", help="overwrite existing config"
    )
    init_parser.set_defaults(func=cmd_init)

    # sync command
    sync_parser = subparsers.add_parser("sync", help="sync links to Instapaper")
    sync_parser.add_argument(
        "-n", "--dry-run", action="store_true", help="show what would be synced"
    )
    sync_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="suppress console output (for background runs)",
    )
    sync_parser.add_argument(
        "-r",
        "--max-retries",
        type=int,
        default=3,
        help="maximum number of retries for failed requests (default: 3)",
    )
    sync_parser.set_defaults(func=cmd_sync)

    # status command
    status_parser = subparsers.add_parser("status", help="show sync status")
    status_parser.set_defaults(func=cmd_status)

    # reset command
    reset_parser = subparsers.add_parser("reset", help="reset sync state")
    reset_parser.set_defaults(func=cmd_reset)

    args = parser.parse_args()

    if args.command is None:
        # Default to sync
        args.dry_run = False
        args.quiet = False
        args.max_retries = 3
        cmd_sync(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
