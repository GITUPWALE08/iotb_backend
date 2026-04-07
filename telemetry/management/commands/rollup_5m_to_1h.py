# telemetry/management/commands/rollup_5m_to_1h.py
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from telemetry.task.rollup_engine import TelemetryRollupEngine


class Command(BaseCommand):
    help = 'Roll up 5-minute telemetry data to 1-hour buckets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-time',
            type=str,
            help='Start time in YYYY-MM-DD HH:MM:SS format (optional)'
        )
        parser.add_argument(
            '--end-time', 
            type=str,
            help='End time in YYYY-MM-DD HH:MM:SS format (optional)'
        )

    def handle(self, *args, **options):
        """Execute the rollup"""
        self.stdout.write("🔄 Starting 5-minute to 1-hour rollup...")
        
        # Default to last 2 hours
        end_time = options['end_time']
        start_time = options['start_time']
        
        if not start_time:
            end_time = datetime.now().replace(second=0, microsecond=0)
            start_time = end_time - timedelta(hours=2)
        
        if not end_time:
            end_time = datetime.now().replace(second=0, microsecond=0)
        
        try:
            # Parse times if provided as strings
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
                
            self.stdout.write(f"📊 Processing: {start_time} to {end_time}")
            
            # Execute rollup
            TelemetryRollupEngine.execute_5m_to_1h(start_time, end_time)
            
            self.stdout.write(self.style.SUCCESS(
                f"✅ 5m-to-1h rollup completed successfully"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Rollup failed: {e}"))
