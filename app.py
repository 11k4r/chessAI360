import os
from flask import Flask, render_template, request, jsonify
from config import Config 
import json     
import datetime 
import mimetypes
import os
from groq import Groq

from game_analyzer import analyze_game
from card_generator import generate_player_card
from helpers import load_opening_books
from ChessEvaluationWrapper import ChessEvaluationWrapper

mimetypes.add_type('application/wasm', '.wasm')

# 1. Initialize Flask and load the Config file first
app = Flask(__name__)
app.config.from_object(Config)

# 2. Grab the key directly from the Flask config we just loaded
my_api_key = app.config.get('GROQ_API_KEY')
client = Groq(api_key=my_api_key)

opening_book = load_opening_books(app.config.get('OPENINGS'))

AI_EVALUATOR = ChessEvaluationWrapper(
    model_path="models/chess_evaluator_model.json", 
    columns_path="models/model_columns.json"
)


@app.route('/')
def index():
    return render_template('index.html', 
                           site_name=app.config['SITE_NAME'], # Accessed via app.config
                           tagline="Push Chess Forward",
                           sub_tagline="Go beyond the evaluation bar and decode your chess DNA. Use AI to measure key metrics such as harmony, mobility, pawn structure, and time management. Seamlessly sync with Chess.com and Lichess to transform your game history into a comprehensive player profile.")

@app.route('/analyze')
def analyze():
    return render_template('analyze.html', 
                           site_name=app.config['SITE_NAME'],
                           tc_styles=app.config['TIME_CONTROL_STYLES'])


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
    analysis_results = analyze_game(data, opening_book, client, user_side, evaluator=AI_EVALUATOR)
    
    return jsonify(analysis_results)

@app.route('/manual')
def manual():
    return render_template('manual.html', site_name=app.config['SITE_NAME'])

# Add this alongside your other routes in app.py
@app.route('/player_insights')
def player_card():
    return render_template('player_insights.html', 
                           site_name=app.config['SITE_NAME'])


@app.route('/api/analyze-insights', methods=['POST'])
def analyze_insights():
    data = request.get_json()
    
    os.makedirs('data', exist_ok=True)
    
    filename = "data/mock_player_insights.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
        
    
    return jsonify({"status": "success", "message": "Mock data saved successfully!", "file": filename})


@app.route('/api/analyze-batch', methods=['POST'])
def analyze_batch():
    payload = request.get_json()
    
    # Structure the payload so the card generator knows what needs fast vs deep analysis
    payload = {
        "batch_platform": {
            "batch_tc": {
                "games": payload.get('games', []),
                "analyzed_games": payload.get('analyzed_games', [])
            }
        }
    }
    
    try:
        batch_metrics = generate_player_card(payload, opening_book, client)
        return jsonify(batch_metrics)
    except Exception as e:
        print(f"Batch Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.after_request
def add_header(response):
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'credentialless' 
    return response
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)