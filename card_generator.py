import statistics
import re
import io
import chess.pgn
from game_analyzer import analyze_game
from game_state import GameStateExtractor
from helpers import get_opening_from_fen

def generate_player_card(payload, opening_book, client):
    total_games = wins = losses = draws = 0
    
    # Dictionary trackers for UI lists and stats
    batch_openings = {}
    batch_endgames = {}
    tc_stats = {
        'bullet': {'w': 0, 'l': 0, 'd': 0}, 
        'blitz': {'w': 0, 'l': 0, 'd': 0}, 
        'rapid': {'w': 0, 'l': 0, 'd': 0}
    }
    first_moves_counts = {}
    
    # Trackers for the 12 Card Metrics
    raw_metrics = {
        'ACC': [], 'TAC': [], 'CAL': [], 'STR': [], 'INT': [], 
        'ATK': [], 'TMG': [], 'DEF': [], 'RES': [], 
        'OPN': [], 'MID': [], 'END': []
    }
    
    for platform, tcs in payload.items():
        for tc, tc_data in tcs.items():
            
            # ==========================================
            # 1. Fast PGN Extraction (Basic Stats, Openings, Endgames)
            # ==========================================
            for g in tc_data.get('games', []):
                total_games += 1
                res = g.get('result', 'draw')
                side = g.get('user_side', 'white')
                pgn = g.get('pgn', '')
                
                # Determine Time Control for this specific game heuristically
                event_match = re.search(r'\[Event\s+"([^"]+)"\]', pgn)
                event_str = event_match.group(1).lower() if event_match else ""
                
                if 'rapid' in event_str:
                    norm_tc = 'rapid'
                elif 'bullet' in event_str:
                    norm_tc = 'bullet'
                elif 'blitz' in event_str:
                    norm_tc = 'blitz'
                else:
                    tc_match = re.search(r'\[TimeControl\s+"([^"]+)"\]', pgn)
                    tc_str = tc_match.group(1) if tc_match else "180"
                    try:
                        if '+' in tc_str:
                            base, inc = tc_str.split('+')
                            total_time = int(base) + int(inc) * 40
                        else:
                            total_time = int(tc_str)
                            
                        if total_time < 180: norm_tc = 'bullet'
                        elif total_time < 600: norm_tc = 'blitz'
                        else: norm_tc = 'rapid'
                    except:
                        norm_tc = 'blitz'
                
                # Global and TC-specific W/L/D
                if res == 'win': 
                    wins += 1
                    tc_stats[norm_tc]['w'] += 1
                elif res == 'loss': 
                    losses += 1
                    tc_stats[norm_tc]['l'] += 1
                else: 
                    draws += 1
                    tc_stats[norm_tc]['d'] += 1
                
                # Extract First Move
                if side == 'white':
                    move_match = re.search(r'(?:^|\s)1\.\s*([a-zA-Z0-9]+)', pgn)
                    if move_match:
                        fm = move_match.group(1)
                        first_moves_counts[fm] = first_moves_counts.get(fm, 0) + 1

                opn_name = "Unknown"

                try:
                    pgn_io = io.StringIO(pgn)
                    game = chess.pgn.read_game(pgn_io)
                    
                    if game:
                        board = game.board()
                        book_opening = None
                        node = game
                        
                        # --- A. Find Opening via Book ---
                        # Step through the first 15 moves (30 plies) to find the deepest match
                        while node.variations and board.ply() < 30:
                            node = node.variation(0)
                            board.push(node.move)
                            
                            # Check against your opening book helper
                            op_info = get_opening_from_fen(board.fen(), opening_book)
                            current_opn = op_info.get("name", "Unknown Opening")
                            
                            # Keep overwriting with the latest valid opening name found
                            if current_opn != "Unknown Opening":
                                book_opening = current_opn
                        
                        # Apply Opening (Fallback to PGN headers if the book misses it entirely)
                        if book_opening:
                            opn_name = book_opening
                        else:
                            opn_match = re.search(r'\[Opening\s+"([^"]+)"\]', pgn)
                            eco_match = re.search(r'\[ECO\s+"([^"]+)"\]', pgn)
                            if opn_match: 
                                opn_name = opn_match.group(1).split(':')[0].strip()
                            elif eco_match: 
                                opn_name = f"ECO {eco_match.group(1)}"
                                
                        # Tally Openings
                        if opn_name not in batch_openings:
                            batch_openings[opn_name] = {'w': 0, 'l': 0, 'd': 0, 'color': side}
                        
                        if res == 'win': batch_openings[opn_name]['w'] += 1
                        elif res == 'loss': batch_openings[opn_name]['l'] += 1
                        else: batch_openings[opn_name]['d'] += 1

                        # --- B. Find Endgame ---
                        # Fast-forward to the very end of the game
                        while node.variations:
                            node = node.variation(0)
                            
                        final_board = node.board()
                        state_extractor = GameStateExtractor(final_board.fen(), side[0], opening_book)
                        state_features = state_extractor.extract_all()
                        
                        if state_features["phase"]["name"] == 'Endgame':
                            endgame_type = state_features["phase"]["endgame_type"]
                            if endgame_type and endgame_type != "None":
                                if endgame_type not in batch_endgames:
                                    batch_endgames[endgame_type] = {'w': 0, 'l': 0, 'd': 0}
                                
                                if res == 'win': batch_endgames[endgame_type]['w'] += 1
                                elif res == 'loss': batch_endgames[endgame_type]['l'] += 1
                                else: batch_endgames[endgame_type]['d'] += 1
                                
                except Exception as e:
                    print(f"Error parsing PGN fast: {e}")
                    pass # Silently skip malformed PGNs

            # ==========================================
            # 2. Deep Engine Extraction (Traits Only)
            # ==========================================
            for ag in tc_data.get('analyzed_games', []):
                game_data = ag  
                side = ag.get('user_side', 'white')
                
                try:
                    # Pass include_description=False if you want to skip generating the AI summary text for the player profile queue to save time
                    analysis_results = analyze_game(game_data, opening_book, client, side, include_description=False)
                    pos_metrics = analysis_results.get('position_metrics', [])
                    
                    if not pos_metrics: 
                        continue

                    # Calculate Phase Accuracies
                    opn_accs = [p.get('move_accuracy', 0) for p in pos_metrics if p.get('phase') == 'Opening']
                    mid_accs = [p.get('move_accuracy', 0) for p in pos_metrics if p.get('phase') == 'Midgame']
                    end_accs = [p.get('move_accuracy', 0) for p in pos_metrics if p.get('phase') == 'Endgame']
                    all_accs = [p.get('move_accuracy', 0) for p in pos_metrics]
                    
                    if opn_accs: raw_metrics['OPN'].append(statistics.mean(opn_accs))
                    if mid_accs: raw_metrics['MID'].append(statistics.mean(mid_accs))
                    if end_accs: raw_metrics['END'].append(statistics.mean(end_accs))
                    
                    avg_acc = statistics.mean(all_accs) if all_accs else 0
                    raw_metrics['ACC'].append(avg_acc)

                    # Derive Playstyle Traits
                    crit_accs = [p.get('move_accuracy', 0) for p in pos_metrics if p.get('criticality', 0) > 0.5]
                    tac_val = statistics.mean(crit_accs) if crit_accs else avg_acc
                    
                    raw_metrics['TAC'].append(tac_val)
                    raw_metrics['CAL'].append(tac_val)
                    raw_metrics['ATK'].append(tac_val)
                    
                    raw_metrics['STR'].append(avg_acc)
                    raw_metrics['DEF'].append(avg_acc)
                    raw_metrics['INT'].append(avg_acc)
                    
                    raw_metrics['RES'].append(statistics.mean(end_accs) if end_accs else avg_acc)
                    raw_metrics['TMG'].append(85)
                    
                except Exception as e:
                    print(f"Error analyzing deep game in generator: {e}")

    # ==========================================
    # 3. Final Averages & OVR Calculation
    # ==========================================
    final_metrics = {}
    for key, values in raw_metrics.items():
        valid_vals = [x for x in values if isinstance(x, (int, float))]
        final_metrics[key] = int(statistics.mean(valid_vals)) if valid_vals else 0

    core_attributes = [final_metrics.get('ACC', 0), final_metrics.get('TAC', 0), final_metrics.get('STR', 0), final_metrics.get('CAL', 0)]
    ovr = int(statistics.mean([x for x in core_attributes if x > 0])) if any(x > 0 for x in core_attributes) else 0

    return {
        "performance": {
            "total_games": total_games,
            "win_rate": int((wins / total_games) * 100) if total_games > 0 else 0,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "stability": final_metrics.get('RES', 0),
            "tc_stats": tc_stats,
            "first_moves": first_moves_counts
        },
        "metrics": final_metrics,
        "ovr": ovr,
        "repertoire": {
            "openings": batch_openings,
            "endgames": batch_endgames
        }
    }