import uvicorn
import time
import threading
import multiprocessing
import logging
from fastapi import FastAPI
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from database.models import Base, engine, SessionLocal, Job
from core.renderer import start_video_render
from core.config import settings, ensure_directories_exist
from core.logging import setup_logging
from api import routers as api_routers

# ==============================================================================
# Global State & Multiprocessing Setup
# ==============================================================================

manager = None
active_render_jobs = None
logger = logging.getLogger(__name__)

def process_render_job(job_id: str, shared_active_jobs: dict):
    """
    This function is the target for the new render process.
    It re-initializes logging for the new process.
    """
    setup_logging() 
    
    logger.info(f"Starting separate process for job: {job_id}")
    try:
        start_video_render(job_id, on_finish_callback=lambda: None)
    finally:
        if job_id in shared_active_jobs:
            del shared_active_jobs[job_id]
        logger.info(f"Process for job {job_id} has finished.")

def check_and_start_jobs():
    """ Queue check function. Spawns a new process for the next pending job. """
    if active_render_jobs and len(active_render_jobs) > 0:
        logger.debug(f"Queue check skipped: {len(active_render_jobs)} job(s) already active.")
        return

    db = SessionLocal()
    try:
        next_job = db.query(Job).filter(Job.status == "in_queue").order_by(Job.created_at).first()
        if next_job:
            job_id = next_job.job_id
            logger.info(f"Queue check: Found next job {job_id}. Spawning render process.")
            active_render_jobs[job_id] = True
            p = multiprocessing.Process(target=process_render_job, args=(job_id, active_render_jobs))
            p.start()
    finally:
        db.close()

def queue_worker():
    """ The background thread that periodically checks the queue. """
    while True:
        try:
            check_and_start_jobs()
        except Exception:
            logger.exception("Error in queue_worker loop.")
        time.sleep(5)

# ==============================================================================
# FastAPI Application Setup
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Handles application startup and shutdown. """
    ensure_directories_exist()
    setup_logging()

    global manager, active_render_jobs
    manager = multiprocessing.Manager()
    active_render_jobs = manager.dict()

    logger.info("--- Application Starting Up ---")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        stale_jobs = db.query(Job).filter(Job.status == "rendering").all()
        if stale_jobs:
            logger.warning(f"Found {len(stale_jobs)} stale jobs. Marking as failed.")
            for job in stale_jobs:
                job.status = "failed"
            db.commit()
        else:
            logger.info("No stale jobs found.")
    finally:
        db.close()

    queue_thread = threading.Thread(target=queue_worker, daemon=True)
    queue_thread.start()
    logger.info("--- Database, Directories, and Queue Worker are Ready ---")
    yield
    logger.info("--- Application Shutting Down ---")

app = FastAPI(lifespan=lifespan)
app.include_router(api_routers.admin_router)
app.include_router(api_routers.assets_router)
app.include_router(api_routers.generation_router)
app.include_router(api_routers.status_router)

# ==============================================================================
# Main Entry Point
# ==============================================================================

if __name__ == "__main__":
    multiprocessing.freeze_support()
    uvicorn.run("main:app", host="127.0.0.1", port=4000, reload=True)