#!/usr/bin/env python
"""
Migration script to convert from the original Tapsi Food Map Dashboard
to the optimized version with database storage and caching.

This script will:
1. Check for existing data files
2. Create the new database structure
3. Import any existing data
4. Set up the new configuration
5. Verify the migration was successful

Run this script once before switching to the optimized version.
"""

import os
import sys
import logging
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_original_files() -> Dict[str, bool]:
    """Check which original files are present"""
    original_files = {
        'app.py': Path('app.py').exists(),
        'script.js': Path('script.js').exists() or Path('public/script.js').exists(),
        'index.html': Path('index.html').exists() or Path('public/index.html').exists(),
        'styles.css': Path('styles.css').exists() or Path('public/styles.css').exists(),
        'mini.py': Path('mini.py').exists(),
        'run_production.py': Path('run_production.py').exists(),
        'requirements.txt': Path('requirements.txt').exists(),
    }
    
    data_dirs = {
        'src_vendor': Path('src/vendor').exists(),
        'src_polygons': Path('src/polygons').exists(),
        'src_targets': Path('src/targets').exists(),
    }
    
    return {**original_files, **data_dirs}

def backup_original_files():
    """Create a backup of original files"""
    backup_dir = Path('backup_original')
    backup_dir.mkdir(exist_ok=True)
    
    logger.info(f"Creating backup in {backup_dir}...")
    
    files_to_backup = [
        'app.py', 'script.js', 'index.html', 'styles.css', 
        'mini.py', 'run_production.py', 'requirements.txt'
    ]
    
    backed_up = []
    for file_name in files_to_backup:
        source = Path(file_name)
        if source.exists():
            destination = backup_dir / file_name
            shutil.copy2(source, destination)
            backed_up.append(file_name)
            logger.info(f"Backed up: {file_name}")
    
    # Backup public directory if it exists
    public_dir = Path('public')
    if public_dir.exists():
        backup_public = backup_dir / 'public'
        if backup_public.exists():
            shutil.rmtree(backup_public)
        shutil.copytree(public_dir, backup_public)
        backed_up.append('public/')
        logger.info("Backed up: public/ directory")
    
    return backed_up

