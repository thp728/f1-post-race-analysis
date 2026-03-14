"""Export dashboard charts as PNGs for the blog.

Usage:
    uv run python scripts/export_blog_charts.py --year 2024 --round 1
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.export import export_race_charts


def main() -> None:
    parser = argparse.ArgumentParser(description="Export race charts as PNGs for blog")
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--round", type=int, required=True, help="Round number")
    args = parser.parse_args()

    print(f"Exporting charts for {args.year} R{args.round:02d}...")
    exported = export_race_charts(args.year, args.round)

    if exported:
        print(f"\nExported {len(exported)} charts:")
        for path in exported:
            print(f"  {path}")
    else:
        print("No charts exported. Make sure race data is loaded in the database.")


if __name__ == "__main__":
    main()
