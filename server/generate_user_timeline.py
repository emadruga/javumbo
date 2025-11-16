#!/usr/bin/env python3
"""
User Timeline Generator

Generates detailed user activity timelines similar to those in
LOST_CARDS_COMPARATIVE_ANALYSIS.md by correlating:
- admin.db (user registration)
- user_X.anki2 (card/deck creation)
- Application logs (login, logout, deck switches)

Usage:
    python generate_user_timeline.py --user-id 50 --log-file logs/julho2025-logs.txt
    python generate_user_timeline.py --username Gabrielle --log-file logs/julho2025-logs.txt
    python generate_user_timeline.py --user-id 31 --log-file logs/junho-julho2025-logs.txt --date 2025-06-27
"""

import argparse
import sqlite3
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


class TimelineEvent:
    """Represents a single event in user timeline"""
    def __init__(self, timestamp: datetime, event_type: str, description: str, details: Dict = None, source: str = 'unknown'):
        self.timestamp = timestamp
        self.event_type = event_type  # 'login', 'logout', 'card_create', 'card_review', 'card_delete', 'deck_create', 'deck_delete', 'deck_switch'
        self.description = description
        self.details = details or {}
        self.source = source  # 'log' or 'db' - for deduplication (log takes precedence)

    def __repr__(self):
        return f"{self.timestamp.strftime('%H:%M:%S')}  {self.description}"


