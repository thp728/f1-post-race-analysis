"""Run after each race to load full weekend data into the database.

Usage:
    uv run python scripts/post_race_etl.py --year 2024 --round 1
    uv run python scripts/post_race_etl.py  # Auto-detect latest race
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


from src.loader import get_event_schedule, init_cache, init_db, store_weekend


def find_latest_race(year: int) -> int:
    """Find the most recent completed race round number."""
    init_cache()
    schedule = get_event_schedule(year)

    # Filter to conventional events (races, not testing)
    races = schedule[schedule["EventFormat"] != "testing"]

    from datetime import datetime
    today = datetime.now()
    completed = races[races["EventDate"] < today]

    if completed.empty:
        raise ValueError(f"No completed races found for {year}")

    return int(completed.iloc[-1]["RoundNumber"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Load F1 race weekend data into SQLite")
    parser.add_argument("--year", type=int, default=None, help="Season year")
    parser.add_argument("--round", type=int, default=None, help="Round number")
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Specific session(s) to load, comma-separated (e.g. FP1 or FP1,FP2). "
             "Defaults to all sessions: FP1,FP2,FP3,Q,R",
    )
    args = parser.parse_args()

    # Default to current year if not specified
    if args.year is None:
        from datetime import datetime
        args.year = datetime.now().year

    # Auto-detect latest round if not specified
    if args.round is None:
        try:
            args.round = find_latest_race(args.year)
            print(f"Auto-detected latest race: {args.year} R{args.round:02d}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    session_types = None
    if args.session:
        session_types = [s.strip().upper() for s in args.session.split(",")]

    label = ", ".join(session_types) if session_types else "full weekend"
    print(f"\nLoading {args.year} Round {args.round} ({label})...")
    print("=" * 50)

    # Initialize database
    init_db()

    # Load requested sessions for the weekend
    store_weekend(args.year, args.round, session_types=session_types)

    print("=" * 50)
    print("Done!")


if __name__ == "__main__":
    main()
