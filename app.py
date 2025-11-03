"""
Web Server for Feed Distribution
Serves the generated XML feed and provides status API
"""

from flask import Flask, send_file, jsonify, render_template_string
from pathlib import Path
import json
import os
from datetime import datetime

app = Flask(__name__)

# Paths
PUBLIC_DIR = Path('public')
FEED_PATH = PUBLIC_DIR / 'google_shopping_feed.xml'
METADATA_PATH = PUBLIC_DIR / 'feed_metadata.json'


@app.route('/')
def index():
    """Landing page with feed info"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Racoon Lab Feed Manager</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 800px;
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
            .status { padding: 10px; border-radius: 4px; margin: 10px 0; }
            .success { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
            .info { background: #d1ecf1; color: #0c5460; }
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
            table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            td { padding: 10px; border-bottom: 1px solid #eee; }
            td:first-child { font-weight: bold; width: 200px; }
            .footer { text-align: center; color: #666; margin-top: 40px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🎯 Racoon Lab Feed Manager</h1>
            <p>Google Shopping Feed - Production</p>
            
            <div id="status"></div>
            
            <div style="margin: 20px 0;">
                <a href="/feed.xml" class="btn">📥 Download Feed XML</a>
                <a href="/api/status" class="btn">📊 API Status</a>
                <a href="/api/trigger" class="btn">🔄 Trigger Generation</a>
            </div>
            
            <table id="metadata"></table>
        </div>
        
        <div class="card">
            <h2>📋 Endpoints</h2>
            <table>
                <tr>
                    <td><code>GET /feed.xml</code></td>
                    <td>Download Google Shopping feed XML</td>
                </tr>
                <tr>
                    <td><code>GET /api/status</code></td>
                    <td>Get feed generation status (JSON)</td>
                </tr>
                <tr>
                    <td><code>POST /api/trigger</code></td>
                    <td>Manually trigger feed generation</td>
                </tr>
                <tr>
                    <td><code>GET /health</code></td>
                    <td>Health check endpoint</td>
                </tr>
            </table>
        </div>
        
        <div class="footer">
            <p>Racoon Lab Feed Manager v3.1 • Hosted on Render.com</p>
        </div>
        
        <script>
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    const status = document.getElementById('status');
                    const metadata = document.getElementById('metadata');
                    
                    if (data.feed_exists) {
                        status.className = 'status success';
                        status.innerHTML = '✅ Feed is up and running!';
                        
                        metadata.innerHTML = `
                            <tr><td>Status</td><td>✅ Active</td></tr>
                            <tr><td>Last Generated</td><td>${data.last_generated || 'N/A'}</td></tr>
                            <tr><td>Products</td><td>${data.product_count || 'N/A'}</td></tr>
                            <tr><td>Feed Items</td><td>${data.item_count || 'N/A'}</td></tr>
                            <tr><td>Products with Reviews</td><td>${data.products_with_reviews || 0} ⭐</td></tr>
                            <tr><td>File Size</td><td>${data.file_size_mb || 'N/A'}</td></tr>
                        `;
                    } else {
                        status.className = 'status error';
                        status.innerHTML = '⚠️ Feed not generated yet. Run cron job or trigger manually.';
                        
                        metadata.innerHTML = '<tr><td colspan="2">No feed data available</td></tr>';
                    }
                })
                .catch(err => {
                    document.getElementById('status').className = 'status error';
                    document.getElementById('status').innerHTML = '❌ Error loading status';
                });
        </script>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route('/feed.xml')
def get_feed():
    """Serve the XML feed"""
    if not FEED_PATH.exists():
        return jsonify({'error': 'Feed not generated yet'}), 404
    
    return send_file(
        FEED_PATH,
        mimetype='application/xml',
        as_attachment=False,
        download_name='google_shopping_feed.xml'
    )


@app.route('/api/status')
def api_status():
    """Get feed status"""
    if not FEED_PATH.exists():
        return jsonify({
            'feed_exists': False,
            'message': 'Feed not generated yet'
        })
    
    # Load metadata
    metadata = {}
    if METADATA_PATH.exists():
        with open(METADATA_PATH) as f:
            metadata = json.load(f)
    
    # File info
    file_size = FEED_PATH.stat().st_size if FEED_PATH.exists() else 0
    file_size_mb = f"{file_size / (1024*1024):.2f} MB"
    
    return jsonify({
        'feed_exists': True,
        'feed_url': '/feed.xml',
        'last_generated': metadata.get('generated_at'),
        'product_count': metadata.get('product_count'),
        'item_count': metadata.get('item_count'),
        'products_with_reviews': metadata.get('products_with_reviews', 0),
        'file_size_bytes': file_size,
        'file_size_mb': file_size_mb,
        'status': metadata.get('status', 'unknown')
    })


@app.route('/api/trigger', methods=['GET', 'POST'])
def api_trigger():
    """Manually trigger feed generation in background"""
    try:
        import subprocess
        import os
        
        # Run main.py in background (non-blocking)
        # Output goes to service logs, not captured
        process = subprocess.Popen(
            ['python', 'main.py'],
            stdout=None,  # Goes to service logs
            stderr=None,  # Goes to service logs
            cwd=os.getcwd()
        )
        
        return jsonify({
            'success': True,
            'message': 'Feed generation started in background',
            'pid': process.pid,
            'note': 'Check service logs for progress. Feed will be ready in ~12-15 minutes.',
            'status_url': '/api/status'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error starting feed generation: {str(e)}'
        }), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'feed_exists': FEED_PATH.exists()
    })


if __name__ == '__main__':
    # Create public directory
    PUBLIC_DIR.mkdir(exist_ok=True)
    
    # Run server
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
