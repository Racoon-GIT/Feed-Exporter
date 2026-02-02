"""
Web Server for Multi-Platform Feed Distribution
Serves Google Shopping and Meta Catalog feeds with unified health monitoring
Includes internal scheduled job for automatic feed generation
"""

from flask import Flask, send_file, jsonify, render_template_string
from pathlib import Path
import json
import os
import logging
from datetime import datetime
# APScheduler imports removed - no longer needed for internal scheduling
# from apscheduler.schedulers.background import BackgroundScheduler
# from apscheduler.triggers.cron import CronTrigger
# import atexit

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
PUBLIC_DIR = Path('public')
GOOGLE_FEED_PATH = PUBLIC_DIR / 'google_shopping_feed.xml'
META_FEED_PATH = PUBLIC_DIR / 'meta_catalog_feed.xml'
METRICS_PATH = PUBLIC_DIR / 'feed_metrics.json'


def generate_feeds_job():
    """
    Background job to generate all feeds
    This runs automatically every day at 6:00 AM UTC
    """
    try:
        logger.info("="*80)
        logger.info(f"🔄 Scheduled feed generation started at {datetime.utcnow().isoformat()}")
        logger.info("="*80)
        
        # Import and run orchestrator
        from orchestrator import FeedOrchestrator
        
        orchestrator = FeedOrchestrator()
        success = orchestrator.generate_all_feeds()
        
        if success:
            logger.info("✅ Scheduled feed generation completed successfully!")
        else:
            logger.error("❌ Scheduled feed generation failed!")
            
    except Exception as e:
        logger.error(f"💥 Error in scheduled feed generation: {e}", exc_info=True)


# APScheduler disabled - scheduling now handled by external Scheduler app
# This allows the service to run on Render FREE tier without consuming hours
# when not actively generating feeds. The external Scheduler app triggers
# feed generation via /api/trigger endpoint and keeps service alive during execution.
#
# Previous internal scheduling (now disabled):
# - Daily generation at 6:00 AM UTC (7:00 AM CET)
# - Managed by APScheduler BackgroundScheduler
#
# New external scheduling:
# - Scheduler app calls /api/trigger at 6:00 AM UTC
# - Scheduler app pings /health every 5 minutes during 5:00-7:59 UTC window
# - Service spins down outside generation window to save FREE tier hours


@app.route('/')
def index():
    """Landing page with multi-platform feed info"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Racoon Lab Feed Manager - Multi-Platform</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 1000px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .card {
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            h1 { color: #333; margin-top: 0; }
            h2 { color: #555; margin-top: 0; }
            .platform-card {
                border-left: 4px solid #007bff;
                padding-left: 20px;
                margin: 20px 0;
            }
            .meta-card {
                border-left: 4px solid #4267B2;
            }
            .status-good { color: #28a745; }
            .status-warning { color: #ffc107; }
            .status-error { color: #dc3545; }
            .btn {
                display: inline-block;
                padding: 10px 20px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin: 5px;
            }
            .btn:hover { background: #0056b3; }
            .btn-meta { background: #4267B2; }
            .btn-meta:hover { background: #365899; }
            .metric { 
                display: inline-block;
                margin: 10px 20px 10px 0;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 4px;
            }
            .metric-label { 
                font-size: 0.85em;
                color: #666;
                text-transform: uppercase;
            }
            .metric-value {
                font-size: 1.5em;
                font-weight: bold;
                color: #333;
            }
            .info-box {
                background: #e7f3ff;
                padding: 15px;
                border-radius: 4px;
                border-left: 4px solid #007bff;
                margin: 20px 0;
            }
            .schedule-info {
                background: #fff3cd;
                padding: 10px 15px;
                border-radius: 4px;
                border-left: 4px solid #ffc107;
                margin: 15px 0;
                font-size: 0.9em;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🎯 Racoon Lab Feed Manager</h1>
            <p><strong>Multi-Platform Feed Distribution:</strong> Google Shopping & Meta Catalog</p>
            
            <div class="schedule-info">
                ⏰ <strong>Automatic Generation:</strong> Feeds are generated automatically every day at 6:00 AM UTC (7:00 AM CET) via external Scheduler
            </div>
            
            <div style="margin-top: 20px;">
                <a href="/api/trigger" class="btn">🔄 Trigger Generation (All Feeds)</a>
                <a href="/api/health" class="btn">📊 Health Status</a>
            </div>
        </div>
        
        <div class="card platform-card">
            <h2>📱 Google Shopping Feed</h2>
            
            {% if google_exists %}
                <p class="status-good">✅ Google feed generated successfully</p>
                
                <div class="metric">
                    <div class="metric-label">Products</div>
                    <div class="metric-value">{{ google_metrics.get('total_products', 'N/A') }}</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">Items</div>
                    <div class="metric-value">{{ google_metrics.get('total_items', 'N/A') }}</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">File Size</div>
                    <div class="metric-value">{{ google_metrics.get('file_size_mb', 'N/A') }} MB</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">Generated</div>
                    <div class="metric-value" style="font-size: 1em;">{{ google_metrics.get('generated_at', 'Unknown')[:19] }}</div>
                </div>
                
                <div style="margin-top: 20px;">
                    <a href="/feed/google" class="btn">📥 Download Google Feed</a>
                </div>
            {% else %}
                <p class="status-warning">⚠️ Google feed not generated yet</p>
                <p>No data available</p>
                <div style="margin-top: 20px;">
                    <a href="/feed/google" class="btn">📥 Download Google Feed</a>
                </div>
            {% endif %}
        </div>
        
        <div class="card platform-card meta-card">
            <h2>📘 Meta (Facebook & Instagram) Catalog</h2>
            
            {% if meta_exists %}
                <p class="status-good">✅ Meta feed generated successfully</p>
                
                <div class="metric">
                    <div class="metric-label">Products</div>
                    <div class="metric-value">{{ meta_metrics.get('total_products', 'N/A') }}</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">Items</div>
                    <div class="metric-value">{{ meta_metrics.get('total_items', 'N/A') }}</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">File Size</div>
                    <div class="metric-value">{{ meta_metrics.get('file_size_mb', 'N/A') }} MB</div>
                </div>
                
                <div class="metric">
                    <div class="metric-label">Generated</div>
                    <div class="metric-value" style="font-size: 1em;">{{ meta_metrics.get('generated_at', 'Unknown')[:19] }}</div>
                </div>
                
                <div style="margin-top: 20px;">
                    <a href="/feed/meta" class="btn btn-meta">📥 Download Meta Feed</a>
                </div>
            {% else %}
                <p class="status-warning">⚠️ Meta feed not generated yet</p>
                <p>No data available</p>
                <div style="margin-top: 20px;">
                    <a href="/feed/meta" class="btn btn-meta">📥 Download Meta Feed</a>
                </div>
            {% endif %}
        </div>
        
        <div class="info-box">
            <strong>ℹ️ Feed URLs:</strong><br>
            Google Shopping: <code>{{ request.host_url }}feed/google</code><br>
            Meta Catalog: <code>{{ request.host_url }}feed/meta</code>
        </div>
    </body>
    </html>
    """
    
    # Load metrics
    google_metrics = {}
    meta_metrics = {}
    
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, 'r') as f:
                metrics = json.load(f)
                google_metrics = metrics.get('google', {})
                meta_metrics = metrics.get('meta', {})
        except:
            pass
    
    return render_template_string(
        html,
        google_exists=GOOGLE_FEED_PATH.exists(),
        meta_exists=META_FEED_PATH.exists(),
        google_metrics=google_metrics,
        meta_metrics=meta_metrics
    )


