from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('telemetry', '0005_alter_telemetrylog_options_indicatorresult1day_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertthreshold',
            name='notification_channel',
            field=models.CharField(
                choices=[('EMAIL', 'Email'), ('SMS', 'SMS')],
                default='EMAIL',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='alertthreshold',
            name='notification_target',
            field=models.CharField(
                blank=True,
                help_text='Email address or phone number, depending on notification channel.',
                max_length=255,
            ),
        ),
    ]

