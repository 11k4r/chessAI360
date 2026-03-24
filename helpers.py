import json
import os
import io
import chess.pgn


def fen_to_epd(fen):
    """
    Converts a FEN (Forsyth-Edwards Notation) string to a basic EPD 
    (Extended Position Description) string.
    
    Extracts the first 4 fields:
    1. Piece placement
    2. Active color
    3. Castling rights
    4. En passant target square
    """
    if not isinstance(fen, str) or not fen.strip():
        return ""
        
    # Split the FEN by whitespace and keep only the first 4 segments
    return " ".join(fen.split()[:4])

    
def load_opening_books(folder_name):


    json_filepaths = [
        os.path.join(folder_name, "ecoA.json"),
        os.path.join(folder_name, "ecoB.json"),
        os.path.join(folder_name, "ecoC.json"),
        os.path.join(folder_name, "ecoD.json"),
        os.path.join(folder_name, "ecoE.json")
    ]
    
    opening_book = {}
    
    for filepath in json_filepaths:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                eco_data = json.load(f)
            
            # The eco.json files are Dictionaries mapped by FEN strings
            if isinstance(eco_data, dict):
                for fen_key, opening_data in eco_data.items():
                    epd = fen_to_epd(fen_key)
                    opening_book[epd] = opening_data
            
            # Fallback just in case some files are formatted as a List
            elif isinstance(eco_data, list):
                for entry in eco_data:
                    if "fen" in entry:
                        epd = fen_to_epd(entry["fen"])
                        opening_book[epd] = entry
                        
        except FileNotFoundError:
            print(f"Warning: Could not find {filepath}. Make sure the path is correct.")
            
    return opening_book

    


def get_opening_from_fen(fen, book):
    """
    Takes a FEN string and the loaded opening book dictionary,
    and returns the opening details if a match is found.
    """
    if not fen:
        return {"eco": "Unknown", "name": "Unknown Position"}
        
    # Convert FEN to EPD by keeping only the first 4 segments
    # (Piece placement, active color, castling rights, en passant)
    epd = " ".join(fen.split()[:4])
    
    # Look up the EPD in the book
    if epd in book:
        return book[epd]
    else:
        return {"eco": "Unknown", "name": "Unknown Opening"}
        


def calculate_final_score(mg, eg, phase):
    if mg is None or eg is None or phase is None:
        return None
        
    final_score = ((mg * phase) + (eg * (128 - phase))) / 128
    
    return round(final_score, 2)


def extract_metric(static_trace, metric_key, phase):
    """Safely extracts and calculates the tapered score for a given metric."""
    if not static_trace:
        return 0.0, 0.0
        
    metric_data = static_trace.get(metric_key, {})
    white_data = metric_data.get('White', {})
    black_data = metric_data.get('Black', {})
    
    white_score = calculate_final_score(white_data.get('mg'), white_data.get('eg'), phase) or 0.0
    black_score = calculate_final_score(black_data.get('mg'), black_data.get('eg'), phase) or 0.0
    
    return white_score, black_score



def extract_time_fields(data):
    """
    Takes the game data dictionary, parses the PGN to calculate the time spent 
    and time remaining for each ply, and appends these fields to the analysis data.
    """
    analysis_data = data.get('analysis', [])
    pgn_str = data.get('pgn', '')
    
    # Default fallback if no PGN or analysis data exists
    if not pgn_str or not analysis_data:
        for pos in analysis_data:
            pos['time'] = 0.0
            pos['time_remain'] = [0.0, 0.0]
        return data

    game = chess.pgn.read_game(io.StringIO(pgn_str))
    if not game:
        for pos in analysis_data:
            pos['time'] = 0.0
            pos['time_remain'] = [0.0, 0.0]
        return data

    # 1. Parse Time Control Header
    base_time = 0.0
    increment = 0.0
    tc_header = game.headers.get("TimeControl", "")
    try:
        if "+" in tc_header:
            base_time = float(tc_header.split("+")[0])
            increment = float(tc_header.split("+")[1])
        elif tc_header.isdigit():
            base_time = float(tc_header)
    except ValueError:
        pass

    node = game
    w_clock = base_time
    b_clock = base_time
    
    # 2. Try to infer base_time from the first clock if header is missing or empty
    if base_time == 0.0 and node.variations:
        first_clk = node.variation(0).clock()
        if first_clk is not None:
            base_time = float(first_clk)
            w_clock = base_time
            b_clock = base_time

    # 3. Step through the game and record times
    ply_times = {}
    ply_times[0] = {
        "time_remain": [w_clock, b_clock],
        "time": 0.0
    }
    
    ply = 0
    while node.variations:
        next_node = node.variation(0)
        ply += 1
        
        clk = next_node.clock()
        time_taken = 0.0
        
        if clk is not None:
            if ply % 2 == 1: # White's turn completed
                time_taken = max(0.0, w_clock - clk + increment)
                w_clock = float(clk)
            else: # Black's turn completed
                time_taken = max(0.0, b_clock - clk + increment)
                b_clock = float(clk)
        
        ply_times[ply] = {
            "time_remain": [w_clock, b_clock],
            "time": round(time_taken, 1)
        }
        node = next_node

    # 4. Map the calculated times back to the analysis array
    for pos in analysis_data:
        current_ply = pos.get('ply', 0)
        p_times = ply_times.get(current_ply, {"time_remain": [0.0, 0.0], "time": 0.0})
        pos['time'] = p_times['time']
        pos['time_remain'] = p_times['time_remain']

    return data