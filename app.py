import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from config import Config 
import json     
import datetime 
import mimetypes
from groq import Groq
from authlib.integrations.flask_client import OAuth 
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix
from game_analyzer import analyze_game
from helpers import load_opening_books
from StaticChessEvaluator import StaticChessEvaluator
from player_insights import process_insights_batch

from game_analyzer import analyze_game
from helpers import load_opening_books
from StaticChessEvaluator import StaticChessEvaluator
from player_insights import process_insights_batch

mimetypes.add_type('application/wasm', '.wasm')

# 1. Initialize Flask and load the Config file first
app = Flask(__name__)
app.config.from_object(Config)

# Update database URI for Railway (PostgreSQL) vs Local (SQLite)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///chess_dna.db')
# SQLAlchemy 1.4+ requires 'postgresql://', but Railway sometimes provides 'postgres://'
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Define the User Table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120))
    chesscom_username = db.Column(db.String(120), default="")
    lichess_username = db.Column(db.String(120), default="")

class PlayerInsights(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    latest_chesscom_timestamp = db.Column(db.BigInteger, default=0)
    latest_lichess_timestamp = db.Column(db.BigInteger, default=0)
    stats_data = db.Column(db.JSON, nullable=True)

# Create the database tables automatically before the first request
with app.app_context():
    db.create_all()

client = Groq(api_key=my_api_key)

opening_book = load_opening_books(app.config.get('OPENINGS'))

evaluator = StaticChessEvaluator()

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config.get('GOOGLE_CLIENT_ID'),
    client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@app.route('/login')
def login():
    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if user_info:
        # 1. Check if user already exists in our database using their Google ID
        user = User.query.filter_by(google_id=user_info['sub']).first()
        
        # 2. If they don't exist, create a new row for them
        if not user:
            user = User(
                google_id=user_info['sub'],
                email=user_info['email'],
                name=user_info.get('given_name', '')
            )
            db.session.add(user)
            db.session.commit()
            
        # 3. Store their internal database ID in the session
        session['user_id'] = user.id
        session['user'] = user_info # Keep this for the profile picture in the navbar
        
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    return redirect('/')
# -----------------------

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # Ensure they are logged in
    if not session.get('user_id'):
        return redirect('/login')
        
    # Fetch the user directly from the database
    user = User.query.get(session['user_id'])
    
    # ---> ADD THIS CHECK <---
    # If the user ID is in the session but not in the DB (stale cookie)
    if not user:
        session.clear()  # Clear the invalid session
        return redirect('/login')
        
    if request.method == 'POST':
        # Update the database with the form submissions
        user.chesscom_username = request.form.get('chesscom_username', '').strip()
        user.lichess_username = request.form.get('lichess_username', '').strip()
        db.session.commit() # Save changes to the database
        
        return redirect('/profile')

    # Pass the database user object to the template
    return render_template('profile.html', site_name=app.config['SITE_NAME'], db_user=user)



@app.route('/')
def index():
    return render_template('index.html', 
                           site_name=app.config['SITE_NAME'], # Accessed via app.config
                           tagline="Push Chess Forward",
                           sub_tagline="Go beyond the evaluation bar and decode your chess DNA. Use AI to measure key metrics such as harmony, mobility, pawn structure, and time management. Seamlessly sync with Chess.com and Lichess to transform your game history into a comprehensive player profile.")



    
@app.route('/analyze')
def analyze():
    # Check if the user is logged in and fetch their saved usernames
    user = None
    if session.get('user_id'):
        user = User.query.get(session['user_id'])
        
    return render_template('analyze.html', 
                           site_name=app.config['SITE_NAME'],
                           tc_styles=app.config['TIME_CONTROL_STYLES'],
                           db_user=user) # Pass the user to the template


@app.route('/api/analyze-game', methods=['POST'])
def process_analysis_data():
    data = request.get_json()
    
    # 1. Save the JSON data locally (same behavior as before)
    os.makedirs('data', exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data/analysis_{timestamp}.json"
    
    # with open(filename, 'w') as f:
    #     json.dump(data, f, indent=4)

    user_side = data.get('user_side', 'white')
    analysis_results = analyze_game(data, opening_book, client, user_side, evaluator=evaluator)
    
    return jsonify(analysis_results)

@app.route('/manual')
def manual():
    return render_template('manual.html', site_name=app.config['SITE_NAME'])

@app.route('/player_insights')
def player_card():
    if 'user_id' not in session:
        return render_template('player_insights.html', user_logged_in=False)
        
    user = User.query.get(session['user_id'])
    insights = PlayerInsights.query.filter_by(user_id=user.id).first()
    
    can_sync = True
    time_until_sync = ""
    stats_data = None

    if insights and insights.last_updated:
        stats_data = insights.stats_data
        cooldown = datetime.timedelta(seconds=1) 
        next_sync = insights.last_updated + cooldown
        now = datetime.datetime.utcnow()
        
        if now < next_sync:
            can_sync = False
            diff = next_sync - now
            days, seconds = diff.days, diff.seconds
            hours = seconds // 3600
            time_until_sync = f"{days}d {hours}h"

    return render_template('player_insights.html', 
                           site_name=app.config.get('SITE_NAME', 'Chess AI'),
                           user_logged_in=True,
                           can_sync=can_sync,
                           time_until_sync=time_until_sync,
                           stats_data=stats_data or {},
                           db_user=user) # <-- ADD THIS LINE



@app.route('/api/analyze-batch', methods=['POST'])
def analyze_batch():
    data = request.get_json()
    
    batch_metrics = process_insights_batch(
        data=data, 
        opening_book=opening_book, 
        client=client, 
        evaluator=evaluator
    )
    
    return jsonify(batch_metrics)


@app.route('/api/save-insights', methods=['POST'])
def save_insights():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    user_id = session['user_id']
    
    insights = PlayerInsights.query.filter_by(user_id=user_id).first()
    if not insights:
        insights = PlayerInsights(user_id=user_id)
        db.session.add(insights)

    insights.last_updated = datetime.datetime.utcnow()
    insights.stats_data = data.get('stats_data', {})
    
    db.session.commit()
    return jsonify({"status": "success"})


@app.after_request
def add_header(response):
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'credentialless' 
    return response
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)
