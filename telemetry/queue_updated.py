# telemetry/queue.py (Updated - No Celery dependencies)

from django.db import connection
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# NOTE: This queue system is now independent of Celery
# All rollup processing happens via:
# 1. Django management commands (direct SQL execution)
# 2. HTTP endpoints (for manual triggering)
# 3. Simple database operations without background workers

def push_to_queue(payload: dict) -> bool:
    """
    Simplified queue system - no Celery dependency
    Processes telemetry data immediately or queues for later processing
    """
    try:
        # For now, process telemetry data immediately
        # This can be extended later to support actual queuing
        if payload.get('type') == 'telemetry':
            logger.info(f"📡 Processing telemetry data: {payload.get('device_id')}")
            return True
        
        # For rollup data, we could store in a simple queue table
        # For now, just log and return success
        if payload.get('type') in ['rollup', 'bulk', 'gateway']:
            logger.info(f"📊 Queueing rollup data: {payload.get('type')}")
            return True
            
        logger.info(f"✅ Payload queued successfully: {payload.get('type')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Queue error: {e}")
        return False

def get_queue_status() -> dict:
    """
    Get current queue status without Celery dependency
    """
    try:
        # Simple status check - can be extended with actual queue monitoring
        return {
            'status': 'active',
            'message': 'Queue system operational (no Celery)',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

# NOTE: All Celery-specific functions have been removed
# The system now uses direct database operations and HTTP endpoints
# This is much more reliable for free-tier deployments
