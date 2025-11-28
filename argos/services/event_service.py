"""
Event service for event sourcing and publish/subscribe patterns.
"""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Union
import uuid
import json
from datetime import datetime, timezone

from ..core.entities import Event, EventType
from ..core.interfaces import EventHandler, EventStore
from ..core.exceptions import EventSourcingError, ValidationError
from .concurrency_manager import ConcurrencyManager, EventStream


class EventProcessingStatus(Enum):
    """Status of event processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class EventProcessingResult:
    """Result of event processing."""
    success: bool
    processing_time: float
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class EventSubscription:
    """Event subscription information."""
    subscriber_id: str
    event_types: Set[EventType]
    handler: Callable
    filter_func: Optional[Callable] = None
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class InMemoryEventStore(EventStore):
    """In-memory implementation of event store."""
    
    def __init__(self):
        self._events: Dict[str, List[Event]] = defaultdict(list)
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def append_event(self, event: Event) -> None:
        """Append an event to the store."""
        with self._lock:
            self._events[event.stream_id].append(event)
    
    def get_events(self, stream_id: str, from_version: int = 0) -> List[Event]:
        """Get events for a stream."""
        with self._lock:
            events = self._events.get(stream_id, [])
            return events[from_version:]
    
    def get_snapshot(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest snapshot for a stream."""
        with self._lock:
            return self._snapshots.get(stream_id)
    
    def save_snapshot(self, stream_id: str, snapshot: Dict[str, Any]) -> None:
        """Save a snapshot for a stream."""
        with self._lock:
            self._snapshots[stream_id] = snapshot


class EventProcessor(ABC):
    """Abstract base class for event processors."""
    
    @abstractmethod
    def process_event(self, event: Event) -> EventProcessingResult:
        """Process a single event."""
        pass
    
    @abstractmethod
    def can_process(self, event_type: EventType) -> bool:
        """Check if this processor can handle the event type."""
        pass


class EnrollmentEventProcessor(EventProcessor):
    """Processor for enrollment events."""
    
    def __init__(self, enrollment_service):
        self._enrollment_service = enrollment_service
    
    def process_event(self, event: Event) -> EventProcessingResult:
        """Process enrollment event."""
        start_time = time.time()
        
        try:
            event_data = event.event_data
            
            if event.event_type == EventType.ENROLLMENT:
                # Update enrollment statistics
                # This would integrate with the enrollment service
                pass
            
            processing_time = time.time() - start_time
            return EventProcessingResult(
                success=True,
                processing_time=processing_time
            )
        
        except Exception as e:
            processing_time = time.time() - start_time
            return EventProcessingResult(
                success=False,
                processing_time=processing_time,
                error_message=str(e)
            )
    
    def can_process(self, event_type: EventType) -> bool:
        """Check if this processor can handle the event type."""
        return event_type == EventType.ENROLLMENT


class SchedulingEventProcessor(EventProcessor):
    """Processor for scheduling events."""
    
    def __init__(self, scheduler_service):
        self._scheduler_service = scheduler_service
    
    def process_event(self, event: Event) -> EventProcessingResult:
        """Process scheduling event."""
        start_time = time.time()
        
        try:
            event_data = event.event_data
            
            if event.event_type == EventType.SYSTEM_ALERT:
                # Handle scheduling alerts
                pass
            
            processing_time = time.time() - start_time
            return EventProcessingResult(
                success=True,
                processing_time=processing_time
            )
        
        except Exception as e:
            processing_time = time.time() - start_time
            return EventProcessingResult(
                success=False,
                processing_time=processing_time,
                error_message=str(e)
            )
    
    def can_process(self, event_type: EventType) -> bool:
        """Check if this processor can handle the event type."""
        return event_type in [EventType.SYSTEM_ALERT, EventType.POLICY_CHANGE]


