import chess

class MaterialExtractor:
    """
    Extracts all Material Features (Section 2.1) from a given FEN.
    Returns a flat dictionary mapping each feature to its values for white and black.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        self.features = {}
        
        # Define the flattened feature schema
        int_features = [
            "pawn_a", "pawn_b", "pawn_c", "pawn_d", 
            "pawn_e", "pawn_f", "pawn_g", "pawn_h"
        ]
        bool_features = [
            "N1", "N2", "bishop_light", "bishop_dark", "R1", "R2", "queen",
            "bishop_pair", "knight_pair", "rook_pair", "no_pawns",
            "Qv3M", "Qv2R", "Rv2M", "BvN"
        ]
        
        for f in int_features:
            self.features[f] = {"white": 0, "black": 0}
        for f in bool_features:
            self.features[f] = {"white": False, "black": False}

    def extract_all(self) -> dict:
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            
            # --- Pawns ---
            pawns = self.board.pieces(chess.PAWN, color)
            for sq in pawns:
                file_char = chess.square_name(sq)[0]
                # FIX B: Incrementing count to correctly capture doubled/tripled pawns
                self.features[f"pawn_{file_char}"][color_key] += 1
                
            if len(pawns) == 0:
                self.features["no_pawns"][color_key] = True

            # --- Knights ---
            knights = self.board.pieces(chess.KNIGHT, color)
            k_count = len(knights)
            if k_count >= 1: self.features["N1"][color_key] = True
            if k_count >= 2: 
                self.features["N2"][color_key] = True
                self.features["knight_pair"][color_key] = True

            # --- Bishops ---
            bishops = self.board.pieces(chess.BISHOP, color)
            for sq in bishops:
                # (file + rank) % 2 != 0 means it's a light square
                is_light_square = (chess.square_file(sq) + chess.square_rank(sq)) % 2 != 0
                if is_light_square:
                    self.features["bishop_light"][color_key] = True
                else:
                    self.features["bishop_dark"][color_key] = True
                    
            if self.features["bishop_light"][color_key] and self.features["bishop_dark"][color_key]:
                self.features["bishop_pair"][color_key] = True

            # --- Rooks ---
            rooks = self.board.pieces(chess.ROOK, color)
            r_count = len(rooks)
            if r_count >= 1: self.features["R1"][color_key] = True
            if r_count >= 2: 
                self.features["R2"][color_key] = True
                self.features["rook_pair"][color_key] = True

            # --- Queen ---
            queens = self.board.pieces(chess.QUEEN, color)
            q_count = len(queens)
            if q_count > 0:
                self.features["queen"][color_key] = True

            # --- Imbalances ---
            enemy_knights = self.board.pieces(chess.KNIGHT, enemy_color)
            enemy_bishops = self.board.pieces(chess.BISHOP, enemy_color)
            enemy_minors = len(enemy_knights) + len(enemy_bishops)
            
            enemy_rooks = len(self.board.pieces(chess.ROOK, enemy_color))
            enemy_queens = len(self.board.pieces(chess.QUEEN, enemy_color))
            
            # FIX A: Added mutual exclusivity checks (e.g., enemy_queens == 0)
            if q_count > 0 and enemy_queens == 0 and enemy_minors >= 3:
                self.features["Qv3M"][color_key] = True
                
            if q_count > 0 and enemy_queens == 0 and enemy_rooks >= 2:
                self.features["Qv2R"][color_key] = True
                
            if r_count > 0 and enemy_rooks == 0 and enemy_minors >= 2:
                self.features["Rv2M"][color_key] = True
                
            if len(bishops) >= 1 and len(enemy_knights) >= 1 and k_count == 0 and len(enemy_bishops) == 0:
                self.features["BvN"][color_key] = True

        return self.features
