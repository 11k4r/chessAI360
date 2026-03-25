import chess

class CoordinationExtractor:
    """
    Extracts Coordination and Harmony metrics.
    Identifies piece protection networks, overloaded defenders, and bad bishops.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        
        self.features = {
            "defended_pieces": {"white": 0, "black": 0},
            "overloaded_pieces": {"white": 0, "black": 0},
            "bad_bishops": {"white": 0, "black": 0}
        }

    def extract_all(self) -> dict:
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            
            # 1. Defended Pieces & 2. Overloaded Defenders
            defender_map = {}
            defended_count = 0
            
            for sq in chess.SQUARES:
                piece = self.board.piece_at(sq)
                if piece and piece.color == color:
                    # Check if the piece is defended by its own color
                    defenders = self.board.attackers(color, sq)
                    if len(defenders) > 0:
                        defended_count += 1
                        
                    # If the piece is currently under attack by the enemy, map its defenders
                    attackers = self.board.attackers(enemy_color, sq)
                    if len(attackers) > 0:
                        for d_sq in defenders:
                            if d_sq not in defender_map:
                                defender_map[d_sq] = []
                            defender_map[d_sq].append(sq)
                            
            self.features["defended_pieces"][color_key] = defended_count
            
            # An overloaded piece defends 2 or more pieces that are simultaneously under attack
            overloaded_count = sum(1 for d_sq, protected_squares in defender_map.items() if len(protected_squares) > 1)
            self.features["overloaded_pieces"][color_key] = overloaded_count

            # 3. Bad Bishops (Bishop blocked by >= 4 friendly pawns on the same color complex)
            bishops = self.board.pieces(chess.BISHOP, color)
            pawns = self.board.pieces(chess.PAWN, color)
            
            pawn_light_count = sum(1 for p_sq in pawns if (chess.square_file(p_sq) + chess.square_rank(p_sq)) % 2 != 0)
            pawn_dark_count = len(pawns) - pawn_light_count
            
            for b_sq in bishops:
                is_light = (chess.square_file(b_sq) + chess.square_rank(b_sq)) % 2 != 0
                if is_light and pawn_light_count >= 4:
                    self.features["bad_bishops"][color_key] += 1
                elif not is_light and pawn_dark_count >= 4:
                    self.features["bad_bishops"][color_key] += 1

        return self.features