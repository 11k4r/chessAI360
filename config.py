import os

class Config:
    # Basic App Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-chessai360'
    GOOGLE_CLIENT_ID = '42685457896-87g81dkvhmdh8ger6d5df66jo37lrmh9.apps.googleusercontent.com'
    GOOGLE_CLIENT_SECRET = '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'
    SITE_NAME = "chessAI 360"
    GROQ_API_KEY = "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"
    
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
