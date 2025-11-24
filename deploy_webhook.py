"""
VixEditor Deployment Webhook Service
Listens for webhook calls and triggers deployments
"""
import os
import subprocess
import logging
import hmac
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.deploy')

# Configuration
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'change-me-in-production')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '4001'))
DEPLOY_SCRIPT = Path(__file__).parent / 'deploy.sh'
LOG_DIR = Path(__file__).parent / 'logs'
LOG_FILE = LOG_DIR / 'webhook.log'

# Ensure log directory exists
LOG_DIR.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def verify_signature(payload, signature, secret):
    """Verify GitHub/GitLab webhook signature"""
    if not signature:
        return False
    
    # GitHub uses sha256
    if signature.startswith('sha256='):
        expected = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)
    
    # GitLab uses sha256 without prefix
    elif signature.startswith('sha1='):
        expected = 'sha1=' + hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha1
        ).hexdigest()
        return hmac.compare_digest(signature, expected)
    
    # Simple token comparison (fallback)
    return hmac.compare_digest(signature, secret)

def run_deployment(deployment_id):
    """Execute the deployment script in background"""
    try:
        logger.info(f"[{deployment_id}] Starting deployment script...")
        
        # Make script executable
        DEPLOY_SCRIPT.chmod(0o755)
        
        # Run deployment script
        result = subprocess.run(
            [str(DEPLOY_SCRIPT)],
            cwd=DEPLOY_SCRIPT.parent,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logger.info(f"[{deployment_id}] Deployment succeeded:\n{result.stdout}")
        else:
            logger.error(f"[{deployment_id}] Deployment failed:\n{result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error(f"[{deployment_id}] Deployment script timed out")
    except Exception as e:
        logger.error(f"[{deployment_id}] Deployment error: {e}")

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'vixeditor-webhook',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/deploy', methods=['POST'])
def deploy():
    """Main deployment webhook endpoint - responds immediately with 202"""
    
    # Get signature from headers (GitHub, GitLab, or custom)
    github_signature = request.headers.get('X-Hub-Signature-256')
    gitlab_signature = request.headers.get('X-Gitlab-Token')
    custom_signature = request.headers.get('X-Webhook-Secret')
    
    signature = github_signature or gitlab_signature or custom_signature
    
    # Verify signature
    if WEBHOOK_SECRET != 'change-me-in-production':
        if not signature:
            logger.warning(f"Deployment request rejected: No signature provided from {request.remote_addr}")
            return jsonify({'error': 'No authentication provided'}), 401
        
        payload = request.get_data()
        if not verify_signature(payload, signature, WEBHOOK_SECRET):
            logger.warning(f"Deployment request rejected: Invalid signature from {request.remote_addr}")
            return jsonify({'error': 'Invalid signature'}), 401
    else:
        logger.warning("⚠️  WEBHOOK_SECRET not configured - accepting all requests!")
    
    # Generate deployment ID
    deployment_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    
    # Log the webhook trigger
    logger.info(f"[{deployment_id}] Webhook triggered from {request.remote_addr}")
    
    # Get payload info if available
    repo_info = "unknown"
    branch_info = "unknown"
    try:
        data = request.get_json() or {}
        repo_info = data.get('repository', {}).get('full_name', 'unknown')
        branch_info = data.get('ref', 'unknown').split('/')[-1]
        logger.info(f"[{deployment_id}] Repository: {repo_info}, Branch: {branch_info}")
    except:
        pass
    
    # Run deployment in background thread (non-blocking)
    thread = threading.Thread(
        target=run_deployment,
        args=(deployment_id,),
        daemon=True
    )
    thread.start()
    
    # Return 202 immediately - webhook doesn't need to know the result
    return jsonify({
        'status': 'accepted',
        'message': 'Deployment started in background',
        'deployment_id': deployment_id,
        'repository': repo_info,
        'branch': branch_info,
        'timestamp': datetime.now().isoformat()
    }), 202

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get recent deployment logs"""
    try:
        # Read last 50 lines of webhook log
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            recent_logs = ''.join(lines[-50:])
        
        return jsonify({
            'logs': recent_logs,
            'lines': len(lines)
        }), 200
    except FileNotFoundError:
        return jsonify({'logs': 'No logs available yet'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def main():
    """Main entry point for production WSGI servers"""
    logger.info("=" * 60)
    logger.info("VixEditor Deployment Webhook Service [PRODUCTION]")
    logger.info("=" * 60)
    logger.info(f"Mode: Asynchronous (202 Accepted)")
    logger.info(f"Port: {WEBHOOK_PORT}")
    logger.info(f"Deploy script: {DEPLOY_SCRIPT}")
    
    if WEBHOOK_SECRET == 'change-me-in-production':
        logger.warning("⚠️  WARNING: WEBHOOK_SECRET not configured!")
        logger.warning("⚠️  Set WEBHOOK_SECRET in .env.deploy for security")
    else:
        logger.info("✓ Webhook secret configured")
    
    logger.info("=" * 60)

if __name__ == '__main__':
    # This block is for local testing only
    # In production, use: gunicorn -c gunicorn_config.py deploy_webhook:app
    import sys
    
    main()
    
    logger.warning("⚠️  Running with Flask development server")
    logger.warning("⚠️  For production, use: gunicorn -c gunicorn_config.py deploy_webhook:app")
    
    app.run(
        host='0.0.0.0',
        port=WEBHOOK_PORT,
        debug=False,
        threaded=True
    )
