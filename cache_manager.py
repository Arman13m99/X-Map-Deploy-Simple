# cache_manager.py - Intelligent coverage grid cache management
import json
import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from models import DatabaseManager, generate_cache_key
from config import Config

logger = logging.getLogger(__name__)

@dataclass
class CoverageGridTask:
    """Represents a coverage grid calculation task"""
    city_name: str
    business_lines: List[str]
    vendor_filters: Dict[str, Any]
    priority: int = 1  # 1 = highest, 5 = lowest
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class CoverageGridCacheManager:
    """Manages intelligent caching and preloading of coverage grid calculations"""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.preload_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="coverage_preload")
        self.preload_queue = []
        self.queue_lock = threading.Lock()
        self.is_preloading = False
        
        # In-memory cache for frequently accessed grids
        self.memory_cache = {}
        self.memory_cache_lock = threading.Lock()
        self.max_memory_cache_size = 50
        
        # Common filter combinations to preload
        self.common_combinations = self._define_common_combinations()
        
    def _define_common_combinations(self) -> List[Dict[str, Any]]:
        """Define common filter combinations that should be preloaded"""
        combinations = []
        
        cities = ["tehran", "mashhad", "shiraz"]
        business_lines = [
            ["restaurant"], ["coffee"], ["bakery"], ["supermarket"],
            ["restaurant", "coffee"], ["restaurant", "bakery"]
        ]
        
        # Common vendor filters
        common_filters = [
            # All vendors (minimal filtering)
            {
                'status_ids': [5],  # Most common status
                'grades': ['A', 'A+'],  # High-quality vendors
                'visible': 1,
                'is_open': None
            },
            # Premium vendors only
            {
                'status_ids': [5],
                'grades': ['A+'],
                'visible': 1,
                'is_open': 1
            },
            # All active vendors
            {
                'status_ids': [4, 5],
                'grades': ['A', 'A+', 'B'],
                'visible': 1,
                'is_open': None
            }
        ]
        
        # Generate combinations
        for city in cities:
            for bl_combo in business_lines:
                for filter_combo in common_filters:
                    combinations.append({
                        'city_name': city,
                        'business_lines': bl_combo,
                        'vendor_filters': filter_combo,
                        'priority': self._calculate_priority(city, bl_combo, filter_combo)
                    })
        
        return combinations
    
    def _calculate_priority(self, city: str, business_lines: List[str], filters: Dict) -> int:
        """Calculate priority for preloading (1 = highest, 5 = lowest)"""
        priority = 3  # Default medium priority
        
        # Tehran gets higher priority
        if city == "tehran":
            priority -= 1
            
        # Restaurant business line gets higher priority
        if "restaurant" in business_lines:
            priority -= 1
            
        # Single business line gets higher priority (more common use case)
        if len(business_lines) == 1:
            priority -= 1
            
        # Premium filters get higher priority
        if filters.get('grades') == ['A+']:
            priority -= 1
            
        return max(1, min(5, priority))
    
    def get_or_calculate_coverage_grid(self, 
                                     city_name: str,
                                     business_lines: List[str],
                                     vendor_filters: Dict[str, Any],
                                     force_recalculate: bool = False) -> Optional[List[Dict]]:
        """Get coverage grid from cache or calculate if not available"""
        
        # Generate cache key
        cache_key = generate_cache_key(city_name, business_lines, vendor_filters)
        
        # Check memory cache first (fastest)
        if not force_recalculate:
            with self.memory_cache_lock:
                if cache_key in self.memory_cache:
                    logger.info(f"Coverage grid found in memory cache: {cache_key[:8]}...")
                    self._update_memory_cache_access(cache_key)
                    return self.memory_cache[cache_key]['data']
        
        # Check database cache
        if not force_recalculate:
            cached_data = self.db_manager.get_cached_coverage_grid(cache_key)
            if cached_data:
                logger.info(f"Coverage grid found in database cache: {cache_key[:8]}...")
                # Add to memory cache for faster future access
                self._add_to_memory_cache(cache_key, cached_data)
                return cached_data
        
        # If not in cache, add to preload queue for future requests
        self._add_to_preload_queue(city_name, business_lines, vendor_filters)
        
        # Calculate immediately for this request
        logger.info(f"Calculating coverage grid for: {city_name}, BL: {business_lines}")
        grid_data = self._calculate_coverage_grid(city_name, business_lines, vendor_filters)
        
        if grid_data:
            # Cache the result
            self.db_manager.cache_coverage_grid(
                cache_key, city_name, 
                ','.join(business_lines) if business_lines else '',
                vendor_filters, grid_data
            )
            self._add_to_memory_cache(cache_key, grid_data)
            
        return grid_data
    
    def _calculate_coverage_grid(self, 
                                city_name: str, 
                                business_lines: List[str],
                                vendor_filters: Dict[str, Any]) -> Optional[List[Dict]]:
        """Calculate coverage grid with optimized vendor fetching"""
        try:
            # Import here to avoid circular imports
            from app_optimized import generate_coverage_grid, calculate_coverage_for_grid_vectorized, find_marketing_area_for_points
            
            # Get filtered vendors from database
            vendors_df = self.db_manager.get_vendors(
                city_name=city_name,
                business_lines=business_lines,
                status_ids=vendor_filters.get('status_ids'),
                grades=vendor_filters.get('grades'),
                visible=vendor_filters.get('visible'),
                is_open=vendor_filters.get('is_open')
            )
            
            if vendors_df.empty:
                logger.warning(f"No vendors found for filters: {vendor_filters}")
                return []
            
            # Generate grid points
            grid_points = generate_coverage_grid(city_name, self.config.GRID_SIZE_METERS)
            if not grid_points:
                logger.warning(f"No grid points generated for city: {city_name}")
                return []
            
            # Limit grid size for performance
            if len(grid_points) > self.config.MAX_GRID_POINTS:
                logger.info(f"Limiting grid size from {len(grid_points)} to {self.config.MAX_GRID_POINTS}")
                # Sample points evenly
                step = len(grid_points) // self.config.MAX_GRID_POINTS
                grid_points = grid_points[::step]
            
            # Find marketing areas for points (if available)
            point_area_info = find_marketing_area_for_points(grid_points, city_name)
            
            # Calculate coverage
            coverage_results = calculate_coverage_for_grid_vectorized(grid_points, vendors_df, city_name)
            
            # Process results with target-based logic if applicable
            processed_grid_data = self._process_coverage_results(
                coverage_results, point_area_info, business_lines, city_name
            )
            
            logger.info(f"Calculated coverage grid: {len(processed_grid_data)} points with coverage")
            return processed_grid_data
            
        except Exception as e:
            logger.error(f"Error calculating coverage grid: {e}")
            return None
    
    def _process_coverage_results(self, 
                                 coverage_results: List[Dict],
                                 point_area_info: List[Tuple],
                                 business_lines: List[str],
                                 city_name: str) -> List[Dict]:
        """Process coverage results with target-based analysis"""
        processed_data = []
        
        # Load target lookup if available
        target_lookup = {}
        if city_name == "tehran" and len(business_lines) == 1:
            # This would need to be loaded from the target data
            # For now, we'll skip target-based analysis in the cache manager
            pass
        
        for i, coverage in enumerate(coverage_results):
            if coverage['total_vendors'] > 0:
                area_id, area_name = point_area_info[i] if i < len(point_area_info) else (None, None)
                
                point_data = {
                    'lat': coverage['lat'],
                    'lng': coverage['lng'],
                    'coverage': coverage,
                    'marketing_area': area_name
                }
                
                # Add target-based analysis if applicable
                if target_lookup and area_id and len(business_lines) == 1:
                    target_key = (area_id, business_lines[0])
                    if target_key in target_lookup:
                        target_value = target_lookup[target_key]
                        actual_value = coverage['by_business_line'].get(business_lines[0], 0)
                        
                        point_data.update({
                            'target_business_line': business_lines[0],
                            'target_value': target_value,
                            'actual_value': actual_value,
                            'performance_ratio': (actual_value / target_value) if target_value > 0 else 2.0
                        })
                
                processed_data.append(point_data)
        
        return processed_data
    
    def _add_to_memory_cache(self, cache_key: str, data: List[Dict]):
        """Add data to memory cache with LRU eviction"""
        with self.memory_cache_lock:
            # Remove oldest entries if cache is full
            if len(self.memory_cache) >= self.max_memory_cache_size:
                # Find least recently used
                oldest_key = min(self.memory_cache.keys(), 
                               key=lambda k: self.memory_cache[k]['last_accessed'])
                del self.memory_cache[oldest_key]
            
            self.memory_cache[cache_key] = {
                'data': data,
                'last_accessed': datetime.now(),
                'access_count': 1
            }
    
    def _update_memory_cache_access(self, cache_key: str):
        """Update access time and count for memory cache entry"""
        if cache_key in self.memory_cache:
            self.memory_cache[cache_key]['last_accessed'] = datetime.now()
            self.memory_cache[cache_key]['access_count'] += 1
    
    def _add_to_preload_queue(self, city_name: str, business_lines: List[str], vendor_filters: Dict[str, Any]):
        """Add a coverage grid calculation to the preload queue"""
        task = CoverageGridTask(
            city_name=city_name,
            business_lines=business_lines,
            vendor_filters=vendor_filters,
            priority=self._calculate_priority(city_name, business_lines, vendor_filters)
        )
        
        with self.queue_lock:
            # Check if similar task already exists
            cache_key = generate_cache_key(city_name, business_lines, vendor_filters)
            existing_keys = [generate_cache_key(t.city_name, t.business_lines, t.vendor_filters) 
                           for t in self.preload_queue]
            
            if cache_key not in existing_keys:
                self.preload_queue.append(task)
                # Sort by priority
                self.preload_queue.sort(key=lambda x: x.priority)
    
    def start_preloading(self):
        """Start preloading common coverage grid combinations"""
        if self.is_preloading:
            logger.warning("Preloading already in progress")
            return
        
        self.is_preloading = True
        
        # Add common combinations to queue
        for combo in self.common_combinations:
            task = CoverageGridTask(**combo)
            with self.queue_lock:
                self.preload_queue.append(task)
        
        # Sort queue by priority
        with self.queue_lock:
            self.preload_queue.sort(key=lambda x: x.priority)
        
        # Start preloading worker
        self.preload_executor.submit(self._preload_worker)
        logger.info(f"Started coverage grid preloading with {len(self.preload_queue)} tasks")
    
    def _preload_worker(self):
        """Worker function for preloading coverage grids"""
        logger.info("Coverage grid preloading worker started")
        
        while self.is_preloading:
            task = None
            
            with self.queue_lock:
                if self.preload_queue:
                    task = self.preload_queue.pop(0)
            
            if task:
                try:
                    # Check if already cached
                    cache_key = generate_cache_key(task.city_name, task.business_lines, task.vendor_filters)
                    
                    if not self.db_manager.get_cached_coverage_grid(cache_key):
                        logger.info(f"Preloading coverage grid: {task.city_name}, BL: {task.business_lines}")
                        
                        grid_data = self._calculate_coverage_grid(
                            task.city_name, task.business_lines, task.vendor_filters
                        )
                        
                        if grid_data:
                            self.db_manager.cache_coverage_grid(
                                cache_key, task.city_name,
                                ','.join(task.business_lines) if task.business_lines else '',
                                task.vendor_filters, grid_data
                            )
                            logger.info(f"Preloaded coverage grid: {cache_key[:8]}... ({len(grid_data)} points)")
                    
                except Exception as e:
                    logger.error(f"Error preloading coverage grid: {e}")
                
                # Small delay between calculations to not overwhelm the system
                time.sleep(2)
            else:
                # No tasks in queue, wait before checking again
                time.sleep(10)
        
        logger.info("Coverage grid preloading worker stopped")
    
    def stop_preloading(self):
        """Stop the preloading process"""
        self.is_preloading = False
        self.preload_executor.shutdown(wait=False)
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.memory_cache_lock:
            memory_stats = {
                'size': len(self.memory_cache),
                'max_size': self.max_memory_cache_size,
                'keys': list(self.memory_cache.keys())
            }
        
        with self.queue_lock:
            queue_stats = {
                'pending_tasks': len(self.preload_queue),
                'is_preloading': self.is_preloading
            }
        
        # Database cache stats
        db_stats = {}
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM coverage_grid_cache")
                db_stats['database_cache_size'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT AVG(point_count) FROM coverage_grid_cache")
                avg_points = cursor.fetchone()[0]
                db_stats['average_points_per_grid'] = avg_points if avg_points else 0
        except Exception as e:
            logger.error(f"Error getting database cache stats: {e}")
            db_stats = {'error': str(e)}
        
        return {
            'memory_cache': memory_stats,
            'preload_queue': queue_stats,
            'database_cache': db_stats
        }
    
    def clear_cache(self, cache_type: str = "all"):
        """Clear cache (memory, database, or both)"""
        if cache_type in ("all", "memory"):
            with self.memory_cache_lock:
                self.memory_cache.clear()
                logger.info("Cleared memory cache")
        
        if cache_type in ("all", "database"):
            try:
                with self.db_manager.get_connection() as conn:
                    conn.execute("DELETE FROM coverage_grid_cache")
                    conn.commit()
                    logger.info("Cleared database cache")
            except Exception as e:
                logger.error(f"Error clearing database cache: {e}")
    
    def warm_up_cache(self, priority_cities: List[str] = None):
        """Warm up cache with high-priority combinations"""
        if priority_cities is None:
            priority_cities = ["tehran"]
        
        high_priority_combos = [
            combo for combo in self.common_combinations
            if combo['city_name'] in priority_cities and combo['priority'] <= 2
        ]
        
        logger.info(f"Warming up cache with {len(high_priority_combos)} high-priority combinations")
        
        for combo in high_priority_combos:
            try:
                self.get_or_calculate_coverage_grid(
                    combo['city_name'],
                    combo['business_lines'],
                    combo['vendor_filters']
                )
            except Exception as e:
                logger.error(f"Error warming up cache for {combo}: {e}")

# Global cache manager instance
_cache_manager = None

def get_cache_manager() -> Optional[CoverageGridCacheManager]:
    """Get the global cache manager instance"""
    return _cache_manager

def init_cache_manager(config: Config, db_manager: DatabaseManager) -> CoverageGridCacheManager:
    """Initialize the global cache manager instance"""
    global _cache_manager
    _cache_manager = CoverageGridCacheManager(config, db_manager)
    return _cache_manager
