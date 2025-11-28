"""
Snapshot manager for event sourcing and state reconstruction.
"""

import json
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from datetime import datetime, timezone, timedelta

from ..core.entities import AbstractEntity, Event, EventType
from ..core.interfaces import EventStore
from ..core.exceptions import PersistenceError, EventSourcingError
from .repositories import BaseRepository

T = TypeVar('T', bound=AbstractEntity)


class SnapshotManager:
    """Manages snapshots for event sourcing and state reconstruction."""
    
    def __init__(self, event_store: EventStore, repositories: Dict[str, BaseRepository]):
        self._event_store = event_store
        self._repositories = repositories
        self._lock = threading.RLock()
        self._snapshot_frequency = 100  # Create snapshot every 100 events
        self._max_snapshot_age_days = 30  # Keep snapshots for 30 days
    
    def create_snapshot(self, stream_id: str, entity_id: str, 
                       entity_type: str) -> Optional[Dict[str, Any]]:
        """Create a snapshot for an entity stream."""
        with self._lock:
            try:
                # Get all events for the stream
                events = self._event_store.get_events(stream_id)
                
                if not events:
                    return None
                
                # Find the entity in the appropriate repository
                if entity_type not in self._repositories:
                    raise PersistenceError(f"No repository found for entity type: {entity_type}")
                
                repository = self._repositories[entity_type]
                entity = repository.find_by_id(entity_id)
                
                if not entity:
                    return None
                
                # Create snapshot data
                snapshot_data = {
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "stream_id": stream_id,
                    "version": len(events),
                    "entity_data": entity.to_dict(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "event_count": len(events)
                }
                
                # Save snapshot
                self._event_store.save_snapshot(stream_id, snapshot_data)
                
                return snapshot_data
                
            except Exception as e:
                raise PersistenceError(f"Failed to create snapshot: {str(e)}")
    
    def restore_from_snapshot(self, stream_id: str, entity_type: str) -> Optional[AbstractEntity]:
        """Restore an entity from snapshot."""
        with self._lock:
            try:
                # Get snapshot
                snapshot = self._event_store.get_snapshot(stream_id)
                if not snapshot:
                    return None
                
                # Get entity ID from snapshot
                entity_id = snapshot.get("entity_id")
                if not entity_id:
                    return None
                
                # Restore entity from repository
                if entity_type not in self._repositories:
                    raise PersistenceError(f"No repository found for entity type: {entity_type}")
                
                repository = self._repositories[entity_type]
                entity = repository.find_by_id(entity_id)
                
                return entity
                
            except Exception as e:
                raise PersistenceError(f"Failed to restore from snapshot: {str(e)}")
    
    def replay_events(self, stream_id: str, entity_type: str, 
                     from_version: int = 0) -> Optional[AbstractEntity]:
        """Replay events to reconstruct entity state."""
        with self._lock:
            try:
                # Get events from the specified version
                events = self._event_store.get_events(stream_id, from_version)
                
                if not events:
                    return None
                
                # Get the first event to determine entity ID
                first_event = events[0]
                entity_id = first_event.event_data.get("entity_id")
                
                if not entity_id:
                    return None
                
                # Start with snapshot if available and from_version is 0
                entity = None
                if from_version == 0:
                    entity = self.restore_from_snapshot(stream_id, entity_type)
                
                # If no snapshot, create entity from first event
                if not entity:
                    entity = self._create_entity_from_event(first_event, entity_type)
                
                # Apply remaining events
                for event in events[1:]:
                    entity = self._apply_event_to_entity(entity, event)
                
                return entity
                
            except Exception as e:
                raise PersistenceError(f"Failed to replay events: {str(e)}")
    
    def _create_entity_from_event(self, event: Event, entity_type: str) -> Optional[AbstractEntity]:
        """Create an entity from the first event."""
        try:
            if entity_type not in self._repositories:
                return None
            
            repository = self._repositories[entity_type]
            
            # This is a simplified approach - in practice, you'd have more sophisticated
            # event-to-entity mapping logic
            if hasattr(repository, '_entity_from_dict'):
                entity_data = event.event_data
                entity_data["id"] = event.event_data.get("entity_id", event.id)
                return repository._entity_from_dict(entity_data)
            
            return None
            
        except Exception as e:
            raise PersistenceError(f"Failed to create entity from event: {str(e)}")
    
    def _apply_event_to_entity(self, entity: AbstractEntity, event: Event) -> AbstractEntity:
        """Apply an event to an entity to update its state."""
        try:
            event_data = event.event_data
            event_type = event.event_type
            
            # Apply event based on type
            if event_type == EventType.ENROLLMENT:
                self._apply_enrollment_event(entity, event_data)
            elif event_type == EventType.GRADING:
                self._apply_grading_event(entity, event_data)
            elif event_type == EventType.FACILITY_ACCESS:
                self._apply_facility_access_event(entity, event_data)
            elif event_type == EventType.SYSTEM_ALERT:
                self._apply_system_alert_event(entity, event_data)
            elif event_type == EventType.POLICY_CHANGE:
                self._apply_policy_change_event(entity, event_data)
            
            # Update entity metadata
            entity._updated_at = event.created_at
            entity._version += 1
            
            return entity
            
        except Exception as e:
            raise PersistenceError(f"Failed to apply event to entity: {str(e)}")
    
    def _apply_enrollment_event(self, entity: AbstractEntity, event_data: Dict[str, Any]) -> None:
        """Apply enrollment event to entity."""
        if hasattr(entity, 'enroll_in_section'):
            section_id = event_data.get('section_id')
            if section_id:
                entity.enroll_in_section(section_id)
        elif hasattr(entity, 'add_enrollment'):
            section_id = event_data.get('section_id')
            if section_id:
                entity.add_enrollment(section_id)
    
    def _apply_grading_event(self, entity: AbstractEntity, event_data: Dict[str, Any]) -> None:
        """Apply grading event to entity."""
        if hasattr(entity, 'update_gpa'):
            gpa = event_data.get('gpa')
            if gpa is not None:
                entity.update_gpa(gpa)
    
    def _apply_facility_access_event(self, entity: AbstractEntity, event_data: Dict[str, Any]) -> None:
        """Apply facility access event to entity."""
        # This would implement facility access logic
        pass
    
    def _apply_system_alert_event(self, entity: AbstractEntity, event_data: Dict[str, Any]) -> None:
        """Apply system alert event to entity."""
        # This would implement system alert handling
        pass
    
    def _apply_policy_change_event(self, entity: AbstractEntity, event_data: Dict[str, Any]) -> None:
        """Apply policy change event to entity."""
        # This would implement policy change handling
        pass
    
    def should_create_snapshot(self, stream_id: str) -> bool:
        """Check if a snapshot should be created for a stream."""
        with self._lock:
            try:
                # Get current stream version
                current_version = self._event_store.get_stream_version(stream_id)
                
                # Get snapshot version
                snapshot = self._event_store.get_snapshot(stream_id)
                snapshot_version = snapshot.get("version", 0) if snapshot else 0
                
                # Create snapshot if enough events have occurred
                return (current_version - snapshot_version) >= self._snapshot_frequency
                
            except Exception as e:
                print(f"Error checking snapshot need: {e}")
                return False
    
    def cleanup_old_snapshots(self) -> int:
        """Clean up old snapshots."""
        with self._lock:
            try:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=self._max_snapshot_age_days)
                cleaned_count = 0
                
                # Get all streams
                streams = self._event_store.get_all_streams()
                
                for stream_id in streams:
                    snapshot = self._event_store.get_snapshot(stream_id)
                    if snapshot:
                        created_at = datetime.fromisoformat(snapshot.get("created_at", ""))
                        if created_at < cutoff_date:
                            # Delete old snapshot
                            self._event_store.save_snapshot(stream_id, {})
                            cleaned_count += 1
                
                return cleaned_count
                
            except Exception as e:
                print(f"Error cleaning up snapshots: {e}")
                return 0
    
    def get_snapshot_statistics(self) -> Dict[str, Any]:
        """Get snapshot statistics."""
        with self._lock:
            try:
                streams = self._event_store.get_all_streams()
                total_snapshots = 0
                total_events = 0
                
                for stream_id in streams:
                    snapshot = self._event_store.get_snapshot(stream_id)
                    if snapshot:
                        total_snapshots += 1
                        total_events += snapshot.get("event_count", 0)
                
                return {
                    "total_streams": len(streams),
                    "total_snapshots": total_snapshots,
                    "total_events": total_events,
                    "snapshot_frequency": self._snapshot_frequency,
                    "max_snapshot_age_days": self._max_snapshot_age_days
                }
                
            except Exception as e:
                print(f"Error getting snapshot statistics: {e}")
                return {
                    "total_streams": 0,
                    "total_snapshots": 0,
                    "total_events": 0,
                    "snapshot_frequency": self._snapshot_frequency,
                    "max_snapshot_age_days": self._max_snapshot_age_days
                }
    
    def set_snapshot_frequency(self, frequency: int) -> None:
        """Set snapshot creation frequency."""
        with self._lock:
            self._snapshot_frequency = max(1, frequency)
    
    def set_max_snapshot_age(self, days: int) -> None:
        """Set maximum snapshot age in days."""
        with self._lock:
            self._max_snapshot_age_days = max(1, days)
    
    def create_snapshots_for_all_streams(self) -> Dict[str, bool]:
        """Create snapshots for all streams that need them."""
        with self._lock:
            results = {}
            streams = self._event_store.get_all_streams()
            
            for stream_id in streams:
                try:
                    if self.should_create_snapshot(stream_id):
                        # Determine entity type from stream ID or first event
                        events = self._event_store.get_events(stream_id, 0, 1)
                        if events:
                            entity_type = events[0].event_data.get("entity_type", "unknown")
                            entity_id = events[0].event_data.get("entity_id", stream_id)
                            
                            snapshot = self.create_snapshot(stream_id, entity_id, entity_type)
                            results[stream_id] = snapshot is not None
                        else:
                            results[stream_id] = False
                    else:
                        results[stream_id] = False
                except Exception as e:
                    print(f"Error creating snapshot for stream {stream_id}: {e}")
                    results[stream_id] = False
            
            return results