class EventService:
    """Service for managing events and event sourcing."""
    
    def __init__(self, concurrency_manager: ConcurrencyManager):
        self._concurrency_manager = concurrency_manager
        self._event_store = InMemoryEventStore()
        self._event_streams: Dict[str, EventStream] = {}
        self._subscriptions: Dict[str, EventSubscription] = {}
        self._processors: List[EventProcessor] = []
        self._processing_queue: deque = deque()
        self._processing_results: Dict[str, EventProcessingResult] = {}
        self._lock = threading.RLock()
        
        # Start background processing
        self._processing_thread = threading.Thread(target=self._process_events, daemon=True)
        self._processing_thread.start()
    
    def create_event_stream(self, stream_name: str) -> EventStream:
        """Create a new event stream."""
        with self._lock:
            if stream_name in self._event_streams:
                return self._event_streams[stream_name]
            
            stream = EventStream(stream_name)
            self._event_streams[stream_name] = stream
            return stream
    
    def get_event_stream(self, stream_name: str) -> Optional[EventStream]:
        """Get an existing event stream."""
        with self._lock:
            return self._event_streams.get(stream_name)
    
    def publish_event(self, event: Event) -> None:
        """Publish an event to the system."""
        with self._lock:
            # Store the event
            self._event_store.append_event(event)
            
            # Add to processing queue
            self._processing_queue.append(event)
            
            # Publish to relevant streams
            stream = self._event_streams.get(event.stream_id)
            if stream:
                stream.publish(event.event_data)
            
            # Notify subscribers
            self._notify_subscribers(event)
    
    def subscribe(self, subscriber_id: str, event_types: Set[EventType], 
                 handler: Callable, filter_func: Optional[Callable] = None) -> None:
        """Subscribe to events."""
        with self._lock:
            subscription = EventSubscription(
                subscriber_id=subscriber_id,
                event_types=event_types,
                handler=handler,
                filter_func=filter_func
            )
            self._subscriptions[subscriber_id] = subscription
    
    def unsubscribe(self, subscriber_id: str) -> None:
        """Unsubscribe from events."""
        with self._lock:
            self._subscriptions.pop(subscriber_id, None)
    
    def add_processor(self, processor: EventProcessor) -> None:
        """Add an event processor."""
        with self._lock:
            self._processors.append(processor)
    
    def remove_processor(self, processor: EventProcessor) -> None:
        """Remove an event processor."""
        with self._lock:
            if processor in self._processors:
                self._processors.remove(processor)
    
    def _notify_subscribers(self, event: Event) -> None:
        """Notify all relevant subscribers."""
        for subscription in self._subscriptions.values():
            if event.event_type in subscription.event_types:
                try:
                    # Apply filter if provided
                    if subscription.filter_func and not subscription.filter_func(event):
                        continue
                    
                    subscription.handler(event)
                except Exception as e:
                    print(f"Error notifying subscriber {subscription.subscriber_id}: {e}")
    
    def _process_events(self) -> None:
        """Background thread for processing events."""
        while True:
            try:
                if self._processing_queue:
                    event = self._processing_queue.popleft()
                    self._process_single_event(event)
                else:
                    time.sleep(0.01)  # Small delay when no events
            except Exception as e:
                print(f"Error in event processing: {e}")
                time.sleep(0.1)
    
    def _process_single_event(self, event: Event) -> None:
        """Process a single event."""
        event_id = str(uuid.uuid4())
        
        # Find suitable processors
        suitable_processors = [p for p in self._processors if p.can_process(event.event_type)]
        
        if not suitable_processors:
            # No processor found, mark as failed
            self._processing_results[event_id] = EventProcessingResult(
                success=False,
                processing_time=0.0,
                error_message="No suitable processor found"
            )
            return
        
        # Process with all suitable processors
        for processor in suitable_processors:
            try:
                result = processor.process_event(event)
                self._processing_results[event_id] = result
            except Exception as e:
                self._processing_results[event_id] = EventProcessingResult(
                    success=False,
                    processing_time=0.0,
                    error_message=str(e)
                )
    
    def get_events(self, stream_id: str, from_version: int = 0) -> List[Event]:
        """Get events for a stream."""
        return self._event_store.get_events(stream_id, from_version)
    
    def get_snapshot(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get snapshot for a stream."""
        return self._event_store.get_snapshot(stream_id)
    
    def save_snapshot(self, stream_id: str, snapshot: Dict[str, Any]) -> None:
        """Save snapshot for a stream."""
        self._event_store.save_snapshot(stream_id, snapshot)
    
    def replay_events(self, stream_id: str, from_version: int = 0) -> List[Event]:
        """Replay events from a stream."""
        return self.get_events(stream_id, from_version)
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get event processing statistics."""
        with self._lock:
            total_processed = len(self._processing_results)
            successful = sum(1 for r in self._processing_results.values() if r.success)
            failed = total_processed - successful
            
            avg_processing_time = 0.0
            if total_processed > 0:
                total_time = sum(r.processing_time for r in self._processing_results.values())
                avg_processing_time = total_time / total_processed
            
            return {
                'total_processed': total_processed,
                'successful': successful,
                'failed': failed,
                'success_rate': successful / max(total_processed, 1),
                'avg_processing_time': avg_processing_time,
                'queue_size': len(self._processing_queue),
                'active_subscriptions': len(self._subscriptions),
                'active_processors': len(self._processors)
            }
    
    def get_event_streams(self) -> List[str]:
        """Get list of all event streams."""
        with self._lock:
            return list(self._event_streams.keys())
    
    def cleanup_old_events(self, max_age_hours: int = 24) -> int:
        """Clean up old events and return count of cleaned events."""
        with self._lock:
            cutoff_time = time.time() - (max_age_hours * 3600)
            cleaned_count = 0
            
            for stream_id, events in self._event_store._events.items():
                original_count = len(events)
                # Keep only recent events
                self._event_store._events[stream_id] = [
                    event for event in events 
                    if event.created_at.timestamp() > cutoff_time
                ]
                cleaned_count += original_count - len(self._event_store._events[stream_id])
            
            return cleaned_count
