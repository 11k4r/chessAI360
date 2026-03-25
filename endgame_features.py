import chess

class EndgameExtractor:
    """
    Extracts Endgame-specific spatial and tactical features.
    Evaluates King centralization, opposition, and blockaders.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        
        self.features = {
            "king_centralization": {"white": 0, "black": 0},
            "opposition": {"white": False, "black": False},
            "knight_blockaders": {"white": 0, "black": 0}
        }

    def extract_all(self) -> dict:
        wk = self.board.king(chess.WHITE)
        bk = self.board.king(chess.BLACK)

        # 1. King Centralization (Chebyshev distance to the 4 central squares)
        def get_center_dist(sq):
            if sq is None: return 0
            f, r = chess.square_file(sq), chess.square_rank(sq)
            dx = 0 if f in [3, 4] else min(abs(f - 3), abs(f - 4))
            dy = 0 if r in [3, 4] else min(abs(r - 3), abs(r - 4))
            return max(dx, dy)

        self.features["king_centralization"]["white"] = get_center_dist(wk)
        self.features["king_centralization"]["black"] = get_center_dist(bk)

        # 2. Opposition (Simplified: Same file or rank, odd squares apart, no pieces between)
        if wk is not None and bk is not None:
            wf, wr = chess.square_file(wk), chess.square_rank(wk)
            bf, br = chess.square_file(bk), chess.square_rank(bk)
            
            if wf == bf and abs(wr - br) % 2 == 0: # Note: absolute diff of ranks is even means 1, 3, 5 empty squares between
                empty_between = all(self.board.piece_at(chess.square(wf, r)) is None for r in range(min(wr, br) + 1, max(wr, br)))
                if empty_between:
                    # The player whose turn it is NOT has the opposition
                    if self.board.turn == chess.WHITE:
                        self.features["opposition"]["black"] = True
                    else:
                        self.features["opposition"]["white"] = True
                        
            elif wr == br and abs(wf - bf) % 2 == 0:
                empty_between = all(self.board.piece_at(chess.square(f, wr)) is None for f in range(min(wf, bf) + 1, max(wf, bf)))
                if empty_between:
                    if self.board.turn == chess.WHITE:
                        self.features["opposition"]["black"] = True
                    else:
                        self.features["opposition"]["white"] = True

        # 3. Knight Blockaders (Enemy Knights immediately in front of my pawns)
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            forward = 1 if color == chess.WHITE else -1
            
            pawns = self.board.pieces(chess.PAWN, color)
            for sq in pawns:
                f, r = chess.square_file(sq), chess.square_rank(sq)
                block_sq = chess.square(f, r + forward)
                if 0 <= r + forward <= 7:
                    piece = self.board.piece_at(block_sq)
                    if piece and piece.color == enemy_color and piece.piece_type == chess.KNIGHT:
                        self.features["knight_blockaders"][color_key] += 1

        return self.features