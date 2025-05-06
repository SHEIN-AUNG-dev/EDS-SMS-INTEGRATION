import azure.functions as func
import datetime
import logging
import os
import json

from eds_client import EDSClient
from tnz_client import TNZClient
from alarm_processor import AlarmProcessor

app = func.FunctionApp()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('alarm_notification_function')

@app.function_name(name="AlarmNotificationTrigger")
@app.schedule(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def alarm_notification_function(timer: func.TimerRequest) -> None:
    """
    Azure Function that retrieves alarms from EDS API and sends SMS notifications via TNZ API
    This function runs every 5 minutes by default
    """
    logger.info('Alarm notification function executed at %s', datetime.datetime.utcnow().isoformat())
    
    if timer.past_due:
        logger.info('The timer is past due!')
    
    try:
        # Initialize EDS client
        eds_client = EDSClient(
            base_url=os.environ.get('EDS_API_BASE_URL'),
            username=os.environ.get('EDS_API_USERNAME'),
            password=os.environ.get('EDS_API_PASSWORD'),
            client_type=os.environ.get('EDS_API_CLIENT_TYPE', 'azure_function')
        )
        
        # Initialize TNZ client
        tnz_client = TNZClient(
            base_url=os.environ.get('TNZ_API_BASE_URL', 'https://api.tnz.co.nz/api/v1'),
            api_key=os.environ.get('TNZ_API_KEY')
        )
        
        # Initialize alarm processor
        processor = AlarmProcessor(
            notification_threshold=int(os.environ.get('ALARM_NOTIFICATION_THRESHOLD', '2')),
            last_run_minutes=int(os.environ.get('LAST_RUN_MINUTES', '15'))
        )
        
        # Login to EDS API
        session_id = eds_client.login()
        if not session_id:
            logger.error("Failed to login to EDS API")
            return
        
        # Retrieve alarms from EDS API
        try:
            # Query alarms based on timestamp and priority
            alarms = eds_client.query_alarms()
            logger.info(f"Retrieved {len(alarms)} alarms from EDS API")
            
            # Process alarms to determine which ones need SMS notifications
            notifications = processor.process_alarms(alarms)
            logger.info(f"Processed {len(notifications)} alarms that require notifications")
            
            # Send SMS notifications
            if notifications:
                for notification in notifications:
                    result = tnz_client.send_sms(
                        to=notification['recipient'],
                        message=notification['message']
                    )
                    if result:
                        logger.info(f"SMS notification sent successfully to {notification['recipient']}")
                    else:
                        logger.error(f"Failed to send SMS notification to {notification['recipient']}")
            else:
                logger.info("No notifications to send")
                
        finally:
            # Always logout from EDS API
            eds_client.logout()
            
    except Exception as e:
        logger.error(f"Error in alarm notification function: {str(e)}")
        raise