class UserTimelineGenerator:
    """Generates user activity timelines from multiple data sources"""

    def __init__(self, admin_db_path: str = None, user_db_dir: str = None, log_file: str = None):
        self.admin_db_path = admin_db_path or "admin.db"
        self.user_db_dir = user_db_dir or "user_dbs"
        self.log_file = log_file
        self.events: List[TimelineEvent] = []

    def get_user_info(self, user_id: int = None, username: str = None) -> Tuple[int, str]:
        """Get user_id and username from admin.db"""
        if not Path(self.admin_db_path).exists():
            raise FileNotFoundError(f"Admin database not found: {self.admin_db_path}")

        conn = sqlite3.connect(self.admin_db_path)
        cursor = conn.cursor()

        if user_id:
            cursor.execute("SELECT user_id, username, name FROM users WHERE user_id = ?", (user_id,))
        elif username:
            cursor.execute("SELECT user_id, username, name FROM users WHERE username = ?", (username,))
        else:
            raise ValueError("Must provide either user_id or username")

        row = cursor.fetchone()
        conn.close()

        if not row:
            raise ValueError(f"User not found: {user_id or username}")

        return row[0], row[1], row[2]

    def get_user_db_path(self, username: str) -> str:
        """Get path to user's .anki2 database"""
        user_db_path = Path(self.user_db_dir) / f"{username}.anki2"
        if not user_db_path.exists():
            raise FileNotFoundError(f"User database not found: {user_db_path}")
        return str(user_db_path)

    def parse_all_log_events(self, username: str, target_date: str = None) -> List[TimelineEvent]:
        """Parse all event types from application logs (deck switches, logins, logouts, card operations, etc.)"""
        events = []

        if not self.log_file or not Path(self.log_file).exists():
            print(f"Warning: Log file not found or not specified: {self.log_file}")
            return events

        # Regex patterns for log parsing
        # Example: "2025-07-04 17:00:07 - User 50 (Gabrielle) set current deck to 1751658410042"
        deck_switch_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+-\s+User\s+\d+\s+\(([^)]+)\)\s+set\s+current\s+deck\s+to\s+(\d+)'
        )

        # Example: "2025-07-04 16:48:12 - User 50 (Gabrielle) logged in"
        login_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+-\s+User\s+\d+\s+\(([^)]+)\)\s+logged\s+in'
        )

        # Example: "2025-07-04 18:41:23 - User 50 (Gabrielle) logged out"
        logout_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+-\s+User\s+\d+\s+\(([^)]+)\)\s+logged\s+out'
        )

        # NEW: Card creation pattern
        # Example: "User 50 (Gabrielle) created card 1751658410043 in deck 1 (MyFirstDeck): \"Capital of Fra...\""
        card_create_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?User\s+\d+\s+\(([^)]+)\)\s+created\s+card\s+(\d+)\s+in\s+deck\s+(\d+)\s+\(([^)]+)\):\s+"([^"]+)"'
        )

        # NEW: Card review pattern
        # Example: "User 50 (Gabrielle) reviewed card 1751658410043 (\"Capital of Fra...\") ease=3: New → Learning"
        card_review_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?User\s+\d+\s+\(([^)]+)\)\s+reviewed\s+card\s+(\d+)\s+\("([^"]+)"\)\s+ease=(\d):\s+(\w+)\s+→\s+(\w+)'
        )

        # NEW: Card deletion pattern
        # Example: "User 50 (Gabrielle) deleted card 1751658410043 from deck 1 (MyFirstDeck): \"Capital of Fra...\" [state: New]"
        card_delete_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?User\s+\d+\s+\(([^)]+)\)\s+deleted\s+card\s+(\d+)\s+from\s+deck\s+(\d+)\s+\(([^)]+)\):\s+"([^"]+)"\s+\[state:\s+(\w+)\]'
        )

        # NEW: Deck deletion pattern
        # Example: "User 50 (Gabrielle) deleted deck 1751658410042 (Test Deck) with 15 cards"
        deck_delete_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?User\s+\d+\s+\(([^)]+)\)\s+deleted\s+deck\s+(\d+)\s+\(([^)]+)\)\s+with\s+(\d+)\s+cards'
        )

        with open(self.log_file, 'r') as f:
            for line in f:
                # Check for deck switches
                match = deck_switch_pattern.search(line)
                if match and match.group(2) == username:
                    timestamp_str, user, deck_id = match.groups()
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                        continue

                    events.append(TimelineEvent(
                        timestamp=timestamp,
                        event_type='deck_switch',
                        description=f"Switch to deck {deck_id}",
                        details={'deck_id': int(deck_id)},
                        source='log'
                    ))
                    continue

                # Check for logins
                match = login_pattern.search(line)
                if match and match.group(2) == username:
                    timestamp_str = match.group(1)
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                        continue

                    events.append(TimelineEvent(
                        timestamp=timestamp,
                        event_type='login',
                        description="Logged in",
                        source='log'
                    ))
                    continue

                # Check for logouts
                match = logout_pattern.search(line)
                if match and match.group(2) == username:
                    timestamp_str = match.group(1)
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                        continue

                    events.append(TimelineEvent(
                        timestamp=timestamp,
                        event_type='logout',
                        description="Logged out",
                        source='log'
                    ))
                    continue

                # NEW: Check for card creation
                match = card_create_pattern.search(line)
                if match and match.group(2) == username:
                    timestamp_str, user, card_id, deck_id, deck_name, front = match.groups()
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                        continue

                    events.append(TimelineEvent(
                        timestamp=timestamp,
                        event_type='card_create',
                        description=f"Created card: \"{front}\"",
                        details={
                            'card_id': int(card_id),
                            'deck_id': int(deck_id),
                            'deck_name': deck_name,
                            'front': front
                        },
                        source='log'
                    ))
                    continue

                # NEW: Check for card review
                match = card_review_pattern.search(line)
                if match and match.group(2) == username:
                    timestamp_str, user, card_id, front, ease, old_state, new_state = match.groups()
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                        continue

                    events.append(TimelineEvent(
                        timestamp=timestamp,
                        event_type='card_review',
                        description=f"Reviewed \"{front}\" (ease={ease}): {old_state} → {new_state}",
                        details={
                            'card_id': int(card_id),
                            'front': front,
                            'ease': int(ease),
                            'old_state': old_state,
                            'new_state': new_state
                        },
                        source='log'
                    ))
                    continue

                # NEW: Check for card deletion
                match = card_delete_pattern.search(line)
                if match and match.group(2) == username:
                    timestamp_str, user, card_id, deck_id, deck_name, front, state = match.groups()
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                        continue

                    events.append(TimelineEvent(
                        timestamp=timestamp,
                        event_type='card_delete',
                        description=f"Deleted card: \"{front}\" [was: {state}]",
                        details={
                            'card_id': int(card_id),
                            'deck_id': int(deck_id),
                            'deck_name': deck_name,
                            'front': front,
                            'state': state
                        },
                        source='log'
                    ))
                    continue

                # NEW: Check for deck deletion
                match = deck_delete_pattern.search(line)
                if match and match.group(2) == username:
                    timestamp_str, user, deck_id, deck_name, card_count = match.groups()
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                    if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                        continue

                    events.append(TimelineEvent(
                        timestamp=timestamp,
                        event_type='deck_delete',
                        description=f"Deleted deck \"{deck_name}\" ({card_count} cards)",
                        details={
                            'deck_id': int(deck_id),
                            'deck_name': deck_name,
                            'card_count': int(card_count)
                        },
                        source='log'
                    ))
                    continue

        return events

    def get_cards_from_db(self, user_db_path: str, target_date: str = None) -> List[TimelineEvent]:
        """Get card creation events from user database"""
        events = []

        conn = sqlite3.connect(user_db_path)
        cursor = conn.cursor()

        # Get cards with their creation timestamps and deck IDs
        # Join notes and cards tables
        query = """
        SELECT
            n.id as note_id,
            n.flds as fields,
            n.mod as note_mod,
            c.id as card_id,
            c.did as deck_id,
            c.mod as card_mod
        FROM notes n
        JOIN cards c ON c.nid = n.id
        WHERE n.id > 1700000000000  -- Exclude sample cards
        ORDER BY c.mod
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            note_id, fields, note_mod, card_id, deck_id, card_mod = row

            # Use card modification time as creation time
            timestamp = datetime.fromtimestamp(card_mod)

            # Filter by target_date if specified
            if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                continue

            # Parse fields (front is first field)
            field_list = fields.split('\x1f')
            front = field_list[0] if field_list else 'Unknown'

            # Truncate long fronts
            if len(front) > 50:
                front = front[:47] + "..."

            events.append(TimelineEvent(
                timestamp=timestamp,
                event_type='card_create',
                description=f"Created card: \"{front}\"",
                details={
                    'card_id': card_id,
                    'note_id': note_id,
                    'deck_id': deck_id,
                    'front': front
                },
                source='db'
            ))

        conn.close()
        return events

    def get_decks_from_db(self, user_db_path: str) -> Dict[int, Dict]:
        """Get deck info from user database"""
        conn = sqlite3.connect(user_db_path)
        cursor = conn.cursor()

        # Get collection with decks
        cursor.execute("SELECT decks FROM col")
        row = cursor.fetchone()
        conn.close()

        if not row or not row[0]:
            return {}

        import json
        decks_json = row[0]
        decks = json.loads(decks_json)

        # Convert to int keys
        deck_map = {}
        for deck_id_str, deck_data in decks.items():
            deck_map[int(deck_id_str)] = deck_data

        return deck_map

    def get_deck_creation_events(self, user_db_path: str, target_date: str = None) -> List[TimelineEvent]:
        """Get deck creation events"""
        events = []

        decks = self.get_decks_from_db(user_db_path)

        for deck_id, deck_data in decks.items():
            if deck_id == 1:
                continue  # Skip default deck

            # Use deck mod time as creation time
            if 'mod' in deck_data:
                timestamp = datetime.fromtimestamp(deck_data['mod'])

                # Filter by target_date if specified
                if target_date and timestamp.strftime('%Y-%m-%d') != target_date:
                    continue

                deck_name = deck_data.get('name', 'Unknown')

                events.append(TimelineEvent(
                    timestamp=timestamp,
                    event_type='deck_create',
                    description=f"CREATED deck \"{deck_name}\" ({deck_id})",
                    details={
                        'deck_id': deck_id,
                        'deck_name': deck_name
                    },
                    source='db'
                ))

        return events

    def generate_timeline(self, user_id: int = None, username: str = None, target_date: str = None):
        """Generate complete user timeline"""
        # Get user info
        user_id, username, name = self.get_user_info(user_id=user_id, username=username)
        user_db_path = self.get_user_db_path(username)

        print(f"\nGenerating timeline for User {user_id} ({username} - {name})")
        if target_date:
            print(f"Filtering by date: {target_date}")
        print("=" * 80)

        # Collect all events
        self.events = []

        # Get events from different sources
        # NEW: Parse all log events (includes deck switches, card creation/review/deletion, deck deletion)
        self.events.extend(self.parse_all_log_events(username, target_date))

        # Get database events (as fallback for events not captured in logs)
        self.events.extend(self.get_cards_from_db(user_db_path, target_date))
        self.events.extend(self.get_deck_creation_events(user_db_path, target_date))

        # Sort by timestamp
        self.events.sort(key=lambda e: e.timestamp)

        # Deduplication: Remove database events if log events exist for same card_id
        # This ensures logs (source='log') take precedence over database (source='db')
        seen_card_creates = {}  # card_id -> event from log

        # First pass: collect all log-based card creations
        for event in self.events:
            if event.event_type == 'card_create' and event.source == 'log':
                card_id = event.details.get('card_id')
                if card_id:
                    seen_card_creates[card_id] = event

        # Second pass: filter out database card creations that have log equivalents
        deduplicated_events = []
        for event in self.events:
            if event.event_type == 'card_create' and event.source == 'db':
                card_id = event.details.get('card_id')
                if card_id in seen_card_creates:
                    # Skip this database event - we have a log event for it
                    continue
            deduplicated_events.append(event)

        self.events = deduplicated_events

        if not self.events:
            print("\nNo events found for this user/date.")
            return

        # Get deck map for display
        deck_map = self.get_decks_from_db(user_db_path)

        # Print timeline
        self._print_timeline(deck_map)

        # Print statistics
        self._print_statistics(deck_map)

    def _print_timeline(self, deck_map: Dict[int, Dict]):
        """Print formatted timeline"""
        print("\n\nTIMELINE")
        print("=" * 80)

        if not self.events:
            print("No events to display.")
            return

        # Group events by time periods
        current_period_start = None
        period_events = []
        period_description = ""

        def print_period():
            if not period_events:
                return

            period_end = period_events[-1].timestamp
            time_range = f"{current_period_start.strftime('%H:%M')}-{period_end.strftime('%H:%M')}"

            print(f"\n{time_range}  {period_description}")
            for event in period_events:
                icon = self._get_event_icon(event.event_type)
                print(f"             {icon} {event.timestamp.strftime('%H:%M:%S')}  {event.description}")

        last_timestamp = None

        for event in self.events:
            # Check if we need to start a new period (gap > 2 minutes)
            if last_timestamp and (event.timestamp - last_timestamp) > timedelta(minutes=2):
                # Print previous period
                print_period()

                # Start new period
                current_period_start = event.timestamp
                period_events = [event]
                period_description = self._get_period_description(event)
            else:
                # Continue current period
                if not current_period_start:
                    current_period_start = event.timestamp
                    period_description = self._get_period_description(event)

                period_events.append(event)

            last_timestamp = event.timestamp

        # Print final period
        print_period()

    def _get_event_icon(self, event_type: str) -> str:
        """Get emoji icon for event type"""
        icons = {
            'login': '🔑',
            'logout': '🚪',
            'card_create': '✅',
            'deck_create': '📁',
            'deck_switch': '🔀',
            'card_review': '📖',
            'card_delete': '🗑️',
            'deck_delete': '🗂️'
        }
        return icons.get(event_type, '•')

    def _get_period_description(self, event: TimelineEvent) -> str:
        """Get description for time period based on event type"""
        if event.event_type == 'card_create':
            return "Card Creation"
        elif event.event_type == 'card_review':
            return "Card Review"
        elif event.event_type == 'card_delete':
            return "Card Deletion"
        elif event.event_type == 'deck_create':
            return "Deck Creation"
        elif event.event_type == 'deck_delete':
            return "Deck Deletion"
        elif event.event_type == 'deck_switch':
            return "Deck Switching"
        elif event.event_type == 'login':
            return "Session Start"
        elif event.event_type == 'logout':
            return "Session End"
        else:
            return "Activity"

    def _print_statistics(self, deck_map: Dict[int, Dict]):
        """Print timeline statistics"""
        print("\n\nSTATISTICS")
        print("=" * 80)

        # Count events by type
        event_counts = defaultdict(int)
        for event in self.events:
            event_counts[event.event_type] += 1

        print(f"\nTotal Events: {len(self.events)}")
        print(f"  - Logins: {event_counts['login']}")
        print(f"  - Logouts: {event_counts['logout']}")
        print(f"  - Cards Created: {event_counts['card_create']}")
        print(f"  - Cards Reviewed: {event_counts['card_review']}")
        print(f"  - Cards Deleted: {event_counts['card_delete']}")
        print(f"  - Decks Created: {event_counts['deck_create']}")
        print(f"  - Decks Deleted: {event_counts['deck_delete']}")
        print(f"  - Deck Switches: {event_counts['deck_switch']}")

        # Session duration
        if self.events:
            session_start = self.events[0].timestamp
            session_end = self.events[-1].timestamp
            duration = session_end - session_start

            print(f"\nSession Duration: {duration}")
            print(f"  Start: {session_start.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  End:   {session_end.strftime('%Y-%m-%d %H:%M:%S')}")

        # Cards by deck
        print("\n\nCards Created by Deck:")
        cards_by_deck = defaultdict(int)
        for event in self.events:
            if event.event_type == 'card_create':
                deck_id = event.details.get('deck_id', 1)
                cards_by_deck[deck_id] += 1

        for deck_id, count in sorted(cards_by_deck.items()):
            deck_name = deck_map.get(deck_id, {}).get('name', 'Unknown')
            print(f"  - Deck {deck_id} ({deck_name}): {count} cards")

        # Deck switching patterns
        deck_switches = [e for e in self.events if e.event_type == 'deck_switch']
        if deck_switches:
            print(f"\n\nDeck Switching Pattern:")

            # Count switches per deck
            switch_counts = defaultdict(int)
            for event in deck_switches:
                deck_id = event.details['deck_id']
                switch_counts[deck_id] += 1

            print(f"  Total switches: {len(deck_switches)}")
            print(f"  Unique decks accessed: {len(switch_counts)}")

            # Find repeated switches to same deck
            for deck_id, count in sorted(switch_counts.items(), key=lambda x: -x[1]):
                deck_name = deck_map.get(deck_id, {}).get('name', 'Unknown')
                if count > 1:
                    print(f"  - Deck {deck_id} ({deck_name}): {count} times ⚠️")
                else:
                    print(f"  - Deck {deck_id} ({deck_name}): {count} time")

        # Identify potential issues
        self._identify_issues(deck_map)

    def _detect_duplicate_cards(self) -> Dict[str, List[TimelineEvent]]:
        """Detect duplicate cards by comparing front text"""
        card_creates = [e for e in self.events if e.event_type == 'card_create']

        # Group cards by front text (normalized for comparison)
        cards_by_front = defaultdict(list)
        for event in card_creates:
            front = event.details.get('front', '').strip().lower()
            if front:  # Ignore empty fronts
                cards_by_front[front].append(event)

        # Filter to only duplicates (2+ cards with same front)
        duplicates = {front: events for front, events in cards_by_front.items() if len(events) > 1}

        return duplicates

    def _detect_delete_recreate_pattern(self) -> List[Dict]:
        """Detect cards that were deleted and then recreated (Rayssa pattern)"""
        deletions = [e for e in self.events if e.event_type == 'card_delete']
        creations = [e for e in self.events if e.event_type == 'card_create']

        patterns = []

        # For each deletion, look for a creation with matching front text within time window
        for delete_event in deletions:
            delete_front = delete_event.details.get('front', '').strip().lower()
            delete_time = delete_event.timestamp
            delete_deck_id = delete_event.details.get('deck_id')

            # Look for matching card created within 10 minutes after deletion
            for create_event in creations:
                if create_event.timestamp <= delete_time:
                    continue  # Only consider creations after deletion

                time_diff = create_event.timestamp - delete_time
                if time_diff > timedelta(minutes=10):
                    continue  # Too far apart

                create_front = create_event.details.get('front', '').strip().lower()
                create_deck_id = create_event.details.get('deck_id')

                # Check if front text matches (normalized comparison)
                if delete_front == create_front:
                    patterns.append({
                        'delete_event': delete_event,
                        'create_event': create_event,
                        'time_gap': time_diff,
                        'same_deck': delete_deck_id == create_deck_id,
                        'delete_deck_id': delete_deck_id,
                        'create_deck_id': create_deck_id
                    })
                    break  # Found a match for this deletion

        return patterns

    def _identify_issues(self, deck_map: Dict[int, Dict]):
        """Identify potential UX issues from timeline"""
        print("\n\nPOTENTIAL ISSUES")
        print("=" * 80)

        issues_found = False

        # Check for duplicate cards (PRIMARY INDICATOR of lost cards bug)
        duplicates = self._detect_duplicate_cards()
        if duplicates:
            print(f"\n🔴 DUPLICATE CARDS DETECTED")
            print(f"   Found {len(duplicates)} unique cards that were created multiple times")
            print(f"   This is a PRIMARY INDICATOR of the 'lost cards' UX issue\n")

            # Sort by number of duplicates (most duplicated first)
            sorted_duplicates = sorted(duplicates.items(), key=lambda x: -len(x[1]))

            # Show details for each duplicate set
            for front, events in sorted_duplicates[:5]:  # Show top 5
                original_front = events[0].details.get('front', front)  # Get original case
                print(f"   Card: \"{original_front}\"")
                print(f"   Created {len(events)} times:")

                for i, event in enumerate(events, 1):
                    deck_id = event.details.get('deck_id', 1)
                    deck_name = deck_map.get(deck_id, {}).get('name', 'Unknown')
                    timestamp = event.timestamp.strftime('%H:%M:%S')

                    if i == 1:
                        print(f"     {i}. {timestamp} - Deck {deck_id} ({deck_name}) [ORIGINAL]")
                    else:
                        # Calculate time gap from original
                        time_gap = event.timestamp - events[0].timestamp
                        minutes = int(time_gap.total_seconds() / 60)
                        seconds = int(time_gap.total_seconds() % 60)
                        print(f"     {i}. {timestamp} - Deck {deck_id} ({deck_name}) [+{minutes}m {seconds}s]")

                print()  # Blank line between duplicate sets

            if len(duplicates) > 5:
                print(f"   ... and {len(duplicates) - 5} more duplicate cards\n")

            issues_found = True

        # Check for delete-recreate patterns (Rayssa pattern)
        delete_recreate_patterns = self._detect_delete_recreate_pattern()
        if delete_recreate_patterns:
            print(f"\n🔴 DELETE-RECREATE PATTERN DETECTED")
            print(f"   Found {len(delete_recreate_patterns)} cards that were deleted and then recreated")
            print(f"   This suggests user deleted cards from wrong deck, then recreated them\n")

            for pattern in delete_recreate_patterns[:5]:  # Show top 5
                delete_event = pattern['delete_event']
                create_event = pattern['create_event']
                time_gap = pattern['time_gap']
                delete_deck_id = pattern['delete_deck_id']
                create_deck_id = pattern['create_deck_id']

                delete_deck_name = deck_map.get(delete_deck_id, {}).get('name', 'Unknown')
                create_deck_name = deck_map.get(create_deck_id, {}).get('name', 'Unknown')

                card_front = delete_event.details.get('front', 'Unknown')
                delete_time = delete_event.timestamp.strftime('%H:%M:%S')
                create_time = create_event.timestamp.strftime('%H:%M:%S')

                minutes = int(time_gap.total_seconds() / 60)
                seconds = int(time_gap.total_seconds() % 60)

                print(f"   Card: \"{card_front}\"")
                print(f"     1. {delete_time} - DELETED from Deck {delete_deck_id} ({delete_deck_name})")
                print(f"     2. {create_time} - RECREATED in Deck {create_deck_id} ({create_deck_name}) [+{minutes}m {seconds}s]")

                if pattern['same_deck']:
                    print(f"     ⚠️  Same deck - unusual pattern")
                else:
                    print(f"     ⚠️  Different deck - user correcting mistake")
                print()

            if len(delete_recreate_patterns) > 5:
                print(f"   ... and {len(delete_recreate_patterns) - 5} more patterns\n")

            issues_found = True

        # Check for repeated switches to same deck (Rayssa pattern)
        deck_switches = [e for e in self.events if e.event_type == 'deck_switch']
        if deck_switches:
            # Check for same deck switched to multiple times in short period
            for i, event in enumerate(deck_switches):
                same_deck_switches = [event]
                deck_id = event.details['deck_id']

                # Look ahead for more switches to same deck
                for j in range(i+1, min(i+5, len(deck_switches))):
                    if deck_switches[j].details['deck_id'] == deck_id:
                        time_diff = deck_switches[j].timestamp - event.timestamp
                        if time_diff < timedelta(minutes=10):
                            same_deck_switches.append(deck_switches[j])

                if len(same_deck_switches) >= 3:
                    deck_name = deck_map.get(deck_id, {}).get('name', 'Unknown')
                    print(f"\n🔴 REPEATED SWITCHING to deck {deck_id} ({deck_name})")
                    print(f"   Switched {len(same_deck_switches)} times in {(same_deck_switches[-1].timestamp - same_deck_switches[0].timestamp)}")
                    print(f"   This pattern suggests user confusion or UI malfunction")
                    issues_found = True
                    break  # Only report first instance

        # Check for gaps between card creation and deck switching
        card_creates = [e for e in self.events if e.event_type == 'card_create']
        if card_creates and deck_switches:
            last_card = card_creates[-1]
            next_switches = [s for s in deck_switches if s.timestamp > last_card.timestamp]

            if next_switches:
                first_switch_after_cards = next_switches[0]
                time_gap = first_switch_after_cards.timestamp - last_card.timestamp

                if time_gap < timedelta(minutes=1):
                    print(f"\n⚠️  QUICK DECK SWITCH AFTER CARD CREATION")
                    print(f"   Last card: {last_card.timestamp.strftime('%H:%M:%S')}")
                    print(f"   Deck switch: {first_switch_after_cards.timestamp.strftime('%H:%M:%S')}")
                    print(f"   Gap: {time_gap.total_seconds():.0f} seconds")
                    print(f"   User may be looking for cards in wrong deck")
                    issues_found = True

        # Check for logout/login (Gabrielle pattern)
        logins = [e for e in self.events if e.event_type == 'login']
        logouts = [e for e in self.events if e.event_type == 'logout']

        if len(logins) > 1 or len(logouts) > 0:
            print(f"\n⚠️  SESSION INTERRUPTION")
            print(f"   Logins: {len(logins)}, Logouts: {len(logouts)}")
            print(f"   User may be trying to fix an issue by re-logging")
            issues_found = True

        if not issues_found:
            print("\nNo obvious issues detected in timeline.")
            print("User workflow appears normal.")


def main():
    parser = argparse.ArgumentParser(
        description='Generate user activity timeline from logs and databases'
    )

    # User identification (one required)
    user_group = parser.add_mutually_exclusive_group(required=True)
    user_group.add_argument('--user-id', type=int, help='User ID')
    user_group.add_argument('--username', type=str, help='Username')

    # Data sources
    parser.add_argument('--admin-db', default='admin.db', help='Path to admin.db (default: admin.db)')
    parser.add_argument('--user-db-dir', default='user_dbs', help='Directory containing user databases (default: user_dbs)')
    parser.add_argument('--log-file', help='Path to application log file')

    # Filters
    parser.add_argument('--date', help='Filter events by date (YYYY-MM-DD format)')

    args = parser.parse_args()

    try:
        generator = UserTimelineGenerator(
            admin_db_path=args.admin_db,
            user_db_dir=args.user_db_dir,
            log_file=args.log_file
        )

        generator.generate_timeline(
            user_id=args.user_id,
            username=args.username,
            target_date=args.date
        )

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
