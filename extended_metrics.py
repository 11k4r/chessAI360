import math
import numpy as np
import chess
from tactics import TacticsExtractor
from mobility import MobilityExtractor
from advanced_piece import AdvancedPieceExtractor
from battery import BatteryExtractor

# ---------------------------------------------------------
# 1. CORE MATH & WIN PROBABILITY
# ---------------------------------------------------------

def calculate_win_prob(cp: float) -> float:
    """Converts a centipawn evaluation to a win probability (0.0 to 1.0)."""
    # Cap the centipawns to prevent math overflows in extreme positions
    cp = max(-10000, min(10000, cp))
    # Standard logistical curve used by chess engines
    return 0.5 + 0.5 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def calculate_move_metrics(prev_eval_pawns: float, curr_eval_pawns: float, time_taken: float, is_white_turn: bool) -> dict:
    """Calculates move accuracy, classification, time classification, and criticality."""
    if prev_eval_pawns is None:
        return {"accuracy": 100.0, "classification": "Book", "time_class": "Normal", "criticality": 0.0}

    # Convert pawn advantage to centipawns
    cp_prev = prev_eval_pawns * 100
    cp_curr = curr_eval_pawns * 100

    wp_prev = calculate_win_prob(cp_prev)
    wp_curr = calculate_win_prob(cp_curr)

    # Probability loss based on whose turn it was
    loss = wp_prev - wp_curr if is_white_turn else wp_curr - wp_prev
    loss = max(0.0, loss)

    # ACCURACY MATH: Exponential decay based on Win Probability Loss (Multiplier 4.0)
    # 0.00 loss = 100% | 0.05 loss = ~81% | 0.10 loss = ~67% | 0.20 loss = ~45%
    accuracy = 100.0 * math.exp(-loss * 4.0)

    # Classification Thresholds based on Probability Loss
    if loss < 0.01: classif = "Best"
    elif loss < 0.03: classif = "Excellent"
    elif loss < 0.06: classif = "Good"
    elif loss < 0.12: classif = "Inaccuracy"
    elif loss < 0.22: classif = "Mistake"
    else: classif = "Blunder"

    time_class = "Normal"
    if time_taken < 1.0: time_class = "Fast"
    elif time_taken > 20.0: time_class = "Slow"

    # Criticality: How sharp/tense the position is (closer to 0.0 eval = higher criticality)
    criticality = max(0.0, 10.0 - abs(prev_eval_pawns))

    return {
        "accuracy": round(accuracy, 2),
        "classification": classif,
        "time_class": time_class,
        "criticality": round(criticality, 2)
    }

# ---------------------------------------------------------
# 2. AGGREGATION & PLAYSTYLE PROFILING
# ---------------------------------------------------------

