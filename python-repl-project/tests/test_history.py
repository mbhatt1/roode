"""
Tests for the HistoryManager class.
"""

import os
import json
import tempfile
import unittest
from pathlib import Path

from src.pyrepl.history import HistoryManager


class TestHistoryManager(unittest.TestCase):
    """Test cases for HistoryManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.history = HistoryManager(db_path=self.db_path)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary database
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_initialization(self):
        """Test HistoryManager initialization."""
        self.assertIsNotNone(self.history)
        self.assertEqual(len(self.history), 0)
        self.assertTrue(os.path.exists(self.db_path))
    
    def test_add_command(self):
        """Test adding commands to history."""
        self.history.add_command("print('Hello')")
        self.assertEqual(len(self.history), 1)
        
        self.history.add_command("x = 42")
        self.assertEqual(len(self.history), 2)
        
        # Test duplicate filtering
        self.history.add_command("x = 42")
        self.assertEqual(len(self.history), 2)
        
        # Test empty command
        self.history.add_command("")
        self.assertEqual(len(self.history), 2)
        
        self.history.add_command("   ")
        self.assertEqual(len(self.history), 2)
    
    def test_get_history(self):
        """Test retrieving command history."""
        commands = ["cmd1", "cmd2", "cmd3"]
        for cmd in commands:
            self.history.add_command(cmd)
        
        history = self.history.get_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history, commands)
    
    def test_get_history_with_limit(self):
        """Test retrieving limited history."""
        for i in range(10):
            self.history.add_command(f"command_{i}")
        
        history = self.history.get_history(limit=5)
        self.assertEqual(len(history), 5)
    
    def test_search_history(self):
        """Test searching command history."""
        commands = [
            "print('Hello')",
            "x = 42",
            "print(x)",
            "import math",
            "print(math.pi)"
        ]
        
        for cmd in commands:
            self.history.add_command(cmd)
        
        # Search for 'print'
        results = self.history.search_history("print")
        self.assertEqual(len(results), 3)
        
        # Search for 'math'
        results = self.history.search_history("math")
        self.assertEqual(len(results), 2)
        
        # Search for non-existent pattern
        results = self.history.search_history("nonexistent")
        self.assertEqual(len(results), 0)
    
    def test_search_history_case_sensitivity(self):
        """Test case-sensitive and case-insensitive search."""
        self.history.add_command("PRINT('Hello')")
        self.history.add_command("print('World')")
        
        # Case-insensitive (default)
        results = self.history.search_history("print", case_sensitive=False)
        self.assertEqual(len(results), 2)
        
        # Case-sensitive
        results = self.history.search_history("print", case_sensitive=True)
        self.assertEqual(len(results), 1)
    
    def test_navigation_previous(self):
        """Test backward navigation through history."""
        commands = ["cmd1", "cmd2", "cmd3"]
        for cmd in commands:
            self.history.add_command(cmd)
        
        # Navigate backwards
        self.assertEqual(self.history.get_previous(), "cmd3")
        self.assertEqual(self.history.get_previous(), "cmd2")
        self.assertEqual(self.history.get_previous(), "cmd1")
        self.assertEqual(self.history.get_previous(), "cmd1")  # At beginning
    
    def test_navigation_next(self):
        """Test forward navigation through history."""
        commands = ["cmd1", "cmd2", "cmd3"]
        for cmd in commands:
            self.history.add_command(cmd)
        
        # Go back first
        self.history.get_previous()
        self.history.get_previous()
        
        # Navigate forward
        self.assertEqual(self.history.get_next(), "cmd3")
        self.assertEqual(self.history.get_next(), "")  # At end
    
    def test_navigation_reset(self):
        """Test resetting navigation position."""
        self.history.add_command("cmd1")
        self.history.add_command("cmd2")
        
        self.history.get_previous()
        self.history.reset_position()
        
        self.assertEqual(self.history.current_position, -1)
    
    def test_save_to_json(self):
        """Test exporting history to JSON file."""
        commands = ["cmd1", "cmd2", "cmd3"]
        for cmd in commands:
            self.history.add_command(cmd)
        
        json_file = self.db_path + ".json"
        try:
            self.history.save_to_file(json_file, format="json")
            self.assertTrue(os.path.exists(json_file))
            
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            self.assertEqual(len(data), 3)
            self.assertEqual([entry["command"] for entry in data], commands)
        finally:
            if os.path.exists(json_file):
                os.unlink(json_file)
    
    def test_save_to_text(self):
        """Test exporting history to text file."""
        commands = ["cmd1", "cmd2", "cmd3"]
        for cmd in commands:
            self.history.add_command(cmd)
        
        text_file = self.db_path + ".txt"
        try:
            self.history.save_to_file(text_file, format="text")
            self.assertTrue(os.path.exists(text_file))
            
            with open(text_file, 'r') as f:
                lines = [line.strip() for line in f]
            
            self.assertEqual(lines, commands)
        finally:
            if os.path.exists(text_file):
                os.unlink(text_file)
    
    def test_load_from_json(self):
        """Test importing history from JSON file."""
        # Create test data
        data = [
            {"command": "cmd1", "timestamp": "2024-01-01T10:00:00", "session_id": "test"},
            {"command": "cmd2", "timestamp": "2024-01-01T10:01:00", "session_id": "test"}
        ]
        
        json_file = self.db_path + ".json"
        try:
            with open(json_file, 'w') as f:
                json.dump(data, f)
            
            self.history.load_from_file(json_file, format="json")
            history = self.history.get_history()
            
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0], "cmd1")
            self.assertEqual(history[1], "cmd2")
        finally:
            if os.path.exists(json_file):
                os.unlink(json_file)
    
    def test_load_from_text(self):
        """Test importing history from text file."""
        commands = ["cmd1", "cmd2", "cmd3"]
        
        text_file = self.db_path + ".txt"
        try:
            with open(text_file, 'w') as f:
                for cmd in commands:
                    f.write(cmd + '\n')
            
            self.history.load_from_file(text_file, format="text")
            history = self.history.get_history()
            
            self.assertEqual(len(history), 3)
            self.assertEqual(history, commands)
        finally:
            if os.path.exists(text_file):
                os.unlink(text_file)
    
    def test_clear_history(self):
        """Test clearing all history."""
        self.history.add_command("cmd1")
        self.history.add_command("cmd2")
        
        self.assertEqual(len(self.history), 2)
        
        self.history.clear_history()
        
        self.assertEqual(len(self.history), 0)
        self.assertEqual(self.history.get_history(), [])
    
    def test_clear_session_only(self):
        """Test clearing only current session history."""
        # Add commands to current session
        self.history.add_command("cmd1")
        self.history.add_command("cmd2")
        
        # Simulate commands from another session (by directly inserting)
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (command, timestamp, session_id)
                VALUES (?, ?, ?)
            """, ("other_cmd", "2024-01-01T10:00:00", "other_session"))
            conn.commit()
        
        # Reload cache
        self.history._load_cache()
        
        # Clear only current session
        self.history.clear_history(session_only=True)
        
        # Should still have the other session's command
        all_history = self.history.get_history()
        self.assertEqual(len(all_history), 1)
        self.assertEqual(all_history[0], "other_cmd")
    
    def test_get_statistics(self):
        """Test getting history statistics."""
        commands = ["cmd1", "cmd2", "cmd1"]  # cmd1 repeated
        for cmd in commands:
            self.history.add_command(cmd)
        
        stats = self.history.get_statistics()
        
        self.assertEqual(stats["total_commands"], 3)
        self.assertEqual(stats["session_commands"], 3)
        self.assertEqual(stats["unique_commands"], 2)
        self.assertEqual(stats["total_sessions"], 1)
        self.assertIsNotNone(stats["current_session"])
        self.assertEqual(stats["database_path"], self.db_path)
    
    def test_get_session_list(self):
        """Test getting list of sessions."""
        self.history.add_command("cmd1")
        
        sessions = self.history.get_session_list()
        
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0][0], self.history.session_id)
        self.assertEqual(sessions[0][1], 1)  # command count
    
    def test_delete_session(self):
        """Test deleting a specific session."""
        # Add commands to current session
        self.history.add_command("cmd1")
        
        session_id = self.history.session_id
        
        # Delete the session
        self.history.delete_session(session_id)
        
        # History should be empty
        self.assertEqual(len(self.history.get_history()), 0)
    
    def test_max_history_limit(self):
        """Test that history respects max_history limit."""
        # Create manager with small limit
        small_history = HistoryManager(
            db_path=self.db_path + ".small",
            max_history=5
        )
        
        try:
            # Add more commands than limit
            for i in range(10):
                small_history.add_command(f"cmd_{i}")
            
            # Should only keep last 5
            history = small_history.get_history()
            self.assertLessEqual(len(history), 5)
        finally:
            if os.path.exists(self.db_path + ".small"):
                os.unlink(self.db_path + ".small")
    
    def test_session_only_history(self):
        """Test getting history for current session only."""
        # Add commands to current session
        self.history.add_command("current1")
        self.history.add_command("current2")
        
        # Add command from another session (simulate)
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (command, timestamp, session_id)
                VALUES (?, ?, ?)
            """, ("other_cmd", "2024-01-01T10:00:00", "other_session"))
            conn.commit()
        
        # Get session-only history
        session_history = self.history.get_history(session_only=True)
        
        self.assertEqual(len(session_history), 2)
        self.assertIn("current1", session_history)
        self.assertIn("current2", session_history)
        self.assertNotIn("other_cmd", session_history)
    
    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.history)
        self.assertIn("HistoryManager", repr_str)
        self.assertIn(self.db_path, repr_str)
        self.assertIn(self.history.session_id, repr_str)
    
    def test_compact_database(self):
        """Test database compaction."""
        # Add and remove commands
        for i in range(10):
            self.history.add_command(f"cmd_{i}")
        
        self.history.clear_history()
        
        # Compact should run without errors
        self.history.compact_database()
        self.assertTrue(os.path.exists(self.db_path))


class TestHistoryManagerIntegration(unittest.TestCase):
    """Integration tests for HistoryManager."""
    
    def test_persistence_across_instances(self):
        """Test that history persists across different instances."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        db_path = temp_db.name
        
        try:
            # Create first instance and add commands
            history1 = HistoryManager(db_path=db_path)
            history1.add_command("cmd1")
            history1.add_command("cmd2")
            
            # Create second instance
            history2 = HistoryManager(db_path=db_path)
            
            # Should see commands from first instance
            history = history2.get_history()
            self.assertIn("cmd1", history)
            self.assertIn("cmd2", history)
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_concurrent_sessions(self):
        """Test handling multiple sessions in the same database."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        db_path = temp_db.name
        
        try:
            # Create two instances (simulating two sessions)
            session1 = HistoryManager(db_path=db_path)
            session2 = HistoryManager(db_path=db_path)
            
            # Add commands to each session
            session1.add_command("session1_cmd1")
            session2.add_command("session2_cmd1")
            session1.add_command("session1_cmd2")
            
            # Each should see their own session commands
            history1 = session1.get_history(session_only=True)
            history2 = session2.get_history(session_only=True)
            
            self.assertEqual(len(history1), 2)
            self.assertEqual(len(history2), 1)
            
            # But all commands should be in global history
            all_history = session1.get_history(session_only=False)
            self.assertEqual(len(all_history), 3)
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_export_import_roundtrip(self):
        """Test that export followed by import preserves data."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        db_path = temp_db.name
        
        json_file = db_path + ".json"
        
        try:
            # Create history and add commands
            history1 = HistoryManager(db_path=db_path)
            commands = ["cmd1", "cmd2", "cmd3"]
            for cmd in commands:
                history1.add_command(cmd)
            
            # Export
            history1.save_to_file(json_file, format="json")
            
            # Create new instance and import
            history2 = HistoryManager(db_path=db_path + ".new")
            history2.load_from_file(json_file, format="json")
            
            # Compare
            original = history1.get_history()
            imported = history2.get_history()
            
            self.assertEqual(original, imported)
        finally:
            for path in [db_path, db_path + ".new", json_file]:
                if os.path.exists(path):
                    os.unlink(path)


if __name__ == "__main__":
    unittest.main()
