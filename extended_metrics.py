import math
import numpy as np
import chess
from tactics import TacticsExtractor
from mobility import MobilityExtractor
from advanced_piece import AdvancedPieceExtractor
from battery import BatteryExtractor

def calculate_win_prob(cp: float) -> float:
    """Converts a centipawn evaluation to a win probability (0.0 to 1.0)."""
    cp = max(-10000, min(10000, cp))
    return 0.5 + 0.5 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)

def calculate_move_metrics(prev_eval_cp: float, curr_eval_cp: float, time_taken: float, is_white_turn: bool) -> dict:
    """Calculates move accuracy, classification, time classification, and criticality."""
    if prev_eval_cp is None:
        return {"accuracy": 100.0, "classification": "Book", "time_class": "Normal", "criticality": 0.0}

    wp_prev = calculate_win_prob(prev_eval_cp * 100)
    wp_curr = calculate_win_prob(curr_eval_cp * 100)

    # Probability loss based on whose turn it was
    loss = wp_prev - wp_curr if is_white_turn else wp_curr - wp_prev
    loss = max(0.0, loss)

    accuracy = max(0.0, 100.0 - (loss * 100.0))

    if loss < 0.02: classif = "Best"
    elif loss < 0.05: classif = "Excellent"
    elif loss < 0.10: classif = "Good"
    elif loss < 0.20: classif = "Inaccuracy"
    elif loss < 0.30: classif = "Mistake"
    else: classif = "Blunder"

    time_class = "Normal"
    if time_taken < 1.0: time_class = "Fast"
    elif time_taken > 30.0: time_class = "Slow"

    criticality = max(0.0, 10.0 - abs(prev_eval_cp))

    return {
        "accuracy": round(accuracy, 2),
        "classification": classif,
        "time_class": time_class,
        "criticality": round(criticality, 2)
    }

def calculate_positional_stats(fen: str) -> dict:
    """
    Combines all extractors to formulate heuristics for activity, harmony, attack, and defence.
    """
    tactics = TacticsExtractor(fen).extract_all()
    mobility = MobilityExtractor(fen).extract_all()
    advanced = AdvancedPieceExtractor(fen).extract_all()
    battery = BatteryExtractor(fen).extract_all()

    stats = {
        "activity": {"white": 0.0, "black": 0.0},
        "harmony": {"white": 0.0, "black": 0.0},
        "attack": {"white": 0.0, "black": 0.0},
        "defence": {"white": 0.0, "black": 0.0},
        "space": {"white": tactics["white"]["space_advantage"], "black": tactics["black"]["space_advantage"]},
        "center_control": {"white": tactics["white"]["center_control"], "black": tactics["black"]["center_control"]},
        "mobility": {"white": 0, "black": 0}
    }

    for color in ["white", "black"]:
        # Calculate raw mobility sum
        mob_sum = (mobility[color]["knight_mobility"] + 
                   mobility[color]["bishop_mobility"] + 
                   mobility[color]["rook_mobility"] + 
                   mobility[color]["queen_mobility"])
        stats["mobility"][color] = mob_sum

        # --- Activity (0-100 scale approximation) ---
        # Base mobility + bonuses for aggressive/advanced placement
        activity_score = (mob_sum * 0.5) + \
                         (advanced[color]["knight_outposts"] * 5.0) + \
                         (advanced[color]["rook_on_7th"] * 8.0) + \
                         (advanced[color]["rook_open_file"] * 4.0) + \
                         (advanced[color]["bishop_long_diagonal"] * 3.0)
        stats["activity"][color] = round(min(100.0, activity_score), 2)

        # --- Harmony (0-100 scale approximation) ---
        # Piece coordination (batteries) vs anti-coordination (hanging/trapped pieces)
        harmony_score = 50.0 + \
                        (battery[color]["rook_battery"] * 10.0) + \
                        (battery[color]["diagonal_battery"] * 10.0) - \
                        (tactics[color]["hanging_pieces"] * 15.0) - \
                        (mobility[color]["trapped_pieces"] * 20.0)
        stats["harmony"][color] = round(max(0.0, min(100.0, harmony_score)), 2)

        # --- Attack (0-100 scale approximation) ---
        # Offensive potential: center control + pins + advanced pieces
        attack_score = (stats["activity"][color] * 0.5) + \
                       (tactics[color]["center_control"] * 5.0) + \
                       (tactics[color]["pinned_pieces"] * 10.0) + \
                       (battery[color]["rook_battery"] * 5.0)
        stats["attack"][color] = round(min(100.0, attack_score), 2)

        # --- Defence (0-100 scale approximation) ---
        # Stability: Lack of hanging pieces, safe pieces
        defence_score = 80.0 - (tactics[color]["hanging_pieces"] * 25.0)
        stats["defence"][color] = round(max(0.0, min(100.0, defence_score)), 2)

    return stats

