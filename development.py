import chess

class DevelopmentExtractor:
    """
    Extracts Opening and Development features.
    Measures lead in development and precise pawn center control.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        
        self.features = {
            "undeveloped_minors": {"white": 0, "black": 0},
            "pawn_center": {"white": 0, "black": 0},
            "extended_pawn_center": {"white": 0, "black": 0}
        }
        
        self.sweet_center = [chess.D4, chess.E4, chess.D5, chess.E5]
        self.extended_center = [chess.C4, chess.F4, chess.C5, chess.F5]

    def extract_all(self) -> dict:
        # 1. Undeveloped Minors
        white_home = [(chess.B1, chess.KNIGHT), (chess.G1, chess.KNIGHT), (chess.C1, chess.BISHOP), (chess.F1, chess.BISHOP)]
        black_home = [(chess.B8, chess.KNIGHT), (chess.G8, chess.KNIGHT), (chess.C8, chess.BISHOP), (chess.F8, chess.BISHOP)]
        
        for sq, pt in white_home:
            piece = self.board.piece_at(sq)
            if piece and piece.color == chess.WHITE and piece.piece_type == pt:
                self.features["undeveloped_minors"]["white"] += 1
                
        for sq, pt in black_home:
            piece = self.board.piece_at(sq)
            if piece and piece.color == chess.BLACK and piece.piece_type == pt:
                self.features["undeveloped_minors"]["black"] += 1

        # 2. Pawn Center Control
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            pawns = self.board.pieces(chess.PAWN, color)
            
            for sq in pawns:
                if sq in self.sweet_center:
                    self.features["pawn_center"][color_key] += 1
                elif sq in self.extended_center:
                    self.features["extended_pawn_center"][color_key] += 1

        return self.features