"""
Persistence module for data storage and event sourcing.
"""

from .database import DatabaseManager, SQLiteDatabase, PostgreSQLDatabase, DatabaseFactory
from .event_store import EventStore, FileEventStore, DatabaseEventStore, EventStoreFactory
from .migrations import MigrationManager, Migration
from .repositories import (
    StudentRepository, LecturerRepository, CourseRepository, 
    SectionRepository, GradeRepository, FacilityRepository
)
from .snapshot_manager import SnapshotManager

__all__ = [
    "DatabaseManager",
    "SQLiteDatabase", 
    "PostgreSQLDatabase",
    "EventStore",
    "FileEventStore",
    "DatabaseEventStore",
    "MigrationManager",
    "Migration",
    "StudentRepository",
    "LecturerRepository", 
    "CourseRepository",
    "SectionRepository",
    "GradeRepository",
    "FacilityRepository",
    "SnapshotManager",
]
