import chess

class AdvancedPieceExtractor:
    """
    Extracts advanced positional piece features (Outposts, 7th Rank, etc.).
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        
        # Initialize flattened features schema
        self.features = {
            "knight_outposts": {"white": 0, "black": 0},
            "rook_on_7th": {"white": 0, "black": 0},
            "rook_open_file": {"white": 0, "black": 0},
            "rook_semi_open_file": {"white": 0, "black": 0},
            "bishop_long_diagonal": {"white": 0, "black": 0}
        }

    def extract_all(self) -> dict:
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            seventh_rank = 6 if color == chess.WHITE else 1
            
            # Knights on Outposts (protected by pawn, central rank)
            knights = self.board.pieces(chess.KNIGHT, color)
            for sq in knights:
                rank = chess.square_rank(sq)
                if (color == chess.WHITE and 3 <= rank <= 5) or (color == chess.BLACK and 2 <= rank <= 4):
                    defenders = self.board.attackers(color, sq)
                    if any(self.board.piece_at(d) and self.board.piece_at(d).piece_type == chess.PAWN for d in defenders):
                        self.features["knight_outposts"][color_key] += 1

            # Rooks
            rooks = self.board.pieces(chess.ROOK, color)
            for sq in rooks:
                if chess.square_rank(sq) == seventh_rank:
                    self.features["rook_on_7th"][color_key] += 1
                    
                f = chess.square_file(sq)
                friendly_pawns = sum(1 for r in range(8) if self._is_pawn(f, r, color))
                enemy_pawns = sum(1 for r in range(8) if self._is_pawn(f, r, enemy_color))
                
                if friendly_pawns == 0 and enemy_pawns == 0:
                    self.features["rook_open_file"][color_key] += 1
                elif friendly_pawns == 0 and enemy_pawns > 0:
                    self.features["rook_semi_open_file"][color_key] += 1

            # Bishops on Long Diagonals (a1-h8 or h1-a8)
            long_diagonals = [
                chess.A1, chess.B2, chess.C3, chess.D4, chess.E5, chess.F6, chess.G7, chess.H8,
                chess.H1, chess.G2, chess.F3, chess.E4, chess.D5, chess.C6, chess.B7, chess.A8
            ]
            bishops = self.board.pieces(chess.BISHOP, color)
            for sq in bishops:
                if sq in long_diagonals:
                    self.features["bishop_long_diagonal"][color_key] += 1

        return self.features

    def _is_pawn(self, f: int, r: int, color: bool) -> bool:
        if 0 <= f <= 7 and 0 <= r <= 7:
            p = self.board.piece_at(chess.square(f, r))
            return bool(p and p.piece_type == chess.PAWN and p.color == color)
        return False