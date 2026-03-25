import xgboost as xgb
import shap
import pandas as pd
import json
import math
from chessAI import chessAIExtractor

def calculate_win_prob(row):
    if pd.notna(row.get('mate')):
        mate_val = float(row['mate'])
        return 1.0 if mate_val > 0 else 0.0
    
    if pd.notna(row.get('score')):
        cp = float(row['score'])
        return 1.0 / (1.0 + math.pow(10, -cp / 400.0))
    
    return 0.5

def flatten_features(features_dict):
    if not isinstance(features_dict, dict):
        return {}
        
    engineered = {}
    openness_map = {'closed': 0, 'semi_open': 1, 'open': 2}
    phase_map = {'Opening': 0, 'Midgame': 1, 'Endgame': 2}
    
    for key, value in features_dict.items():
        if isinstance(value, dict) and 'white' in value and 'black' in value:
            w_val = value['white']
            b_val = value['black']
            
            if isinstance(w_val, list): w_val = len(w_val)
            if isinstance(b_val, list): b_val = len(b_val)
            
            if isinstance(w_val, bool): w_val = int(w_val)
            if isinstance(b_val, bool): b_val = int(b_val)
            
            if isinstance(w_val, (int, float)) and isinstance(b_val, (int, float)):
                engineered[f"{key}_white"] = w_val
                engineered[f"{key}_black"] = b_val
                engineered[f"{key}_delta"] = w_val - b_val 
                
        else:
            if key == 'tempo':
                engineered['tempo_is_white'] = 1 if value == 'white' else 0
            elif key == 'center_openness':
                engineered['center_openness_encoded'] = openness_map.get(value, 1)
            elif key == 'game_phase':
                engineered['game_phase_encoded'] = phase_map.get(value, 0)
            elif key in ['is_endgame_ocb', 'has_queens', 'opposite_castling']:
                engineered[key] = int(value)
                
    return engineered

class ChessEvaluationWrapper:
    def __init__(self, model_path: str, columns_path: str):
        self.model = xgb.XGBRegressor()
        self.model.load_model(model_path)
        
        with open(columns_path, "r") as f:
            self.feature_columns = json.load(f)
            
        self.explainer = shap.TreeExplainer(self.model)
        
        self.categories = {
            "Material": [
                "kaufman_material", "Qv3M", "Qv2R", "Rv2M", "BvN", "no_pawns", 
                "queen", "N1", "N2", "R1", "R2", "bishop_light", "bishop_dark", 
                "pawn_a", "pawn_b", "pawn_c", "pawn_f", "pawn_g", "pawn_h"
            ],
            "Pawn_Structure": [
                "isolated", "doubled", "backward", "weak_chain_base", "backward_on_open_file", 
                "ram", "self_blocked", "passed_pawn", "unstoppable_passer", "connected_passers", 
                "candidate_passer", "connected_pawns", "phalanx", "chain_set_right", 
                "chain_set_left", "pawn_island_count", "pawn_chain_count", "majority", "crippled_majority"
            ],
            "King_Safety": [
                "king_sq", "back_rank", "open_file", "semi_open_file", "fianchetto_holes", 
                "opposite_castling", "king_in_square", "is_endgame_ocb"
            ],
            "Center_Control": [
                "center_openness", "pawn_d", "pawn_e", "center_control", 
                "pawn_center", "extended_pawn_center"
            ],
            "Activity": [
                "virtual_mobility", "trapped_pieces", "tempo", "game_phase", "has_queens", "en_passant",
                "knight_outposts", "rook_on_7th", "rook_open_file", "rook_semi_open_file", "bishop_long_diagonal",
                "pst_pawns", "pst_knights", "pst_bishops", "pst_rooks", "pst_queens", "pst_kings",
                "undeveloped_minors", "king_centralization"
            ],
            "Mobility": [
                "knight_mobility_sum", "knight_mobility_max", "knight_mobility_min", 
                "bishop_light_mobility", "bishop_dark_mobility", "rook_mobility_sum", 
                "rook_mobility_max", "rook_mobility_min", "queen_mobility_sum", 
                "queen_mobility_max", "queen_mobility_min"
            ],
            "Space": ["overextended", "both_wings", "one_wing", "space_advantage", "opposition"],
            "Harmony": [
                "bishop_pair", "knight_pair", "rook_pair", "tarrasch_compliance", 
                "rook_battery", "diagonal_battery", "defended_pieces", "bad_bishops"
            ],
            "Attack": ["attackers_count", "lever", "shield_attack", "race_advantage", "pinned_pieces"],
            "Defence": [
                "defenders_count", "shelter_count", "shield_rank_2", "shield_rank_3", 
                "shield_ram", "protected_passer", "king_support", "king_blocking_proximity", 
                "hanging_pieces", "knight_blockaders", "overloaded_pieces"
            ]
        }

    def _get_base_feature_name(self, col_name: str) -> str:
        for suffix in ['_white', '_black', '_delta', '_encoded', '_is_white']:
            if col_name.endswith(suffix):
                return col_name[:-len(suffix)]
        return col_name

    def evaluate_position(self, fen: str, opening_book=None) -> dict:
        raw_dict = chessAIExtractor(fen, opening_book).extract_all()
        flat_dict = flatten_features(raw_dict)
        row_df = pd.DataFrame([flat_dict], columns=self.feature_columns).fillna(0)
        
        win_prob = float(self.model.predict(row_df)[0])
        shap_values = self.explainer.shap_values(row_df)
        feature_impacts = dict(zip(self.feature_columns, shap_values[0]))
        
        breakdown = {cat: {"White": 0.0, "Black": 0.0, "Delta/Global": 0.0} for cat in self.categories.keys()}
        
        for col_name, impact in feature_impacts.items():
            base_name = self._get_base_feature_name(col_name)
            
            assigned_category = None
            for cat, features in self.categories.items():
                if base_name in features:
                    assigned_category = cat
                    break
            
            if assigned_category:
                if col_name.endswith("_white"):
                    breakdown[assigned_category]["White"] += float(impact)
                elif col_name.endswith("_black"):
                    breakdown[assigned_category]["Black"] += float(impact * -1) 
                else:
                    breakdown[assigned_category]["Delta/Global"] += float(impact)

        return {
            "fen": fen,
            "win_probability": win_prob,
            "base_probability": float(self.explainer.expected_value),
            "features": raw_dict,
            "scores": breakdown
        }