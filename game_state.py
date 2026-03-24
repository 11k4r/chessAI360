import chess
import os
import json


# ==========================================
# HELPER & METRIC FUNCTIONS (Embedded)
# ==========================================

def fen_to_epd(fen: str) -> str:
    """Converts a FEN string to a basic EPD (first 4 fields)."""
    if not isinstance(fen, str) or not fen.strip():
        return ""
    return " ".join(fen.split()[:4])

def get_opening_from_fen(fen: str, book: dict) -> dict:
    """Looks up the EPD in the provided opening book."""
    if not fen:
        return {"eco": "Unknown", "name": "Unknown Position"}
    epd = fen_to_epd(fen)
    if epd in book:
        return book[epd]
    return {"eco": "Unknown", "name": "Unknown Opening"}

def get_kaufman_material(fen: str) -> tuple[float, float]:
    """Calculates material values dynamically based on Kaufman's weights."""
    board_state = fen.split()[0]
    
    counts = {
        'P': board_state.count('P'), 'N': board_state.count('N'), 'B': board_state.count('B'), 
        'R': board_state.count('R'), 'Q': board_state.count('Q'),
        'p': board_state.count('p'), 'n': board_state.count('n'), 'b': board_state.count('b'), 
        'r': board_state.count('r'), 'q': board_state.count('q')
    }
    
    # Kaufman's pawn-dependency adjustments
    w_knight_val = 3.25 + (1/16) * (counts['P'] - 5)
    w_rook_val   = 5.00 - (1/8)  * (counts['P'] - 5)
    
    b_knight_val = 3.25 + (1/16) * (counts['p'] - 5)
    b_rook_val   = 5.00 - (1/8)  * (counts['p'] - 5)
    
    white_material = (counts['P'] * 1.0) + (counts['N'] * w_knight_val) + (counts['B'] * 3.25) + (counts['R'] * w_rook_val) + (counts['Q'] * 9.75)
    black_material = (counts['p'] * 1.0) + (counts['n'] * b_knight_val) + (counts['b'] * 3.25) + (counts['r'] * b_rook_val) + (counts['q'] * 9.75)
    
    if counts['B'] >= 2: white_material += 0.5
    if counts['b'] >= 2: black_material += 0.5
        
    return round(white_material, 4), round(black_material, 4)

def is_endgame(fen: str, user_side: str) -> dict:
    """Determines if the position is an endgame and classifies it."""
    board = chess.Board(fen)
    
    w_q = len(board.pieces(chess.QUEEN, chess.WHITE))
    b_q = len(board.pieces(chess.QUEEN, chess.BLACK))
    w_r = len(board.pieces(chess.ROOK, chess.WHITE))
    b_r = len(board.pieces(chess.ROOK, chess.BLACK))
    w_b = len(board.pieces(chess.BISHOP, chess.WHITE))
    b_b = len(board.pieces(chess.BISHOP, chess.BLACK))
    w_n = len(board.pieces(chess.KNIGHT, chess.WHITE))
    b_n = len(board.pieces(chess.KNIGHT, chess.BLACK))
    
    white_material = (w_q * 9) + (w_r * 5) + (w_b * 3) + (w_n * 3)
    black_material = (b_q * 9) + (b_r * 5) + (b_b * 3) + (b_n * 3)
    
    is_end = (white_material <= 13 and black_material <= 13) or (white_material <= 3) or (black_material <= 3)
    
    if not is_end:
        return {"is_endgame": False, "type": "Middlegame or Opening"}

    def get_piece_string(q, r, b, n):
        pieces = []
        if q == 1: pieces.append("Queen")
        elif q > 1: pieces.append(f"{q} Queens")
        if r == 1: pieces.append("Rook")
        elif r > 1: pieces.append(f"{r} Rooks")
        if b == 1: pieces.append("Bishop")
        elif b > 1: pieces.append(f"{b} Bishops")
        if n == 1: pieces.append("Knight")
        elif n > 1: pieces.append(f"{n} Knights")
        
        if not pieces: return "King"
        if len(pieces) == 1: return pieces[0]
        if len(pieces) == 2: return f"{pieces[0]} and {pieces[1]}"
        return ", ".join(pieces[:-1]) + f" and {pieces[-1]}"

    def get_bishop_type(board_obj):
        w_bishops = list(board_obj.pieces(chess.BISHOP, chess.WHITE))
        b_bishops = list(board_obj.pieces(chess.BISHOP, chess.BLACK))
        if len(w_bishops) == 1 and len(b_bishops) == 1:
            w_sq, b_sq = w_bishops[0], b_bishops[0]
            w_is_light = (chess.square_file(w_sq) + chess.square_rank(w_sq)) % 2 != 0
            b_is_light = (chess.square_file(b_sq) + chess.square_rank(b_sq)) % 2 != 0
            return "Same-colored Bishops" if w_is_light == b_is_light else "Opposite-colored Bishops"
        return None

    white_str = get_piece_string(w_q, w_r, w_b, w_n)
    black_str = get_piece_string(b_q, b_r, b_b, b_n)
    
    if white_str == "King" and black_str == "King":
        endgame_type = "Pawn Endgame"
    else:
        if user_side.lower() == 'w':
            endgame_type = f"{white_str} vs {black_str}"
        elif user_side.lower() == 'b':
            endgame_type = f"{black_str} vs {white_str}"
        else:
            endgame_type = f"{white_str} vs {black_str}"

    if w_b == 1 and b_b == 1:
        bishop_type = get_bishop_type(board)
        if bishop_type:
            if w_q == 0 and w_r == 0 and w_n == 0 and b_q == 0 and b_r == 0 and b_n == 0:
                endgame_type = bishop_type
            else:
                endgame_type += f" ({bishop_type})"

    return {"is_endgame": True, "type": endgame_type}

