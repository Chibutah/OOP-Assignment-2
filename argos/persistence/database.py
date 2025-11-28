"""
Database management and connection handling.
"""

import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union
import json
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from ..core.exceptions import PersistenceError, ConfigurationError


class DatabaseManager(ABC):
    """Abstract base class for database management."""
    
    @abstractmethod
    def connect(self) -> Any:
        """Create a database connection."""
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        pass
    
    @abstractmethod
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute an update query and return affected rows."""
        pass
    
    @abstractmethod
    def execute_transaction(self, queries: List[tuple]) -> bool:
        """Execute multiple queries in a transaction."""
        pass
    
    @abstractmethod
    def create_tables(self, schema: Dict[str, str]) -> None:
        """Create database tables from schema."""
        pass
    
    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        pass
    
    @abstractmethod
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table schema information."""
        pass


class SQLiteDatabase(DatabaseManager):
    """SQLite database implementation."""
    
    def __init__(self, database_path: str = "argos.db"):
        self._database_path = database_path
        self._lock = threading.RLock()
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """Initialize the database with basic schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create basic tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            cursor.execute("""
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
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    stream_id TEXT PRIMARY KEY,
                    snapshot_data TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    version INTEGER NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = None
        try:
            conn = sqlite3.connect(self._database_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise PersistenceError(f"Database connection error: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def connect(self) -> sqlite3.Connection:
        """Create a database connection."""
        return sqlite3.connect(self._database_path, check_same_thread=False)
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            columns = [description[0] for description in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute an update query and return affected rows."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
    
    def execute_transaction(self, queries: List[tuple]) -> bool:
        """Execute multiple queries in a transaction."""
        with self._get_connection() as conn:
            try:
                cursor = conn.cursor()
                for query, params in queries:
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                raise PersistenceError(f"Transaction failed: {str(e)}")
    
    def create_tables(self, schema: Dict[str, str]) -> None:
        """Create database tables from schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for table_name, table_schema in schema.items():
                cursor.execute(table_schema)
            conn.commit()
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        results = self.execute_query(query, (table_name,))
        return len(results) > 0
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table schema information."""
        query = "PRAGMA table_info(?)"
        return self.execute_query(query, (table_name,))


class PostgreSQLDatabase(DatabaseManager):
    """PostgreSQL database implementation."""
    
    def __init__(self, host: str = "localhost", port: int = 5432, 
                 database: str = "argos", user: str = "argos", password: str = ""):
        if not PSYCOPG2_AVAILABLE:
            raise ConfigurationError("psycopg2 is required for PostgreSQL support")
        
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._lock = threading.RLock()
        self._initialize_database()
    
    def _get_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return f"host={self._host} port={self._port} dbname={self._database} user={self._user} password={self._password}"
    
    def _initialize_database(self) -> None:
        """Initialize the database with basic schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create basic tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id VARCHAR(255) PRIMARY KEY,
                    type VARCHAR(100) NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1,
                    status VARCHAR(50) DEFAULT 'active'
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id VARCHAR(255) PRIMARY KEY,
                    stream_id VARCHAR(255) NOT NULL,
                    event_type VARCHAR(100) NOT NULL,
                    event_data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1,
                    correlation_id VARCHAR(255),
                    causation_id VARCHAR(255)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    stream_id VARCHAR(255) PRIMARY KEY,
                    snapshot_data JSONB NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = None
        try:
            conn = psycopg2.connect(self._get_connection_string())
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise PersistenceError(f"Database connection error: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def connect(self):
        """Create a database connection."""
        return psycopg2.connect(self._get_connection_string())
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = []
            for row in cursor.fetchall():
                results.append(dict(row))
            return results
    
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """Execute an update query and return affected rows."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
    
    def execute_transaction(self, queries: List[tuple]) -> bool:
        """Execute multiple queries in a transaction."""
        with self._get_connection() as conn:
            try:
                cursor = conn.cursor()
                for query, params in queries:
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                raise PersistenceError(f"Transaction failed: {str(e)}")
    
    def create_tables(self, schema: Dict[str, str]) -> None:
        """Create database tables from schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for table_name, table_schema in schema.items():
                cursor.execute(table_schema)
            conn.commit()
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        query = "SELECT table_name FROM information_schema.tables WHERE table_name = %s"
        results = self.execute_query(query, (table_name,))
        return len(results) > 0
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table schema information."""
        query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position
        """
        return self.execute_query(query, (table_name,))


class DatabaseFactory:
    """Factory for creating database instances."""
    
    @staticmethod
    def create_database(database_type: str, **kwargs) -> DatabaseManager:
        """Create a database instance based on type."""
        if database_type.lower() == "sqlite":
            return SQLiteDatabase(**kwargs)
        elif database_type.lower() == "postgresql":
            return PostgreSQLDatabase(**kwargs)
        else:
            raise ConfigurationError(f"Unsupported database type: {database_type}")
