import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger('alarm_processor')

class AlarmProcessor:
    """
    Processes alarm data and determines which alarms require SMS notifications
    """
    
    def __init__(self, notification_threshold: int = 2, last_run_minutes: int = 15):
        """
        Initialize the alarm processor
        
        Args:
            notification_threshold: Priority threshold for sending notifications (1 = highest)
            last_run_minutes: Time window in minutes to look for new alarms
        """
        self.notification_threshold = notification_threshold
        self.last_run_minutes = last_run_minutes
        
        # Keep track of already notified alarms to prevent duplicates
        self.notified_alarms: Set[int] = set()
        
        # Load contact list from environment variables
        self.contacts = []
        try:
            contact_list_str = os.environ.get('CONTACT_LIST', '[]')
            self.contacts = json.loads(contact_list_str)
            logger.info(f"Loaded {len(self.contacts)} contacts for notifications")
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error loading contact list: {str(e)}")
            self.contacts = []
        
    def process_alarms(self, alarms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process alarms and determine which ones need SMS notifications
        
        Args:
            alarms: List of alarm objects from the EDS API
            
        Returns:
            List of notification objects with recipient and message details
        """
        notifications = []
        
        for alarm in alarms:
            # Skip alarms we've already notified about
            if alarm.get('sid') in self.notified_alarms:
                continue
                
            # Check if alarm priority meets the threshold
            priority = alarm.get('ap')
            if priority is None or priority > self.notification_threshold:
                continue
            
            # If we have contacts configured, send to all contacts
            if self.contacts:
                # Format the alarm timestamp
                timestamp = alarm.get('ts')
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp)
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    formatted_time = "Unknown time"
                    
                # Format the message
                message = self._format_message(alarm, formatted_time)
                
                # Create notifications for each contact
                for contact in self.contacts:
                    if contact.get('number'):
                        notifications.append({
                            'recipient': contact['number'],
                            'message': message,
                            'alarm_id': alarm.get('sid'),
                            'priority': alarm.get('ap'),
                            'timestamp': timestamp,
                            'contact_name': contact.get('name', 'Unknown')
                        })
                
                # Add to notified alarms set to prevent duplicate notifications
                sid = alarm.get('sid')
                if sid is not None:
                    self.notified_alarms.add(sid)
            else:
                # Fall back to old behavior for backward compatibility
                notification = self._prepare_notification(alarm)
                if notification:
                    notifications.append(notification)
                    
                    # Add to notified alarms set to prevent duplicate notifications
                    sid = alarm.get('sid')
                    if sid is not None:
                        self.notified_alarms.add(sid)
                
        return notifications
        
    def _prepare_notification(self, alarm: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Prepare a notification object for an alarm
        
        Args:
            alarm: Alarm object from the EDS API
            
        Returns:
            Notification object with recipient and message
        """
        try:
            # Extract recipient from aux field if available
            # This assumes aux field contains contact information in a specific format
            recipient = self._extract_recipient(alarm)
            if not recipient:
                logger.warning(f"No recipient found for alarm {alarm.get('sid')}")
                return None
                
            # Format the alarm timestamp
            timestamp = alarm.get('ts')
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                formatted_time = "Unknown time"
                
            # Format the message
            message = self._format_message(alarm, formatted_time)
            
            return {
                'recipient': recipient,
                'message': message,
                'alarm_id': alarm.get('sid'),
                'priority': alarm.get('ap'),
                'timestamp': timestamp
            }
            
        except Exception as e:
            logger.error(f"Error preparing notification for alarm {alarm.get('sid')}: {str(e)}")
            return None
            
    def _extract_recipient(self, alarm: Dict[str, Any]) -> Optional[str]:
        """
        Extract recipient phone number from alarm data or contact list
        
        Args:
            alarm: Alarm object from the EDS API
            
        Returns:
            Recipient phone number or None if not found
        """
        # First, check if we have configured contacts
        if self.contacts:
            # For now, just return the first contact's number if available
            # In a real implementation, you might want to look up the appropriate contact
            # based on alarm attributes like source (zd) or technological group (tg)
            if len(self.contacts) > 0:
                logger.info(f"Using contact {self.contacts[0]['name']} for alarm notification")
                return self.contacts[0]['number']
        
        # Fallback: Check if aux field contains contact info
        aux = alarm.get('aux', '')
        
        # Example: if aux field has format "contact:+1234567890;details:..."
        if aux and 'contact:' in aux:
            contact_part = aux.split('contact:')[1].split(';')[0]
            # Format phone number if needed
            return contact_part.strip()
        
        # If no contacts are configured and no contact info in the alarm,
        # log a warning and return None
        logger.warning("No contacts configured and no contact information in alarm data")
        return None
        
    def _format_message(self, alarm: Dict[str, Any], formatted_time: str) -> str:
        """
        Format alarm notification message
        
        Args:
            alarm: Alarm object from the EDS API
            formatted_time: Formatted timestamp string
            
        Returns:
            Formatted message string
        """
        # Extract alarm information
        alarm_id = alarm.get('sid', 'Unknown')
        point_name = alarm.get('iess', 'Unknown')
        description = alarm.get('desc', 'No description')
        value = alarm.get('value', 'Unknown')
        source = alarm.get('zd', 'Unknown')
        
        # Get priority string
        priority_map = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}
        ap_value = alarm.get('ap')
        priority = "UNKNOWN"
        if ap_value is not None:
            try:
                priority_key = int(ap_value)
                priority = priority_map.get(priority_key, "UNKNOWN")
            except (ValueError, TypeError):
                pass
        
        # Format message
        message = (
            f"ALARM NOTIFICATION\n"
            f"Priority: {priority}\n"
            f"Time: {formatted_time}\n"
            f"Point: {point_name}\n"
            f"Description: {description}\n"
            f"Value: {value}\n"
            f"Source: {source}\n"
            f"ID: {alarm_id}"
        )
        
        return message
