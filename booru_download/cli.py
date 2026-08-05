"""BooruDownload - CLI tool for downloading images from booru sites.

Usage examples:
    python main.py --tags "landscape rating:g score:>50" --limit 20
    python main.py --tags "1girl solo" --rating s --min-score 100 --format "{artist}_{id}.{ext}"
    python main.py --url "https://safebooru.donmai.us" --tags "scenery" --limit 50
    python main.py --tags "touhou" --output ./touhou_images --concurrent 12
"""

import argparse
import sys
import time
from pathlib import Path

# Fix Windows console encoding for emoji/unicode output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from booru_download.core.config import Config
from booru_download.core.credentials import (
    CredentialsStore,
    default_credentials_path,
    get_auth_profile,
    validate_credentials,
)
from booru_download.core.danbooru_client import DanbooruClient
from booru_download.core.formatter import FilenameFormatter
from booru_download.core.downloader import Downloader
from booru_download.core.fs_safety import VIDEO_EXTENSIONS, is_video_extension


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


DEFAULT_CREDENTIALS_PATH = default_credentials_path(_app_dir())


BANNER = """
BooruDownload
Fast image downloader for booru sites
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download images from Danbooru and compatible booru sites.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -t "landscape rating:g" -l 20
  %(prog)s -t "1girl solo" --rating s --min-score 100 -f "{artist}_{id}.{ext}"
  %(prog)s -u "https://safebooru.donmai.us" -t "scenery" -l 50
  %(prog)s -t "touhou" -o ./touhou_images -c 12
  %(prog)s --config config.yaml

Filename format placeholders:
  {id}        Post ID              {md5}       File MD5 hash
  {artist}    Artist name(s)       {character} Character name(s)
  {copyright} Series/copyright     {rating}    Rating (g/s/q/e)
  {score}     Post score           {date}      Upload date
  {width}     Image width          {height}    Image height
  {ext}       File extension       {tags}      All tags (first 10)
        """,
    )

    # Search
    parser.add_argument("-t", "--tags", type=str, default="",
                        help="Search tags (supports metatags like 'score:>100 order:score')")
    parser.add_argument("--rating", type=str, choices=["g", "s", "q", "e"],
                        help="Filter by rating: g(eneral), s(ensitive), q(uestionable), e(xplicit)")
    parser.add_argument("--min-score", type=int, default=None,
                        help="Minimum post score filter")

    # Output
    parser.add_argument("-o", "--output", type=str, default="./downloads",
                        help="Save directory (default: ./downloads)")
    parser.add_argument("-f", "--format", type=str, default="{id}_{artist}_{md5}.{ext}",
                        help="Filename format template (default: {id}_{artist}_{md5}.{ext})")

    # Limits
    parser.add_argument("-l", "--limit", type=int, default=100,
                        help="Maximum number of posts to download (default: 100)")
    parser.add_argument("-c", "--concurrent", type=int, default=8,
                        help="Concurrent download count (default: 8)")

    # Site
    parser.add_argument("-u", "--url", type=str, default="https://danbooru.donmai.us",
                        help="Base URL for Danbooru or mirror site")
    parser.add_argument("--username", type=str, default=None,
                        help="Danbooru username for API authentication")
    parser.add_argument("--api-key", type=str, default=None,
                        help="Danbooru API key for authentication")

    # Config file
    parser.add_argument("--config", type=str, default=None,
                        help="Path to YAML config file (CLI args override config values)")
    parser.add_argument("--save-config", type=str, default=None,
                        help="Save current settings to a YAML config file and exit")

    # Misc
    parser.add_argument("--no-skip", action="store_true",
                        help="Re-download files even if they already exist")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="HTTP request timeout in seconds (default: 30)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Search and list files that would be downloaded, without writing to disk",
    )
    parser.add_argument(
        "--include-video",
        action="store_true",
        help="Include mp4/webm/zip video and animation files (skipped by default)",
    )

    args = parser.parse_args()

    # Fail fast on out-of-range values: concurrent=0 would wait forever on
    # the semaphore and negative values raise deep inside asyncio.
    if not 1 <= args.concurrent <= 64:
        parser.error("--concurrent must be between 1 and 64")
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if not (args.timeout > 0 and args.timeout == args.timeout
            and args.timeout != float("inf")):
        parser.error("--timeout must be a finite number greater than 0")

    return args


def build_config(args: argparse.Namespace) -> Config:
    """Build Config from CLI args, optionally merging with a YAML config file."""
    # Start with defaults or config file
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"ERROR Config file not found: {args.config}")
            sys.exit(1)
        config = Config.from_yaml(config_path)
    else:
        config = Config()

    # CLI args override config file values
    if args.tags:
        config.tags = args.tags
    if args.rating:
        config.rating = args.rating
    if args.min_score is not None:
        config.min_score = args.min_score
    if args.output != "./downloads" or not args.config:
        config.save_dir = args.output
    if args.format != "{id}_{artist}_{md5}.{ext}" or not args.config:
        config.filename_format = args.format
    if args.limit != 100 or not args.config:
        config.max_posts = args.limit
    if args.concurrent != 8 or not args.config:
        config.concurrent_downloads = args.concurrent
    if args.url != "https://danbooru.donmai.us":
        config.base_url = args.url
    if args.username:
        config.username = args.username
    if args.api_key:
        config.api_key = args.api_key
    if args.no_skip:
        config.skip_existing = False
    if args.timeout != 30.0:
        config.timeout = args.timeout

    store = CredentialsStore(DEFAULT_CREDENTIALS_PATH)
    store.load()
    store.apply_to_config(
        config,
        override_username=args.username,
        override_api_key=args.api_key,
    )

    return config


