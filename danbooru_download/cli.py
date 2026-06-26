"""DanbooruDownload - CLI tool for downloading images from Danbooru and mirrors.

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

from danbooru_download.core.config import Config
from danbooru_download.core.danbooru_client import DanbooruClient
from danbooru_download.core.formatter import FilenameFormatter
from danbooru_download.core.downloader import Downloader


BANNER = """
DanbooruDownload
Fast image downloader for Danbooru
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

    return parser.parse_args()


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

    return config


def main():
    print(BANNER)
    args = parse_args()
    config = build_config(args)

    # Save config and exit if requested
    if args.save_config:
        config.to_yaml(args.save_config)
        print(f"OK Config saved to: {args.save_config}")
        return

    # Validate
    tags_query = config.build_tags_query()
    if not tags_query.strip():
        print("WARN No search tags specified. Use -t/--tags to provide search tags.")
        print("    Example: python main.py -t \"landscape rating:g score:>50\"")
        sys.exit(1)

    # Display search info
    print(f"Search tags:      {tags_query}")
    print(f"Site:             {config.base_url}")
    print(f"Save to:          {Path(config.save_dir).resolve()}")
    print(f"Filename format:  {config.filename_format}")
    print(f"Max posts:        {config.max_posts}")
    print(f"Concurrent:       {config.concurrent_downloads}")
    print(f"Convert images:   {config.auto_convert_format if config.auto_convert_images else 'off'}")
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
    print(f"Found {len(posts)} downloadable posts ({search_time:.1f}s)")

    if not posts:
        print("No posts found matching your search criteria.")
        return

    print()

    # Download images
    formatter = FilenameFormatter(config.filename_format)
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


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
