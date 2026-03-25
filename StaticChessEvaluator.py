import math
from chessAI import chessAIExtractor

class StaticChessEvaluator:
    def __init__(self):
        self.categories = {
            "Material": ["kaufman_material", "Qv3M", "Qv2R", "Rv2M", "BvN", "no_pawns", "queen", "N1", "N2", "R1", "R2", "bishop_light", "bishop_dark", "pawn_a", "pawn_b", "pawn_c", "pawn_f", "pawn_g", "pawn_h"],
            "Pawn_Structure": ["isolated", "doubled", "backward", "weak_chain_base", "backward_on_open_file", "ram", "self_blocked", "passed_pawn", "unstoppable_passer", "connected_passers", "candidate_passer", "connected_pawns", "phalanx", "chain_set_right", "chain_set_left", "pawn_island_count", "pawn_chain_count", "majority", "crippled_majority", "is_gonna_promote_first"],
            "King_Safety": ["king_sq", "back_rank", "open_file", "semi_open_file", "fianchetto_holes", "opposite_castling", "king_in_square", "is_endgame_ocb"],
            "Center_Control": ["center_openness", "pawn_d", "pawn_e", "center_control", "pawn_center", "extended_pawn_center"],
            "Activity": ["virtual_mobility", "trapped_pieces", "tempo", "game_phase", "has_queens", "en_passant", "knight_outposts", "rook_on_7th", "rook_open_file", "rook_semi_open_file", "bishop_long_diagonal", "pst_pawns", "pst_knights", "pst_bishops", "pst_rooks", "pst_queens", "pst_kings", "undeveloped_minors", "king_centralization"],
            "Mobility": ["knight_mobility_sum", "knight_mobility_max", "knight_mobility_min", "bishop_light_mobility", "bishop_dark_mobility", "rook_mobility_sum", "rook_mobility_max", "rook_mobility_min", "queen_mobility_sum", "queen_mobility_max", "queen_mobility_min"],
            "Space": ["overextended", "both_wings", "one_wing", "space_advantage", "opposition"],
            "Harmony": ["bishop_pair", "knight_pair", "rook_pair", "tarrasch_compliance", "rook_battery", "diagonal_battery", "defended_pieces", "bad_bishops"],
            "Attack": ["attackers_count", "lever", "shield_attack", "race_advantage", "pinned_pieces"],
            "Defence": ["defenders_count", "shelter_count", "shield_rank_2", "shield_rank_3", "shield_ram", "protected_passer", "king_support", "king_blocking_proximity", "hanging_pieces", "knight_blockaders", "overloaded_pieces"]
        }

        self.weights = {
            "kaufman_material": 1.0, "Qv3M": 0.5, "Qv2R": -0.5, "Rv2M": -0.5, "BvN": 0.1, "no_pawns": -1.5, "queen": 9.0, "N1": 3.0, "N2": 3.0, "R1": 5.0, "R2": 5.0, "bishop_light": 3.0, "bishop_dark": 3.0, "pawn_a": 1.0, "pawn_b": 1.0, "pawn_c": 1.0, "pawn_f": 1.0, "pawn_g": 1.0, "pawn_h": 1.0,
            "isolated": -0.3, "doubled": -0.3, "backward": -0.2, "weak_chain_base": -0.2, "backward_on_open_file": -0.4, "ram": 0.0, "self_blocked": -0.1, "passed_pawn": 0.5, "unstoppable_passer": 3.0, "connected_passers": 1.5, "candidate_passer": 0.3, "connected_pawns": 0.1, "phalanx": 0.2, "chain_set_right": 0.1, "chain_set_left": 0.1, "pawn_island_count": -0.15, "pawn_chain_count": 0.1, "majority": 0.2, "crippled_majority": -0.2, "is_gonna_promote_first": 6.0,
            "king_sq": 0.0, "back_rank": -0.3, "open_file": -0.3, "semi_open_file": -0.15, "fianchetto_holes": -0.25, "opposite_castling": 0.0, "king_in_square": 0.5, "is_endgame_ocb": 0.0,
            "center_openness": 0.0, "pawn_d": 0.2, "pawn_e": 0.2, "center_control": 0.15, "pawn_center": 0.3, "extended_pawn_center": 0.2,
            "virtual_mobility": 0.05, "trapped_pieces": -0.8, "tempo": 0.1, "game_phase": 0.0, "has_queens": 0.0, "en_passant": 0.1, "knight_outposts": 0.4, "rook_on_7th": 0.6, "rook_open_file": 0.3, "rook_semi_open_file": 0.15, "bishop_long_diagonal": 0.3, "pst_pawns": 0.02, "pst_knights": 0.02, "pst_bishops": 0.02, "pst_rooks": 0.02, "pst_queens": 0.02, "pst_kings": 0.02, "undeveloped_minors": -0.2, "king_centralization": 0.3,
            "knight_mobility_sum": 0.05, "knight_mobility_max": 0.0, "knight_mobility_min": 0.0, "bishop_light_mobility": 0.05, "bishop_dark_mobility": 0.05, "rook_mobility_sum": 0.04, "rook_mobility_max": 0.0, "rook_mobility_min": 0.0, "queen_mobility_sum": 0.02, "queen_mobility_max": 0.0, "queen_mobility_min": 0.0,
            "overextended": -0.3, "both_wings": 0.15, "one_wing": 0.05, "space_advantage": 0.2, "opposition": 0.4,
            "bishop_pair": 0.5, "knight_pair": 0.05, "rook_pair": 0.1, "tarrasch_compliance": 0.2, "rook_battery": 0.3, "diagonal_battery": 0.3, "defended_pieces": 0.05, "bad_bishops": -0.3,
            "attackers_count": 0.15, "lever": 0.1, "shield_attack": 0.2, "race_advantage": 0.3, "pinned_pieces": -0.4,
            "defenders_count": 0.1, "shelter_count": 0.1, "shield_rank_2": 0.2, "shield_rank_3": 0.1, "shield_ram": 0.2, "protected_passer": 0.5, "king_support": 0.15, "king_blocking_proximity": 0.1, "hanging_pieces": -1.0, "knight_blockaders": 0.2, "overloaded_pieces": -0.3
        }

        self.default_weight = 0.0 

        # Define theoretical bounds to natively guarantee 0 to 1 scaling without clip/max
        # "base" represents the maximum possible sum of penalties in this category.
        # "max" represents the absolute ceiling (base + maximum possible positive score).
        self.category_bounds = {
            "Material": {"base": 3.0, "max": 100.0},
            "Pawn_Structure": {"base": 15.0, "max": 66.0},
            "King_Safety": {"base": 3.0, "max": 10.0},
            "Center_Control": {"base": 0.0, "max": 10.0},
            "Activity": {"base": 5.0, "max": 25.0},
            "Mobility": {"base": 0.0, "max": 15.0},
            "Space": {"base": 4.0, "max": 15.0},
            "Harmony": {"base": 2.0, "max": 10.0},
            "Attack": {"base": 3.0, "max": 20.0},
            "Defence": {"base": 12.0, "max": 30.0}
        }

    def _to_numeric(self, val):
        if isinstance(val, bool): return 1.0 if val else 0.0
        if isinstance(val, list): return float(len(val))
        if isinstance(val, (int, float)): return float(val)
        return 0.0

    def evaluate_position(self, fen: str, opening_book=None) -> dict:
        raw_dict = chessAIExtractor(fen, opening_book).extract_all()
        
        # Initialize scores directly at the Base safe floor
        breakdown = {cat: {
            "White": self.category_bounds[cat]["base"], 
            "Black": self.category_bounds[cat]["base"], 
            "Delta/Global": 0.0
        } for cat in self.categories.keys()}
        
        # We need raw un-shifted scores just for calculating overall Centipawn advantage
        raw_cp_white = 0.0
        raw_cp_black = 0.0

        for feature_name, value in raw_dict.items():
            weight = self.weights.get(feature_name, self.default_weight)
            
            assigned_category = next((cat for cat, feats in self.categories.items() if feature_name in feats), None)
            
            if assigned_category and isinstance(value, dict) and 'white' in value and 'black' in value:
                w_val = self._to_numeric(value['white'])
                b_val = self._to_numeric(value['black'])
                
                w_score = w_val * weight
                b_score = b_val * weight
                
                breakdown[assigned_category]["White"] += w_score
                breakdown[assigned_category]["Black"] += b_score
                
                raw_cp_white += w_score
                raw_cp_black += b_score

        # Normalize the UI scores between 0 and 1 linearly without any smoothing logic
        for cat in self.categories.keys():
            breakdown[cat]["White"] = breakdown[cat]["White"] / self.category_bounds[cat]["max"]
            breakdown[cat]["Black"] = breakdown[cat]["Black"] / self.category_bounds[cat]["max"]

        # Calculate win prob based on raw centipawn advantage, NOT normalized UI values
        net_advantage_cp = (raw_cp_white - raw_cp_black) * 100
        try:
            win_prob = 1.0 / (1.0 + math.pow(10, -net_advantage_cp / 400.0))
        except OverflowError:
            win_prob = 1.0 if net_advantage_cp > 0 else 0.0

        return {
            "fen": fen,
            "win_probability": win_prob,
            "base_probability": 0.5,
            "features": raw_dict,
            "scores": breakdown
        }