import chess

class KingSafetyExtractor:
    """
    Extracts King Safety Features (Section 2.4).
    Evaluates pawn shields, king mobility, and attacking pressure.
    Returns a flat dictionary mapping each feature to white and black values.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        
        # Initialize flattened features schema
        self.features = {
            "king_sq": {"white": None, "black": None},
            "shield_rank_2": {"white": [], "black": []},
            "shield_rank_3": {"white": [], "black": []},
            "shield_attack": {"white": [], "black": []},
            "shield_ram": {"white": [], "black": []},
            "shelter_count": {"white": 0, "black": 0},
            "virtual_mobility": {"white": 0, "black": 0},
            "back_rank": {"white": False, "black": False},
            "open_file": {"white": False, "black": False},
            "semi_open_file": {"white": False, "black": False},
            "fianchetto_holes": {"white": [], "black": []},
            "zone_squares": {"white": [], "black": []},
            "attackers_count": {"white": 0, "black": 0},
            "defenders_count": {"white": 0, "black": 0}
        }

    def extract_all(self) -> dict:
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            king_sq = self.board.king(color)
            
            if king_sq is None:
                continue

            self.features["king_sq"][color_key] = chess.square_name(king_sq)

            kf = chess.square_file(king_sq)
            kr = chess.square_rank(king_sq)
            home_rank = 0 if color == chess.WHITE else 7
            forward = 1 if color == chess.WHITE else -1

            # Environment
            if kr == home_rank:
                self.features["back_rank"][color_key] = True

            friendly_pawns_on_file = sum(1 for r in range(8) if self._has_piece(kf, r, chess.PAWN, color))
            enemy_pawns_on_file = sum(1 for r in range(8) if self._has_piece(kf, r, chess.PAWN, enemy_color))
            
            if friendly_pawns_on_file == 0 and enemy_pawns_on_file == 0:
                self.features["open_file"][color_key] = True
            elif friendly_pawns_on_file == 0:
                self.features["semi_open_file"][color_key] = True

            # --- Pawn Shield ---
            # Evaluated regardless of King rank, based on the files immediately around the King
            shield_files = [f for f in [kf-1, kf, kf+1] if 0 <= f <= 7]
            for f in shield_files:
                # Rank 2 Shield
                sq_r2 = chess.square(f, home_rank + forward)
                if self._has_piece(f, home_rank + forward, chess.PAWN, color):
                    sq_name = chess.square_name(sq_r2)
                    self.features["shield_rank_2"][color_key].append(sq_name)
                    
                    if self.board.is_attacked_by(enemy_color, sq_r2):
                        self.features["shield_attack"][color_key].append(sq_name)
                    if self._has_piece(f, home_rank + (2 * forward), chess.PAWN, enemy_color):
                        self.features["shield_ram"][color_key].append(sq_name)

                # Rank 3 Shield
                sq_r3 = chess.square(f, home_rank + (2 * forward))
                if self._has_piece(f, home_rank + (2 * forward), chess.PAWN, color):
                    sq_name = chess.square_name(sq_r3)
                    self.features["shield_rank_3"][color_key].append(sq_name)
                    
                    if self.board.is_attacked_by(enemy_color, sq_r3):
                        self.features["shield_attack"][color_key].append(sq_name)
                    if self._has_piece(f, home_rank + (3 * forward), chess.PAWN, enemy_color):
                        self.features["shield_ram"][color_key].append(sq_name)

            # --- Virtual Mobility (King as a Queen) ---
            vm_count = 0
            directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
            for df, dr in directions:
                ray_f, ray_r = kf + df, kr + dr
                while 0 <= ray_f <= 7 and 0 <= ray_r <= 7:
                    target_sq = chess.square(ray_f, ray_r)
                    piece = self.board.piece_at(target_sq)
                    if piece:
                        if piece.color == enemy_color:
                            vm_count += 1 # Count capturing an enemy piece as mobility
                        break  # Stop if blocked by ANY piece
                    vm_count += 1 # Empty square
                    ray_f += df
                    ray_r += dr
            self.features["virtual_mobility"][color_key] = vm_count

            # --- Structural Weaknesses ---
            # Queenside = file 1 ('b'), Kingside = file 6 ('g')
            for flank_name, flank_file in [("queenside", 1), ("kingside", 6)]:
                pawn_on_start = self._has_piece(flank_file, home_rank + forward, chess.PAWN, color)
                has_pawn_on_file = any(self._has_piece(flank_file, r, chess.PAWN, color) for r in range(8))
                
                pawn_advanced = has_pawn_on_file and not pawn_on_start
                bishop_present = self._has_piece(flank_file, home_rank + forward, chess.BISHOP, color)
                
                if pawn_advanced and not bishop_present:
                    self.features["fianchetto_holes"][color_key].append(flank_name)

            # --- Zone Pressure & Shelter ---
            adj_squares = [
                chess.square(f, r) for f in [kf-1, kf, kf+1] for r in [kr-1, kr, kr+1]
                if 0 <= f <= 7 and 0 <= r <= 7 and not (f == kf and r == kr)
            ]
            
            zone_sq_names = [chess.square_name(sq) for sq in adj_squares]
            self.features["zone_squares"][color_key] = zone_sq_names

            shelter = sum(1 for sq in adj_squares if self.board.piece_at(sq) and self.board.piece_at(sq).color == color)
            self.features["shelter_count"][color_key] = shelter

            attackers = set()
            defenders = set()
            for sq in adj_squares:
                attackers.update(self.board.attackers(enemy_color, sq))
                defenders.update(self.board.attackers(color, sq))
            
            self.features["attackers_count"][color_key] = len(attackers)
            self.features["defenders_count"][color_key] = len(defenders)

        return self.features

    def calculate_safety_score(self) -> dict:
        """ Calculates a simple centipawn score and returns the bundle. """
        features = self.extract_all()
        scores = {"white": 0, "black": 0}

        for color in ["white", "black"]:
            if features["king_sq"][color] is None:
                continue

            score = 0
            
            # Bonuses
            score += len(features["shield_rank_2"][color]) * 10
            score += len(features["shield_rank_3"][color]) * 5
            score += features["shelter_count"][color] * 5
            
            # Penalties
            if features["open_file"][color]:
                score -= 30
            elif features["semi_open_file"][color]:
                score -= 15
                
            score -= features["attackers_count"][color] * 10
            
            scores[color] = score

        return {
            "white_score": scores["white"],
            "black_score": scores["black"],
            "relative_eval_cp": scores["white"] - scores["black"],
            "features": features
        }

    def _has_piece(self, f: int, r: int, p_type: int, color: bool) -> bool:
        if 0 <= f <= 7 and 0 <= r <= 7:
            p = self.board.piece_at(chess.square(f, r))
            return bool(p and p.piece_type == p_type and p.color == color)
        return False