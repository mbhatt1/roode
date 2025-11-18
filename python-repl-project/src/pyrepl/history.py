"""
History management for Python REPL.

This module provides persistent command history storage, search functionality,
and session-based tracking using SQLite database.
"""

import os
import json
import sqlite3
from typing import List, Optional, Tuple
from datetime import datetime
from pathlib import Path


class HistoryManager:
    """
    Manages command history for the REPL with persistent storage.
    
    Features:
    - Persistent storage using SQLite
    - Session-based tracking
    - History search (reverse-i-search)
    - Navigation support (up/down arrows)
    - Export/import capabilities
    """
    
    def __init__(self, db_path: Optional[str] = None, max_history: int = 10000):
        """
        Initialize the HistoryManager.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
            max_history: Maximum number of history entries to keep.
        """
        self.max_history = max_history
        self.current_position = -1  # For navigation
        self.session_id = self._generate_session_id()
        
        # Set up database path
        if db_path is None:
            home = Path.home()
            config_dir = home / ".pyrepl"
            config_dir.mkdir(exist_ok=True)
            self.db_path = str(config_dir / "history.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Cache for current session
        self._cache: List[Tuple[int, str, str, str]] = []
        self._load_cache()
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    def _init_database(self):
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL
                )
            """)
            
            # Create index for faster searches
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_command 
                ON history(command)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session 
                ON history(session_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON history(timestamp)
            """)
            
            conn.commit()
    
    def _load_cache(self):
        """Load recent history into cache for faster access."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, command, timestamp, session_id 
                FROM history 
                ORDER BY id DESC 
                LIMIT ?
            """, (self.max_history,))
            
            self._cache = list(reversed(cursor.fetchall()))
    
    def add_command(self, cmd: str):
        """
        Add a command to history.
        
        Args:
            cmd: The command string to add.
        """
        # Skip empty commands or duplicates of the last command
        cmd = cmd.strip()
        if not cmd:
            return
        
        if self._cache and self._cache[-1][1] == cmd:
            return
        
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (command, timestamp, session_id)
                VALUES (?, ?, ?)
            """, (cmd, timestamp, self.session_id))
            
            row_id = cursor.lastrowid
            conn.commit()
        
        # Update cache
        self._cache.append((row_id, cmd, timestamp, self.session_id))
        
        # Trim cache if it exceeds max_history
        if len(self._cache) > self.max_history:
            self._cache = self._cache[-self.max_history:]
        
        # Reset navigation position
        self.current_position = -1
        
        # Trim database if it exceeds max_history
        self._trim_history()
    
    def _trim_history(self):
        """Remove old entries if history exceeds max_history."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Count total entries
            cursor.execute("SELECT COUNT(*) FROM history")
            count = cursor.fetchone()[0]
            
            if count > self.max_history:
                # Delete oldest entries
                to_delete = count - self.max_history
                cursor.execute("""
                    DELETE FROM history 
                    WHERE id IN (
                        SELECT id FROM history 
                        ORDER BY id ASC 
                        LIMIT ?
                    )
                """, (to_delete,))
                conn.commit()
    
    def get_history(self, limit: Optional[int] = None, 
                    session_only: bool = False) -> List[str]:
        """
        Get command history.
        
        Args:
            limit: Maximum number of entries to return. If None, returns all.
            session_only: If True, return only commands from current session.
        
        Returns:
            List of command strings in chronological order.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if session_only:
                query = """
                    SELECT command FROM history 
                    WHERE session_id = ?
                    ORDER BY id ASC
                """
                params = [self.session_id]
            else:
                query = """
                    SELECT command FROM history 
                    ORDER BY id ASC
                """
                params = []
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            return [row[0] for row in cursor.fetchall()]
    
    def search_history(self, pattern: str, case_sensitive: bool = False,
                      limit: Optional[int] = 50) -> List[str]:
        """
        Search history for commands matching a pattern.
        
        Args:
            pattern: Search pattern (SQL LIKE pattern).
            case_sensitive: Whether search should be case-sensitive.
            limit: Maximum number of results to return.
        
        Returns:
            List of matching command strings.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if case_sensitive:
                # Use GLOB for case-sensitive search
                query = """
                    SELECT DISTINCT command FROM history
                    WHERE command GLOB ?
                    ORDER BY id DESC
                """
                search_pattern = f"*{pattern}*"
            else:
                query = """
                    SELECT DISTINCT command FROM history
                    WHERE command LIKE ? COLLATE NOCASE
                    ORDER BY id DESC
                """
                search_pattern = f"%{pattern}%"

            if limit:
                query += " LIMIT ?"
                params = [search_pattern, limit]
            else:
                params = [search_pattern]

            cursor.execute(query, params)
            return [row[0] for row in cursor.fetchall()]
    
    def get_previous(self) -> Optional[str]:
        """
        Get previous command in history (for up arrow navigation).
        
        Returns:
            Previous command string or None if at the beginning.
        """
        if not self._cache:
            return None
        
        if self.current_position == -1:
            self.current_position = len(self._cache) - 1
        elif self.current_position > 0:
            self.current_position -= 1
        
        if 0 <= self.current_position < len(self._cache):
            return self._cache[self.current_position][1]
        
        return None
    
    def get_next(self) -> Optional[str]:
        """
        Get next command in history (for down arrow navigation).
        
        Returns:
            Next command string or None if at the end.
        """
        if not self._cache or self.current_position == -1:
            return None
        
        if self.current_position < len(self._cache) - 1:
            self.current_position += 1
            return self._cache[self.current_position][1]
        else:
            self.current_position = -1
            return ""
    
    def reset_position(self):
        """Reset navigation position to the end of history."""
        self.current_position = -1
    
    def save_to_file(self, filename: str, format: str = "json",
                     session_only: bool = False):
        """
        Export history to a file.
        
        Args:
            filename: Path to the output file.
            format: Export format ('json' or 'text').
            session_only: If True, export only current session history.
        """
        history = self.get_history(session_only=session_only)
        
        if format == "json":
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if session_only:
                    cursor.execute("""
                        SELECT command, timestamp, session_id 
                        FROM history 
                        WHERE session_id = ?
                        ORDER BY id ASC
                    """, (self.session_id,))
                else:
                    cursor.execute("""
                        SELECT command, timestamp, session_id 
                        FROM history 
                        ORDER BY id ASC
                    """)
                
                data = [
                    {
                        "command": row[0],
                        "timestamp": row[1],
                        "session_id": row[2]
                    }
                    for row in cursor.fetchall()
                ]
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        elif format == "text":
            with open(filename, 'w', encoding='utf-8') as f:
                for cmd in history:
                    f.write(cmd + '\n')
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def load_from_file(self, filename: str, format: str = "json",
                      merge: bool = True):
        """
        Import history from a file.
        
        Args:
            filename: Path to the input file.
            format: Import format ('json' or 'text').
            merge: If True, merge with existing history. If False, replace.
        """
        if not merge:
            self.clear_history()
        
        if format == "json":
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for entry in data:
                    if isinstance(entry, dict):
                        cmd = entry.get("command", "")
                        timestamp = entry.get("timestamp", 
                                            datetime.now().isoformat())
                        session_id = entry.get("session_id", "imported")
                    else:
                        cmd = str(entry)
                        timestamp = datetime.now().isoformat()
                        session_id = "imported"
                    
                    if cmd.strip():
                        cursor.execute("""
                            INSERT INTO history (command, timestamp, session_id)
                            VALUES (?, ?, ?)
                        """, (cmd, timestamp, session_id))
                
                conn.commit()
        
        elif format == "text":
            with open(filename, 'r', encoding='utf-8') as f:
                commands = [line.strip() for line in f if line.strip()]
            
            timestamp = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for cmd in commands:
                    cursor.execute("""
                        INSERT INTO history (command, timestamp, session_id)
                        VALUES (?, ?, ?)
                    """, (cmd, timestamp, "imported"))
                
                conn.commit()
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Reload cache
        self._load_cache()
        self.reset_position()
    
    def clear_history(self, session_only: bool = False):
        """
        Clear command history.
        
        Args:
            session_only: If True, clear only current session. If False, clear all.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if session_only:
                cursor.execute("""
                    DELETE FROM history WHERE session_id = ?
                """, (self.session_id,))
            else:
                cursor.execute("DELETE FROM history")
            
            conn.commit()
        
        # Clear cache
        if session_only:
            self._cache = [entry for entry in self._cache 
                          if entry[3] != self.session_id]
        else:
            self._cache = []
        
        self.reset_position()
    
    def get_statistics(self) -> dict:
        """
        Get history statistics.
        
        Returns:
            Dictionary containing various statistics.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total commands
            cursor.execute("SELECT COUNT(*) FROM history")
            total = cursor.fetchone()[0]
            
            # Commands in current session
            cursor.execute("""
                SELECT COUNT(*) FROM history WHERE session_id = ?
            """, (self.session_id,))
            session_count = cursor.fetchone()[0]
            
            # Unique commands
            cursor.execute("SELECT COUNT(DISTINCT command) FROM history")
            unique = cursor.fetchone()[0]
            
            # Total sessions
            cursor.execute("SELECT COUNT(DISTINCT session_id) FROM history")
            sessions = cursor.fetchone()[0]
            
            # Most used commands
            cursor.execute("""
                SELECT command, COUNT(*) as count 
                FROM history 
                GROUP BY command 
                ORDER BY count DESC 
                LIMIT 10
            """)
            top_commands = cursor.fetchall()
            
            # First and last timestamps
            cursor.execute("""
                SELECT MIN(timestamp), MAX(timestamp) FROM history
            """)
            first, last = cursor.fetchone()
        
        return {
            "total_commands": total,
            "session_commands": session_count,
            "unique_commands": unique,
            "total_sessions": sessions,
            "top_commands": [{"command": cmd, "count": count} 
                           for cmd, count in top_commands],
            "first_command_time": first,
            "last_command_time": last,
            "current_session": self.session_id,
            "database_path": self.db_path
        }
    
    def get_session_list(self) -> List[Tuple[str, int, str, str]]:
        """
        Get list of all sessions with their details.
        
        Returns:
            List of tuples: (session_id, command_count, first_time, last_time)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    session_id,
                    COUNT(*) as count,
                    MIN(timestamp) as first_time,
                    MAX(timestamp) as last_time
                FROM history
                GROUP BY session_id
                ORDER BY first_time DESC
            """)
            return cursor.fetchall()
    
    def delete_session(self, session_id: str):
        """
        Delete all commands from a specific session.
        
        Args:
            session_id: The session ID to delete.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM history WHERE session_id = ?
            """, (session_id,))
            conn.commit()
        
        # Update cache
        self._load_cache()
        self.reset_position()
    
    def compact_database(self):
        """Compact the database by running VACUUM."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
    
    def __len__(self) -> int:
        """Return the total number of history entries."""
        return len(self._cache)
    
    def __repr__(self) -> str:
        """String representation of the HistoryManager."""
        return (f"HistoryManager(db_path='{self.db_path}', "
                f"entries={len(self._cache)}, "
                f"session='{self.session_id}')")


# Convenience function for testing
def demo():
    """Demonstration of HistoryManager capabilities."""
    print("=== HistoryManager Demo ===\n")
    
    # Create a temporary history manager
    import tempfile
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    
    hm = HistoryManager(db_path=temp_db.name)
    
    # Add some commands
    print("Adding commands...")
    commands = [
        "print('Hello, World!')",
        "x = 42",
        "import math",
        "math.sqrt(16)",
        "for i in range(5): print(i)",
        "x += 10",
        "print(x)"
    ]
    
    for cmd in commands:
        hm.add_command(cmd)
        print(f"  Added: {cmd}")
    
    # Get history
    print("\n--- Full History ---")
    for i, cmd in enumerate(hm.get_history(), 1):
        print(f"{i}. {cmd}")
    
    # Search history
    print("\n--- Search for 'print' ---")
    results = hm.search_history("print")
    for i, cmd in enumerate(results, 1):
        print(f"{i}. {cmd}")
    
    # Navigation
    print("\n--- Navigation (Up Arrow) ---")
    for _ in range(3):
        prev = hm.get_previous()
        print(f"  Previous: {prev}")
    
    print("\n--- Navigation (Down Arrow) ---")
    for _ in range(2):
        next_cmd = hm.get_next()
        print(f"  Next: {next_cmd}")
    
    # Statistics
    print("\n--- Statistics ---")
    stats = hm.get_statistics()
    for key, value in stats.items():
        if key != "top_commands":
            print(f"  {key}: {value}")
    
    # Export
    print("\n--- Export to JSON ---")
    json_file = temp_db.name + ".json"
    hm.save_to_file(json_file, format="json")
    print(f"  Exported to: {json_file}")
    
    # Clean up
    os.unlink(temp_db.name)
    os.unlink(json_file)
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    demo()
