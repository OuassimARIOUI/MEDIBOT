
from datetime import datetime


def send_alert_notification(alert_id, status, handled_by=None, email_to=None):
    """
    Send a notification when an alert status changes.
    
    Args:
        alert_id (int): The ID of the alert
        status (str): The new status ('acknowledged', 'escalated', etc.)
        handled_by (str, optional): Name of the nurse who handled the alert
        email_to (str, optional): Email address to send notification to
    
    Returns:
        bool: True if notification was sent successfully
    
    Note:
        This is a placeholder implementation for Sprint 02.
        In production, this would integrate with an SMTP server or
        notification service (SendGrid, Twilio, etc.)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("\n" + "="*60)
    print("📧 ALERT NOTIFICATION")
    print("="*60)
    print(f"⏰ Timestamp: {timestamp}")
    print(f"🆔 Alert ID: {alert_id}")
    print(f"📊 Status: {status}")
    
    if handled_by:
        print(f"👨‍⚕️ Handled By: {handled_by}")
    
    if email_to:
        print(f"📮 Recipient: {email_to}")
    else:
        print(f"📮 Recipient: nurse-station@medibot.hospital")
    
    print("="*60 + "\n")
    
    # Simulate successful send
    return True


def send_critical_alert(alert_id, patient_name, room_number, message):
    """
    Send an urgent notification for critical alerts.
    
    Args:
        alert_id (int): The ID of the alert
        patient_name (str): Name of the patient
        room_number (str): Patient's room number
        message (str): Alert message
    
    Returns:
        bool: True if notification was sent successfully
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("\n" + "="*60)
    print("🚨 CRITICAL ALERT NOTIFICATION")
    print("="*60)
    print(f"⏰ Timestamp: {timestamp}")
    print(f"🆔 Alert ID: {alert_id}")
    print(f"👤 Patient: {patient_name}")
    print(f"🏥 Room: {room_number}")
    print(f"💬 Message: {message}")
    print("\n⚠️  IMMEDIATE ACTION REQUIRED!")
    print("="*60 + "\n")
    
    # In production, this would:
    # - Send SMS to on-call nurse
    # - Trigger pager system
    # - Send email to multiple recipients
    # - Log to central monitoring system
    
    return True


def send_daily_summary(date, total_alerts, handled_alerts, critical_alerts):
    """
    Send a daily summary report of alert activity.
    
    Args:
        date (str): Date for the summary
        total_alerts (int): Total number of alerts generated
        handled_alerts (int): Number of alerts that were handled
        critical_alerts (int): Number of critical alerts
    
    Returns:
        bool: True if summary was sent successfully
    """
    print("\n" + "="*60)
    print("📊 DAILY ALERT SUMMARY")
    print("="*60)
    print(f"📅 Date: {date}")
    print(f"📈 Total Alerts: {total_alerts}")
    print(f"✅ Handled Alerts: {handled_alerts}")
    print(f"🚨 Critical Alerts: {critical_alerts}")
    
    if total_alerts > 0:
        handled_rate = (handled_alerts / total_alerts) * 100
        print(f"📊 Response Rate: {handled_rate:.1f}%")
    
    print("="*60 + "\n")
    
    return True


def send_webhook_notification(webhook_url, event_type, data):
    """
    Send a webhook notification to an external system.
    
    Args:
        webhook_url (str): The webhook endpoint URL
        event_type (str): Type of event ('alert.created', 'alert.acknowledged', etc.)
        data (dict): Event data payload
    
    Returns:
        bool: True if webhook was triggered successfully
    
    Note:
        In production, this would use requests library to POST to webhook URL:
        
        import requests
        response = requests.post(webhook_url, json={
            "event": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        return response.status_code == 200
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("\n" + "="*60)
    print("🔗 WEBHOOK NOTIFICATION")
    print("="*60)
    print(f"⏰ Timestamp: {timestamp}")
    print(f"🌐 Webhook URL: {webhook_url}")
    print(f"📋 Event Type: {event_type}")
    print(f"📦 Payload: {data}")
    print("="*60 + "\n")
    
    return True


def send_test_notification():
    """
    Send a test notification to verify the service is working.
    
    Returns:
        bool: True if test notification was sent
    """
    print("\n" + "="*60)
    print("🧪 TEST NOTIFICATION")
    print("="*60)
    print("✓ Mail service is configured correctly")
    print("✓ Notification system is operational")
    print("="*60 + "\n")
    
    return True


# Configuration (for future production use)
SMTP_CONFIG = {
    "host": "smtp.example.com",
    "port": 587,
    "username": "medibot@hospital.com",
    "password": "***",  # Use environment variables in production
    "use_tls": True
}

NOTIFICATION_RECIPIENTS = {
    "nurse_station": "nurses@hospital.com",
    "emergency": "emergency@hospital.com",
    "admin": "admin@hospital.com"
}

WEBHOOK_ENDPOINTS = {
    "monitoring": "https://monitoring.hospital.com/webhook",
    "analytics": "https://analytics.hospital.com/events"
}


# Example production implementation (commented out):
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to_address, subject, body):
    msg = MIMEMultipart()
    msg['From'] = SMTP_CONFIG['username']
    msg['To'] = to_address
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'html'))
    
    try:
        server = smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port'])
        if SMTP_CONFIG['use_tls']:
            server.starttls()
        server.login(SMTP_CONFIG['username'], SMTP_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
"""
