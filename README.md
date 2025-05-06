# EDS SMS Alarm Notification System

An Azure Function application that monitors the EDS API for alarms and sends SMS notifications via the TNZ API. This project includes a web interface for configuration and monitoring of the alarm notification system.

## Features

- **Azure Function Timer Trigger**: Automatically checks for new alarms at regular intervals
- **EDS API Integration**: Connects to the EDS API to retrieve alarm data
- **TNZ SMS API Integration**: Sends SMS notifications for critical alarms
- **Web Interface**: Configuration and monitoring dashboard
- **Contact Management**: Define and manage contacts for SMS notifications
- **Alarm Filtering**: Configure which alarm priorities trigger notifications

## Components

- **function_app.py**: Main Azure Function with timer trigger
- **eds_client.py**: Client for interacting with EDS API
- **tnz_client.py**: Client for interacting with TNZ SMS API
- **alarm_processor.py**: Logic for processing alarms and determining notification needs
- **main.py**: Flask web interface with configuration functionality

## Setup

1. Clone this repository
2. Create a `local.settings.json` file (see `local.settings.json.example` for template)
3. Install required Python packages: `pip install -r requirements.txt`
4. Run the web interface: `python main.py`
5. For local Azure Function testing: `func start`

## Configuration

Configuration is managed through the web interface at `/config` or by manually editing the `local.settings.json` file.

Required configuration values:
- **EDS_API_BASE_URL**: Base URL for the EDS API
- **EDS_API_USERNAME**: Username for EDS API authentication
- **EDS_API_PASSWORD**: Password for EDS API authentication
- **TNZ_API_BASE_URL**: Base URL for the TNZ API
- **TNZ_API_KEY**: API key for TNZ API authentication
- **ALARM_NOTIFICATION_THRESHOLD**: Priority threshold (1-3) for sending notifications
- **LAST_RUN_MINUTES**: Time window in minutes to look for new alarms

## Contact Management

Contact numbers for SMS notifications can be managed through the web interface:
1. Navigate to the Configuration page
2. Add or remove contacts in the Contact Management section
3. Save the configuration

## Deployment to Azure

1. Create an Azure Function App resource in Azure Portal
2. Deploy this code to the Function App
3. Configure application settings with the required configuration values
4. Set up a timer trigger as defined in `function.json`

## License

This project is proprietary and confidential.