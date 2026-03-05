Industrial IoT Monitoring System (IIoT)
Status: Development & Local Integration Phase 
This project focuses on high-frequency data ingestion and real-time visualization. It is currently demonstrated using a custom-built Python device simulator to stress-test backend reliability.

System Architecture
Understanding how data flows from a "device" to the "dashboard" is the most critical part of this project.

The Data Flow:
Ingestion: A Python-based Device Simulator generates telemetry data (Temperature, Humidity, Status).

Processing: The Django Backend receives data via REST/MQTT, validates it, and commits it to a PostgreSQL database.

Real-Time Broadcast: Django Channels (WebSockets) pushes the updated state to the frontend immediately.

Visualization: The React Dashboard renders the live data stream using interactive charts and status indicators.

Key Technical Features
1. High-Frequency Device Simulation
Because I am building for industrial scale, I developed a standalone simulation script that:

Mimics multiple concurrent devices.

Introduces random "fault" states to test error-handling logic.

Uses requests and websockets libraries to simulate real hardware behavior.

2. Real-Time Communication (WebSockets)
Instead of standard polling, I implemented Django Channels. This ensures:

Zero-latency updates for critical sensor changes.

Reduced server load by maintaining persistent connections rather than thousands of HTTP requests.

3. Schema & Data Integrity
The database is optimized for time-series data:

Django ORM is used to manage device ownership and metadata.

Implemented Zod validation on the frontend to ensure data consistency across the stack.

Tech Stack
Backend: Python, Django, Django REST Framework, Django Channels (WebSockets)

Frontend: React (Vite), TypeScript, Tailwind CSS, Lucide Icons

Database: PostgreSQL

DevOps/Tools: Git, Docker (optional), Python Simulators

Local Preview
Since the project is in a local development phase to ensure data privacy and system performance, here is a breakdown of the core modules:

backend/core/consumers.py: Handles the WebSocket logic.

backend/sensors/models.py: Defines the relational structure for IoT devices.

simulator/mock_device.py: The script used to generate test data.