def main():
    print(BANNER)
    args = parse_args()
    config = build_config(args)

    # Save config and exit if requested (credentials are never written to
    # task configs; they stay in the global credential store)
    if args.save_config:
        config.to_yaml(args.save_config)
        print(f"OK Config saved to: {args.save_config} (credentials excluded)")
        return

    # Validate
    tags_query = config.build_tags_query()
    if not tags_query.strip():
        print("WARN No search tags specified. Use -t/--tags to provide search tags.")
        print("    Example: python main.py -t \"landscape rating:g score:>50\"")
        sys.exit(1)

    auth = get_auth_profile(config.base_url)
    if auth.auth_required:
        auth_errors = validate_credentials(
            config.base_url, config.username, config.api_key
        )
        if auth_errors:
            print(
                "ERROR This site requires API credentials. "
                "Set them in Settings (GUI) / api_credentials.yaml, "
                "or pass --username and --api-key."
            )
            sys.exit(1)

    # Display search info
    print(f"Search tags:      {tags_query}")
    print(f"Site:             {config.base_url}")
    print(f"Save to:          {Path(config.save_dir).resolve()}")
    print(f"Filename format:  {config.filename_format}")
    print(f"Max posts:        {config.max_posts}")
    print(f"Concurrent:       {config.concurrent_downloads}")
    print(f"Include video:    {'yes' if args.include_video else 'no (default)'}")
    print(f"Convert images:   {config.auto_convert_format if config.auto_convert_images else 'off'}")
    if args.dry_run:
        print("Mode:             dry-run (no files will be written)")
    if config.username:
        print(f"Auth:             {config.username}")
    print()

    # Search for posts
    print("Searching for posts...")
    start_time = time.time()

    with DanbooruClient(
        base_url=config.base_url,
        username=config.username,
        api_key=config.api_key,
        timeout=config.timeout,
    ) as client:
        posts = list(client.search_all(tags=tags_query, max_posts=config.max_posts))

    search_time = time.time() - start_time

    if not args.include_video:
        before = len(posts)
        posts = [
            p for p in posts
            if not is_video_extension(p.get("file_ext", ""))
        ]
        skipped_video = before - len(posts)
        if skipped_video:
            print(
                f"Filtered out {skipped_video} video/animation posts "
                f"({', '.join(sorted(VIDEO_EXTENSIONS))}); "
                "use --include-video to keep them."
            )

    print(f"Found {len(posts)} downloadable posts ({search_time:.1f}s)")

    if not posts:
        print("No posts found matching your search criteria.")
        return

    formatter = FilenameFormatter(config.filename_format)

    if args.dry_run:
        print()
        print("Dry-run preview (no downloads):")
        print("-" * 42)
        for post in posts:
            name = formatter.format(post)
            url = post.get("file_url") or post.get("large_file_url") or ""
            print(f"  #{post.get('id', '?')}  {name}")
            if url:
                print(f"       {url}")
        print("-" * 42)
        print(f"Would download {len(posts)} file(s) to {Path(config.save_dir).resolve()}")
        return

    print()

    # Download images
    dl = Downloader(
        save_dir=config.save_dir,
        formatter=formatter,
        max_concurrent=config.concurrent_downloads,
        skip_existing=config.skip_existing,
        timeout=config.timeout,
        save_tag_txt=config.save_tag_txt,
        tag_txt_categories=config.tag_txt_categories,
        tag_txt_underscore_to_space=config.tag_txt_underscore_to_space,
        tag_txt_escape_special_chars=config.tag_txt_escape_special_chars,
        auto_convert_images=config.auto_convert_images,
        auto_convert_format=config.auto_convert_format,
        auto_convert_quality=config.auto_convert_quality,
        auto_convert_lossless=config.auto_convert_lossless,
        auto_convert_effort=config.auto_convert_effort,
        auto_convert_background_mode=config.auto_convert_background_mode,
        auto_convert_background_color=config.auto_convert_background_color,
        auto_convert_keep_original=config.auto_convert_keep_original,
        referer_base=config.base_url,
    )

    start_time = time.time()
    stats = dl.download_batch(posts)
    dl_time = time.time() - start_time

    # Summary
    print()
    print("=" * 42)
    print(f"Downloaded:  {stats['downloaded']}")
    print(f"Skipped:     {stats['skipped']}")
    if stats["failed"]:
        print(f"Failed:      {stats['failed']}")
    print(f"Time:        {dl_time:.1f}s")
    print(f"Saved to:    {Path(config.save_dir).resolve()}")
    print("=" * 42)

    # Non-zero exit when any file failed so scripts/schedulers can react.
    if stats["failed"]:
        sys.exit(1)


def run():
    """CLI entrypoint with exit-code semantics shared by all launchers."""
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
