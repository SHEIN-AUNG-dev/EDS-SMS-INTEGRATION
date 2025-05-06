import requests
import logging
import json
from typing import Dict, List, Optional, Any

logger = logging.getLogger('tnz_client')

class TNZClient:
    """
    Client for interacting with the TNZ SMS API
    """
    
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize the TNZ API client
        
        Args:
            base_url: Base URL for the TNZ API
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        # Set up default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Basic {self.api_key}'
        })
    
    def send_sms(self, to: str, message: str, sender_id: str = None, 
                 reference: str = None, validate_only: bool = False) -> bool:
        """
        Send an SMS via the TNZ API
        
        Args:
            to: Recipient phone number
            message: SMS message content
            sender_id: Optional sender ID
            reference: Optional reference for tracking
            validate_only: If True, only validate the request without sending
            
        Returns:
            True if SMS was sent successfully, False otherwise
        """
        try:
            url = f"{self.base_url}/sms/send"
            
            # Build the payload
            payload = {
                "Destinations": [to],
                "Message": message,
                "ValidateOnly": validate_only
            }
            
            # Add optional parameters if provided
            if sender_id:
                payload["SenderId"] = sender_id
                
            if reference:
                payload["Reference"] = reference
            
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            result = data.get('Result', {})
            
            # Check if the SMS was sent successfully
            if result.get('Success', False):
                message_id = result.get('MessageId')
                logger.info(f"SMS sent successfully. Message ID: {message_id}")
                return True
            else:
                errors = result.get('Errors', [])
                error_msg = '; '.join(errors) if errors else 'Unknown error'
                logger.error(f"Failed to send SMS: {error_msg}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending SMS: {str(e)}")
            return False
    
    def check_message_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Check the status of a sent message
        
        Args:
            message_id: The ID of the message to check
            
        Returns:
            Message status details or None if retrieval failed
        """
        try:
            url = f"{self.base_url}/sms/status/{message_id}"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            result = data.get('Result', {})
            
            if result.get('Success', False):
                logger.info(f"Retrieved status for message {message_id}")
                return result
            else:
                errors = result.get('Errors', [])
                error_msg = '; '.join(errors) if errors else 'Unknown error'
                logger.error(f"Failed to get message status: {error_msg}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking message status: {str(e)}")
            return None
