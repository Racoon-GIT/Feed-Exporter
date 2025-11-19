"""
Web Server for Multi-Platform Feed Distribution
Serves Google Shopping and Meta Catalog feeds with unified health monitoring
"""

from flask import Flask, send_file, jsonify, render_template_string
from pathlib import Path
import json
import os
from datetime import datetime

app = Flask(__name__)

# Paths
PUBLIC_DIR = Path('public')
GOOGLE_FEED_PATH = PUBLIC_DIR / 'google_shopping_feed.xml'
META_FEED_PATH = PUBLIC_DIR / 'meta_catalog_feed.xml'
METRICS_PATH = PUBLIC_DIR / 'feed_metrics.json'


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
            .platform-card.meta { border-left-color: #1877f2; }
            .status { padding: 10px; border-radius: 4px; margin: 10px 0; }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
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
            .btn.meta { background: #1877f2; }
            .btn.meta:hover { background: #145dbf; }
            table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            td { padding: 10px; border-bottom: 1px solid #eee; }
            td:first-child { font-weight: bold; width: 200px; }
            .footer { text-align: center; color: #666; margin-top: 40px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🎯 Racoon Lab Feed Manager</h1>
            <p>Multi-Platform Feed Distribution: Google Shopping & Meta Catalog</p>
            
            <div style="margin: 20px 0;">
                <a href="/api/trigger" class="btn">🔄 Trigger Generation (All Feeds)</a>
                <a href="/api/health" class="btn">📊 Health Status</a>
            </div>
        </div>
        
        <!-- Google Shopping Feed -->
        <div class="card platform-card">
            <h2>📱 Google Shopping Feed</h2>
            <div id="google-status"></div>
            <table id="google-metrics"></table>
            <div style="margin: 20px 0;">
                <a href="/feed/google" class="btn">📥 Download Google Feed</a>
            </div>
        </div>
        
        <!-- Meta Catalog Feed -->
        <div class="card platform-card meta">
            <h2>📘 Meta (Facebook & Instagram) Catalog</h2>
            <div id="meta-status"></div>
            <table id="meta-metrics"></table>
            <div style="margin: 20px 0;">
                <a href="/feed/meta" class="btn meta">📥 Download Meta Feed</a>
            </div>
        </div>
        
        <div class="card">
            <h2>📋 API Endpoints</h2>
            <table>
                <tr>
                    <td><code>GET /feed/google</code></td>
                    <td>Download Google Shopping feed XML</td>
                </tr>
                <tr>
                    <td><code>GET /feed/meta</code></td>
                    <td>Download Meta catalog feed XML</td>
                </tr>
                <tr>
                    <td><code>GET /api/health</code></td>
                    <td>Health check for all platforms (JSON)</td>
                </tr>
                <tr>
                    <td><code>POST /api/trigger</code></td>
                    <td>Manually trigger feed generation (all platforms)</td>
                </tr>
            </table>
        </div>
        
        <div class="footer">
            <p>Racoon Lab Feed Manager v4.0 • Multi-Platform Architecture • Hosted on Render.com</p>
        </div>
        
        <script>
            fetch('/api/health')
                .then(r => r.json())
                .then(data => {
                    // Google Feed Status
                    const googleStatus = document.getElementById('google-status');
                    const googleMetrics = document.getElementById('google-metrics');
                    
                    if (data.google && data.google.exists) {
                        googleStatus.className = 'status success';
                        googleStatus.innerHTML = '✅ Google feed is active';
                        
                        googleMetrics.innerHTML = `
                            <tr><td>Last Generated</td><td>${data.google.generated_at || 'N/A'}</td></tr>
                            <tr><td>Products</td><td>${data.google.products || 'N/A'}</td></tr>
                            <tr><td>Items</td><td>${data.google.items || 'N/A'}</td></tr>
                            <tr><td>File Size</td><td>${data.google.file_size_mb || 'N/A'} MB</td></tr>
                        `;
                    } else {
                        googleStatus.className = 'status error';
                        googleStatus.innerHTML = '⚠️ Google feed not generated yet';
                        googleMetrics.innerHTML = '<tr><td colspan="2">No data available</td></tr>';
                    }
                    
                    // Meta Feed Status
                    const metaStatus = document.getElementById('meta-status');
                    const metaMetrics = document.getElementById('meta-metrics');
                    
                    if (data.meta && data.meta.exists) {
                        metaStatus.className = 'status success';
                        metaStatus.innerHTML = '✅ Meta feed is active';
                        
                        metaMetrics.innerHTML = `
                            <tr><td>Last Generated</td><td>${data.meta.generated_at || 'N/A'}</td></tr>
                            <tr><td>Products</td><td>${data.meta.products || 'N/A'}</td></tr>
                            <tr><td>Items</td><td>${data.meta.items || 'N/A'}</td></tr>
                            <tr><td>File Size</td><td>${data.meta.file_size_mb || 'N/A'} MB</td></tr>
                        `;
                    } else {
                        metaStatus.className = 'status error';
                        metaStatus.innerHTML = '⚠️ Meta feed not generated yet';
                        metaMetrics.innerHTML = '<tr><td colspan="2">No data available</td></tr>';
                    }
                })
                .catch(err => {
                    console.error('Error loading status:', err);
                });
        </script>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route('/feed/google')
def get_google_feed():
    """Serve Google Shopping feed"""
    if not GOOGLE_FEED_PATH.exists():
        return jsonify({'error': 'Google feed not generated yet'}), 404
    
    return send_file(
        GOOGLE_FEED_PATH,
        mimetype='application/xml',
        as_attachment=False,
        download_name='google_shopping_feed.xml'
    )


@app.route('/feed/meta')
def get_meta_feed():
    """Serve Meta catalog feed"""
    if not META_FEED_PATH.exists():
        return jsonify({'error': 'Meta feed not generated yet'}), 404
    
    return send_file(
        META_FEED_PATH,
        mimetype='application/xml',
        as_attachment=False,
        download_name='meta_catalog_feed.xml'
    )


@app.route('/api/health')
def api_health():
    """Get health status for all platforms"""
    
    # Load metrics
    metrics = {}
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH) as f:
                metrics = json.load(f)
        except:
            pass
    
    # Google feed status
    google_status = {
        'exists': GOOGLE_FEED_PATH.exists(),
        'url': '/feed/google'
    }
    
    if GOOGLE_FEED_PATH.exists():
        file_size = GOOGLE_FEED_PATH.stat().st_size / (1024 * 1024)
        google_status['file_size_mb'] = round(file_size, 2)
        
        # Add metrics if available
        if 'google' in metrics:
            google_status.update({
                'generated_at': metrics['google'].get('generated_at'),
                'products': metrics['google'].get('total_products'),
                'items': metrics['google'].get('total_items'),
                'duration_seconds': metrics['google'].get('duration_seconds')
            })
    
    # Meta feed status
    meta_status = {
        'exists': META_FEED_PATH.exists(),
        'url': '/feed/meta'
    }
    
    if META_FEED_PATH.exists():
        file_size = META_FEED_PATH.stat().st_size / (1024 * 1024)
        meta_status['file_size_mb'] = round(file_size, 2)
        
        # Add metrics if available
        if 'meta' in metrics:
            meta_status.update({
                'generated_at': metrics['meta'].get('generated_at'),
                'products': metrics['meta'].get('total_products'),
                'items': metrics['meta'].get('total_items'),
                'duration_seconds': metrics['meta'].get('duration_seconds')
            })
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'google': google_status,
        'meta': meta_status
    })


@app.route('/api/trigger', methods=['GET', 'POST'])
def api_trigger():
    """Manually trigger feed generation (all platforms)"""
    try:
        import subprocess
        
        # Run orchestrator in background
        process = subprocess.Popen(
            ['python', 'orchestrator.py'],
            stdout=None,
            stderr=None,
            cwd=os.getcwd()
        )
        
        return jsonify({
            'success': True,
            'message': 'Feed generation started for all platforms',
            'pid': process.pid,
            'note': 'Check service logs for progress. Feeds will be ready in ~15-20 minutes.',
            'status_url': '/api/health'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error starting feed generation: {str(e)}'
        }), 500


@app.route('/health')
def health():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


if __name__ == '__main__':
    # Create public directory
    PUBLIC_DIR.mkdir(exist_ok=True)
    
    # Run server
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
