"""
Distributed coordination service for managing distributed operations.
"""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
import uuid
import json
from datetime import datetime, timezone

from ..core.exceptions import ConcurrencyError, NetworkError, TimeoutError
from .concurrency_manager import ConcurrencyManager


class CoordinationStatus(Enum):
    """Status of a coordination operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMMITTED = "committed"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


class OperationType(Enum):
    """Types of distributed operations."""
    TWO_PHASE_COMMIT = "two_phase_commit"
    CONSENSUS = "consensus"
    LEADER_ELECTION = "leader_election"
    DISTRIBUTED_LOCK = "distributed_lock"


@dataclass
class CoordinationRequest:
    """Request for coordination operation."""
    operation_id: str
    operation_type: OperationType
    participants: List[str]
    data: Dict[str, Any]
    timeout: float = 30.0
    retry_count: int = 3


@dataclass
class CoordinationResult:
    """Result of a coordination operation."""
    success: bool
    status: CoordinationStatus
    message: str
    participants_results: Dict[str, Any]
    operation_id: str


class DistributedParticipant(ABC):
    """Abstract base class for distributed participants."""
    
    @abstractmethod
    async def prepare(self, operation_id: str, data: Dict[str, Any]) -> bool:
        """Prepare for a distributed operation."""
        pass
    
    @abstractmethod
    async def commit(self, operation_id: str) -> bool:
        """Commit a distributed operation."""
        pass
    
    @abstractmethod
    async def abort(self, operation_id: str) -> bool:
        """Abort a distributed operation."""
        pass
    
    @abstractmethod
    async def get_status(self, operation_id: str) -> CoordinationStatus:
        """Get status of an operation."""
        pass


class TwoPhaseCommitCoordinator:
    """Two-phase commit coordinator implementation."""
    
    def __init__(self, coordinator_id: str):
        self._coordinator_id = coordinator_id
        self._operations: Dict[str, Dict[str, Any]] = {}
        self._participants: Dict[str, DistributedParticipant] = {}
        self._lock = threading.RLock()
    
    def register_participant(self, participant_id: str, participant: DistributedParticipant) -> None:
        """Register a participant."""
        with self._lock:
            self._participants[participant_id] = participant
    
    def unregister_participant(self, participant_id: str) -> None:
        """Unregister a participant."""
        with self._lock:
            self._participants.pop(participant_id, None)
    
    async def execute_transaction(self, request: CoordinationRequest) -> CoordinationResult:
        """Execute a two-phase commit transaction."""
        operation_id = request.operation_id
        participants = request.participants
        
        with self._lock:
            # Initialize operation
            self._operations[operation_id] = {
                'status': CoordinationStatus.PENDING,
                'participants': participants,
                'data': request.data,
                'start_time': time.time(),
                'timeout': request.timeout,
                'phase': 'prepare'
            }
        
        try:
            # Phase 1: Prepare
            prepare_results = await self._prepare_phase(operation_id, participants, request.data)
            
            if all(prepare_results.values()):
                # All participants prepared successfully, proceed to commit
                commit_results = await self._commit_phase(operation_id, participants)
                
                if all(commit_results.values()):
                    # All participants committed successfully
                    self._update_operation_status(operation_id, CoordinationStatus.COMMITTED)
                    return CoordinationResult(
                        success=True,
                        status=CoordinationStatus.COMMITTED,
                        message="Transaction committed successfully",
                        participants_results=commit_results,
                        operation_id=operation_id
                    )
                else:
                    # Some participants failed to commit
                    await self._abort_phase(operation_id, participants)
                    self._update_operation_status(operation_id, CoordinationStatus.ABORTED)
                    return CoordinationResult(
                        success=False,
                        status=CoordinationStatus.ABORTED,
                        message="Transaction aborted due to commit failures",
                        participants_results=commit_results,
                        operation_id=operation_id
                    )
            else:
                # Some participants failed to prepare, abort
                await self._abort_phase(operation_id, participants)
                self._update_operation_status(operation_id, CoordinationStatus.ABORTED)
                return CoordinationResult(
                    success=False,
                    status=CoordinationStatus.ABORTED,
                    message="Transaction aborted due to prepare failures",
                    participants_results=prepare_results,
                    operation_id=operation_id
                )
        
        except asyncio.TimeoutError:
            self._update_operation_status(operation_id, CoordinationStatus.TIMEOUT)
            return CoordinationResult(
                success=False,
                status=CoordinationStatus.TIMEOUT,
                message="Transaction timed out",
                participants_results={},
                operation_id=operation_id
            )
        except Exception as e:
            self._update_operation_status(operation_id, CoordinationStatus.ABORTED)
            return CoordinationResult(
                success=False,
                status=CoordinationStatus.ABORTED,
                message=f"Transaction failed: {str(e)}",
                participants_results={},
                operation_id=operation_id
            )
    
    async def _prepare_phase(self, operation_id: str, participants: List[str], 
                           data: Dict[str, Any]) -> Dict[str, bool]:
        """Execute prepare phase."""
        prepare_tasks = []
        
        for participant_id in participants:
            if participant_id in self._participants:
                task = asyncio.create_task(
                    self._participants[participant_id].prepare(operation_id, data)
                )
                prepare_tasks.append((participant_id, task))
        
        results = {}
        for participant_id, task in prepare_tasks:
            try:
                result = await asyncio.wait_for(task, timeout=10.0)
                results[participant_id] = result
            except asyncio.TimeoutError:
                results[participant_id] = False
            except Exception:
                results[participant_id] = False
        
        return results
    
    async def _commit_phase(self, operation_id: str, participants: List[str]) -> Dict[str, bool]:
        """Execute commit phase."""
        commit_tasks = []
        
        for participant_id in participants:
            if participant_id in self._participants:
                task = asyncio.create_task(
                    self._participants[participant_id].commit(operation_id)
                )
                commit_tasks.append((participant_id, task))
        
        results = {}
        for participant_id, task in commit_tasks:
            try:
                result = await asyncio.wait_for(task, timeout=10.0)
                results[participant_id] = result
            except asyncio.TimeoutError:
                results[participant_id] = False
            except Exception:
                results[participant_id] = False
        
        return results
    
    async def _abort_phase(self, operation_id: str, participants: List[str]) -> Dict[str, bool]:
        """Execute abort phase."""
        abort_tasks = []
        
        for participant_id in participants:
            if participant_id in self._participants:
                task = asyncio.create_task(
                    self._participants[participant_id].abort(operation_id)
                )
                abort_tasks.append((participant_id, task))
        
        results = {}
        for participant_id, task in abort_tasks:
            try:
                result = await asyncio.wait_for(task, timeout=10.0)
                results[participant_id] = result
            except asyncio.TimeoutError:
                results[participant_id] = False
            except Exception:
                results[participant_id] = False
        
        return results
    
    def _update_operation_status(self, operation_id: str, status: CoordinationStatus) -> None:
        """Update operation status."""
        with self._lock:
            if operation_id in self._operations:
                self._operations[operation_id]['status'] = status
    
    def get_operation_status(self, operation_id: str) -> Optional[CoordinationStatus]:
        """Get operation status."""
        with self._lock:
            if operation_id in self._operations:
                return self._operations[operation_id]['status']
            return None
    
    def cleanup_old_operations(self, max_age_hours: int = 24) -> int:
        """Clean up old operations."""
        with self._lock:
            cutoff_time = time.time() - (max_age_hours * 3600)
            to_remove = []
            
            for operation_id, operation in self._operations.items():
                if operation['start_time'] < cutoff_time:
                    to_remove.append(operation_id)
            
            for operation_id in to_remove:
                del self._operations[operation_id]
            
            return len(to_remove)


class LeaderElection:
    """Leader election implementation using bully algorithm."""
    
    def __init__(self, node_id: str, all_nodes: List[str]):
        self._node_id = node_id
        self._all_nodes = all_nodes
        self._current_leader: Optional[str] = None
        self._election_in_progress = False
        self._lock = threading.RLock()
    
    async def start_election(self) -> str:
        """Start leader election process."""
        with self._lock:
            if self._election_in_progress:
                return self._current_leader or self._node_id
            
            self._election_in_progress = True
        
        try:
            # Find higher priority nodes
            higher_priority_nodes = [node for node in self._all_nodes if node > self._node_id]
            
            if not higher_priority_nodes:
                # This node has highest priority, become leader
                self._current_leader = self._node_id
                return self._node_id
            
            # Send election messages to higher priority nodes
            responses = await self._send_election_messages(higher_priority_nodes)
            
            if not any(responses.values()):
                # No higher priority node responded, become leader
                self._current_leader = self._node_id
                await self._announce_leadership()
                return self._node_id
            else:
                # Wait for leader announcement
                await self._wait_for_leader_announcement()
                return self._current_leader or self._node_id
        
        finally:
            with self._lock:
                self._election_in_progress = False
    
    async def _send_election_messages(self, nodes: List[str]) -> Dict[str, bool]:
        """Send election messages to nodes."""
        # This would implement actual network communication
        # For now, simulate responses
        responses = {}
        for node in nodes:
            responses[node] = False  # Simulate no response
        return responses
    
    async def _announce_leadership(self) -> None:
        """Announce leadership to all nodes."""
        # This would implement actual network communication
        pass
    
    async def _wait_for_leader_announcement(self, timeout: float = 5.0) -> None:
        """Wait for leader announcement."""
        # This would implement actual waiting logic
        await asyncio.sleep(0.1)  # Simulate waiting
    
    def get_current_leader(self) -> Optional[str]:
        """Get current leader."""
        with self._lock:
            return self._current_leader
    
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        with self._lock:
            return self._current_leader == self._node_id


class DistributedCoordinator:
    """Main distributed coordination service."""
    
    def __init__(self, node_id: str, concurrency_manager: ConcurrencyManager):
        self._node_id = node_id
        self._concurrency_manager = concurrency_manager
        self._two_phase_commit = TwoPhaseCommitCoordinator(node_id)
        self._leader_election = None
        self._distributed_locks: Dict[str, str] = {}  # resource_id -> holder_node_id
        self._lock = threading.RLock()
    
    def initialize_leader_election(self, all_nodes: List[str]) -> None:
        """Initialize leader election with all nodes."""
        with self._lock:
            self._leader_election = LeaderElection(self._node_id, all_nodes)
    
    async def elect_leader(self) -> str:
        """Elect a leader."""
        if not self._leader_election:
            raise RuntimeError("Leader election not initialized")
        
        return await self._leader_election.start_election()
    
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        if not self._leader_election:
            return False
        return self._leader_election.is_leader()
    
    def get_current_leader(self) -> Optional[str]:
        """Get current leader."""
        if not self._leader_election:
            return None
        return self._leader_election.get_current_leader()
    
    def register_participant(self, participant_id: str, participant: DistributedParticipant) -> None:
        """Register a participant for two-phase commit."""
        self._two_phase_commit.register_participant(participant_id, participant)
    
    async def execute_transaction(self, participants: List[str], 
                                data: Dict[str, Any], timeout: float = 30.0) -> CoordinationResult:
        """Execute a distributed transaction."""
        operation_id = str(uuid.uuid4())
        request = CoordinationRequest(
            operation_id=operation_id,
            operation_type=OperationType.TWO_PHASE_COMMIT,
            participants=participants,
            data=data,
            timeout=timeout
        )
        
        return await self._two_phase_commit.execute_transaction(request)
    
    async def acquire_distributed_lock(self, resource_id: str, timeout: float = 10.0) -> bool:
        """Acquire a distributed lock."""
        # This is a simplified implementation
        # In practice, this would use a distributed lock service like etcd or Redis
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if resource_id not in self._distributed_locks:
                    self._distributed_locks[resource_id] = self._node_id
                    return True
                elif self._distributed_locks[resource_id] == self._node_id:
                    return True  # Already held by this node
            
            await asyncio.sleep(0.1)
        
        return False
    
    def release_distributed_lock(self, resource_id: str) -> bool:
        """Release a distributed lock."""
        with self._lock:
            if resource_id in self._distributed_locks and self._distributed_locks[resource_id] == self._node_id:
                del self._distributed_locks[resource_id]
                return True
            return False
    
    def get_coordination_statistics(self) -> Dict[str, Any]:
        """Get coordination statistics."""
        with self._lock:
            return {
                'node_id': self._node_id,
                'is_leader': self.is_leader(),
                'current_leader': self.get_current_leader(),
                'distributed_locks_held': len(self._distributed_locks),
                'registered_participants': len(self._two_phase_commit._participants)
            }
