# telemetry/ingestion.py (Updated - No Celery)

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from telemetry.task.rollup_engine import TelemetryRollupEngine
from telemetry.queue_updated import push_to_queue
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def rollup_raw_to_1m(request):
    """Manual trigger for raw->1m rollup"""
    try:
        # Get times from request or default
        end_time = request.POST.get('end_time')
        start_time = request.POST.get('start_time')
        
        if not start_time:
            end_time = datetime.now().replace(second=0, microsecond=0)
            start_time = end_time - timedelta(minutes=2)
        
        if not end_time:
            end_time = datetime.now().replace(second=0, microsecond=0)
        
        # Parse times if provided as strings
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)
                
        logger.info(f"📊 Manual rollup request: {start_time} to {end_time}")
        
        # Execute rollup using updated engine
        TelemetryRollupEngine.execute_raw_to_1m(start_time, end_time)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Raw to 1-minute rollup completed',
            'processed_time': end_time.isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Manual rollup failed: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt  
@require_http_methods(["POST"])
def rollup_all(request):
    """Manual trigger for complete rollup pipeline"""
    try:
        # Get times from request or default
        end_time = request.POST.get('end_time')
        start_time = request.POST.get('start_time')
        
        if not start_time:
            end_time = datetime.now().replace(second=0, microsecond=0)
            start_time = end_time - timedelta(hours=24)
        
        if not end_time:
            end_time = datetime.now().replace(second=0, microsecond=0)
        
        # Parse times if provided as strings
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)
                
        logger.info(f"📊 Complete pipeline request: {start_time} to {end_time}")
        
        # Execute complete pipeline using updated engine
        TelemetryRollupEngine.execute_raw_to_1m(start_time, end_time)
        TelemetryRollupEngine.execute_1m_to_5m(start_time, end_time)
        TelemetryRollupEngine.execute_5m_to_1h(start_time, end_time)
        TelemetryRollupEngine.execute_1h_to_1d(start_time, end_time)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Complete rollup pipeline finished',
            'processed_time': end_time.isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Complete pipeline failed: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_queue_status(request):
    """Get current queue status without Celery dependency"""
    try:
        from telemetry.queue_updated import get_queue_status
        return JsonResponse(get_queue_status())
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

# NOTE: All rollup functions now use updated engine and queue system
# No Celery imports or dependencies - completely removed for stability
