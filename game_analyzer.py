import numpy as np
import chess
import math

from helpers import extract_time_fields
from extended_metrics import calculate_move_metrics, calculate_aggregate_metrics

def eval_to_cp(eval_val):
    if isinstance(eval_val, str) and 'M' in eval_val:
        is_negative = eval_val.startswith('-')
        moves = int(eval_val.replace('-', '').replace('M', ''))
        mate_cp = 10000 - (moves * 50)
        return -mate_cp if is_negative else mate_cp
    return float(eval_val) if eval_val is not None else 0.0

def analyze_game(data, opening_book=None, client=None, user_side='white', include_description=True, evaluator=None):
    if not evaluator:
        raise ValueError("Chess AI Evaluator is required!")

    data = extract_time_fields(data)
    analysis_data = data['analysis']
    position_metrics = []

    curr_opn = 'Starting Position'
    prev_eval_val = None  
    
    for i, pos in enumerate(analysis_data):
        fen = pos.get('fen')
        board_obj = chess.Board(fen)
        deep_eval = pos.get('deep_eval', 0)

        if board_obj.is_checkmate():
            deep_eval = "-M0" if board_obj.turn == chess.WHITE else "M0"
        elif board_obj.is_game_over():
            deep_eval = 0.0
            
        eval_val = eval_to_cp(deep_eval) / 100.0  
        
        if isinstance(deep_eval, str) and 'M' in deep_eval:
            eval_text = deep_eval
        else:
            eval_text = f"+{eval_val:.1f}" if eval_val > 0 else f"{eval_val:.1f}"
            if eval_val == 0.0:
                eval_text = "0.0"

        time_taken = pos.get('time', 0.0)
        white_time_remain, black_time_remain = pos.get('time_remain', [0.0, 0.0])

        # ---------------------------------------------------------
        # 1. RUN THE MASTER AI EVALUATOR
        # ---------------------------------------------------------
        ai_data = evaluator.evaluate_position(fen, opening_book)
        ai_features = ai_data["features"]
        ai_scores = ai_data["scores"]
        win_prob = ai_data["win_probability"]

        cp = eval_val * 100.0
        
        try:
            sf_win_prob = 1.0 / (1.0 + math.pow(10, -cp / 400.0))
        except OverflowError:
            sf_win_prob = 1.0 if cp > 0 else 0.0

        sharpness_score = round(abs(sf_win_prob - win_prob) * 10, 1)

        # ---------------------------------------------------------
        # 2. EXTRACT GAME STATE FROM AI FEATURES
        # ---------------------------------------------------------
        game_phase = ai_features.get('game_phase', 'Opening')
        endgame = ai_features.get('endgame_type', '-')
        
        raw_opening = ai_features.get('opening_name', 'Unknown Opening')
        if raw_opening == 'Unknown Opening':
            opening = curr_opn
        else:
            opening = raw_opening
            curr_opn = opening

        # ---------------------------------------------------------
        # 3. CALCULATE MOVE METRICS
        # ---------------------------------------------------------
        is_white_turn = pos.get('ply', 0) % 2 == 1 
        
        if i == 0:
            move_metrics = {"accuracy": 0.0, "classification": "-", "time_class": "-", "criticality": 0.0}
        else:
            move_metrics = calculate_move_metrics(prev_eval_val, eval_val, time_taken, is_white_turn)

        # ---------------------------------------------------------
        # 4. FORMAT TOP LINES (Predicting future phases via Evaluator)
        # ---------------------------------------------------------
        raw_top_lines = pos.get('top_lines', [])
        formatted_top_lines = []
        
        for line in raw_top_lines[:3]:
            line_eval = line.get('eval', 0)
            first_move_lan = line.get('move', '')
            full_line = line.get('line', '')
            
            if isinstance(line_eval, str) and 'M' in line_eval:
                line_eval_text = str(line_eval) 
            else:
                val = float(line_eval) / 100.0
                if val > 0: line_eval_text = f"+{val:.1f}"
                elif val < 0: line_eval_text = f"{val:.1f}"
                else: line_eval_text = "0.0"
            
            display_text = full_line
            
            if first_move_lan and fen:
                board = chess.Board(fen)
                move_obj = chess.Move.from_uci(first_move_lan)
                first_move_san = board.san(move_obj) 
                
                board.push(move_obj)
                new_fen = board.fen()
                
                # Re-use the AI wrapper to check the future state of the top line
                future_data = evaluator.evaluate_position(new_fen, opening_book)
                future_features = future_data["features"]
                future_phase = future_features.get("game_phase", "Opening")
                future_endgame = future_features.get("endgame_type", "-")
                future_opening = future_features.get("opening_name", "Unknown Opening")

                if game_phase == 'Opening':
                    if future_opening != 'Unknown Opening' and future_opening != curr_opn:
                        display_text = f"{first_move_san} \u2192 {future_opening}"
                elif game_phase == 'Endgame':
                    if future_phase == 'Endgame' and future_endgame != endgame:
                        display_text = f"{first_move_san} \u2192 {future_endgame}"

            formatted_top_lines.append({
                "eval": line_eval_text,
                "display_text": display_text,
                "line": full_line
            })

        # ---------------------------------------------------------
        # 5. SCALE SHAP SCORES FOR UI
        # ---------------------------------------------------------
        ui_scores = {}
        for cat in ["Material", "Pawn_Structure", "King_Safety", "Center_Control", "Activity", "Mobility", "Space", "Harmony", "Attack", "Defence"]:
            ui_scores[cat.lower()] = {
                "white": round(max(0, ai_scores[cat]["White"]) * 1000, 1),
                "black": round(max(0, ai_scores[cat]["Black"]) * 1000, 1)
            }

        if include_description:
            desc = "Game starting position." if i == 0 else ""
        else:
            desc = ""
        
        # ---------------------------------------------------------
        # 6. ASSEMBLE FINAL METRICS
        # ---------------------------------------------------------
        position_metrics.append({
            "ply": pos.get('ply'),
            "eval": eval_val,
            "win_prob": win_prob, 
            "sharpness": sharpness_score,
            "eval_text": eval_text, 
            "move_accuracy": move_metrics["accuracy"],
            "move_classification": move_metrics["classification"],
            "time": time_taken, 
            "time_classification": move_metrics["time_class"],
            "time_remain": {"white": white_time_remain, "black": black_time_remain},
            "phase": game_phase,
            "opening": opening, 
            "endgame": endgame, 
            
            # Sourced natively from AI evaluator
            "material": ui_scores["material"],
            "mobility": ui_scores["mobility"],
            "activity": ui_scores["activity"],
            "space": ui_scores["space"],
            "center_control": ui_scores["center_control"],
            "attack": ui_scores["attack"],
            "defence": ui_scores["defence"],
            "harmony": ui_scores["harmony"],
            "king_safety": ui_scores["king_safety"],
            "pawn_structure": ui_scores["pawn_structure"],
            
            # Raw features for the interactive UI highlights
            "ai_features": ai_features, 
            
            "criticality": move_metrics["criticality"],
            "top_lines": formatted_top_lines,
            "description": desc
        })

        prev_eval_val = eval_val
        
    game_metrics = calculate_aggregate_metrics(position_metrics)
        
    return {
        "user_color": user_side, 
        "game_metrics": game_metrics,
        "position_metrics": position_metrics
    }