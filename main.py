import os
import logging
import datetime
import json
from typing import Dict, Any, Optional, List, Union, cast
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import requests
from datetime import datetime, timedelta

from eds_client import EDSClient
from tnz_client import TNZClient
from alarm_processor import AlarmProcessor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('eds_alarm_web')

# Load settings from local.settings.json
def load_settings():
    try:
        with open('local.settings.json', 'r') as f:
            settings = json.load(f)
            if 'Values' in settings:
                for key, value in settings['Values'].items():
                    if key not in os.environ:
                        os.environ[key] = value
                logger.info(f"Loaded settings from local.settings.json")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load settings from local.settings.json: {str(e)}")

# Load settings on startup
load_settings()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Main dashboard
@app.route('/')
def index():
    # Get configuration values for the template
    eds_api_base_url = os.environ.get('EDS_API_BASE_URL', 'Not configured')
    tnz_api_base_url = os.environ.get('TNZ_API_BASE_URL', 'Not configured')
    
    return render_template('index.html', 
                          eds_api_base_url=eds_api_base_url,
                          tnz_api_base_url=tnz_api_base_url)

# API status endpoint
@app.route('/api/status')
def api_status():
    eds_status = False
    tnz_status = False
    
    try:
        # Check EDS API status - handle None values with defaults
        base_url = os.environ.get('EDS_API_BASE_URL')
        username = os.environ.get('EDS_API_USERNAME')
        password = os.environ.get('EDS_API_PASSWORD')
        
        # Only proceed if we have the required values
        if base_url and username and password:
            eds_client = EDSClient(
                base_url=base_url,
                username=username,
                password=password,
            )
            session_id = eds_client.login()
            if session_id:
                eds_status = True
                eds_client.logout()
    except Exception as e:
        logger.error(f"Error checking EDS API status: {str(e)}")
    
    try:
        # Check TNZ API status (just verifying API key format for demo)
        api_key = os.environ.get('TNZ_API_KEY')
        if api_key:
            tnz_client = TNZClient(
                base_url=os.environ.get('TNZ_API_BASE_URL', 'https://api.tnz.co.nz/api/v1'),
                api_key=api_key
            )
            # For actual status check, we would need to make an API call
            # This is just checking if the API key is set and has reasonable length
            if len(api_key) > 5:
                tnz_status = True
    except Exception as e:
        logger.error(f"Error checking TNZ API status: {str(e)}")
    
    return jsonify({
        'eds_api': {
            'status': 'connected' if eds_status else 'disconnected',
            'base_url': os.environ.get('EDS_API_BASE_URL', 'Not configured')
        },
        'tnz_api': {
            'status': 'connected' if tnz_status else 'disconnected',
            'base_url': os.environ.get('TNZ_API_BASE_URL', 'Not configured')
        }
    })

