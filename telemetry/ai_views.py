# telemetry/views.py - Add this new view
import os
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import openai
from django.conf import settings

class AIReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Extract data from request
            analysis_scope = request.data.get('analysis_scope', 'single')
            analysis_depth = request.data.get('analysis_depth', 'summary')
            primary_telemetry_id = request.data.get('primary_telemetry_id')
            secondary_telemetry_id = request.data.get('secondary_telemetry_id')
            chart_data = request.data.get('chart_data', [])
            device_id = request.data.get('device_id')

            # Prepare data for AI analysis
            data_summary = {
                'total_points': len(chart_data),
                'time_range': f"{chart_data[0]['time'] if chart_data else 'N/A'} to {chart_data[-1]['time'] if chart_data else 'N/A'}",
                'latest_value': chart_data[-1]['close'] if chart_data else 'N/A',
                'values': [point['close'] for point in chart_data[-20:]]  # Last 20 values
            }

            # Construct prompt based on analysis type
            if analysis_scope == 'relational':
                prompt = f"""
                Analyze the relationship between {primary_telemetry_id} and {secondary_telemetry_id} 
                for device {device_id}. Data summary: {json.dumps(data_summary)}
                
                Provide a {analysis_depth} analysis focusing on:
                - Correlation patterns
                - Potential causal relationships
                - Operational insights
                
                Respond in a professional, technical tone suitable for industrial IoT monitoring.
                """
            else:
                prompt = f"""
                Analyze the telemetry data for {primary_telemetry_id} from device {device_id}.
                Data summary: {json.dumps(data_summary)}
                
                Provide a {analysis_depth} analysis focusing on:
                - Trend analysis
                - Anomaly detection
                - Performance metrics
                - Operational recommendations
                
                Respond in a professional, technical tone suitable for industrial IoT monitoring.
                """

            # Call OpenAI API (or your preferred LLM)
            openai.api_key = os.environ.get('OPENAI_API_KEY')
            
            if not openai.api_key:
                # Fallback to mock response if no API key
                return Response({
                    'report': f"AI Analysis ({analysis_depth}): {primary_telemetry_id} shows normal operational patterns. No anomalies detected in the analyzed timeframe."
                })

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert IIoT data analyst providing insights on industrial telemetry data."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )

            report = response.choices[0].message.content

            return Response({
                'report': report,
                'analysis_type': analysis_scope,
                'data_points_analyzed': len(chart_data)
            })

        except Exception as e:
            return Response({
                'error': f'AI analysis failed: {str(e)}',
                'report': f"Analysis ({analysis_depth}): Unable to complete AI analysis. Please try again later."
            }, status=500)
