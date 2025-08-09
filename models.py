# models.py - Database models and schema
import sqlite3
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta
import json
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import hashlib

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database operations with connection pooling and proper error handling"""
    
    def __init__(self, db_path: str = "tapsi_food_data.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with proper cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")  # Better for concurrent access
            conn.execute("PRAGMA synchronous = NORMAL")  # Balance between safety and speed
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def init_database(self):
        """Initialize database with all required tables and indexes"""
        with self.get_connection() as conn:
            # Metadata table for tracking updates
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Orders table with proper indexing
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    vendor_code TEXT,
                    city_id INTEGER,
                    city_name TEXT,
                    business_line TEXT,
                    marketing_area TEXT,
                    customer_latitude REAL,
                    customer_longitude REAL,
                    user_id TEXT,
                    organic INTEGER,
                    created_at TIMESTAMP,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(order_id, vendor_code, created_at)
                )
            """)
            
            # Vendors table with spatial capabilities
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_code TEXT UNIQUE,
                    vendor_name TEXT,
                    city_id INTEGER,
                    city_name TEXT,
                    business_line TEXT,
                    latitude REAL,
                    longitude REAL,
                    radius REAL,
                    original_radius REAL,
                    status_id REAL,
                    visible REAL,
                    open REAL,
                    grade TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Coverage grid cache table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coverage_grid_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE,
                    city_name TEXT,
                    business_line TEXT,
                    vendor_filters TEXT,  -- JSON string of filters
                    grid_data TEXT,       -- JSON string of grid results
                    point_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Heatmap cache table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS heatmap_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE,
                    heatmap_type TEXT,
                    city_name TEXT,
                    date_range TEXT,
                    business_line TEXT,
                    zoom_level INTEGER,
                    heatmap_data TEXT,    -- JSON string of heatmap points
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            self._create_indexes(conn)
            conn.commit()
            
    def _create_indexes(self, conn):
        """Create all necessary indexes for optimal query performance"""
        indexes = [
            # Orders indexes
            "CREATE INDEX IF NOT EXISTS idx_orders_city_name ON orders(city_name)",
            "CREATE INDEX IF NOT EXISTS idx_orders_business_line ON orders(business_line)",
            "CREATE INDEX IF NOT EXISTS idx_orders_vendor_code ON orders(vendor_code)",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_orders_location ON orders(customer_latitude, customer_longitude)",
            "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_marketing_area ON orders(marketing_area)",
            
            # Vendors indexes
            "CREATE INDEX IF NOT EXISTS idx_vendors_city_name ON vendors(city_name)",
            "CREATE INDEX IF NOT EXISTS idx_vendors_business_line ON vendors(business_line)",
            "CREATE INDEX IF NOT EXISTS idx_vendors_location ON vendors(latitude, longitude)",
            "CREATE INDEX IF NOT EXISTS idx_vendors_status_id ON vendors(status_id)",
            "CREATE INDEX IF NOT EXISTS idx_vendors_grade ON vendors(grade)",
            "CREATE INDEX IF NOT EXISTS idx_vendors_visible ON vendors(visible)",
            "CREATE INDEX IF NOT EXISTS idx_vendors_open ON vendors(open)",
            
            # Cache indexes
            "CREATE INDEX IF NOT EXISTS idx_coverage_cache_key ON coverage_grid_cache(cache_key)",
            "CREATE INDEX IF NOT EXISTS idx_coverage_city_bl ON coverage_grid_cache(city_name, business_line)",
            "CREATE INDEX IF NOT EXISTS idx_coverage_accessed ON coverage_grid_cache(last_accessed)",
            "CREATE INDEX IF NOT EXISTS idx_heatmap_cache_key ON heatmap_cache(cache_key)",
            "CREATE INDEX IF NOT EXISTS idx_heatmap_type_city ON heatmap_cache(heatmap_type, city_name)"
        ]
        
        for index_sql in indexes:
            try:
                conn.execute(index_sql)
            except sqlite3.Error as e:
                logger.warning(f"Could not create index: {e}")

    def upsert_orders(self, df_orders: pd.DataFrame) -> int:
        """Insert or update orders data with conflict resolution"""
        if df_orders.empty:
            return 0
            
        # Prepare data
        df_clean = df_orders.copy()
        df_clean['imported_at'] = datetime.now()
        
        # Convert to records for insertion
        records = df_clean.to_dict('records')
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Use INSERT OR REPLACE for upsert behavior
            insert_sql = """
                INSERT OR REPLACE INTO orders (
                    order_id, vendor_code, city_id, city_name, business_line,
                    marketing_area, customer_latitude, customer_longitude,
                    user_id, organic, created_at, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Batch insert for performance
            batch_size = 1000
            inserted_count = 0
            
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                batch_data = [
                    (
                        r.get('order_id'), r.get('vendor_code'), r.get('city_id'),
                        r.get('city_name'), r.get('business_line'), r.get('marketing_area'),
                        r.get('customer_latitude'), r.get('customer_longitude'),
                        r.get('user_id'), r.get('organic'), r.get('created_at'),
                        r.get('imported_at')
                    ) for r in batch
                ]
                
                cursor.executemany(insert_sql, batch_data)
                inserted_count += len(batch)
                
                if i % 10000 == 0:  # Progress logging
                    logger.info(f"Inserted {inserted_count}/{len(records)} orders...")
            
            conn.commit()
            logger.info(f"Successfully upserted {inserted_count} orders")
            return inserted_count

    def upsert_vendors(self, df_vendors: pd.DataFrame) -> int:
        """Insert or update vendors data"""
        if df_vendors.empty:
            return 0
            
        df_clean = df_vendors.copy()
        df_clean['updated_at'] = datetime.now()
        records = df_clean.to_dict('records')
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            insert_sql = """
                INSERT OR REPLACE INTO vendors (
                    vendor_code, vendor_name, city_id, city_name, business_line,
                    latitude, longitude, radius, original_radius, status_id,
                    visible, open, grade, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            batch_data = [
                (
                    r.get('vendor_code'), r.get('vendor_name'), r.get('city_id'),
                    r.get('city_name'), r.get('business_line'), r.get('latitude'),
                    r.get('longitude'), r.get('radius'), r.get('original_radius'),
                    r.get('status_id'), r.get('visible'), r.get('open'),
                    r.get('grade'), r.get('updated_at')
                ) for r in records
            ]
            
            cursor.executemany(insert_sql, batch_data)
            conn.commit()
            
            logger.info(f"Successfully upserted {len(records)} vendors")
            return len(records)

    def get_orders(self, 
                   city_name: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   business_lines: Optional[List[str]] = None,
                   vendor_codes: Optional[List[str]] = None) -> pd.DataFrame:
        """Retrieve filtered orders data"""
        
        where_conditions = []
        params = []
        
        if city_name and city_name != "all":
            where_conditions.append("city_name = ?")
            params.append(city_name)
            
        if start_date:
            where_conditions.append("created_at >= ?")
            params.append(start_date)
            
        if end_date:
            where_conditions.append("created_at <= ?")
            params.append(end_date)
            
        if business_lines:
            placeholders = ','.join(['?' for _ in business_lines])
            where_conditions.append(f"business_line IN ({placeholders})")
            params.extend(business_lines)
            
        if vendor_codes:
            placeholders = ','.join(['?' for _ in vendor_codes])
            where_conditions.append(f"vendor_code IN ({placeholders})")
            params.extend(vendor_codes)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        sql = f"""
            SELECT * FROM orders 
            {where_clause}
            ORDER BY created_at DESC
        """
        
        with self.get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def get_vendors(self, 
                    city_name: Optional[str] = None,
                    business_lines: Optional[List[str]] = None,
                    vendor_codes: Optional[List[str]] = None,
                    status_ids: Optional[List[int]] = None,
                    grades: Optional[List[str]] = None,
                    visible: Optional[int] = None,
                    is_open: Optional[int] = None) -> pd.DataFrame:
        """Retrieve filtered vendors data"""
        
        where_conditions = []
        params = []
        
        if city_name and city_name != "all":
            where_conditions.append("city_name = ?")
            params.append(city_name)
            
        if business_lines:
            placeholders = ','.join(['?' for _ in business_lines])
            where_conditions.append(f"business_line IN ({placeholders})")
            params.extend(business_lines)
            
        if vendor_codes:
            placeholders = ','.join(['?' for _ in vendor_codes])
            where_conditions.append(f"vendor_code IN ({placeholders})")
            params.extend(vendor_codes)
            
        if status_ids:
            placeholders = ','.join(['?' for _ in status_ids])
            where_conditions.append(f"status_id IN ({placeholders})")
            params.extend(status_ids)
            
        if grades:
            placeholders = ','.join(['?' for _ in grades])
            where_conditions.append(f"grade IN ({placeholders})")
            params.extend(grades)
            
        if visible is not None:
            where_conditions.append("visible = ?")
            params.append(visible)
            
        if is_open is not None:
            where_conditions.append("open = ?")
            params.append(is_open)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        sql = f"SELECT * FROM vendors {where_clause}"
        
        with self.get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def cache_coverage_grid(self, cache_key: str, city_name: str, 
                           business_line: str, vendor_filters: Dict[str, Any],
                           grid_data: List[Dict]) -> bool:
        """Cache coverage grid results"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO coverage_grid_cache 
                    (cache_key, city_name, business_line, vendor_filters, grid_data, point_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    cache_key, city_name, business_line,
                    json.dumps(vendor_filters), json.dumps(grid_data), len(grid_data)
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to cache coverage grid: {e}")
            return False

    def get_cached_coverage_grid(self, cache_key: str) -> Optional[List[Dict]]:
        """Retrieve cached coverage grid results"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT grid_data FROM coverage_grid_cache 
                    WHERE cache_key = ?
                """, (cache_key,))
                
                result = cursor.fetchone()
                if result:
                    # Update last accessed timestamp
                    conn.execute("""
                        UPDATE coverage_grid_cache 
                        SET last_accessed = CURRENT_TIMESTAMP 
                        WHERE cache_key = ?
                    """, (cache_key,))
                    conn.commit()
                    
                    return json.loads(result[0])
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve cached coverage grid: {e}")
            return None

    def cache_heatmap(self, cache_key: str, heatmap_type: str, city_name: str,
                     date_range: str, business_line: str, zoom_level: int,
                     heatmap_data: List[Dict]) -> bool:
        """Cache heatmap results"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO heatmap_cache 
                    (cache_key, heatmap_type, city_name, date_range, business_line, zoom_level, heatmap_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    cache_key, heatmap_type, city_name, date_range,
                    business_line, zoom_level, json.dumps(heatmap_data)
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to cache heatmap: {e}")
            return False

    def get_cached_heatmap(self, cache_key: str) -> Optional[List[Dict]]:
        """Retrieve cached heatmap results"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT heatmap_data FROM heatmap_cache 
                    WHERE cache_key = ?
                """, (cache_key,))
                
                result = cursor.fetchone()
                if result:
                    return json.loads(result[0])
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve cached heatmap: {e}")
            return None

    def cleanup_old_cache(self, days_old: int = 7):
        """Clean up old cache entries to prevent database bloat"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        with self.get_connection() as conn:
            # Clean old coverage grid cache
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM coverage_grid_cache 
                WHERE last_accessed < ?
            """, (cutoff_date,))
            
            coverage_deleted = cursor.rowcount
            
            # Clean old heatmap cache
            cursor.execute("""
                DELETE FROM heatmap_cache 
                WHERE created_at < ?
            """, (cutoff_date,))
            
            heatmap_deleted = cursor.rowcount
            conn.commit()
            
            logger.info(f"Cleaned up {coverage_deleted} coverage cache entries and {heatmap_deleted} heatmap cache entries")

    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else None

    def set_metadata(self, key: str, value: str):
        """Set metadata value"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            conn.commit()

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Count records in each table
            for table in ['orders', 'vendors', 'coverage_grid_cache', 'heatmap_cache']:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f'{table}_count'] = cursor.fetchone()[0]
            
            # Database size
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            stats['database_size_bytes'] = cursor.fetchone()[0]
            
            # Last update times
            cursor.execute("SELECT key, updated_at FROM metadata WHERE key LIKE '%_last_update'")
            for key, updated_at in cursor.fetchall():
                stats[key] = updated_at
            
            return stats

def generate_cache_key(city_name: str, business_lines: List[str], 
                      vendor_filters: Dict[str, Any], 
                      additional_params: Dict[str, Any] = None) -> str:
    """Generate a consistent cache key for given parameters"""
    key_data = {
        'city': city_name,
        'business_lines': sorted(business_lines) if business_lines else [],
        'vendor_filters': vendor_filters,
        'additional': additional_params or {}
    }
    
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()
