import chess

class TacticsExtractor:
    """
    Extracts Tactical features and Threats.
    Finds pins, hanging pieces, and center control.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        
        # Initialize flattened features schema
        self.features = {
            "pinned_pieces": {"white": 0, "black": 0},
            "hanging_pieces": {"white": 0, "black": 0},
            "center_control": {"white": 0, "black": 0},
            "space_advantage": {"white": 0, "black": 0}
        }
        self.center_squares = [chess.D4, chess.E4, chess.D5, chess.E5]

    def extract_all(self) -> dict:
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            
            # Pins (Pieces of 'color' that are pinned to their King)
            pinned_count = 0
            for sq in chess.SQUARES:
                piece = self.board.piece_at(sq)
                if piece and piece.color == color:
                    # check if the piece at this square is pinned to the king
                    if self.board.is_pinned(color, sq):
                        pinned_count += 1
            self.features["pinned_pieces"][color_key] = pinned_count

            # Hanging Pieces & Space
            space_count = 0
            for sq in chess.SQUARES:
                piece = self.board.piece_at(sq)
                attackers = self.board.attackers(enemy_color, sq)
                defenders = self.board.attackers(color, sq)
                
                # Space: Attacks on enemy half of the board
                if len(defenders) > 0:
                    rank = chess.square_rank(sq)
                    if (color == chess.WHITE and rank >= 4) or (color == chess.BLACK and rank <= 3):
                        space_count += 1
                        
                # Center Control
                if sq in self.center_squares and len(defenders) > 0:
                    self.features["center_control"][color_key] += 1

                # Hanging piece logic (if occupied by my piece, attacked by enemy, and undefended/outnumbered)
                if piece and piece.color == color:
                    if len(attackers) > len(defenders):
                        self.features["hanging_pieces"][color_key] += 1

            self.features["space_advantage"][color_key] = space_count

        return self.features