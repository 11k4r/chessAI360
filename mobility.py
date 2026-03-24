import chess

class MobilityExtractor:
    """
    Extracts Piece Mobility Features.
    Calculates pseudo-legal safe moves and identifies trapped pieces.
    Provides granular metrics (sum, max, min) for identical pieces (Knights, Rooks, Queens)
    and explicitly separates Bishop mobility by square color.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        
        # Initialize flattened features schema
        self.features = {
            "knight_mobility_sum": {"white": 0, "black": 0},
            "knight_mobility_max": {"white": 0, "black": 0},
            "knight_mobility_min": {"white": 0, "black": 0},
            
            "bishop_light_mobility": {"white": 0, "black": 0},
            "bishop_dark_mobility": {"white": 0, "black": 0},
            
            "rook_mobility_sum": {"white": 0, "black": 0},
            "rook_mobility_max": {"white": 0, "black": 0},
            "rook_mobility_min": {"white": 0, "black": 0},
            
            "queen_mobility_sum": {"white": 0, "black": 0},
            "queen_mobility_max": {"white": 0, "black": 0},
            "queen_mobility_min": {"white": 0, "black": 0},
            
            "trapped_pieces": {"white": 0, "black": 0}
        }

    def extract_all(self) -> dict:
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            
            # Identify squares attacked by enemy pawns (unsafe squares)
            enemy_pawn_attacks = set()
            for sq in self.board.pieces(chess.PAWN, enemy_color):
                enemy_pawn_attacks.update(self.board.attacks(sq))
            
            # Temporary storage to hold the mobilities of individual pieces before aggregating
            mobs = {
                chess.KNIGHT: [],
                chess.ROOK: [],
                chess.QUEEN: []
            }
            bishop_light_mobs = []
            bishop_dark_mobs = []
            
            trapped_count = 0

            for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
                pieces = self.board.pieces(piece_type, color)
                
                for sq in pieces:
                    attacks = self.board.attacks(sq)
                    safe_moves = 0
                    
                    for target_sq in attacks:
                        target_piece = self.board.piece_at(target_sq)
                        
                        # Move is invalid if blocked by own piece or attacked by enemy pawn
                        if (target_piece and target_piece.color == color) or (target_sq in enemy_pawn_attacks):
                            continue 
                            
                        safe_moves += 1
                    
                    # Store mobility into the correct temporary bucket
                    if piece_type == chess.BISHOP:
                        is_light_square = (chess.square_file(sq) + chess.square_rank(sq)) % 2 != 0
                        if is_light_square:
                            bishop_light_mobs.append(safe_moves)
                        else:
                            bishop_dark_mobs.append(safe_moves)
                    else:
                        mobs[piece_type].append(safe_moves)
                        
                    # Trapped piece penalty (only evaluating minors: Knights and Bishops)
                    if safe_moves == 0 and piece_type in [chess.KNIGHT, chess.BISHOP]:
                        trapped_count += 1

            # --- Map the collected data to the final flattened schema ---
            
            self.features["trapped_pieces"][color_key] = trapped_count
            
            # Bishops (Using 'sum' gracefully handles the rare case of promoting to a 2nd bishop of the same color)
            self.features["bishop_light_mobility"][color_key] = sum(bishop_light_mobs)
            self.features["bishop_dark_mobility"][color_key] = sum(bishop_dark_mobs)
            
            # Knights, Rooks, Queens (Sum, Max, Min)
            piece_map = {
                chess.KNIGHT: "knight",
                chess.ROOK: "rook",
                chess.QUEEN: "queen"
            }
            
            for pt, name in piece_map.items():
                p_mobs = mobs[pt]
                # If a piece type doesn't exist (e.g. they lost their Queen), default to 0
                self.features[f"{name}_mobility_sum"][color_key] = sum(p_mobs) if p_mobs else 0
                self.features[f"{name}_mobility_max"][color_key] = max(p_mobs) if p_mobs else 0
                self.features[f"{name}_mobility_min"][color_key] = min(p_mobs) if p_mobs else 0

        return self.features