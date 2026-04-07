# Render Cron Configuration

## 🚀 FINAL DEPLOYMENT COMMANDS

### 1. Deploy Changes
```bash
git add .
git commit -m "Remove Celery, add Django management commands"
git push
```

### 2. Set Up Render Cron Jobs

Add these cron jobs in Render Dashboard:

#### Rollup Every 5 Minutes (Raw -> 1m)
```
*/5 * * * * /opt/render/project/src/manage.py rollup_raw_to_1m
```

#### Rollup Every Hour (1m -> 5m)  
```
0 * * * * /opt/render/project/src/manage.py rollup_1m_to_5m
```

#### Rollup Daily (5m -> 1h)
```
5 0 * * * /opt/render/project/src/manage.py rollup_5m_to_1h
```

#### Rollup Daily (1h -> 1d)
```
10 0 * * * /opt/render/project/src/manage.py rollup_1h_to_1d
```

### 3. Manual Trigger URLs

You can also trigger rollups manually via HTTP:

#### Single Rollup
```bash
curl -X POST https://iot-bridge.onrender.com/api/v1/rollup/raw-to-1m/ \
  -H "Content-Type: application/json" \
  -d '{"start_time": "2026-04-02T12:00:00"}'
```

#### Complete Pipeline
```bash
curl -X POST https://iot-bridge.onrender.com/api/v1/rollup/all/ \
  -H "Content-Type: application/json" \
  -d '{"start_time": "2026-04-02T12:00:00"}'
```

### 4. Example Usage

#### Run with Custom Time Range
```bash
python manage.py rollup_raw_to_1m --start-time "2026-04-01T10:00:00" --end-time "2026-04-01T12:00:00"
```

#### Run Default (Last 2 minutes)
```bash
python manage.py rollup_raw_to_1m
```

## 🎯 Benefits

✅ **No Celery dependency** - No worker processes needed
✅ **Free tier friendly** - Uses Render cron instead of background workers
✅ **Predictable scheduling** - Cron jobs run exactly when configured
✅ **Manual triggering** - HTTP endpoints for on-demand rollups
✅ **Database safe** - Uses Django's connection management
✅ **Easy debugging** - Direct command execution with clear output

Your system is now **stable and production-ready** without Celery complexity! 🎉
