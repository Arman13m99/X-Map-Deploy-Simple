# .env.example - Example environment configuration
# Copy this file to .env and update the values according to your setup

# =============================================================================
# METABASE CONFIGURATION
# =============================================================================
METABASE_URL=https://metabase.ofood.cloud
METABASE_USERNAME=your.email@company.com
METABASE_PASSWORD=your_password_here

# Metabase Question IDs (update these with your actual question IDs)
ORDER_DATA_QUESTION_ID=5822
VENDOR_DATA_QUESTION_ID=5045

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
# Path to SQLite database file (will be created if it doesn't exist)
DATABASE_PATH=tapsi_food_data.db

# =============================================================================
# FLASK CONFIGURATION
# =============================================================================
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
FLASK_DEBUG=false

# =============================================================================
# PERFORMANCE SETTINGS
# =============================================================================
# Number of parallel workers for data fetching
WORKER_COUNT=10

# Page size for data fetching (larger = faster but more memory usage)
PAGE_SIZE=100000

# Enable query optimization
ENABLE_QUERY_OPTIMIZATION=true

# Enable coverage grid preloading
PRELOAD_COVERAGE_GRIDS=true

# Enable response compression
ENABLE_COMPRESSION=true

# =============================================================================
# SCHEDULER SETTINGS
# =============================================================================
# How often to update vendor data (in minutes)
VENDORS_UPDATE_INTERVAL_MINUTES=10

# What time to update orders data daily (24-hour format)
ORDERS_UPDATE_TIME=09:00

# What time to clean up cache daily (24-hour format)
CACHE_CLEANUP_TIME=02:00

# =============================================================================
# CACHE SETTINGS
# =============================================================================
# How many days to keep cache entries
CACHE_CLEANUP_DAYS=7

# Maximum number of coverage grid cache entries
MAX_COVERAGE_CACHE_SIZE=1000

# Maximum number of heatmap cache entries
MAX_HEATMAP_CACHE_SIZE=500

# =============================================================================
# .env.development - Development environment
# Copy for local development
# =============================================================================

# Metabase (use development instance if available)
METABASE_URL=https://metabase-dev.ofood.cloud
METABASE_USERNAME=dev.user@company.com
METABASE_PASSWORD=dev_password

# Development database
DATABASE_PATH=tapsi_food_data_dev.db

# Flask development settings
FLASK_ENV=development
FLASK_DEBUG=true
FLASK_PORT=5001

# Reduced performance settings for development
WORKER_COUNT=4
PAGE_SIZE=50000
PRELOAD_COVERAGE_GRIDS=false

# More frequent cache cleanup in development
CACHE_CLEANUP_DAYS=1
VENDORS_UPDATE_INTERVAL_MINUTES=30

# =============================================================================
# .env.production - Production environment
# Use for production deployment
# =============================================================================

# Production Metabase
METABASE_URL=https://metabase.ofood.cloud
METABASE_USERNAME=prod.user@company.com
METABASE_PASSWORD=secure_production_password

# Production database
DATABASE_PATH=/app/data/tapsi_food_data.db

# Production Flask settings
FLASK_ENV=production
FLASK_DEBUG=false
FLASK_HOST=0.0.0.0
FLASK_PORT=5001

# Optimized performance settings
WORKER_COUNT=12
PAGE_SIZE=150000
ENABLE_QUERY_OPTIMIZATION=true
PRELOAD_COVERAGE_GRIDS=true
ENABLE_COMPRESSION=true

# Production cache settings
CACHE_CLEANUP_DAYS=7
MAX_COVERAGE_CACHE_SIZE=2000
MAX_HEATMAP_CACHE_SIZE=1000

# Scheduler settings
VENDORS_UPDATE_INTERVAL_MINUTES=10
ORDERS_UPDATE_TIME=09:00
CACHE_CLEANUP_TIME=02:00

# =============================================================================
# .env.docker - Docker environment
# For Docker deployment
# =============================================================================

# Use environment variables for sensitive data
METABASE_URL=${METABASE_URL}
METABASE_USERNAME=${METABASE_USERNAME}
METABASE_PASSWORD=${METABASE_PASSWORD}

# Docker-specific paths
DATABASE_PATH=/app/data/tapsi_food_data.db

# Container settings
FLASK_ENV=production
FLASK_DEBUG=false
FLASK_HOST=0.0.0.0
FLASK_PORT=5001

# Container-optimized settings
WORKER_COUNT=8
PAGE_SIZE=100000
ENABLE_QUERY_OPTIMIZATION=true
PRELOAD_COVERAGE_GRIDS=true
ENABLE_COMPRESSION=true

# Cache settings for container
CACHE_CLEANUP_DAYS=7
MAX_COVERAGE_CACHE_SIZE=1500
MAX_HEATMAP_CACHE_SIZE=750
