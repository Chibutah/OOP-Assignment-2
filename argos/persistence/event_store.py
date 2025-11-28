"""
Event store implementations for event sourcing.
"""

import json
import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Iterator
from datetime import datetime, timezone
import uuid

from ..core.entities import Event, EventType
from ..core.interfaces import EventStore
from ..core.exceptions import EventSourcingError, PersistenceError
from .database import DatabaseManager


class FileEventStore(EventStore):
    """File-based event store implementation."""
    
    def __init__(self, base_path: str = "events"):
        self._base_path = base_path
        self._lock = threading.RLock()
        self._ensure_directory_exists()
    
    def _ensure_directory_exists(self) -> None:
        """Ensure the events directory exists."""
        os.makedirs(self._base_path, exist_ok=True)
    
    def _get_stream_path(self, stream_id: str) -> str:
        """Get file path for a stream."""
        return os.path.join(self._base_path, f"{stream_id}.jsonl")
    
    def _get_snapshot_path(self, stream_id: str) -> str:
        """Get file path for a snapshot."""
        return os.path.join(self._base_path, f"{stream_id}.snapshot.json")
    
    def append_event(self, event: Event) -> None:
        """Append an event to the store."""
        with self._lock:
            stream_path = self._get_stream_path(event.stream_id)
            
            try:
                with open(stream_path, "a", encoding="utf-8") as f:
                    event_data = {
                        "id": event.id,
                        "event_type": event.event_type.value,
                        "stream_id": event.stream_id,
                        "event_data": event.event_data,
                        "created_at": event.created_at.isoformat(),
                        "version": event.version,
                        "correlation_id": event.correlation_id,
                        "causation_id": event.causation_id
                    }
                    f.write(json.dumps(event_data) + "\n")
            except Exception as e:
                raise EventSourcingError(f"Failed to append event: {str(e)}")
    
    def get_events(self, stream_id: str, from_version: int = 0) -> List[Event]:
        """Get events for a stream."""
        with self._lock:
            stream_path = self._get_stream_path(stream_id)
            
            if not os.path.exists(stream_path):
                return []
            
            events = []
            try:
                with open(stream_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        if line_num <= from_version:
                            continue
                        
                        try:
                            event_data = json.loads(line.strip())
                            event = Event(
                                event_type=EventType(event_data["event_type"]),
                                stream_id=event_data["stream_id"],
                                event_data=event_data["event_data"],
                                entity_id=event_data["id"]
                            )
                            event._created_at = datetime.fromisoformat(event_data["created_at"])
                            event._version = event_data["version"]
                            event._correlation_id = event_data.get("correlation_id")
                            event._causation_id = event_data.get("causation_id")
                            events.append(event)
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            print(f"Warning: Skipping malformed event at line {line_num}: {e}")
                            continue
            except Exception as e:
                raise EventSourcingError(f"Failed to read events: {str(e)}")
            
            return events
    
    def get_snapshot(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest snapshot for a stream."""
        with self._lock:
            snapshot_path = self._get_snapshot_path(stream_id)
            
            if not os.path.exists(snapshot_path):
                return None
            
            try:
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                raise EventSourcingError(f"Failed to read snapshot: {str(e)}")
    
    def save_snapshot(self, stream_id: str, snapshot: Dict[str, Any]) -> None:
        """Save a snapshot for a stream."""
        with self._lock:
            snapshot_path = self._get_snapshot_path(stream_id)
            
            try:
                with open(snapshot_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, indent=2)
            except Exception as e:
                raise EventSourcingError(f"Failed to save snapshot: {str(e)}")
    
    def get_all_streams(self) -> List[str]:
        """Get all stream IDs."""
        with self._lock:
            streams = []
            for filename in os.listdir(self._base_path):
                if filename.endswith(".jsonl"):
                    stream_id = filename[:-6]  # Remove .jsonl extension
                    streams.append(stream_id)
            return streams
    
    def get_stream_version(self, stream_id: str) -> int:
        """Get the current version of a stream."""
        events = self.get_events(stream_id)
        return len(events)
    
    def delete_stream(self, stream_id: str) -> bool:
        """Delete a stream and its snapshot."""
        with self._lock:
            stream_path = self._get_stream_path(stream_id)
            snapshot_path = self._get_snapshot_path(stream_id)
            
            deleted = False
            if os.path.exists(stream_path):
                os.remove(stream_path)
                deleted = True
            
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
            
            return deleted


class DatabaseEventStore(EventStore):
    """Database-based event store implementation."""
    
    def __init__(self, database: DatabaseManager):
        self._database = database
        self._lock = threading.RLock()
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self) -> None:
        """Ensure event store tables exist."""
        if not self._database.table_exists("events"):
            schema = {
                "events": """
                    CREATE TABLE events (
                        id VARCHAR(255) PRIMARY KEY,
                        stream_id VARCHAR(255) NOT NULL,
                        event_type VARCHAR(100) NOT NULL,
                        event_data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        version INTEGER DEFAULT 1,
                        correlation_id VARCHAR(255),
                        causation_id VARCHAR(255),
                        INDEX idx_stream_id (stream_id),
                        INDEX idx_event_type (event_type),
                        INDEX idx_created_at (created_at)
                    )
                """,
                "snapshots": """
                    CREATE TABLE snapshots (
                        stream_id VARCHAR(255) PRIMARY KEY,
                        snapshot_data TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            }
            self._database.create_tables(schema)
    
    def append_event(self, event: Event) -> None:
        """Append an event to the store."""
        with self._lock:
            try:
                query = """
                    INSERT INTO events (id, stream_id, event_type, event_data, created_at, version, correlation_id, causation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                # Convert event data to JSON string
                event_data_json = json.dumps(event.event_data)
                
                params = (
                    event.id,
                    event.stream_id,
                    event.event_type.value,
                    event_data_json,
                    event.created_at.isoformat(),
                    event.version,
                    event.correlation_id,
                    event.causation_id
                )
                
                self._database.execute_update(query, params)
            except Exception as e:
                raise EventSourcingError(f"Failed to append event: {str(e)}")
    
    def get_events(self, stream_id: str, from_version: int = 0) -> List[Event]:
        """Get events for a stream."""
        with self._lock:
            try:
                query = """
                    SELECT id, event_type, stream_id, event_data, created_at, version, correlation_id, causation_id
                    FROM events
                    WHERE stream_id = ? AND version > ?
                    ORDER BY version ASC
                """
                
                results = self._database.execute_query(query, (stream_id, from_version))
                
                events = []
                for row in results:
                    event = Event(
                        event_type=EventType(row["event_type"]),
                        stream_id=row["stream_id"],
                        event_data=json.loads(row["event_data"]),
                        entity_id=row["id"]
                    )
                    event._created_at = datetime.fromisoformat(row["created_at"])
                    event._version = row["version"]
                    event._correlation_id = row.get("correlation_id")
                    event._causation_id = row.get("causation_id")
                    events.append(event)
                
                return events
            except Exception as e:
                raise EventSourcingError(f"Failed to get events: {str(e)}")
    
    def get_snapshot(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest snapshot for a stream."""
        with self._lock:
            try:
                query = "SELECT snapshot_data FROM snapshots WHERE stream_id = ?"
                results = self._database.execute_query(query, (stream_id,))
                
                if results:
                    return json.loads(results[0]["snapshot_data"])
                return None
            except Exception as e:
                raise EventSourcingError(f"Failed to get snapshot: {str(e)}")
    
    def save_snapshot(self, stream_id: str, snapshot: Dict[str, Any]) -> None:
        """Save a snapshot for a stream."""
        with self._lock:
            try:
                # Get current stream version
                version_query = "SELECT MAX(version) as max_version FROM events WHERE stream_id = ?"
                version_results = self._database.execute_query(version_query, (stream_id,))
                version = version_results[0]["max_version"] if version_results and version_results[0]["max_version"] else 0
                
                # Insert or update snapshot
                query = """
                    INSERT OR REPLACE INTO snapshots (stream_id, snapshot_data, version, created_at)
                    VALUES (?, ?, ?, ?)
                """
                
                snapshot_data_json = json.dumps(snapshot)
                params = (stream_id, snapshot_data_json, version, datetime.now(timezone.utc).isoformat())
                
                self._database.execute_update(query, params)
            except Exception as e:
                raise EventSourcingError(f"Failed to save snapshot: {str(e)}")
    
    def get_all_streams(self) -> List[str]:
        """Get all stream IDs."""
        with self._lock:
            try:
                query = "SELECT DISTINCT stream_id FROM events ORDER BY stream_id"
                results = self._database.execute_query(query)
                return [row["stream_id"] for row in results]
            except Exception as e:
                raise EventSourcingError(f"Failed to get streams: {str(e)}")
    
    def get_stream_version(self, stream_id: str) -> int:
        """Get the current version of a stream."""
        with self._lock:
            try:
                query = "SELECT MAX(version) as max_version FROM events WHERE stream_id = ?"
                results = self._database.execute_query(query, (stream_id,))
                return results[0]["max_version"] if results and results[0]["max_version"] else 0
            except Exception as e:
                raise EventSourcingError(f"Failed to get stream version: {str(e)}")
    
    def get_events_by_type(self, event_type: EventType, limit: Optional[int] = None) -> List[Event]:
        """Get events by type."""
        with self._lock:
            try:
                query = """
                    SELECT id, event_type, stream_id, event_data, created_at, version, correlation_id, causation_id
                    FROM events
                    WHERE event_type = ?
                    ORDER BY created_at ASC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                results = self._database.execute_query(query, (event_type.value,))
                
                events = []
                for row in results:
                    event = Event(
                        event_type=EventType(row["event_type"]),
                        stream_id=row["stream_id"],
                        event_data=json.loads(row["event_data"]),
                        entity_id=row["id"]
                    )
                    event._created_at = datetime.fromisoformat(row["created_at"])
                    event._version = row["version"]
                    event._correlation_id = row.get("correlation_id")
                    event._causation_id = row.get("causation_id")
                    events.append(event)
                
                return events
            except Exception as e:
                raise EventSourcingError(f"Failed to get events by type: {str(e)}")
    
    def delete_stream(self, stream_id: str) -> bool:
        """Delete a stream and its snapshot."""
        with self._lock:
            try:
                # Delete events
                events_query = "DELETE FROM events WHERE stream_id = ?"
                events_deleted = self._database.execute_update(events_query, (stream_id,))
                
                # Delete snapshot
                snapshot_query = "DELETE FROM snapshots WHERE stream_id = ?"
                self._database.execute_update(snapshot_query, (stream_id,))
                
                return events_deleted > 0
            except Exception as e:
                raise EventSourcingError(f"Failed to delete stream: {str(e)}")


class EventStoreFactory:
    """Factory for creating event store instances."""
    
    @staticmethod
    def create_event_store(store_type: str, **kwargs) -> EventStore:
        """Create an event store instance based on type."""
        if store_type.lower() == "file":
            return FileEventStore(**kwargs)
        elif store_type.lower() == "database":
            return DatabaseEventStore(**kwargs)
        else:
            raise ConfigurationError(f"Unsupported event store type: {store_type}")
