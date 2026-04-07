# telemetry/management/commands/remove_celery_tasks.py
from django.core.management.base import BaseCommand
from django.core.management.utils import find_command
import os


class Command(BaseCommand):
    help = 'Remove all Celery task files and imports'

    def handle(self, *args, **options):
        """Remove Celery task files and clean up imports"""
        self.stdout.write("🧹 Removing Celery task files...")
        
        # Files to remove
        files_to_remove = [
            'telemetry/tasks.py',
            'telemetry/task/__init__.py',
            'telemetry/task/rollup_engine.py',
        ]
        
        # Remove task files
        import shutil
        for file_path in files_to_remove:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.stdout.write(f"🗑️ Removed: {file_path}")
        
        # Clean up imports in telemetry/views.py
        views_file = 'telemetry/views.py'
        if os.path.exists(views_file):
            with open(views_file, 'r') as f:
                content = f.read()
            
            # Remove Celery imports
            lines_to_remove = [
                'from celery import shared_task',
                'from .task.rollup_engine import TelemetryRollupEngine',
                '@shared_task',
                'task_rollup_raw_to_1m',
                'task_rollup_1m_to_5m',
                'task_rollup_5m_to_1h',
                'task_rollup_1h_to_1d',
            ]
            
            for line in lines_to_remove:
                if line in content:
                    content = content.replace(line, f"# REMOVED: {line}")
            
            with open(views_file, 'w') as f:
                f.write(content)
            
            self.stdout.write(f"🧹 Cleaned up: {views_file}")
        
        self.stdout.write(self.style.SUCCESS(
            "✅ Celery removal completed. Use Django management commands instead."
        ))
