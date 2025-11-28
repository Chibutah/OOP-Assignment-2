"""
Concurrency management and thread safety components.
"""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Callable
from concurrent.futures import ThreadPoolExecutor, Future
import uuid

from ..core.exceptions import ConcurrencyError, ValidationError


class LockType(Enum):
    """Types of locks available."""
    READ = "read"
    WRITE = "write"
    EXCLUSIVE = "exclusive"


@dataclass
class LockInfo:
    """Information about a held lock."""
    lock_id: str
    resource_id: str
    lock_type: LockType
    holder_id: str
    acquired_at: float
    timeout: Optional[float] = None


class ConcurrencyManager:
    """Manages concurrency control with optimistic and pessimistic locking."""
    
    def __init__(self, max_workers: int = 10):
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._locks: Dict[str, Dict[LockType, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self._lock_holders: Dict[str, LockInfo] = {}
        self._lock_timeouts: Dict[str, float] = {}
        self._version_tracker: Dict[str, int] = {}
        self._lock = threading.RLock()
        self._cleanup_thread = threading.Thread(target=self._cleanup_expired_locks, daemon=True)
        self._cleanup_thread.start()
    
    def acquire_lock(self, resource_id: str, lock_type: LockType, 
                    holder_id: str, timeout: Optional[float] = None) -> str:
        """Acquire a lock on a resource."""
        with self._lock:
            lock_id = str(uuid.uuid4())
            
            # Check for lock conflicts
            if not self._can_acquire_lock(resource_id, lock_type, holder_id):
                raise ConcurrencyError(f"Cannot acquire {lock_type.value} lock on {resource_id}")
            
            # Acquire the lock
            self._locks[resource_id][lock_type].add(lock_id)
            lock_info = LockInfo(
                lock_id=lock_id,
                resource_id=resource_id,
                lock_type=lock_type,
                holder_id=holder_id,
                acquired_at=time.time(),
                timeout=timeout
            )
            self._lock_holders[lock_id] = lock_info
            
            if timeout:
                self._lock_timeouts[lock_id] = time.time() + timeout
            
            return lock_id
    
    def release_lock(self, lock_id: str) -> bool:
        """Release a lock."""
        with self._lock:
            if lock_id not in self._lock_holders:
                return False
            
            lock_info = self._lock_holders[lock_id]
            resource_id = lock_info.resource_id
            lock_type = lock_info.lock_type
            
            # Remove from locks
            if lock_id in self._locks[resource_id][lock_type]:
                self._locks[resource_id][lock_type].remove(lock_id)
            
            # Clean up empty lock types
            if not self._locks[resource_id][lock_type]:
                del self._locks[resource_id][lock_type]
            
            # Clean up empty resources
            if not self._locks[resource_id]:
                del self._locks[resource_id]
            
            # Remove from holders and timeouts
            del self._lock_holders[lock_id]
            self._lock_timeouts.pop(lock_id, None)
            
            return True
    
    def _can_acquire_lock(self, resource_id: str, lock_type: LockType, 
                         holder_id: str) -> bool:
        """Check if a lock can be acquired."""
        existing_locks = self._locks[resource_id]
        
        # Check for existing locks by the same holder
        for locks in existing_locks.values():
            for lock_id in locks:
                if self._lock_holders[lock_id].holder_id == holder_id:
                    return True  # Same holder can acquire multiple locks
        
        # Check for conflicts
        if lock_type == LockType.READ:
            # Read locks can coexist with other read locks
            return LockType.WRITE not in existing_locks and LockType.EXCLUSIVE not in existing_locks
        elif lock_type == LockType.WRITE:
            # Write locks conflict with all other locks
            return not any(existing_locks.values())
        elif lock_type == LockType.EXCLUSIVE:
            # Exclusive locks conflict with all other locks
            return not any(existing_locks.values())
        
        return False
    
    def _cleanup_expired_locks(self):
        """Clean up expired locks in background."""
        while True:
            try:
                time.sleep(1)  # Check every second
                current_time = time.time()
                expired_locks = []
                
                with self._lock:
                    for lock_id, timeout in self._lock_timeouts.items():
                        if current_time > timeout:
                            expired_locks.append(lock_id)
                
                for lock_id in expired_locks:
                    self.release_lock(lock_id)
                    
            except Exception as e:
                print(f"Error in lock cleanup: {e}")
    
    @contextmanager
    def lock(self, resource_id: str, lock_type: LockType, 
             holder_id: str, timeout: Optional[float] = None):
        """Context manager for acquiring and releasing locks."""
        lock_id = None
        try:
            lock_id = self.acquire_lock(resource_id, lock_type, holder_id, timeout)
            yield lock_id
        finally:
            if lock_id:
                self.release_lock(lock_id)
    
    def get_version(self, resource_id: str) -> int:
        """Get current version of a resource for optimistic concurrency control."""
        with self._lock:
            return self._version_tracker.get(resource_id, 0)
    
    def increment_version(self, resource_id: str) -> int:
        """Increment version of a resource."""
        with self._lock:
            current_version = self._version_tracker.get(resource_id, 0)
            new_version = current_version + 1
            self._version_tracker[resource_id] = new_version
            return new_version
    
    def check_version(self, resource_id: str, expected_version: int) -> bool:
        """Check if resource version matches expected version."""
        with self._lock:
            current_version = self._version_tracker.get(resource_id, 0)
            return current_version == expected_version
    
    def execute_with_retry(self, func: Callable, max_retries: int = 3, 
                          backoff_factor: float = 1.0) -> Any:
        """Execute a function with retry logic for optimistic concurrency control."""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except ConcurrencyError as e:
                last_exception = e
                if attempt < max_retries:
                    time.sleep(backoff_factor * (2 ** attempt))
                else:
                    raise last_exception
        
        raise last_exception
    
    def get_lock_info(self, resource_id: str) -> List[LockInfo]:
        """Get information about all locks on a resource."""
        with self._lock:
            locks = []
            for lock_type, lock_ids in self._locks[resource_id].items():
                for lock_id in lock_ids:
                    if lock_id in self._lock_holders:
                        locks.append(self._lock_holders[lock_id])
            return locks
    
    def get_holder_locks(self, holder_id: str) -> List[LockInfo]:
        """Get all locks held by a specific holder."""
        with self._lock:
            return [lock_info for lock_info in self._lock_holders.values() 
                   if lock_info.holder_id == holder_id]
    
    def cleanup(self):
        """Clean up resources."""
        self._executor.shutdown(wait=True)
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=1)


class EventStream:
    """Thread-safe event stream for publish/subscribe pattern."""
    
    def __init__(self, name: str):
        self._name = name
        self._subscribers: Dict[str, Callable] = {}
        self._events: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_events = 10000  # Keep last 10k events
    
    def subscribe(self, subscriber_id: str, callback: Callable) -> None:
        """Subscribe to events."""
        with self._lock:
            self._subscribers[subscriber_id] = callback
    
    def unsubscribe(self, subscriber_id: str) -> None:
        """Unsubscribe from events."""
        with self._lock:
            self._subscribers.pop(subscriber_id, None)
    
    def publish(self, event: Dict[str, Any]) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            # Add event to history
            event['timestamp'] = time.time()
            event['stream'] = self._name
            self._events.append(event)
            
            # Keep only recent events
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
            
            # Notify subscribers
            for subscriber_id, callback in self._subscribers.items():
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error notifying subscriber {subscriber_id}: {e}")
    
    def get_events(self, since: Optional[float] = None) -> List[Dict[str, Any]]:
        """Get events since a timestamp."""
        with self._lock:
            if since is None:
                return self._events.copy()
            return [event for event in self._events if event['timestamp'] > since]
    
    def get_subscriber_count(self) -> int:
        """Get number of subscribers."""
        with self._lock:
            return len(self._subscribers)


class ConcurrencyStressTest:
    """Stress test for concurrency control."""
    
    def __init__(self, concurrency_manager: ConcurrencyManager):
        self._concurrency_manager = concurrency_manager
        self._results: Dict[str, Any] = {}
    
    def run_test(self, num_clients: int = 100, operations_per_client: int = 100) -> Dict[str, Any]:
        """Run concurrency stress test."""
        print(f"Running concurrency stress test with {num_clients} clients, {operations_per_client} operations each")
        
        start_time = time.time()
        results = {
            'successful_operations': 0,
            'failed_operations': 0,
            'deadlocks_detected': 0,
            'lock_timeouts': 0,
            'version_conflicts': 0
        }
        
        def client_worker(client_id: int):
            """Worker function for each client."""
            for op in range(operations_per_client):
                try:
                    resource_id = f"resource_{op % 10}"  # 10 different resources
                    holder_id = f"client_{client_id}"
                    
                    # Try to acquire lock
                    with self._concurrency_manager.lock(resource_id, LockType.WRITE, holder_id, timeout=1.0):
                        # Simulate work
                        time.sleep(0.001)
                        
                        # Update version
                        self._concurrency_manager.increment_version(resource_id)
                        results['successful_operations'] += 1
                
                except ConcurrencyError as e:
                    if "timeout" in str(e).lower():
                        results['lock_timeouts'] += 1
                    elif "version" in str(e).lower():
                        results['version_conflicts'] += 1
                    else:
                        results['failed_operations'] += 1
        
        # Start all clients
        threads = []
        for client_id in range(num_clients):
            thread = threading.Thread(target=client_worker, args=(client_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all clients to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        results['total_time'] = end_time - start_time
        results['operations_per_second'] = (results['successful_operations'] + results['failed_operations']) / results['total_time']
        
        self._results = results
        return results
    
    def get_results(self) -> Dict[str, Any]:
        """Get test results."""
        return self._results.copy()
