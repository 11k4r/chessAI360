import chess

class PSTExtractor:
    """
    Extracts Piece-Square Table Features (Section 2.2).
    Tracks the exact squares occupied by specific piece types for both players.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        self.piece_map = {
            chess.PAWN: "pst_pawns",
            chess.KNIGHT: "pst_knights",
            chess.BISHOP: "pst_bishops",
            chess.ROOK: "pst_rooks",
            chess.QUEEN: "pst_queens",
            chess.KING: "pst_kings"
        }
        
        # Initialize flattened features schema
        self.features = {}
        for feature_name in self.piece_map.values():
            self.features[feature_name] = {"white": [], "black": []}

    def extract_all(self) -> dict:
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece:
                color_key = "white" if piece.color == chess.WHITE else "black"
                piece_category = self.piece_map[piece.piece_type]
                sq_name = chess.square_name(sq)
                
                # Exclude ranks 1 and 8 for pawns as per 2.2.1
                if piece.piece_type == chess.PAWN and (chess.square_rank(sq) == 0 or chess.square_rank(sq) == 7):
                    continue
                    
                self.features[piece_category][color_key].append(sq_name)
                
        return self.features