def is_not_opening(fen: str) -> bool:
    """Evaluates piece development and game state to see if the opening is over."""
    board = chess.Board(fen)
    if board.fullmove_number > 12:
        return True
    
    def is_developed(color):
        minors = [(chess.B1, chess.KNIGHT), (chess.G1, chess.KNIGHT), (chess.C1, chess.BISHOP), (chess.F1, chess.BISHOP)] if color == chess.WHITE else \
                 [(chess.B8, chess.KNIGHT), (chess.G8, chess.KNIGHT), (chess.C8, chess.BISHOP), (chess.F8, chess.BISHOP)]
        undeveloped_count = sum(1 for sq, pt in minors if board.piece_type_at(sq) == pt and board.color_at(sq) == color)
        return undeveloped_count <= 1

    both_developed = is_developed(chess.WHITE) and is_developed(chess.BLACK)

    def rooks_connected_or_traded(color):
        rooks = list(board.pieces(chess.ROOK, color))
        if len(rooks) < 2: return True
        for sq in rooks:
            attacks = board.attacks(sq)
            if any(other_sq in attacks for other_sq in rooks if sq != other_sq): return True
        return False

    rooks_passed = rooks_connected_or_traded(chess.WHITE) or rooks_connected_or_traded(chess.BLACK)
    queens_traded = len(board.pieces(chess.QUEEN, chess.WHITE)) == 0 and len(board.pieces(chess.QUEEN, chess.BLACK)) == 0

    return both_developed and (rooks_passed or queens_traded)

def load_opening_books(folder_name='openings'):


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

    

# ==========================================
# EXTRACTOR CLASS
# ==========================================

class GameStateExtractor:
    """
    Extracts Game Type and Board State Features.
    Global/color-agnostic features are mapped to single values.
    Player-specific features (like material) are mapped to {"white": val, "black": val}.
    """
    def __init__(self, fen: str, user_side: str = 'w', opening_book: dict = None):
        self.board = chess.Board(fen)
        self.user_side = user_side
        if opening_book == None:
            self.opening_book = load_opening_books()
        else:
            self.opening_book = opening_book
        
        # Initialize flat, logically grouped schema
        self.features = {
            "tempo": "white" if self.board.turn == chess.WHITE else "black",
            "opening_name": "Unknown Opening",
            "opening_eco": "Unknown",
            "game_phase": "Opening",
            "endgame_type": "-",
            "is_endgame_ocb": False,
            "has_queens": False,
            "center_openness": "semi_open",
            "opposite_castling": False,
            "kaufman_material": {"white": 0.0, "black": 0.0}
        }

    def extract_all(self) -> dict:
        # 1. Opening Lookup (Global)
        if self.opening_book:
            op_info = get_opening_from_fen(self.board.fen(), self.opening_book)
            self.features["opening_name"] = op_info.get("name", "Unknown Opening")
            self.features["opening_eco"] = op_info.get("eco", "Unknown")

        # 2. Material Calculation (Player-Specific)
        w_mat, b_mat = get_kaufman_material(self.board.fen())
        self.features["kaufman_material"] = {"white": w_mat, "black": b_mat}

        # 3. Phase Logic (Global)
        is_fen_endgame = is_endgame(self.board.fen(), self.user_side)
        
        if is_fen_endgame['is_endgame']:
            self.features["game_phase"] = "Endgame"
            self.features["endgame_type"] = is_fen_endgame['type']
            
            # Opposite Colored Bishops (OCB) Detection
            w_bishops = list(self.board.pieces(chess.BISHOP, chess.WHITE))
            b_bishops = list(self.board.pieces(chess.BISHOP, chess.BLACK))
            non_pawn_piece_count = sum(len(self.board.pieces(pt, c)) for pt in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN] for c in [chess.WHITE, chess.BLACK])
            
            if len(w_bishops) == 1 and len(b_bishops) == 1:
                w_sq, b_sq = w_bishops[0], b_bishops[0]
                w_is_light = (chess.square_file(w_sq) + chess.square_rank(w_sq)) % 2 != 0
                b_is_light = (chess.square_file(b_sq) + chess.square_rank(b_sq)) % 2 != 0
                
                if w_is_light != b_is_light and non_pawn_piece_count == 2:
                    self.features["is_endgame_ocb"] = True
        else:
            if is_not_opening(self.board.fen()):
                self.features["game_phase"] = "Midgame"

        # Queens Presence (Global)
        w_queens = len(self.board.pieces(chess.QUEEN, chess.WHITE))
        b_queens = len(self.board.pieces(chess.QUEEN, chess.BLACK))
        self.features["has_queens"] = (w_queens > 0 and b_queens > 0)

        # 4. Openness (Global)
        pawn_count = len(self.board.pieces(chess.PAWN, chess.WHITE)) + len(self.board.pieces(chess.PAWN, chess.BLACK))
        if pawn_count < 8:
            self.features["center_openness"] = "open"
        elif pawn_count > 12:
            self.features["center_openness"] = "closed"
        else:
            self.features["center_openness"] = "semi_open"

        # 5. Castling Scenario (Global)
        wk = self.board.king(chess.WHITE)
        bk = self.board.king(chess.BLACK)
        if wk and bk:
            w_kingside = chess.square_file(wk) >= 5
            w_queenside = chess.square_file(wk) <= 2
            b_kingside = chess.square_file(bk) >= 5
            b_queenside = chess.square_file(bk) <= 2
            
            if (w_kingside and b_queenside) or (w_queenside and b_kingside):
                self.features["opposite_castling"] = True

        return self.features