import chess

class BatteryExtractor:
    """
    Extracts Battery Features.
    Identifies doubled rooks, rook/queen batteries, and bishop/queen batteries.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        self.features = {
            "white": self._create_player_template(),
            "black": self._create_player_template()
        }

    def _create_player_template(self) -> dict:
        return {
            "rook_battery": 0,    # Rooks/Queens on the same file
            "diagonal_battery": 0 # Bishops/Queens on the same diagonal
        }

    def extract_all(self) -> dict:
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            
            rooks = list(self.board.pieces(chess.ROOK, color))
            bishops = list(self.board.pieces(chess.BISHOP, color))
            queens = list(self.board.pieces(chess.QUEEN, color))
            
            # File Batteries (Rook + Rook or Rook + Queen)
            straight_sliders = rooks + queens
            file_counts = {}
            for sq in straight_sliders:
                f = chess.square_file(sq)
                file_counts[f] = file_counts.get(f, 0) + 1
            
            for f, count in file_counts.items():
                if count >= 2:
                    self.features[color_key]["rook_battery"] += 1

            # Diagonal Batteries (Bishop + Queen)
            diagonal_sliders = bishops + queens
            if len(bishops) > 0 and len(queens) > 0:
                for b_sq in bishops:
                    for q_sq in queens:
                        # Check if they share a diagonal (difference in rank == difference in file)
                        if abs(chess.square_rank(b_sq) - chess.square_rank(q_sq)) == abs(chess.square_file(b_sq) - chess.square_file(q_sq)):
                            # Simplified check: assumes no blocking friendly pieces in between for the feature flag
                            self.features[color_key]["diagonal_battery"] += 1

        return self.features