def calculate_aggregate_metrics(position_metrics: list) -> dict:
    """Aggregates game-level personality and accuracy metrics from the array of position metrics."""
    w_accs, b_accs = [], []
    w_op_acc, b_op_acc = [], []
    w_mg_acc, b_mg_acc = [], []
    w_eg_acc, b_eg_acc = [], []
    
    w_missed, b_missed = 0, 0
    w_time_spent, b_time_spent = 0.0, 0.0
    evals = []

    for p in position_metrics:
        if p["ply"] == 0: continue
        
        is_white_turn = p["ply"] % 2 == 1
        acc = p["move_accuracy"]
        evals.append(p["eval"])

        if is_white_turn:
            w_accs.append(acc)
            w_time_spent += p["time"]
            if p["phase"] == "Opening": w_op_acc.append(acc)
            elif p["phase"] == "Midgame": w_mg_acc.append(acc)
            elif p["phase"] == "Endgame": w_eg_acc.append(acc)
            if p["move_classification"] in ["Blunder", "Mistake"]: w_missed += 1
        else:
            b_accs.append(acc)
            b_time_spent += p["time"]
            if p["phase"] == "Opening": b_op_acc.append(acc)
            elif p["phase"] == "Midgame": b_mg_acc.append(acc)
            elif p["phase"] == "Endgame": b_eg_acc.append(acc)
            if p["move_classification"] in ["Blunder", "Mistake"]: b_missed += 1

    # Safe mean calculations
    safe_mean = lambda lst: round(float(np.mean(lst)), 2) if lst else 0.0
    
    agg = {
        "accuracy": {"white": safe_mean(w_accs), "black": safe_mean(b_accs)},
        "opening_acc": {"white": safe_mean(w_op_acc), "black": safe_mean(b_op_acc)},
        "middlegame_acc": {"white": safe_mean(w_mg_acc), "black": safe_mean(b_mg_acc)},
        "endgame_acc": {"white": safe_mean(w_eg_acc), "black": safe_mean(b_eg_acc)},
        "volatility": round(float(np.std(evals)), 2) if len(evals) > 1 else 0.0,
        "missed_opp": {"white": w_missed, "black": b_missed},
        "time_management": {"white": round(w_time_spent, 1), "black": round(b_time_spent, 1)}
    }

    # Derive playstyle stats based on game phases and volatility
    for color in ["white", "black"]:
        base_acc = agg["accuracy"][color]
        
        # Tactics/Calculation scale with volatility (high standard deviation in eval = sharp game)
        sharpness_bonus = min(10.0, agg["volatility"] * 2.0)
        
        agg["tactics"] = agg.get("tactics", {})
        agg["tactics"][color] = min(100.0, round(base_acc * 0.8 + sharpness_bonus, 2))
        
        agg["strategy"] = agg.get("strategy", {})
        agg["strategy"][color] = min(100.0, round(agg["middlegame_acc"][color] * 0.9 + (10 - sharpness_bonus), 2))
        
        agg["calculation"] = agg.get("calculation", {})
        agg["calculation"][color] = min(100.0, round(base_acc * 0.85 + sharpness_bonus, 2))
        
        agg["intuition"] = agg.get("intuition", {})
        agg["intuition"][color] = min(100.0, round(agg["opening_acc"][color] * 0.9, 2))
        
        # Attack correlates heavily with middlegame accuracy
        agg["attack"] = agg.get("attack", {})
        agg["attack"][color] = min(100.0, round(agg["middlegame_acc"][color] * 0.95, 2))
        
        # Defence takes a hit for every missed opportunity/blunder
        misses = agg["missed_opp"][color]
        agg["defence"] = agg.get("defence", {})
        agg["defence"][color] = max(0.0, round(base_acc - (misses * 2.0), 2))
        
        agg["resourceful"] = agg.get("resourceful", {})
        agg["resourceful"][color] = min(100.0, round(agg["endgame_acc"][color] * 0.95, 2))

    # Determine Game Type classification
    if agg["volatility"] > 3.0:
        agg["Game Type"] = "Highly Tactical & Chaotic"
    elif agg["volatility"] > 1.5:
        agg["Game Type"] = "Sharp Middlegame Battle"
    else:
        agg["Game Type"] = "Quiet Positional Grind"

    return agg