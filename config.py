import os

class Config:
    # Basic App Settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-chessai360')
    
    # Securely fetch credentials from environment variables
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    
    SITE_NAME = "chessAI 360"
    
    # Analysis Settings
    Thinking_Time = 10.0  # Seconds for static server-side analysis
    Threads = 2         
    TIME_CONTROL_STYLES = {
        'bullet': 'text-purple-400',    # Purple (Chaotic/Fast)
        'blitz': 'text-yellow-400',     # Yellow (Electric/Lightning)
        'rapid': 'text-blue-400',       # Blue (Calm/Thinking)
        'daily': 'text-cyan-400',       # Cyan (Slow)
        'classical': 'text-cyan-400'
    }

    OPENINGS = 'openings'
