"""
Database migration system for schema versioning.
"""

import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone
import uuid

from ..core.exceptions import PersistenceError, ValidationError
from .database import DatabaseManager


@dataclass
class Migration:
    """Represents a database migration."""
    id: str
    name: str
    version: int
    up_sql: str
    down_sql: str
    description: str = ""
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class MigrationManager:
    """Manages database migrations and schema versioning."""
    
    def __init__(self, database: DatabaseManager, migrations_path: str = "migrations"):
        self._database = database
        self._migrations_path = migrations_path
        self._migrations: Dict[str, Migration] = {}
        self._lock = threading.RLock()
        self._ensure_migrations_table()
        self._load_migrations()
    
    def _ensure_migrations_table(self) -> None:
        """Ensure the migrations table exists."""
        try:
            if not self._database.table_exists("migrations"):
                schema = {
                    "migrations": """
                        CREATE TABLE migrations (
                            id VARCHAR(255) PRIMARY KEY,
                            name VARCHAR(255) UNIQUE NOT NULL,
                            version INTEGER NOT NULL,
                            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            description TEXT
                        )
                    """
                }
                self._database.create_tables(schema)
        except Exception as e:
            print(f"Warning: Could not create migrations table: {e}")
    
    def _load_migrations(self) -> None:
        """Load migrations from the migrations directory."""
        if not os.path.exists(self._migrations_path):
            os.makedirs(self._migrations_path, exist_ok=True)
            return
        
        for filename in sorted(os.listdir(self._migrations_path)):
            if filename.endswith(".json"):
                migration_path = os.path.join(self._migrations_path, filename)
                try:
                    with open(migration_path, "r", encoding="utf-8") as f:
                        migration_data = json.load(f)
                    
                    migration = Migration(
                        id=migration_data["id"],
                        name=migration_data["name"],
                        version=migration_data["version"],
                        up_sql=migration_data["up_sql"],
                        down_sql=migration_data["down_sql"],
                        description=migration_data.get("description", ""),
                        created_at=datetime.fromisoformat(migration_data.get("created_at", datetime.now(timezone.utc).isoformat()))
                    )
                    
                    self._migrations[migration.id] = migration
                except Exception as e:
                    print(f"Warning: Failed to load migration {filename}: {e}")
    
    def create_migration(self, name: str, up_sql: str, down_sql: str, 
                        description: str = "") -> Migration:
        """Create a new migration."""
        with self._lock:
            migration_id = str(uuid.uuid4())
            version = len(self._migrations) + 1
            
            migration = Migration(
                id=migration_id,
                name=name,
                version=version,
                up_sql=up_sql,
                down_sql=down_sql,
                description=description
            )
            
            # Save migration to file
            self._save_migration_file(migration)
            
            # Add to in-memory collection
            self._migrations[migration_id] = migration
            
            return migration
    
    def _save_migration_file(self, migration: Migration) -> None:
        """Save migration to file."""
        migration_data = {
            "id": migration.id,
            "name": migration.name,
            "version": migration.version,
            "up_sql": migration.up_sql,
            "down_sql": migration.down_sql,
            "description": migration.description,
            "created_at": migration.created_at.isoformat()
        }
        
        filename = f"{migration.version:03d}_{migration.name}.json"
        filepath = os.path.join(self._migrations_path, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(migration_data, f, indent=2)
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get migrations that haven't been applied yet."""
        with self._lock:
            applied_migrations = self._get_applied_migrations()
            pending = []
            
            for migration in sorted(self._migrations.values(), key=lambda m: m.version):
                if migration.id not in applied_migrations:
                    pending.append(migration)
            
            return pending
    
    def _get_applied_migrations(self) -> Dict[str, str]:
        """Get list of applied migration IDs."""
        try:
            query = "SELECT id, name FROM migrations ORDER BY version"
            results = self._database.execute_query(query)
            return {row["id"]: row["name"] for row in results}
        except Exception:
            # If migrations table doesn't exist or has issues, return empty dict
            return {}
    
    def apply_migration(self, migration: Migration) -> bool:
        """Apply a migration."""
        with self._lock:
            try:
                # Check if already applied
                if self._is_migration_applied(migration.id):
                    return True
                
                # Execute up SQL - split multiple statements
                statements = [stmt.strip() for stmt in migration.up_sql.split(';') if stmt.strip()]
                for statement in statements:
                    self._database.execute_update(statement)
                
                # Record migration as applied
                insert_query = """
                    INSERT INTO migrations (id, name, version, applied_at, description)
                    VALUES (?, ?, ?, ?, ?)
                """
                params = (
                    migration.id,
                    migration.name,
                    migration.version,
                    datetime.now(timezone.utc).isoformat(),
                    migration.description
                )
                self._database.execute_update(insert_query, params)
                
                return True
            except Exception as e:
                raise PersistenceError(f"Failed to apply migration {migration.name}: {str(e)}")
    
    def rollback_migration(self, migration: Migration) -> bool:
        """Rollback a migration."""
        with self._lock:
            try:
                # Check if migration is applied
                if not self._is_migration_applied(migration.id):
                    return True
                
                # Execute down SQL
                self._database.execute_update(migration.down_sql)
                
                # Remove migration record
                delete_query = "DELETE FROM migrations WHERE id = ?"
                self._database.execute_update(delete_query, (migration.id,))
                
                return True
            except Exception as e:
                raise PersistenceError(f"Failed to rollback migration {migration.name}: {str(e)}")
    
    def _is_migration_applied(self, migration_id: str) -> bool:
        """Check if a migration has been applied."""
        query = "SELECT COUNT(*) as count FROM migrations WHERE id = ?"
        results = self._database.execute_query(query, (migration_id,))
        return results[0]["count"] > 0
    
    def migrate_up(self, target_version: Optional[int] = None) -> List[Migration]:
        """Apply pending migrations up to target version."""
        with self._lock:
            pending_migrations = self.get_pending_migrations()
            applied_migrations = []
            
            for migration in pending_migrations:
                if target_version and migration.version > target_version:
                    break
                
                if self.apply_migration(migration):
                    applied_migrations.append(migration)
                else:
                    break  # Stop on first failure
            
            return applied_migrations
    
    def migrate_down(self, target_version: Optional[int] = None) -> List[Migration]:
        """Rollback migrations down to target version."""
        with self._lock:
            applied_migrations = self._get_applied_migrations_by_version()
            rolled_back_migrations = []
            
            # Sort by version descending
            for migration in sorted(applied_migrations.values(), key=lambda m: m.version, reverse=True):
                if target_version and migration.version <= target_version:
                    break
                
                if self.rollback_migration(migration):
                    rolled_back_migrations.append(migration)
                else:
                    break  # Stop on first failure
            
            return rolled_back_migrations
    
    def _get_applied_migrations_by_version(self) -> Dict[int, Migration]:
        """Get applied migrations sorted by version."""
        query = "SELECT id FROM migrations ORDER BY version DESC"
        results = self._database.execute_query(query)
        
        applied_migrations = {}
        for row in results:
            migration_id = row["id"]
            if migration_id in self._migrations:
                migration = self._migrations[migration_id]
                applied_migrations[migration.version] = migration
        
        return applied_migrations
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status information."""
        with self._lock:
            applied_migrations = self._get_applied_migrations()
            total_migrations = len(self._migrations)
            applied_count = len(applied_migrations)
            pending_count = total_migrations - applied_count
            
            return {
                "total_migrations": total_migrations,
                "applied_migrations": applied_count,
                "pending_migrations": pending_count,
                "current_version": max([m.version for m in self._migrations.values()], default=0),
                "applied_version": max([m.version for m in self._migrations.values() 
                                     if m.id in applied_migrations], default=0)
            }
    
    def create_initial_migrations(self) -> None:
        """Create initial migrations for the system."""
        # Check if migrations already exist
        if self._migrations:
            return
            
        # Migration 1: Create basic entities table
        self.create_migration(
            name="create_entities_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'active'
                )
            """,
            down_sql="DROP TABLE IF EXISTS entities",
            description="Create basic entities table"
        )
        
        # Migration 2: Create events table
        self.create_migration(
            name="create_events_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    stream_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1,
                    correlation_id TEXT,
                    causation_id TEXT
                )
            """,
            down_sql="DROP TABLE IF EXISTS events",
            description="Create events table for event sourcing"
        )
        
        # Migration 3: Create snapshots table
        self.create_migration(
            name="create_snapshots_table",
            up_sql="""
                CREATE TABLE IF NOT EXISTS snapshots (
                    stream_id TEXT PRIMARY KEY,
                    snapshot_data TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            down_sql="DROP TABLE IF EXISTS snapshots",
            description="Create snapshots table for event sourcing"
        )
        
        # Migration 4: Add indexes for performance
        self.create_migration(
            name="add_performance_indexes",
            up_sql="""
                CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
                CREATE INDEX IF NOT EXISTS idx_entities_status ON entities(status);
                CREATE INDEX IF NOT EXISTS idx_events_stream_id ON events(stream_id);
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
                CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
            """,
            down_sql="""
                DROP INDEX IF EXISTS idx_entities_type;
                DROP INDEX IF EXISTS idx_entities_status;
                DROP INDEX IF EXISTS idx_events_stream_id;
                DROP INDEX IF EXISTS idx_events_type;
                DROP INDEX IF EXISTS idx_events_created_at;
            """,
            description="Add performance indexes"
        )
    
    def validate_migrations(self) -> List[str]:
        """Validate all migrations for consistency."""
        with self._lock:
            errors = []
            
            for migration in self._migrations.values():
                # Check for duplicate versions
                version_count = sum(1 for m in self._migrations.values() if m.version == migration.version)
                if version_count > 1:
                    errors.append(f"Duplicate version {migration.version} in migration {migration.name}")
                
                # Check for empty SQL
                if not migration.up_sql.strip():
                    errors.append(f"Empty up_sql in migration {migration.name}")
                
                if not migration.down_sql.strip():
                    errors.append(f"Empty down_sql in migration {migration.name}")
            
            return errors
