import requests
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any

logger = logging.getLogger('eds_client')

class EDSClient:
    """
    Client for interacting with the EDS API
    """
    
    def __init__(self, base_url: str, username: str, password: str, client_type: str = 'azure_function'):
        """
        Initialize the EDS client
        
        Args:
            base_url: Base URL for the EDS API
            username: Username for authentication
            password: Password for authentication
            client_type: Client type identifier
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.client_type = client_type
        self.session_id = None
        self.session = requests.Session()
        
    def login(self) -> Optional[str]:
        """
        Login to the EDS API and get a session ID
        
        Returns:
            Session ID or None if login failed
        """
        try:
            url = f"{self.base_url}/api/v1/login"
            payload = {
                "username": self.username,
                "password": self.password,
                "type": self.client_type
            }
            
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            self.session_id = data.get('sessionId')
            
            if self.session_id:
                # Update session headers with the Authorization token
                self.session.headers.update({
                    'Authorization': f'Bearer {self.session_id}'
                })
                logger.info("Successfully logged in to EDS API")
                return self.session_id
            else:
                logger.error("Login response did not contain a session ID")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during login: {str(e)}")
            return None
    
    def logout(self) -> bool:
        """
        Logout from the EDS API
        
        Returns:
            True if logout was successful, False otherwise
        """
        if not self.session_id:
            logger.warning("No active session to logout from")
            return True
            
        try:
            url = f"{self.base_url}/api/v1/logout"
            response = self.session.post(url)
            response.raise_for_status()
            
            logger.info("Successfully logged out from EDS API")
            self.session_id = None
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during logout: {str(e)}")
            return False
    
    def ping(self) -> bool:
        """
        Ping the EDS API to keep the session alive
        
        Returns:
            True if ping was successful, False otherwise
        """
        if not self.session_id:
            logger.warning("No active session for ping")
            return False
            
        try:
            url = f"{self.base_url}/api/v1/ping"
            response = self.session.get(url)
            response.raise_for_status()
            
            logger.debug("Successfully pinged EDS API")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during ping: {str(e)}")
            return False
    
    def query_alarms(self, minutes: int = 15, priorities: List[int] = None) -> List[Dict[str, Any]]:
        """
        Query alarms from the EDS API
        
        Args:
            minutes: Look for alarms in the last X minutes
            priorities: List of alarm priorities to filter by
            
        Returns:
            List of alarm objects
        """
        if not self.session_id:
            logger.error("No active session for querying alarms")
            return []
            
        try:
            # Use the points/query endpoint to get alarm data
            url = f"{self.base_url}/api/v1/points/query"
            
            # Calculate the timestamp for filtering
            from_time = int((datetime.now() - timedelta(minutes=minutes)).timestamp())
            till_time = int(datetime.now().timestamp())
            
            # Set default priorities if not provided
            if priorities is None:
                priorities = [1, 2]  # High and medium priority alarms
                
            # Construct the filter for active alarms
            payload = {
                "filters": [{
                    "ts": {
                        "from": from_time,
                        "till": till_time
                    },
                    "ap": priorities,  # Alarm priority filter
                    # Filter for points with alarm status bit set
                    "stSet": 1,  # Assuming bit 0 is the alarm status bit
                    "quality": ["GOOD", "FAIR"]  # Only get alarms with good quality
                }],
                "order": ["ap", "-ts"],  # Order by priority and then by timestamp desc
                "fields": ["sid", "iess", "desc", "value", "ts", "ap", "quality", "aux"]
            }
            
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            alarms = data.get('points', [])
            
            logger.info(f"Retrieved {len(alarms)} alarms from EDS API")
            return alarms
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying alarms: {str(e)}")
            return []
            
    def get_alarm_details(self, sid: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific alarm
        
        Args:
            sid: The system ID of the alarm point
            
        Returns:
            Alarm details or None if retrieval failed
        """
        if not self.session_id:
            logger.error("No active session for getting alarm details")
            return None
            
        try:
            url = f"{self.base_url}/api/v1/points/query"
            
            payload = {
                "filters": [{
                    "sid": [sid]
                }],
                "fields": ["sid", "iess", "desc", "value", "ts", "ap", "quality", 
                           "aux", "idcs", "zd", "un", "dp", "artd", "ard"]
            }
            
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            points = data.get('points', [])
            
            if points:
                return points[0]
            else:
                logger.warning(f"No details found for alarm with sid {sid}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting alarm details: {str(e)}")
            return None