def calculate_aggregate_metrics(position_metrics: list) -> dict:
    """Aggregates game-level personality and accuracy metrics."""
    w_accs, b_accs = [], []
    w_op_acc, b_op_acc = [], []
    w_mg_acc, b_mg_acc = [], []
    w_eg_acc, b_eg_acc = [], []
    
    # Store individual move time scores to calculate the 0-100 average
    w_time_scores, b_time_scores = [], []
    
    w_missed, b_missed = 0, 0
    evals = []

    for p in position_metrics:
        if p["ply"] == 0: continue
        
        is_white_turn = p["ply"] % 2 == 1
        
        # Clamp accuracy to prevent math domain errors on reverse engineering
        acc = max(0.001, min(100.0, p["move_accuracy"]))
        evals.append(p["eval"])
        
        phase = p.get("phase", "Midgame")
        cls = p.get("move_classification", "Good")
        t = p.get("time", 0.0)

        # --- TIME MANAGEMENT HEURISTIC (0-100 per move) ---
        t_score = 100.0
        if t < 2.0:  # Played very fast
            if cls in ["Blunder", "Mistake"]: t_score = 25.0   # Rushed and blundered
            elif cls == "Inaccuracy": t_score = 50.0           # Rushed inaccuracy
            else: t_score = 95.0                               # Good fast move (book/premove)
        elif t > 20.0: # Tanked a lot of time
            if cls in ["Blunder", "Mistake"]: t_score = 40.0   # Tanked and still blundered
            elif cls == "Inaccuracy": t_score = 65.0           # Tanked and played an inaccuracy
            else: t_score = 90.0                               # Tanked but found a great move
        else: # Normal time pacing
            if cls in ["Blunder", "Mistake"]: t_score = 75.0   # Normal pace, but should have spent more time
            else: t_score = 100.0                              # Perfect pacing

        # Distribute into White and Black metrics
        if is_white_turn:
            w_accs.append(acc)
            w_time_scores.append(t_score)
            if phase == "Opening": w_op_acc.append(acc)
            elif phase in ["Midgame", "Middlegame"]: w_mg_acc.append(acc)
            elif phase == "Endgame": w_eg_acc.append(acc)
            if cls in ["Blunder", "Mistake"]: w_missed += 1
        else:
            b_accs.append(acc)
            b_time_scores.append(t_score)
            if phase == "Opening": b_op_acc.append(acc)
            elif phase in ["Midgame", "Middlegame"]: b_mg_acc.append(acc)
            elif phase == "Endgame": b_eg_acc.append(acc)
            if cls in ["Blunder", "Mistake"]: b_missed += 1

    # --- PROPER ACCURACY AGGREGATION ---
    def safe_exp_mean(acc_list):
        if not acc_list: return 0.0
        # Reverse-engineer the Win Probability Loss from the move accuracies
        losses = [-math.log(a / 100.0) / 4.0 for a in acc_list]
        avg_loss = sum(losses) / len(losses)
        # Apply the exponential curve to the average loss
        overall_acc = 100.0 * math.exp(-avg_loss * 4.0)
        return round(overall_acc, 2)
        
    def safe_mean(lst):
        """Standard arithmetic mean for normal 0-100 scores."""
        return round(float(np.mean(lst)), 2) if lst else 0.0
    
    agg = {
        "accuracy": {"white": safe_exp_mean(w_accs), "black": safe_exp_mean(b_accs)},
        "opening_acc": {"white": safe_exp_mean(w_op_acc), "black": safe_exp_mean(b_op_acc)},
        "middlegame_acc": {"white": safe_exp_mean(w_mg_acc), "black": safe_exp_mean(b_mg_acc)},
        "endgame_acc": {"white": safe_exp_mean(w_eg_acc), "black": safe_exp_mean(b_eg_acc)},
        "volatility": round(float(np.std(evals)), 2) if len(evals) > 1 else 0.0,
        "missed_opp": {"white": w_missed, "black": b_missed},
        
        # TIME MANAGEMENT is now cleanly scaled from 0 to 100
        "time_management": {"white": safe_mean(w_time_scores), "black": safe_mean(b_time_scores)}
    }

    # --- PLAYSTYLE TRAITS (Strictly 0-100 Scale) ---
    for color in ["white", "black"]:
        base_acc = agg["accuracy"][color]
        
        # Volatility bonus (rewards accuracy in chaotic/sharp positions)
        sharpness_bonus = min(15.0, agg["volatility"] * 3.0)
        
        agg["tactics"] = agg.get("tactics", {})
        agg["tactics"][color] = max(0.0, min(100.0, round(base_acc * 0.75 + sharpness_bonus + (10 - agg["missed_opp"][color]*2), 2)))
        
        agg["strategy"] = agg.get("strategy", {})
        agg["strategy"][color] = max(0.0, min(100.0, round(agg["middlegame_acc"][color] * 0.9 + max(0, 10 - sharpness_bonus), 2)))
        
        agg["calculation"] = agg.get("calculation", {})
        agg["calculation"][color] = max(0.0, min(100.0, round(base_acc * 0.85 + sharpness_bonus, 2)))
        
        agg["intuition"] = agg.get("intuition", {})
        agg["intuition"][color] = max(0.0, min(100.0, round(agg["opening_acc"][color] * 0.95, 2)))
        
        agg["attack"] = agg.get("attack", {})
        agg["attack"][color] = max(0.0, min(100.0, round(agg["middlegame_acc"][color] * 0.85 + sharpness_bonus, 2)))
        
        # Defence takes a massive hit for every missed opportunity/blunder
        agg["defence"] = agg.get("defence", {})
        agg["defence"][color] = max(0.0, min(100.0, round(base_acc - (agg["missed_opp"][color] * 4.0), 2)))
        
        agg["resourceful"] = agg.get("resourceful", {})
        agg["resourceful"][color] = max(0.0, min(100.0, round(agg["endgame_acc"][color], 2)))

    # --- GAME CLASSIFICATION ---
    if agg["volatility"] > 2.5:
        agg["Game Type"] = "Highly Tactical & Chaotic"
    elif agg["volatility"] > 1.2:
        agg["Game Type"] = "Sharp Middlegame Battle"
    else:
        agg["Game Type"] = "Quiet Positional Grind"

    return agg