def extract_config_from_original() -> Dict[str, Any]:
    """Extract configuration from original app.py"""
    config = {}
    
    try:
        if Path('app.py').exists():
            with open('app.py', 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Extract configuration values using simple string parsing
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if 'METABASE_URL' in line and '=' in line:
                        config['METABASE_URL'] = line.split('=')[1].strip().strip('"\'')
                    elif 'METABASE_USERNAME' in line and '=' in line:
                        config['METABASE_USERNAME'] = line.split('=')[1].strip().strip('"\'')
                    elif 'METABASE_PASSWORD' in line and '=' in line:
                        config['METABASE_PASSWORD'] = line.split('=')[1].strip().strip('"\'')
                    elif 'ORDER_DATA_QUESTION_ID' in line and '=' in line:
                        try:
                            config['ORDER_DATA_QUESTION_ID'] = int(line.split('=')[1].strip())
                        except ValueError:
                            pass
                    elif 'VENDOR_DATA_QUESTION_ID' in line and '=' in line:
                        try:
                            config['VENDOR_DATA_QUESTION_ID'] = int(line.split('=')[1].strip())
                        except ValueError:
                            pass
                    elif 'WORKER_COUNT' in line and '=' in line:
                        try:
                            config['WORKER_COUNT'] = int(line.split('=')[1].strip())
                        except ValueError:
                            pass
                    elif 'PAGE_SIZE' in line and '=' in line:
                        try:
                            config['PAGE_SIZE'] = int(line.split('=')[1].strip())
                        except ValueError:
                            pass
                
                logger.info("Extracted configuration from original app.py")
                
    except Exception as e:
        logger.warning(f"Could not extract configuration from app.py: {e}")
    
    return config

def create_env_file(config: Dict[str, Any]):
    """Create .env file with extracted configuration"""
    env_content = f"""# Tapsi Food Map Dashboard - Environment Configuration
# Generated by migration script on {datetime.now().isoformat()}

# Metabase Configuration
METABASE_URL={config.get('METABASE_URL', 'https://metabase.ofood.cloud')}
METABASE_USERNAME={config.get('METABASE_USERNAME', 'your.email@company.com')}
METABASE_PASSWORD={config.get('METABASE_PASSWORD', 'your_password_here')}

# Question IDs
ORDER_DATA_QUESTION_ID={config.get('ORDER_DATA_QUESTION_ID', 5822)}
VENDOR_DATA_QUESTION_ID={config.get('VENDOR_DATA_QUESTION_ID', 5045)}

# Database
DATABASE_PATH=tapsi_food_data.db

# Flask Settings
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5001
FLASK_DEBUG=false

# Performance Settings
WORKER_COUNT={config.get('WORKER_COUNT', 10)}
PAGE_SIZE={config.get('PAGE_SIZE', 100000)}
ENABLE_QUERY_OPTIMIZATION=true
PRELOAD_COVERAGE_GRIDS=true
ENABLE_COMPRESSION=true

# Scheduler Settings
VENDORS_UPDATE_INTERVAL_MINUTES=10
ORDERS_UPDATE_TIME=09:00
CACHE_CLEANUP_TIME=02:00

# Cache Settings
CACHE_CLEANUP_DAYS=7
MAX_COVERAGE_CACHE_SIZE=1000
MAX_HEATMAP_CACHE_SIZE=500
"""
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    logger.info("Created .env file with configuration")

def check_data_directories():
    """Check and report on data directories"""
    required_dirs = [
        'src/vendor',
        'src/polygons/tapsifood_marketing_areas',
        'src/polygons/tehran_districts',
        'src/targets',
        'public'
    ]
    
    missing_dirs = []
    existing_dirs = []
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            existing_dirs.append(dir_path)
        else:
            missing_dirs.append(dir_path)
    
    logger.info(f"Found {len(existing_dirs)} required directories")
    for dir_path in existing_dirs:
        logger.info(f"  ✓ {dir_path}")
    
    if missing_dirs:
        logger.warning(f"Missing {len(missing_dirs)} directories:")
        for dir_path in missing_dirs:
            logger.warning(f"  ✗ {dir_path}")
    
    return existing_dirs, missing_dirs

def initialize_database():
    """Initialize the new database"""
    try:
        # Import the new modules
        sys.path.insert(0, '.')
        from models import DatabaseManager
        from config import get_config
        
        config = get_config()
        db_manager = DatabaseManager(config.DATABASE_PATH)
        
        logger.info("Database initialized successfully")
        
        # Get database stats
        stats = db_manager.get_database_stats()
        logger.info(f"Database stats: {stats}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def test_new_system():
    """Test if the new system can start up properly"""
    try:
        logger.info("Testing new system startup...")
        
        # Try to import and create the app
        from app_optimized import create_app
        
        app = create_app()
        
        # Test the app configuration
        with app.app_context():
            # Try to access initial data endpoint
            from app_optimized import db_manager
            if db_manager:
                stats = db_manager.get_database_stats()
                logger.info(f"System test successful. Database stats: {stats}")
                return True
            else:
                logger.error("Database manager not initialized")
                return False
        
    except Exception as e:
        logger.error(f"System test failed: {e}")
        return False

def create_migration_report(original_files: Dict[str, bool], 
                          backed_up_files: list,
                          missing_dirs: list) -> str:
    """Create a migration report"""
    report = f"""
# Tapsi Food Map Dashboard - Migration Report
Generated: {datetime.now().isoformat()}

## Original Files Status
"""
    
    for file_name, exists in original_files.items():
        status = "✓ Found" if exists else "✗ Missing"
        report += f"- {file_name}: {status}\n"
    
    report += f"""
## Backup Status
Backed up {len(backed_up_files)} files to backup_original/:
"""
    
    for file_name in backed_up_files:
        report += f"- {file_name}\n"
    
    if missing_dirs:
        report += f"""
## Missing Data Directories
⚠️  The following directories are missing and may affect functionality:
"""
        for dir_path in missing_dirs:
            report += f"- {dir_path}\n"
    
    report += """
## Next Steps
1. Review the generated .env file and update credentials if needed
2. Install new requirements: pip install -r requirements.txt
3. Run the optimized application: python run_production_optimized.py
4. Check the admin endpoints at http://localhost:5001/api/admin/scheduler-status

## Rollback Instructions
If you need to rollback to the original system:
1. Stop the new application
2. Copy files from backup_original/ back to the main directory
3. Run the original system: python run_production.py

## Support
If you encounter issues, check the logs and ensure all data directories
are properly populated with your organization's data files.
"""
    
    return report

def main():
    """Main migration function"""
    logger.info("=" * 60)
    logger.info("Tapsi Food Map Dashboard - Migration to Optimized Version")
    logger.info("=" * 60)
    
    # Check original files
    logger.info("Step 1: Checking original files...")
    original_files = check_original_files()
    
    # Create backup
    logger.info("Step 2: Creating backup...")
    backed_up_files = backup_original_files()
    
    # Extract configuration
    logger.info("Step 3: Extracting configuration...")
    config = extract_config_from_original()
    
    # Create .env file
    logger.info("Step 4: Creating environment configuration...")
    create_env_file(config)
    
    # Check data directories
    logger.info("Step 5: Checking data directories...")
    existing_dirs, missing_dirs = check_data_directories()
    
    # Initialize database
    logger.info("Step 6: Initializing database...")
    db_success = initialize_database()
    
    # Test new system
    logger.info("Step 7: Testing new system...")
    test_success = test_new_system()
    
    # Create migration report
    report = create_migration_report(original_files, backed_up_files, missing_dirs)
    
    with open('migration_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    # Final status
    logger.info("=" * 60)
    logger.info("Migration Summary:")
    logger.info(f"  Original files found: {sum(original_files.values())}/{len(original_files)}")
    logger.info(f"  Files backed up: {len(backed_up_files)}")
    logger.info(f"  Database initialization: {'✓' if db_success else '✗'}")
    logger.info(f"  System test: {'✓' if test_success else '✗'}")
    logger.info(f"  Missing data directories: {len(missing_dirs)}")
    
    if db_success and test_success:
        logger.info("✅ Migration completed successfully!")
        logger.info("You can now run: python run_production_optimized.py")
    else:
        logger.error("❌ Migration had issues. Check the logs and migration_report.md")
        
    logger.info("Full report saved to: migration_report.md")
    logger.info("=" * 60)

if __name__ == '__main__':
    main()