@app.route('/feed/google')
def serve_google_feed():
    """Serve Google Shopping feed XML"""
    if not GOOGLE_FEED_PATH.exists():
        return jsonify({'error': 'Google feed not found. Please trigger generation first.'}), 404
    
    return send_file(
        GOOGLE_FEED_PATH,
        mimetype='application/xml',
        as_attachment=True,
        download_name='google_shopping_feed.xml'
    )


@app.route('/feed/meta')
def serve_meta_feed():
    """Serve Meta Catalog feed XML"""
    if not META_FEED_PATH.exists():
        return jsonify({'error': 'Meta feed not found. Please trigger generation first.'}), 404
    
    return send_file(
        META_FEED_PATH,
        mimetype='application/xml',
        as_attachment=True,
        download_name='meta_catalog_feed.xml'
    )


@app.route('/api/health')
def api_health():
    """Health check endpoint with feed status"""
    
    google_status = {
        'exists': GOOGLE_FEED_PATH.exists(),
        'file_size_mb': 0,
        'generated_at': None
    }
    
    meta_status = {
        'exists': META_FEED_PATH.exists(),
        'file_size_mb': 0,
        'generated_at': None
    }
    
    # Load metrics if available
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, 'r') as f:
                metrics = json.load(f)
                
                if 'google' in metrics:
                    google_status.update(metrics['google'])
                
                if 'meta' in metrics:
                    meta_status.update(metrics['meta'])
        except:
            pass
    
    # Get file sizes
    if google_status['exists']:
        google_status['file_size_mb'] = round(GOOGLE_FEED_PATH.stat().st_size / (1024 * 1024), 2)
    
    if meta_status['exists']:
        meta_status['file_size_mb'] = round(META_FEED_PATH.stat().st_size / (1024 * 1024), 2)
    
    overall_status = 'healthy' if (google_status['exists'] and meta_status['exists']) else 'partial'
    
    return jsonify({
        'status': overall_status,
        'timestamp': datetime.utcnow().isoformat(),
        'google': google_status,
        'meta': meta_status,
        'scheduled_generation': '6:00 AM UTC daily (external Scheduler)'
    })


@app.route('/api/trigger', methods=['GET', 'POST'])
def api_trigger():
    """Manually trigger feed generation (all platforms) in background thread"""
    try:
        logger.info("="*80)
        logger.info("🔄 Manual feed generation triggered via API")
        logger.info("="*80)
        
        # Define generation function to run in background
        def run_generation():
            """Execute feed generation in background thread"""
            try:
                from orchestrator import FeedOrchestrator
                
                orchestrator = FeedOrchestrator()
                success = orchestrator.generate_all_feeds()
                
                if success:
                    logger.info("✅ Manual feed generation completed successfully!")
                else:
                    logger.error("❌ Manual feed generation completed with errors!")
                    
            except Exception as e:
                logger.error(f"💥 Error in manual feed generation: {e}", exc_info=True)
        
        # Start generation in background thread (daemon=True for cleanup)
        import threading
        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()
        
        # Return immediately - generation continues in background
        return jsonify({
            'success': True,
            'message': 'Feed generation started in background. Check status in ~25 minutes.',
            'timestamp': datetime.utcnow().isoformat(),
            'note': 'This is an async operation. Refresh the dashboard after completion.'
        })
            
    except Exception as e:
        logger.error(f"Error in manual feed generation: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/health')
def health():
    """Simple health check for Render"""
    return 'OK', 200


if __name__ == '__main__':
    # Ensure public directory exists
    PUBLIC_DIR.mkdir(exist_ok=True)
    
    # Run the app
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