# ---------------------------------------------------------
# 3. LEGACY POSITIONAL HEURISTICS (Fallback)
# ---------------------------------------------------------

def calculate_positional_stats(fen: str) -> dict:
    """Combines legacy extractors to formulate heuristics."""
    tactics = TacticsExtractor(fen).extract_all()
    mobility = MobilityExtractor(fen).extract_all()
    advanced = AdvancedPieceExtractor(fen).extract_all()
    battery = BatteryExtractor(fen).extract_all()

    stats = {
        "activity": {"white": 0.0, "black": 0.0},
        "harmony": {"white": 0.0, "black": 0.0},
        "attack": {"white": 0.0, "black": 0.0},
        "defence": {"white": 0.0, "black": 0.0},
        "space": {"white": tactics["white"].get("space_advantage", 0), "black": tactics["black"].get("space_advantage", 0)},
        "center_control": {"white": tactics["white"].get("center_control", 0), "black": tactics["black"].get("center_control", 0)},
        "mobility": {"white": 0, "black": 0}
    }

    for color in ["white", "black"]:
        mob_sum = (mobility[color].get("knight_mobility", 0) + 
                   mobility[color].get("bishop_mobility", 0) + 
                   mobility[color].get("rook_mobility", 0) + 
                   mobility[color].get("queen_mobility", 0))
        stats["mobility"][color] = mob_sum

        activity_score = (mob_sum * 0.5) + \
                         (advanced[color].get("knight_outposts", 0) * 5.0) + \
                         (advanced[color].get("rook_on_7th", 0) * 8.0) + \
                         (advanced[color].get("rook_open_file", 0) * 4.0) + \
                         (advanced[color].get("bishop_long_diagonal", 0) * 3.0)
        stats["activity"][color] = round(min(100.0, activity_score), 2)

        harmony_score = 50.0 + \
                        (battery[color].get("rook_battery", 0) * 10.0) + \
                        (battery[color].get("diagonal_battery", 0) * 10.0) - \
                        (tactics[color].get("hanging_pieces", 0) * 15.0) - \
                        (mobility[color].get("trapped_pieces", 0) * 20.0)
        stats["harmony"][color] = round(max(0.0, min(100.0, harmony_score)), 2)

        attack_score = (stats["activity"][color] * 0.5) + \
                       (tactics[color].get("center_control", 0) * 5.0) + \
                       (tactics[color].get("pinned_pieces", 0) * 10.0) + \
                       (battery[color].get("rook_battery", 0) * 5.0)
        stats["attack"][color] = round(min(100.0, attack_score), 2)

        defence_score = 80.0 - (tactics[color].get("hanging_pieces", 0) * 25.0)
        stats["defence"][color] = round(max(0.0, min(100.0, defence_score)), 2)

    return stats