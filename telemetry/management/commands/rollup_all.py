# telemetry/management/commands/rollup_all.py
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from telemetry.task.rollup_engine import TelemetryRollupEngine


class Command(BaseCommand):
    help = 'Run all rollup tasks in sequence (raw->1m->5m->1h->1d)'

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
        """Execute all rollups in sequence"""
        self.stdout.write("🔄 Starting complete rollup pipeline...")
        
        # Default to last 24 hours
        end_time = options['end_time']
        start_time = options['start_time']
        
        if not start_time:
            end_time = datetime.now().replace(second=0, microsecond=0)
            start_time = end_time - timedelta(hours=24)
        
        if not end_time:
            end_time = datetime.now().replace(second=0, microsecond=0)
        
        try:
            # Parse times if provided as strings
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
                
            self.stdout.write(f"📊 Processing: {start_time} to {end_time}")
            
            # Execute rollups in sequence
            self.stdout.write("📈 Step 1: Raw -> 1-minute...")
            TelemetryRollupEngine.execute_raw_to_1m(start_time, end_time)
            
            self.stdout.write("📈 Step 2: 1-minute -> 5-minute...")
            TelemetryRollupEngine.execute_1m_to_5m(start_time, end_time)
            
            self.stdout.write("📈 Step 3: 5-minute -> 1-hour...")
            TelemetryRollupEngine.execute_5m_to_1h(start_time, end_time)
            
            self.stdout.write("📈 Step 4: 1-hour -> 1-day...")
            TelemetryRollupEngine.execute_1h_to_1d(start_time, end_time)
            
            self.stdout.write(self.style.SUCCESS(
                "✅ Complete rollup pipeline finished successfully"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Rollup pipeline failed: {e}"))
