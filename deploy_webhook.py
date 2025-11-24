"""
VixEditor Deployment Webhook Service
Listens for webhook calls and triggers deployments
"""
import os
import subprocess
import logging
import hmac
import hashlib
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

def run_deployment():
    """Execute the deployment script"""
    try:
        logger.info("Starting deployment script...")
        
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
            logger.info(f"Deployment succeeded:\n{result.stdout}")
            return True, result.stdout
        else:
            logger.error(f"Deployment failed:\n{result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        logger.error("Deployment script timed out")
        return False, "Deployment timed out after 5 minutes"
    except Exception as e:
        logger.error(f"Deployment error: {e}")
        return False, str(e)

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
    """Main deployment webhook endpoint"""
    
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
        logger.warning("WEBHOOK_SECRET not configured - accepting all requests!")
    
    # Log the webhook trigger
    logger.info(f"Deployment webhook triggered from {request.remote_addr}")
    
    # Get payload info if available
    try:
        data = request.get_json() or {}
        repo = data.get('repository', {}).get('full_name', 'unknown')
        branch = data.get('ref', 'unknown').split('/')[-1]
        logger.info(f"Repository: {repo}, Branch: {branch}")
    except:
        pass
    
    # Run deployment in background
    success, output = run_deployment()
    
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Deployment completed successfully',
            'timestamp': datetime.now().isoformat(),
            'output': output[-500:]  # Last 500 chars
        }), 200
    else:
        return jsonify({
            'status': 'failed',
            'message': 'Deployment failed',
            'timestamp': datetime.now().isoformat(),
            'error': output[-500:]  # Last 500 chars
        }), 500

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

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("VixEditor Deployment Webhook Service")
    logger.info("=" * 60)
    logger.info(f"Listening on port: {WEBHOOK_PORT}")
    logger.info(f"Deploy script: {DEPLOY_SCRIPT}")
    
    if WEBHOOK_SECRET == 'change-me-in-production':
        logger.warning("⚠️  WARNING: WEBHOOK_SECRET not configured!")
        logger.warning("⚠️  Set WEBHOOK_SECRET in .env.deploy for security")
    else:
        logger.info("✓ Webhook secret configured")
    
    logger.info("=" * 60)
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=WEBHOOK_PORT,
        debug=False
    )
