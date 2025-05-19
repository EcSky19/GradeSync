import os
import requests
from flask import Flask, redirect, url_for, session, request, jsonify, render_template
from authlib.integrations.flask_client import OAuth
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

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
    token = canvas.authorize_access_token()
    session['canvas_token'] = token
    return redirect('/sync')

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('google_auth', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google')
def google_auth():
    token = google.authorize_access_token()
    session['google_token'] = token
    return redirect('/sync')

@app.route('/sync')
def sync_assignments():
    canvas_token = session.get('canvas_token')
    google_token = session.get('google_token')

    if not canvas_token or not google_token:
        return redirect('/login/canvas')

    # Fetch assignments from Canvas
    headers = {'Authorization': f"Bearer {canvas_token['access_token']}"}
    response = requests.get('https://canvas.cornell.edu/api/v1/courses', headers=headers)
    courses = response.json()

    assignments = []
    for course in courses:
        course_id = course['id']
        response = requests.get(f'https://canvas.cornell.edu/api/v1/courses/{course_id}/assignments', headers=headers)
        assignments.extend(response.json())

    # Sync to Google Calendar
    for assignment in assignments:
        event = {
            'summary': assignment['name'],
            'description': assignment['description'],
            'start': {'dateTime': assignment['due_at'], 'timeZone': 'America/New_York'},
            'end': {'dateTime': assignment['due_at'], 'timeZone': 'America/New_York'}
        }
        google_headers = {'Authorization': f"Bearer {google_token['access_token']}"}
        requests.post('https://www.googleapis.com/calendar/v3/calendars/primary/events', json=event, headers=google_headers)

    return render_template('sync.html', assignments=assignments)

if __name__ == '__main__':
    app.run(debug=True)
