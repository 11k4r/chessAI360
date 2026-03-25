import chess
import json

class PawnStructureExtractor:
    """
    Extracts all Pawn Structure Features (Section 2.3) from a given FEN.
    Returns a flat dictionary mapping each feature to its values for white and black.
    """
    def __init__(self, fen: str):
        self.board = chess.Board(fen)
        self.files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        self.adj_files = [f"{self.files[i]}{self.files[i+1]}" for i in range(7)]
        
        # Initialize flattened features schema
        self.features = {}
        
        # Define expected data types for initialization
        list_features = [
            "isolated", "doubled", "backward", "weak_chain_base", "overextended", 
            "backward_on_open_file", "ram", "lever", "self_blocked",
            "passed_pawn", "protected_passer", "unstoppable_passer", 
            "connected_passers", "candidate_passer",
            "connected_pawns", "phalanx", "chain_set_right", "chain_set_left", 
            "pawn_island_shapes", "majority", "crippled_majority"
        ]
        bool_features = [
            "race_advantage", "tarrasch_compliance", "king_in_square", 
            "king_support", "king_blocking_proximity", "both_wings", 
            "one_wing", "en_passant"
        ]
        int_features = ["pawn_chain_count", "pawn_island_count"]
        
        for f in list_features:
            self.features[f] = {"white": [], "black": []}
        for f in bool_features:
            self.features[f] = {"white": False, "black": False}
        for f in int_features:
            self.features[f] = {"white": 0, "black": 0}


    def extract_all(self) -> dict:
        """Main execution method to extract and return all features."""
        self._extract_base_and_passed()
        self._extract_connectivity_and_complex()
        self._extract_wings_and_dynamic()
        self.features["is_gonna_promote_first"] = self._calculate_promotion_race()
        
        return self.features

    # --- Helper Methods ---
    def _has_pawn(self, f: int, r: int, color: bool) -> bool:
        if 0 <= f <= 7 and 0 <= r <= 7:
            p = self.board.piece_at(chess.square(f, r))
            return bool(p and p.piece_type == chess.PAWN and p.color == color)
        return False

    def _has_piece(self, f: int, r: int, color: bool) -> bool:
        if 0 <= f <= 7 and 0 <= r <= 7:
            p = self.board.piece_at(chess.square(f, r))
            return bool(p and p.color == color)
        return False

    def _get_pawn_files(self, color: bool) -> set:
        return {chess.square_file(sq) for sq in self.board.pieces(chess.PAWN, color)}

    def _chebyshev_dist(self, sq1: chess.Square, sq2: chess.Square) -> int:
        return max(abs(chess.square_file(sq1) - chess.square_file(sq2)), 
                   abs(chess.square_rank(sq1) - chess.square_rank(sq2)))

    # --- Feature Extraction Methods ---
    def _extract_base_and_passed(self):
        passed_pawns_cache = {chess.WHITE: [], chess.BLACK: []}
        min_prom_dist = {chess.WHITE: float('inf'), chess.BLACK: float('inf')}

        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if not piece or piece.piece_type != chess.PAWN:
                continue
                
            color = piece.color
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            sq_name = chess.square_name(sq)
            
            f = chess.square_file(sq)
            r = chess.square_rank(sq)
            
            forward_dir = 1 if color == chess.WHITE else -1
            prom_r = 7 if color == chess.WHITE else 0
            prom_sq = chess.square(f, prom_r)
            rel_rank = r + 1 if color == chess.WHITE else 8 - r
            
            adj_files = [af for af in [f - 1, f + 1] if 0 <= af <= 7]
            
            friendly_pawns_on_file = sum(1 for rank in range(8) if self._has_pawn(f, rank, color))
            enemy_pawns_on_file = sum(1 for rank in range(8) if self._has_pawn(f, rank, enemy_color))

            # --- File-Based Features ---
            is_isolated = True
            for af in adj_files:
                if any(self._has_pawn(af, rank, color) for rank in range(8)):
                    is_isolated = False
                    break
            if is_isolated:
                self.features["isolated"][color_key].append(sq_name)
                
            if friendly_pawns_on_file >= 2:
                self.features["doubled"][color_key].append(sq_name)

            is_supported = any(self._has_pawn(af, r - forward_dir, color) for af in adj_files)
            supports_another = any(self._has_pawn(af, r + forward_dir, color) for af in adj_files)
            attacks_enemy = any(self._has_pawn(af, r + forward_dir, enemy_color) for af in adj_files)

            is_rearmost = True
            for rank in range(8):
                if self._has_pawn(f, rank, color):
                    if (color == chess.WHITE and rank < r) or (color == chess.BLACK and rank > r):
                        is_rearmost = False
                        break
            
            has_adj_support_potential = False
            for af in adj_files:
                for rank in range(8):
                    if self._has_pawn(af, rank, color):
                        if (color == chess.WHITE and rank < r) or (color == chess.BLACK and rank > r):
                            has_adj_support_potential = True
                            
            is_backward = is_rearmost and not has_adj_support_potential
            if is_backward:
                self.features["backward"][color_key].append(sq_name)
                
                no_other_friendly_pawns = (friendly_pawns_on_file == 1)
                file_is_semi_open = (enemy_pawns_on_file == 0)
                
                if no_other_friendly_pawns and file_is_semi_open:
                    self.features["backward_on_open_file"][color_key].append(sq_name)

            if supports_another and not is_supported:
                self.features["weak_chain_base"][color_key].append(sq_name)
            if rel_rank >= 5 and not is_supported:
                self.features["overextended"][color_key].append(sq_name)
            if self._has_pawn(f, r + forward_dir, enemy_color):
                self.features["ram"][color_key].append(sq_name)
            if attacks_enemy:
                self.features["lever"][color_key].append(sq_name)
            if self._has_piece(f, r + forward_dir, color):
                self.features["self_blocked"][color_key].append(sq_name)

            # --- Passed Pawn Features ---
            is_passed = True
            check_ranks = range(r + forward_dir, 8) if color == chess.WHITE else range(r + forward_dir, -1, -1)
            
            for check_r in check_ranks:
                if self._has_pawn(f, check_r, enemy_color) or \
                   self._has_pawn(f - 1, check_r, enemy_color) or \
                   self._has_pawn(f + 1, check_r, enemy_color):
                    is_passed = False
                    break
                    
            if is_passed:
                self.features["passed_pawn"][color_key].append(sq_name)
                passed_pawns_cache[color].append((f, r, sq_name))
                
                dist_to_prom = abs(prom_r - r)
                min_prom_dist[color] = min(min_prom_dist[color], dist_to_prom)

                if is_supported:
                    self.features["protected_passer"][color_key].append(sq_name)

                enemy_king_sq = self.board.king(enemy_color)
                if enemy_king_sq is not None:
                    enemy_k_dist = self._chebyshev_dist(enemy_king_sq, prom_sq)
                    
                    pawn_moves_req = dist_to_prom
                    if (color == chess.WHITE and r == 1) or (color == chess.BLACK and r == 6):
                        pawn_moves_req -= 1
                    if self.board.turn == color:
                        pawn_moves_req -= 1
                        
                    if pawn_moves_req < enemy_k_dist:
                        self.features["unstoppable_passer"][color_key].append(sq_name)
                        
                friendly_king_sq = self.board.king(color)
                if friendly_king_sq is not None and self._chebyshev_dist(friendly_king_sq, sq) <= 2:
                    self.features["king_support"][color_key] = True

                if enemy_king_sq is not None:
                    path_squares = [chess.square(f, path_r) for path_r in check_ranks]
                    min_path_dist = min((self._chebyshev_dist(enemy_king_sq, p_sq) for p_sq in path_squares), default=float('inf'))
                    if min_path_dist <= 3:
                        self.features["king_blocking_proximity"]["black" if color == chess.WHITE else "white"] = True

                    if self._chebyshev_dist(enemy_king_sq, prom_sq) <= dist_to_prom:
                        self.features["king_in_square"]["black" if color == chess.WHITE else "white"] = True
            else:
                enemy_pawn_ahead = any(self._has_pawn(f, check_r, enemy_color) for check_r in check_ranks)
                if not enemy_pawn_ahead:
                    local_files = [af for af in [f - 1, f, f + 1] if 0 <= af <= 7]
                    friendly_local = sum(1 for af in local_files for rank in range(8) if self._has_pawn(af, rank, color))
                    enemy_local = sum(1 for af in local_files for rank in range(8) if self._has_pawn(af, rank, enemy_color))
                    
                    if friendly_local > enemy_local:
                        self.features["candidate_passer"][color_key].append(sq_name)

        # Global Passed Pawn Pass
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            
            passer_files = {p[0] for p in passed_pawns_cache[color]}
            for f, r, sq_name in passed_pawns_cache[color]:
                if (f - 1) in passer_files or (f + 1) in passer_files:
                    self.features["connected_passers"][color_key].append(sq_name)

            if len(passed_pawns_cache[color]) > 0 and len(passed_pawns_cache[enemy_color]) > 0:
                if min_prom_dist[color] < min_prom_dist[enemy_color]:
                    self.features["race_advantage"][color_key] = True

            for rook_sq in self.board.pieces(chess.ROOK, color):
                rook_f = chess.square_file(rook_sq)
                rook_r = chess.square_rank(rook_sq)
                is_compliant = False
                
                for pf, pr, _ in passed_pawns_cache[color]:
                    if rook_f == pf and ((color == chess.WHITE and rook_r < pr) or (color == chess.BLACK and rook_r > pr)):
                        is_compliant = True
                        break
                        
                if not is_compliant:
                    for pf, pr, _ in passed_pawns_cache[enemy_color]:
                        if rook_f == pf and ((color == chess.WHITE and rook_r < pr) or (color == chess.BLACK and rook_r > pr)):
                            is_compliant = True
                            break
                            
                if is_compliant:
                    self.features["tarrasch_compliance"][color_key] = True
                    break

    def _extract_connectivity_and_complex(self):
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            forward_dir = 1 if color == chess.WHITE else -1
            
            pawn_files = self._get_pawn_files(color)
            pawns_list = list(self.board.pieces(chess.PAWN, color))
            
            for f in range(7):
                adj_name = self.adj_files[f]
                if f in pawn_files and (f + 1) in pawn_files:
                    self.features["connected_pawns"][color_key].append(adj_name)
                    
                for r in range(8):
                    if self._has_pawn(f, r, color) and self._has_pawn(f + 1, r, color):
                        self.features["phalanx"][color_key].append(adj_name)
                        break 
                        
            for sq in pawns_list:
                f = chess.square_file(sq)
                r = chess.square_rank(sq)
                sq_name = chess.square_name(sq)
                
                if self._has_pawn(f + 1, r + forward_dir, color):
                    self.features["chain_set_right"][color_key].append(sq_name)
                if self._has_pawn(f - 1, r + forward_dir, color):
                    self.features["chain_set_left"][color_key].append(sq_name)

            # Calculate precise pawn chain count (integer)
            visited = set()
            num_chains = 0
            
            for sq in pawns_list:
                if sq not in visited:
                    stack = [sq]
                    component_size = 0
                    while stack:
                        curr = stack.pop()
                        if curr not in visited:
                            visited.add(curr)
                            component_size += 1
                            cf = chess.square_file(curr)
                            cr = chess.square_rank(curr)
                            
                            for nsq in pawns_list:
                                if nsq not in visited:
                                    nf = chess.square_file(nsq)
                                    nr = chess.square_rank(nsq)
                                    if abs(cf - nf) == 1 and abs(cr - nr) == 1:
                                        stack.append(nsq)
                    if component_size >= 2:
                        num_chains += 1

            self.features["pawn_chain_count"][color_key] = num_chains

            # Extracting Islands and calculating precise count (integer)
            islands = []
            current_island = []
            for f in range(8):
                if f in pawn_files:
                    current_island.append(self.files[f])
                elif current_island:
                    islands.append("".join(current_island))
                    current_island = []
            if current_island:
                islands.append("".join(current_island))
                
            self.features["pawn_island_shapes"][color_key] = islands
            self.features["pawn_island_count"][color_key] = len(islands)

    def _extract_wings_and_dynamic(self):
        for color in [chess.WHITE, chess.BLACK]:
            color_key = "white" if color == chess.WHITE else "black"
            enemy_color = not color
            
            qs_pawns_own = sum(1 for f in range(0, 3) for r in range(8) if self._has_pawn(f, r, color))
            ks_pawns_own = sum(1 for f in range(5, 8) for r in range(8) if self._has_pawn(f, r, color))
            c_pawns_own = sum(1 for f in range(3, 5) for r in range(8) if self._has_pawn(f, r, color))
            
            qs_pawns_enemy = sum(1 for f in range(0, 3) for r in range(8) if self._has_pawn(f, r, enemy_color))
            ks_pawns_enemy = sum(1 for f in range(5, 8) for r in range(8) if self._has_pawn(f, r, enemy_color))
            c_pawns_enemy = sum(1 for f in range(3, 5) for r in range(8) if self._has_pawn(f, r, enemy_color))

            if qs_pawns_own > 0 and ks_pawns_own > 0:
                self.features["both_wings"][color_key] = True
            elif (qs_pawns_own > 0 and ks_pawns_own == 0) or (qs_pawns_own == 0 and ks_pawns_own > 0):
                self.features["one_wing"][color_key] = True
                
            maj_qs = qs_pawns_own > qs_pawns_enemy
            maj_ks = ks_pawns_own > ks_pawns_enemy
            maj_c = c_pawns_own > c_pawns_enemy

            # Convert to categorized string lists
            if maj_ks: self.features["majority"][color_key].append("kingside")
            if maj_qs: self.features["majority"][color_key].append("queenside")
            if maj_c: self.features["majority"][color_key].append("central")

            # Check Crippled Majority
            doubled_pawns = self.features["doubled"][color_key]
            backward_pawns = self.features["backward"][color_key]
            weak_pawns = doubled_pawns + backward_pawns

            if maj_qs and any(sq[0] in 'abc' for sq in weak_pawns):
                self.features["crippled_majority"][color_key].append("queenside")
            if maj_c and any(sq[0] in 'de' for sq in weak_pawns):
                self.features["crippled_majority"][color_key].append("central")
            if maj_ks and any(sq[0] in 'fgh' for sq in weak_pawns):
                self.features["crippled_majority"][color_key].append("kingside")

            if self.board.has_legal_en_passant() and self.board.turn == color:
                self.features["en_passant"][color_key] = True

            


    def _calculate_promotion_race(self):
        """
        Determines if a side has an unstoppable passed pawn that will promote 
        before the opponent's passed pawns.
        Returns: {"white": 1, "black": 0} or vice versa, or 0s for both.
        """
        def get_passed_pawns(color):
            passed_pawns = []
            pawns = self.board.pieces(chess.PAWN, color)
            enemy_pawns = self.board.pieces(chess.PAWN, not color)
            
            for sq in pawns:
                file_sq = chess.square_file(sq)
                rank_sq = chess.square_rank(sq)
                
                is_passed = True
                for enemy_sq in enemy_pawns:
                    e_file = chess.square_file(enemy_sq)
                    e_rank = chess.square_rank(enemy_sq)
                    # Enemy pawn is in front and on the same or adjacent file
                    if abs(e_file - file_sq) <= 1:
                        if (color == chess.WHITE and e_rank > rank_sq) or \
                           (color == chess.BLACK and e_rank < rank_sq):
                            is_passed = False
                            break
                if is_passed:
                    passed_pawns.append(sq)
            return passed_pawns

        def can_king_catch(pawn_sq, pawn_color):
            pawn_rank = chess.square_rank(pawn_sq)
            pawn_file = chess.square_file(pawn_sq)
            
            enemy_king_sq = self.board.king(not pawn_color)
            if enemy_king_sq is None: 
                return False
                
            king_rank = chess.square_rank(enemy_king_sq)
            king_file = chess.square_file(enemy_king_sq)
            
            # Unmoved pawns can double step, shrinking their distance
            if pawn_color == chess.WHITE and pawn_rank == 1:
                pawn_rank = 2
            elif pawn_color == chess.BLACK and pawn_rank == 6:
                pawn_rank = 5
                
            dist_to_promote = 7 - pawn_rank if pawn_color == chess.WHITE else pawn_rank
            
            # The square distance the king needs to travel
            king_dist_file = abs(king_file - pawn_file)
            king_dist_rank = abs(king_rank - (7 if pawn_color == chess.WHITE else 0))
            king_dist = max(king_dist_file, king_dist_rank)
            
            # If it's the pawn's turn, the pawn shrinks the square before the king moves
            if pawn_color == self.board.turn:
                dist_to_promote -= 1
                
            return king_dist <= dist_to_promote

        w_passed = get_passed_pawns(chess.WHITE)
        b_passed = get_passed_pawns(chess.BLACK)
        
        # Filter out pawns that the enemy king can catch
        w_unstoppable = [sq for sq in w_passed if not can_king_catch(sq, chess.WHITE)]
        b_unstoppable = [sq for sq in b_passed if not can_king_catch(sq, chess.BLACK)]
        
        # Calculate steps to promote for the fastest passer
        w_min_dist = min([7 - chess.square_rank(sq) for sq in w_unstoppable]) if w_unstoppable else 99
        b_min_dist = min([chess.square_rank(sq) for sq in b_unstoppable]) if b_unstoppable else 99
        
        # No unstoppable passers for either side
        if w_min_dist == 99 and b_min_dist == 99:
            return {"white": 0, "black": 0}
            
        # Tempo calculation: The side whose turn it is wins ties in the race
        if self.board.turn == chess.WHITE:
            w_wins = w_min_dist <= b_min_dist
            b_wins = b_min_dist < w_min_dist
        else:
            b_wins = b_min_dist <= w_min_dist
            w_wins = w_min_dist < b_min_dist
            
        return {"white": int(w_wins), "black": int(b_wins)}