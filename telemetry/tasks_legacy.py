# telemetry/tasks.py (Cleaned - No Celery)

# NOTE: All Celery task decorators and imports have been removed
# This file now only contains legacy task definitions for reference
# All rollups are now handled by Django management commands

# Legacy task definitions (kept for reference)
# task_rollup_raw_to_1m - Now handled by management command
# task_rollup_1m_to_5m - Now handled by management command  
# task_rollup_5m_to_1h - Now handled by management command
# task_rollup_1h_to_1d - Now handled by management command

# All new rollup processing happens via:
# 1. Django management commands (python manage.py rollup_*)
# 2. HTTP endpoints (/api/v1/rollup/*)
# 3. Render cron jobs (configured in dashboard)

print("⚠️  This file is deprecated - Use Django management commands instead")
