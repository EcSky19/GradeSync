import os
import requests
from flask import Flask, redirect, url_for, session, request, jsonify, render_template, flash
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Secret Key Handling
secret_key = os.getenv("FLASK_SECRET_KEY")
if not secret_key:
    print("ERROR: FLASK_SECRET_KEY is not set. Using a default key for testing.")
    secret_key = "super_secret_key"

app.secret_key = secret_key

# OAuth Configuration
oauth = OAuth(app)

# Canvas OAuth
canvas = oauth.register(
    name='canvas',
    client_id=os.getenv("CANVAS_CLIENT_ID"),
    client_secret=os.getenv("CANVAS_CLIENT_SECRET"),
    access_token_url='https://canvas.cornell.edu/login/oauth2/token',
    authorize_url='https://canvas.cornell.edu/login/oauth2/auth',
    client_kwargs={'scope': 'profile email'},
)

# Google OAuth
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
    client_kwargs={'scope': 'https://www.googleapis.com/auth/calendar.events'},
)

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login/canvas')
def login_canvas():
    redirect_uri = url_for('canvas_auth', _external=True)
    return canvas.authorize_redirect(redirect_uri)

@app.route('/auth/canvas')
def canvas_auth():
    try:
        token = canvas.authorize_access_token()
        session['canvas_token'] = token
        flash("Canvas login successful", "success")
        return redirect('/sync')
    except Exception as e:
        flash(f"Canvas login failed: {str(e)}", "error")
        return redirect('/')

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_auth', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google')
def google_auth():
    try:
        token = google.authorize_access_token()
        session['google_token'] = token
        flash("Google login successful", "success")
        return redirect('/sync')
    except Exception as e:
        flash(f"Google login failed: {str(e)}", "error")
        return redirect('/')

@app.route('/sync')
def sync_assignments():
    canvas_token = session.get('canvas_token')
    google_token = session.get('google_token')

    if not canvas_token or not google_token:
        flash("Please log in to both Canvas and Google first.", "warning")
        return redirect('/')

    headers = {'Authorization': f"Bearer {canvas_token['access_token']}"}
    try:
        response = requests.get('https://canvas.cornell.edu/api/v1/courses', headers=headers)
        courses = response.json()

        assignments = []
        for course in courses:
            course_id = course.get('id')
            response = requests.get(f'https://canvas.cornell.edu/api/v1/courses/{course_id}/assignments', headers=headers)
            assignments.extend(response.json())

        # Sync to Google Calendar
        for assignment in assignments:
            event = {
                'summary': assignment['name'],
                'description': assignment.get('description', ''),
                'start': {'dateTime': assignment['due_at'], 'timeZone': 'America/New_York'},
                'end': {'dateTime': assignment['due_at'], 'timeZone': 'America/New_York'}
            }
            google_headers = {'Authorization': f"Bearer {google_token['access_token']}"}
            requests.post('https://www.googleapis.com/calendar/v3/calendars/primary/events', json=event, headers=google_headers)

        return render_template('sync.html', assignments=assignments)

    except Exception as e:
        flash(f"Error syncing assignments: {str(e)}", "error")
        return redirect('/')

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')

    # Create index.html
    with open('templates/index.html', 'w') as index_file:
        index_file.write('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>GradeSync - Home</title>
        </head>
        <body>
            <h1>Welcome to GradeSync</h1>
            <p>Sync your Canvas assignments with Google Calendar</p>
            <a href="/login/canvas">Login with Canvas</a><br>
            <a href="/login/google">Login with Google</a>
        </body>
        </html>
        ''')

    # Create sync.html
    with open('templates/sync.html', 'w') as sync_file:
        sync_file.write('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>GradeSync - Sync Assignments</title>
        </head>
        <body>
            <h1>Assignments Synced</h1>
            <ul>
            {% for assignment in assignments %}
                <li>
                    <strong>{{ assignment.name }}</strong><br>
                    Due: {{ assignment.due_at }}<br>
                    <a href="{{ assignment.html_url }}" target="_blank">View on Canvas</a>
                </li>
            {% endfor %}
            </ul>
        </body>
        </html>
        ''')

    app.run(debug=True)
