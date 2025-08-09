#!/usr/bin/env python
"""
Production server runner for Optimized Tapsi Food Map Dashboard
Works on both Windows and Linux with improved performance and monitoring
"""

import os
import sys
import platform
import multiprocessing
import signal
import atexit
import logging
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our optimized app
from app_optimized import create_app
from config import get_config

def get_worker_count():
    """Calculate optimal worker count based on CPU cores"""
    cpu_count = multiprocessing.cpu_count()
    # Use (2 * CPU cores + 1) as recommended by gunicorn, but cap at 12 for memory efficiency
    return min(12, (cpu_count * 2) + 1)

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def check_dependencies():
    """Check if all required dependencies are available"""
    required_modules = [
        'flask', 'pandas', 'geopandas', 'shapely', 'numpy', 
        'scipy', 'schedule', 'requests'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        logger.error(f"Missing required modules: {missing_modules}")
        logger.error("Please install missing modules: pip install -r requirements.txt")
        sys.exit(1)

def check_data_directories():
    """Ensure required data directories exist"""
    required_dirs = [
        'src/polygons/tapsifood_marketing_areas',
        'src/polygons/tehran_districts',
        'src/vendor',
        'src/targets',
        'public'
    ]
    
    missing_dirs = []
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)
    
    if missing_dirs:
        logger.warning(f"Missing data directories: {missing_dirs}")
        logger.warning("Some features may not work properly without required data files")

def optimize_environment():
    """Set environment variables for optimal performance"""
    # Database optimizations
    os.environ.setdefault('SQLITE_THREADSAFE', '1')
    
    # Memory optimizations
    os.environ.setdefault('PYTHONHASHSEED', '0')  # Reproducible hash randomization
    
    # Flask optimizations
    os.environ.setdefault('FLASK_ENV', 'production')
    
    # Pandas optimizations
    os.environ.setdefault('PANDAS_PLOTTING_BACKEND', 'matplotlib')

def run_with_waitress():
    """Run application with Waitress (Windows-friendly)"""
    try:
        from waitress import serve
        
        config = get_config()
        app = create_app()
        
        logger.info("Starting Waitress server (Windows/Cross-platform)...")
        logger.info(f"Server will be available at http://0.0.0.0:{config.FLASK_PORT}")
        logger.info("Press Ctrl+C to stop the server")
        
        serve(
            app, 
            host='0.0.0.0', 
            port=config.FLASK_PORT,
            threads=8,
            connection_limit=200,
            cleanup_interval=30,
            channel_timeout=120
        )
        
    except ImportError:
        logger.error("Waitress not installed. Please install it with: pip install waitress")
        logger.error("Falling back to Flask development server...")
        run_with_flask()
    except Exception as e:
        logger.error(f"Error running Waitress server: {e}")
        sys.exit(1)

def run_with_gunicorn():
    """Run application with Gunicorn (Linux/Unix)"""
    try:
        import gunicorn.app.base
        
        class StandaloneApplication(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()
            
            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)
            
            def load(self):
                return self.application
        
        config = get_config()
        app = create_app()
        
        worker_count = get_worker_count()
        
        options = {
            'bind': f'0.0.0.0:{config.FLASK_PORT}',
            'workers': worker_count,
            'worker_class': 'sync',
            'worker_connections': 100,
            'timeout': 120,
            'keepalive': 2,
            'threads': 2,
            'max_requests': 1000,
            'max_requests_jitter': 100,
            'preload_app': True,
            'accesslog': '-',
            'errorlog': '-',
            'loglevel': 'info',
            'access_log_format': '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s',
        }
        
        logger.info(f"Starting Gunicorn server (Linux/Unix)...")
        logger.info(f"Workers: {worker_count}")
        logger.info(f"Server will be available at http://0.0.0.0:{config.FLASK_PORT}")
        logger.info("Press Ctrl+C to stop the server")
        
        StandaloneApplication(app, options).run()
        
    except ImportError:
        logger.error("Gunicorn not installed. Please install it with: pip install gunicorn")
        logger.error("Falling back to Waitress...")
        run_with_waitress()
    except Exception as e:
        logger.error(f"Error running Gunicorn server: {e}")
        sys.exit(1)

def run_with_flask():
    """Fallback to Flask development server"""
    logger.warning("Running with Flask development server (not recommended for production)")
    
    config = get_config()
    app = create_app()
    
    app.run(
        host='0.0.0.0', 
        port=config.FLASK_PORT, 
        debug=False,
        threaded=True
    )

def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Tapsi Food Map Dashboard - Production Server")
    logger.info("=" * 60)
    
    # Setup signal handlers
    setup_signal_handlers()
    
    # Check system requirements
    check_dependencies()
    check_data_directories()
    
    # Optimize environment
    optimize_environment()
    
    # Determine the best server to use
    is_windows = platform.system() == 'Windows'
    
    try:
        if is_windows:
            # On Windows, prefer Waitress
            run_with_waitress()
        else:
            # On Linux/Unix, prefer Gunicorn
            run_with_gunicorn()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        logger.info("Server shutdown complete")

if __name__ == '__main__':
    main()
