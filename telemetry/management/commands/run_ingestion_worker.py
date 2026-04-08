import json
import time
from datetime import timezone

from django.utils.timezone import now
from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from devices.models import Device, DeviceProperty
from telemetry.models import TelemetryLog, AlertThreshold
from telemetry.queue import redis_client, TELEMETRY_QUEUE_KEY, push_to_dlq
from telemetry.parsers import parse_gateway_schema


class Command(BaseCommand):
    help = "High-performance telemetry ingestion worker"

    def handle(self, *args, **kwargs):

        self.stdout.write("🚀 Telemetry ingestion worker started")

        channel_layer = get_channel_layer()

        BATCH_SIZE = 500

        while True:

            # -------------------------
            # 1. FETCH BATCH FROM REDIS
            # -------------------------

            pipeline = redis_client.pipeline()

            pipeline.lrange(TELEMETRY_QUEUE_KEY, -BATCH_SIZE, -1)
            pipeline.ltrim(TELEMETRY_QUEUE_KEY, 0, -(BATCH_SIZE + 1))

            raw_items, _ = pipeline.execute()

            if not raw_items:
                time.sleep(0.02)
                continue

            parsed_jobs = []
            device_ids = set()
            labels = set()

            # -------------------------
            # 2. PARSE RAW JOBS
            # -------------------------

            for item in raw_items:

                try:
                    job = json.loads(item)

                    parsed_jobs.append(job)

                    dev_id = str(job["device_id"])
                    device_ids.add(dev_id)

                    payload = job["raw_payload"]

                    if job["type"] == "gateway":
                        labels.update(payload.get("data", {}).keys())

                    elif job["type"] == "single":
                        labels.add(payload.get("label"))

                    elif job["type"] == "bulk":

                        for pt in payload.get("data", []):
                            labels.add(pt.get("label"))

                except Exception as e:
                    push_to_dlq(item, f"JSON decode error: {str(e)}")

            if not parsed_jobs:
                continue

            # -------------------------
            # 3. PREFETCH DEVICE PROPERTIES
            # -------------------------

            properties = DeviceProperty.objects.filter(
                device_id__in=device_ids,
                identifier__in=labels
            ).values("device_id", "identifier", "id")

            property_map = {
                (str(p["device_id"]), p["identifier"]): p["id"]
                for p in properties
            }

            # -------------------------
            # 4. BUILD TELEMETRY OBJECTS
            # -------------------------

            telemetry_objects = []
            broadcast_map = {}

            for job in parsed_jobs:

                try:

                    dev_id = str(job["device_id"])
                    payload = job["raw_payload"]

                    records = []

                    if job["type"] == "gateway":

                        records = parse_gateway_schema(
                            dev_id,
                            payload,
                            property_map
                        )

                    elif job["type"] == "single":

                        prop_id = property_map.get(
                            (dev_id, payload.get("label"))
                        )

                        if prop_id:

                            records.append({
                                "device_id": dev_id,
                                "label": payload["label"],
                                "value": float(payload["value"]),
                                "property_id": prop_id,
                                "timestamp": payload["timestamp"]
                            })

                    elif job["type"] == "bulk":

                        for pt in payload.get("data", []):

                            prop_id = property_map.get(
                                (dev_id, pt.get("label"))
                            )

                            if not prop_id:
                                continue

                            records.append({
                                "device_id": dev_id,
                                "label": pt["label"],
                                "value": float(pt["value"]),
                                "property_id": prop_id,
                                "timestamp": pt["timestamp"]
                            })

                    # -------------------------
                    # ADD RECORDS
                    # -------------------------

                    for rec in records:

                        telemetry_objects.append(TelemetryLog(**rec))

                        if dev_id not in broadcast_map:
                            broadcast_map[dev_id] = []

                        # ultra-compact websocket format
                        broadcast_map[dev_id].append([
                            rec["label"],
                            rec["value"],
                            int(rec["timestamp"].timestamp() * 1000)
                        ])

                except Exception as e:
                    push_to_dlq(job, f"Parsing error: {str(e)}")

            if not telemetry_objects:
                continue

            # -------------------------
            # 5. BULK INSERT
            # -------------------------

            try:

                TelemetryLog.objects.bulk_create(
                    telemetry_objects,
                    batch_size=BATCH_SIZE
                )

            except Exception as e:

                push_to_dlq(raw_items, f"DB bulk insert error: {str(e)}")
                continue

            # -------------------------
            # 6. WEBSOCKET BROADCAST
            # -------------------------

            for dev_id, ticks in broadcast_map.items():

                async_to_sync(channel_layer.group_send)(
                    f"device_{dev_id}",
                    {
                        "type": "live_telemetry",
                        "device_id": dev_id,
                        "payload": ticks
                    }
                )

            # -------------------------
            # 7. HEARTBEAT UPDATE
            # -------------------------

            Device.objects.filter(id__in=device_ids).update(
                last_seen=now(),
                is_online=True
            )

            # -------------------------
            # 8. ALERT EVALUATION
            # -------------------------

            self.evaluate_alerts(telemetry_objects, device_ids, labels)

    # -----------------------------------------------------
    # ALERT ENGINE
    # -----------------------------------------------------

    def evaluate_alerts(self, telemetry_objects, device_ids, labels):

        alerts = AlertThreshold.objects.filter(
            device_id__in=device_ids,
            parameter__in=labels,
            is_active=True
        )

        if not alerts.exists():
            return

        alert_map = {}

        for alert in alerts:

            key = (str(alert.device_id), alert.parameter)

            if key not in alert_map:
                alert_map[key] = []

            alert_map[key].append(alert)

        # Store (alert, triggered_value) so we can notify after DB update.
        triggered = []
        current_time = now()

        for rec in telemetry_objects:

            key = (str(rec.device_id), rec.label)

            if key not in alert_map:
                continue

            for alert in alert_map[key]:

                if alert.last_triggered:

                    delta = (
                        current_time - alert.last_triggered
                    ).total_seconds() / 60

                    if delta < alert.cooldown_minutes:
                        continue

                fire = False

                if alert.operator == ">" and alert.max_value and rec.value > alert.max_value:
                    fire = True

                elif alert.operator == "<" and alert.min_value and rec.value < alert.min_value:
                    fire = True

                elif alert.operator == "=" and alert.min_value and abs(rec.value - alert.min_value) < 0.01:
                    fire = True

                if fire:

                    alert.last_triggered = current_time
                    triggered.append((alert, rec.value))

        if triggered:

            AlertThreshold.objects.bulk_update(
                [a for a, _ in triggered],
                ["last_triggered"]
            )

            # Best-effort notifications. Never let the ingestion worker crash.
            for alert, triggered_value in triggered:
                try:
                    if not alert.notification_target:
                        continue

                    subject = f"Watchdog alert: {alert.parameter}"
                    message = (
                        f"Device parameter '{alert.parameter}' triggered.\n\n"
                        f"Operator: {alert.operator}\n"
                        f"Triggered value: {triggered_value}\n"
                        f"Device: {alert.device.name}\n"
                        f"Cooldown: {alert.cooldown_minutes} minutes\n"
                    )

                    if alert.notification_channel == "EMAIL":
                        send_mail(
                            subject=subject,
                            message=message,
                            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                            recipient_list=[alert.notification_target],
                            fail_silently=True,
                        )
                    elif alert.notification_channel == "SMS":
                        # SMS delivery isn't implemented in this repo yet.
                        # Keep the wiring so you can attach Twilio/other SMS later.
                        self.stdout.write(
                            f"[ALERT-SMS-STUB] {alert.device.id} -> {alert.notification_target}: {subject}"
                        )

                except Exception as e:
                    self.stdout.write(f"[ALERT-NOTIFY-ERROR] {e}")