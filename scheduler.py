"""
Email Scheduler Background Service
Run this script separately to process scheduled emails.
It checks the database every minute and sends emails at their scheduled time.

Usage:
    python scheduler.py

This script must be running for scheduled emails to be sent.
You can run it on any device that has access to the database file.
"""

import sqlite3
import smtplib
import json
import time
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'leadgen.db')
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


def load_config():
    """Load Gmail credentials from config file."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {}


def send_email(recipient, subject, body, config):
    """Send email via Gmail SMTP."""
    gmail_address = config.get('gmail_address')
    gmail_password = config.get('gmail_app_password')
    
    if not gmail_address or not gmail_password:
        return False, "Gmail credentials not configured in config.json"
    
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_address
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_address, gmail_password)
            server.send_message(msg)
        
        return True, "Sent successfully"
    except Exception as e:
        return False, str(e)


def process_scheduled_emails():
    """Check for emails due to be sent and send them."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get emails that are due
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        SELECT id, recipient, subject, body, company_name, website, niche 
        FROM scheduled_emails 
        WHERE scheduled_time <= ? AND status = 'Pending'
    ''', (now,))
    
    due_emails = cursor.fetchall()
    
    if due_emails:
        config = load_config()
        
        for email in due_emails:
            email_id, recipient, subject, body, company_name, website, niche = email
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending to {recipient}...")
            success, message = send_email(recipient, subject, body, config)
            
            # Update status
            new_status = 'Sent' if success else f'Failed: {message}'
            cursor.execute('UPDATE scheduled_emails SET status = ? WHERE id = ?', (new_status, email_id))
            
            # Log to email_log table
            cursor.execute('''
                INSERT INTO email_log (timestamp, company_name, website, contact_email, niche, subject, body, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                company_name, website, recipient, niche, subject, body,
                'Yes (Scheduled)' if success else 'Failed (Scheduled)',
                message if not success else ''
            ))
            
            print(f"  {'✓ Sent!' if success else f'✗ Failed: {message}'}")
        
        conn.commit()
    
    conn.close()
    return len(due_emails)


def main():
    print("=" * 50)
    print("LeadGen Pro - Email Scheduler Service")
    print("=" * 50)
    print(f"Database: {DB_PATH}")
    print(f"Config: {CONFIG_PATH}")
    print("Checking every 60 seconds for scheduled emails...")
    print("Press Ctrl+C to stop.\n")
    
    while True:
        try:
            processed = process_scheduled_emails()
            if processed > 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Processed {processed} email(s)")
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("\nScheduler stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
