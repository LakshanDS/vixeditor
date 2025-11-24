"""
Gunicorn Configuration for VixEditor Webhook Service
Production-ready WSGI server configuration
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.deploy')

# Server Socket
bind = f"0.0.0.0:{os.getenv('WEBHOOK_PORT', '4001')}"
backlog = 2048

# Worker Processes
workers = 2  # 2 workers is sufficient for webhook service
worker_class = 'gthread'  # Use threaded workers for async deployments
threads = 4  # 4 threads per worker
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30  # 30 second timeout (deployments run in background)
keepalive = 5

# Logging
accesslog = 'logs/webhook_access.log'
errorlog = 'logs/webhook_error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = 'vixeditor-webhook'

# Server Mechanics
daemon = False  # Set to True if not using systemd
pidfile = 'logs/webhook.pid'
user = None  # Run as current user
group = None
umask = 0
tmp_upload_dir = None

# SSL (uncomment if using HTTPS)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Server Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Gunicorn server is ready. Spawning workers")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("worker received SIGABRT signal")