# Get recent alarms
@app.route('/api/alarms')
def get_alarms():
    try:
        # Get environment variables and validate
        base_url = os.environ.get('EDS_API_BASE_URL')
        username = os.environ.get('EDS_API_USERNAME')
        password = os.environ.get('EDS_API_PASSWORD')
        
        if not all([base_url, username, password]):
            return jsonify({'error': 'EDS API credentials not configured'}), 500
            
        # Initialize EDS client
        eds_client = EDSClient(
            base_url=base_url,
            username=username,
            password=password,
        )
        
        # Login to EDS API
        session_id = eds_client.login()
        if not session_id:
            return jsonify({'error': 'Failed to login to EDS API'}), 500
        
        try:
            # Get minutes from query parameters, default to 60
            minutes = int(request.args.get('minutes', 60))
            # Limit minutes to a reasonable range
            minutes = min(max(minutes, 5), 1440)  # Between 5 minutes and 24 hours
            
            # Get priority from query parameters, default to all priorities [1, 2, 3]
            priority_param = request.args.get('priority', '1,2,3')
            priorities = [int(p) for p in priority_param.split(',') if p.isdigit()]
            
            # Query alarms
            alarms = eds_client.query_alarms(minutes=minutes, priorities=priorities)
            
            # Format alarms for display
            formatted_alarms = []
            for alarm in alarms:
                # Format timestamp
                ts = alarm.get('ts')
                if ts:
                    formatted_time = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    formatted_time = "Unknown"
                
                # Get priority string
                priority_map = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}
                priority = priority_map.get(alarm.get('ap'), "UNKNOWN")
                
                formatted_alarms.append({
                    'id': alarm.get('sid'),
                    'name': alarm.get('iess', 'Unknown'),
                    'description': alarm.get('desc', ''),
                    'priority': priority,
                    'value': alarm.get('value', 'N/A'),
                    'timestamp': formatted_time,
                    'quality': alarm.get('quality', 'UNKNOWN'),
                    'source': alarm.get('zd', 'Unknown')
                })
            
            return jsonify({'alarms': formatted_alarms})
            
        finally:
            # Always logout
            eds_client.logout()
            
    except Exception as e:
        logger.error(f"Error fetching alarms: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Trigger manual alarm check
@app.route('/api/check-alarms', methods=['POST'])
def check_alarms():
    try:
        # Get and validate credentials
        base_url = os.environ.get('EDS_API_BASE_URL')
        username = os.environ.get('EDS_API_USERNAME')
        password = os.environ.get('EDS_API_PASSWORD')
        api_key = os.environ.get('TNZ_API_KEY')
        
        if not all([base_url, username, password]):
            return jsonify({'error': 'EDS API credentials not configured'}), 500
            
        if not api_key:
            return jsonify({'error': 'TNZ API key not configured'}), 500
        
        # Initialize clients
        eds_client = EDSClient(
            base_url=base_url,
            username=username,
            password=password,
        )
        
        tnz_client = TNZClient(
            base_url=os.environ.get('TNZ_API_BASE_URL', 'https://api.tnz.co.nz/api/v1'),
            api_key=api_key
        )
        
        processor = AlarmProcessor(
            notification_threshold=int(os.environ.get('ALARM_NOTIFICATION_THRESHOLD', '2')),
            last_run_minutes=int(os.environ.get('LAST_RUN_MINUTES', '15'))
        )
        
        # Login to EDS API
        session_id = eds_client.login()
        if not session_id:
            return jsonify({'error': 'Failed to login to EDS API'}), 500
        
        try:
            # Query alarms
            alarms = eds_client.query_alarms()
            
            # Process alarms
            notifications = processor.process_alarms(alarms)
            
            # Send SMS notifications if enabled
            send_sms = request.json.get('send_sms', False)
            sent_count = 0
            
            if send_sms and notifications:
                for notification in notifications:
                    result = tnz_client.send_sms(
                        to=notification['recipient'],
                        message=notification['message']
                    )
                    if result:
                        sent_count += 1
            
            return jsonify({
                'success': True,
                'alarms_processed': len(alarms),
                'notifications_generated': len(notifications),
                'sms_sent': sent_count if send_sms else 'Disabled'
            })
            
        finally:
            # Always logout
            eds_client.logout()
            
    except Exception as e:
        logger.error(f"Error checking alarms: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Configuration page
@app.route('/config')
def config():
    configs = {
        'EDS_API_BASE_URL': os.environ.get('EDS_API_BASE_URL', ''),
        'EDS_API_USERNAME': os.environ.get('EDS_API_USERNAME', ''),
        'EDS_API_CLIENT_TYPE': os.environ.get('EDS_API_CLIENT_TYPE', 'web_interface'),
        'TNZ_API_BASE_URL': os.environ.get('TNZ_API_BASE_URL', 'https://api.tnz.co.nz/api/v1'),
        'ALARM_NOTIFICATION_THRESHOLD': os.environ.get('ALARM_NOTIFICATION_THRESHOLD', '2'),
        'LAST_RUN_MINUTES': os.environ.get('LAST_RUN_MINUTES', '15')
    }
    
    # Mask password and API key
    eds_password_masked = '********' if os.environ.get('EDS_API_PASSWORD') else ''
    tnz_api_key_masked = '********' if os.environ.get('TNZ_API_KEY') else ''
    
    # Get contact list
    contacts = []
    contact_list_str = os.environ.get('CONTACT_LIST', '[]')
    try:
        contacts = json.loads(contact_list_str)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid contact list format in environment variables")
        contacts = []
    
    return render_template('config.html', 
                          configs=configs, 
                          eds_password_masked=eds_password_masked,
                          tnz_api_key_masked=tnz_api_key_masked,
                          contacts=contacts)

# Save configuration
@app.route('/config/save', methods=['POST'])
def save_config():
    try:
        # Get the values from the form
        eds_api_base_url = request.form.get('eds_api_base_url', '')
        eds_api_username = request.form.get('eds_api_username', '')
        eds_api_password = request.form.get('eds_api_password', '')
        eds_api_client_type = request.form.get('eds_api_client_type', 'web_interface')
        tnz_api_base_url = request.form.get('tnz_api_base_url', 'https://api.tnz.co.nz/api/v1')
        tnz_api_key = request.form.get('tnz_api_key', '')
        alarm_notification_threshold = request.form.get('alarm_notification_threshold', '2')
        last_run_minutes = request.form.get('last_run_minutes', '15')
        
        # Log what we're getting from the form
        logger.info(f"Saving configuration - EDS API Base URL: {eds_api_base_url}")
        logger.info(f"Saving configuration - EDS API Username: {eds_api_username}")
        
        # Get contact information from the form
        contact_names = request.form.getlist('contact_name[]')
        contact_numbers = request.form.getlist('contact_number[]')
        
        # Create contact list
        contacts = []
        for i in range(min(len(contact_names), len(contact_numbers))):
            if contact_names[i].strip() and contact_numbers[i].strip():
                contacts.append({
                    'name': contact_names[i].strip(),
                    'number': contact_numbers[i].strip()
                })
        
        # Update the settings.json file
        settings = {}
        
        # Try to load existing settings first
        try:
            with open('local.settings.json', 'r') as f:
                settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default structure if file doesn't exist or is invalid
            settings = {"IsEncrypted": False, "Values": {}}
        
        # Update values
        if 'Values' not in settings:
            settings['Values'] = {}
            
        # Update values in settings
        settings['Values']['EDS_API_BASE_URL'] = eds_api_base_url
        settings['Values']['EDS_API_USERNAME'] = eds_api_username
        settings['Values']['EDS_API_CLIENT_TYPE'] = eds_api_client_type
        settings['Values']['TNZ_API_BASE_URL'] = tnz_api_base_url
        settings['Values']['ALARM_NOTIFICATION_THRESHOLD'] = alarm_notification_threshold
        settings['Values']['LAST_RUN_MINUTES'] = last_run_minutes
        settings['Values']['CONTACT_LIST'] = json.dumps(contacts)
        
        # Only update password and API key if provided
        if eds_api_password and len(eds_api_password.strip()) > 0 and '********' not in eds_api_password:
            settings['Values']['EDS_API_PASSWORD'] = eds_api_password
            
        if tnz_api_key and len(tnz_api_key.strip()) > 0 and '********' not in tnz_api_key:
            settings['Values']['TNZ_API_KEY'] = tnz_api_key
            
        # Save settings to file
        with open('local.settings.json', 'w') as f:
            json.dump(settings, f, indent=2)
        
        # Update environment variables (always update all values)
        os.environ['EDS_API_BASE_URL'] = eds_api_base_url
        os.environ['EDS_API_USERNAME'] = eds_api_username
        os.environ['EDS_API_CLIENT_TYPE'] = eds_api_client_type
        os.environ['TNZ_API_BASE_URL'] = tnz_api_base_url
        os.environ['ALARM_NOTIFICATION_THRESHOLD'] = alarm_notification_threshold
        os.environ['LAST_RUN_MINUTES'] = last_run_minutes
        os.environ['CONTACT_LIST'] = json.dumps(contacts)
        
        # Update password and API key in environment if provided
        if eds_api_password and len(eds_api_password.strip()) > 0 and '********' not in eds_api_password:
            os.environ['EDS_API_PASSWORD'] = eds_api_password
            
        if tnz_api_key and len(tnz_api_key.strip()) > 0 and '********' not in tnz_api_key:
            os.environ['TNZ_API_KEY'] = tnz_api_key
            
        # Make sure existing values are kept if not overwritten    
        if 'EDS_API_PASSWORD' in settings['Values'] and 'EDS_API_PASSWORD' not in os.environ:
            os.environ['EDS_API_PASSWORD'] = settings['Values']['EDS_API_PASSWORD']
            
        if 'TNZ_API_KEY' in settings['Values'] and 'TNZ_API_KEY' not in os.environ:
            os.environ['TNZ_API_KEY'] = settings['Values']['TNZ_API_KEY']
            
        # Log current environment variables (for debugging)
        logger.info(f"After save - EDS API Base URL: {os.environ.get('EDS_API_BASE_URL')}")
        logger.info(f"After save - EDS API Username: {os.environ.get('EDS_API_USERNAME')}")
        
        flash('Configuration updated successfully', 'success')
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        flash(f'Error saving configuration: {str(e)}', 'danger')
        
    return redirect(url_for('config'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)