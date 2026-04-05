import re
import statistics
import io
import copy
import chess
import chess.pgn
from game_analyzer import analyze_game
from game_state import get_opening_from_fen, is_endgame

def determine_tc(pgn):
    """Parses the PGN string to determine the time control format."""
    if not pgn: return 'blitz'
        
    event_match = re.search(r'\[Event\s+"([^"]+)"\]', pgn)
    if event_match:
        event = event_match.group(1).lower()
        if 'bullet' in event: return 'bullet'
        if 'blitz' in event: return 'blitz'
        if 'rapid' in event: return 'rapid'
        
    tc_match = re.search(r'\[TimeControl\s+"([^"]+)"\]', pgn)
    if tc_match:
        tc = tc_match.group(1)
        try:
            base_time = int(tc.split('+')[0])
            if base_time < 180: return 'bullet'
            elif base_time < 600: return 'blitz'
            else: return 'rapid'
        except ValueError:
            pass
            
    return 'blitz'


def get_elo_from_pgn(pgn_str, user_side):
    """Extracts the player's ELO from the PGN string."""
    if not pgn_str: return 1500
    tag = "WhiteElo" if user_side == "white" else "BlackElo"
    match = re.search(rf'\[{tag}\s+"(\d+)"\]', pgn_str)
    if match:
        return int(match.group(1))
    return 1500


def update_single_stat_bucket(current_stats, raw_games, analyzed_games, opening_book, client, evaluator):
    """
    100% Server-Side Aggregation for a single bucket (e.g. 'all', 'chesscom', 'lichess').
    Merges the incoming batch into the historical current_stats.
    """
    if not current_stats:
        current_stats = {
            "totalGames": 0, "analyzedGamesCount": 0, "wins": 0,
            "tcStats": {
                "bullet": {"w": 0, "l": 0, "d": 0, "streak": 0},
                "blitz": {"w": 0, "l": 0, "d": 0, "streak": 0},
                "rapid": {"w": 0, "l": 0, "d": 0, "streak": 0}
            },
            "metrics": {
                "ACC": 0, "OPN": 0, "MID": 0, "END": 0, "TAC": 0,
                "CAL": 0, "STR": 0, "INT": 0, "ATK": 0, "DEF": 0,
                "TMG": 0, "RES": 0
            },
            "openings": {}, # Infinite N-Level Depth Move Tree
            "endgames": {}, 
            "galleryFens": [], # Now stores {"fen": ..., "best_move": ...}
            "playstyle_title": "Balanced Player",
            "raw_aggregates": {"endgame_ply": 100, "fast_ratio": 0.5, "pawn_grabs": 0}
        }

    # --- 1. Basic W/L/D Updates & FAST REPERTOIRE PARSING ---
    if raw_games:
        current_stats['totalGames'] += len(raw_games)
        games_by_tc = {'bullet': [], 'blitz': [], 'rapid': []}
        
        for g in raw_games:
            tc = determine_tc(g.get('pgn', ''))
            games_by_tc[tc].append(g)
            
            # --- FAST PGN PARSER FOR RECURSIVE OPENINGS & ENDGAMES ---
            pgn_str = g.get('pgn', '')
            user_side = g.get('user_side', 'white')
            res = g.get('result', 'draw')
            res_key = res[0] # 'w', 'l', or 'd'
            
            if pgn_str:
                pgn_io = io.StringIO(pgn_str)
                game_obj = chess.pgn.read_game(pgn_io)
                
                if game_obj:
                    board = game_obj.board()
                    endgames_seen = set()
                    curr_level = current_stats['openings']
                    
                    for i, move in enumerate(game_obj.mainline_moves()):
                        san = board.san(move)
                        board.push(move)
                        fen = board.fen()
                        
                        # 1. Opening Tree Extraction
                        if i < 12:
                            op_data = get_opening_from_fen(fen, opening_book)
                            name = op_data.get('name', 'Unknown Opening')
                            
                            if san not in curr_level:
                                curr_level[san] = {
                                    'white': {'w': 0, 'l': 0, 'd': 0},
                                    'black': {'w': 0, 'l': 0, 'd': 0},
                                    'name': name, 
                                    'children': {}
                                }
                            
                            curr_level[san][user_side][res_key] += 1
                            if name not in ["Unknown Position", "Unknown Opening"]:
                                curr_level[san]['name'] = name
                                
                            curr_level = curr_level[san]['children']
                                
                        # 2. Endgame Extraction
                        if i >= 30:
                            eg_data = is_endgame(fen, user_side)
                            if eg_data['is_endgame']:
                                endgames_seen.add(eg_data['type'])

                    for eg_type in endgames_seen:
                        if eg_type not in current_stats['endgames']:
                            current_stats['endgames'][eg_type] = {'w':0, 'l':0, 'd':0}
                        current_stats['endgames'][eg_type][res_key] += 1
            # -----------------------------------------------

        for tc, g_list in games_by_tc.items():
            g_list.sort(key=lambda x: x.get('timestamp', 0))
            current_streak = 0
            max_streak = current_stats['tcStats'][tc].get('streak', 0)
            
            for g in g_list:
                res = g.get('result', 'draw')
                if res == 'win':
                    current_stats['wins'] += 1
                    current_stats['tcStats'][tc]['w'] += 1
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                elif res == 'loss':
                    current_stats['tcStats'][tc]['l'] += 1
                    current_streak = 0
                else:
                    current_stats['tcStats'][tc]['d'] += 1
                    current_streak = 0
                    
            current_stats['tcStats'][tc]['streak'] = max_streak

    # --- 2. Deep Metrics via Existing Pipeline ---
    if analyzed_games:
        batch_metrics_list = []
        for game in analyzed_games:
            user_side = game.get('user_side', 'white')
            try:
                analysis_result = analyze_game(
                    data=game, opening_book=opening_book, client=client, 
                    user_side=user_side, include_description=False, evaluator=evaluator
                )
                
                gm = analysis_result['game_metrics']
                pm = analysis_result['position_metrics']
                tc = determine_tc(game.get('pgn', ''))
                raw_analysis = game.get('analysis', [])
                
                endgame_ply = 100
                fast_moves = 0
                total_user_moves = 0
                
                for i, pos in enumerate(pm):
                    if pos.get('phase') == 'Endgame' and endgame_ply == 100:
                        endgame_ply = pos.get('ply')
                        
                    ply = pos.get('ply', 0)
                    is_user_turn = (ply % 2 == 1) if user_side == 'white' else (ply % 2 == 0)
                    
                    if is_user_turn:
                        total_user_moves += 1
                        if pos.get('time_classification') == 'Fast':
                            fast_moves += 1
                            
                    # --- BLUNDER RECOVERY PUZZLE EXTRACTION ---
                    if tc in ['rapid', 'blitz'] and i > 0:
                        if is_user_turn and pos.get('move_classification') == 'Blunder':
                            if i - 1 < len(raw_analysis):
                                prev_raw = raw_analysis[i - 1]
                                prev_fen = prev_raw.get('fen')
                                top_lines = prev_raw.get('top_lines', [])
                                
                                if top_lines and len(top_lines) > 0:
                                    best_move = top_lines[0].get('move')
                                    # Deduplicate by FEN
                                    if not any(isinstance(x, dict) and x.get('fen') == prev_fen for x in current_stats['galleryFens']):
                                        if len(current_stats['galleryFens']) < 15:
                                            
                                            temp_board = chess.Board(prev_fen)
                                            legal_moves_map = {}
                                            
                                            for move in temp_board.legal_moves:
                                                from_sq = chess.square_name(move.from_square)
                                                to_sq = chess.square_name(move.to_square)
                                                
                                                flags = []
                                                if temp_board.is_capture(move): flags.append('c')
                                                if temp_board.is_en_passant(move): flags.append('e')
                                                
                                                if from_sq not in legal_moves_map:
                                                    legal_moves_map[from_sq] = []
                                                legal_moves_map[from_sq].append({'to': to_sq, 'flags': flags})

                                            current_stats['galleryFens'].append({
                                                'fen': prev_fen,
                                                'best_move': best_move,
                                                'legal_moves': legal_moves_map # Send to client
                                            })
                
                fast_ratio = (fast_moves / total_user_moves) if total_user_moves > 0 else 0.5
                pawn_grabs = len(re.findall(r'\b[a-h]x[a-h][1-8]', game.get('pgn', ''))) / 2.0
                
                batch_metrics_list.append({
                    'ACC': gm['accuracy'][user_side], 'OPN': gm['opening_acc'][user_side],
                    'MID': gm['middlegame_acc'][user_side], 'END': gm['endgame_acc'][user_side],
                    'TAC': gm['tactics'][user_side], 'CAL': gm['calculation'][user_side],
                    'STR': gm['strategy'][user_side], 'INT': gm['intuition'][user_side],
                    'ATK': gm['attack'][user_side], 'DEF': gm['defence'][user_side],
                    'TMG': gm['time_management'][user_side], 'RES': gm['resourceful'][user_side],
                    'endgame_ply': endgame_ply, 'fast_ratio': fast_ratio, 'pawn_grabs': pawn_grabs
                })
                
            except Exception as e:
                print(f"Skipping game due to analyzer error: {e}")
                continue

        # --- 3. Weighted Mathematical Merge on the Server ---
        if batch_metrics_list:
            batch_count = len(batch_metrics_list)
            old_count = current_stats.get('analyzedGamesCount', 0)
            new_count = old_count + batch_count
            
            b_meds = {}
            for key in ['ACC', 'OPN', 'MID', 'END', 'TAC', 'CAL', 'STR', 'INT', 'ATK', 'DEF', 'TMG', 'RES', 'endgame_ply', 'fast_ratio', 'pawn_grabs']:
                vals = [x[key] for x in batch_metrics_list if x[key] is not None and x[key] != 0 and x[key] != 0.0]
                b_meds[key] = statistics.median(vals) if vals else 0

            for key in ['ACC', 'OPN', 'MID', 'END', 'TAC', 'CAL', 'STR', 'INT', 'ATK', 'DEF', 'TMG', 'RES']:
                old_val = current_stats['metrics'].get(key, 0)
                if old_count == 0:
                    current_stats['metrics'][key] = int(b_meds[key])
                else:
                    current_stats['metrics'][key] = int(((old_val * old_count) + (b_meds[key] * batch_count)) / new_count)

            raw = current_stats.get('raw_aggregates', {"endgame_ply": 100, "fast_ratio": 0.5, "pawn_grabs": 0})
            for key in ['endgame_ply', 'fast_ratio', 'pawn_grabs']:
                old_val = raw.get(key, 0)
                if old_count == 0:
                    raw[key] = b_meds[key]
                else:
                    raw[key] = ((old_val * old_count) + (b_meds[key] * batch_count)) / new_count
            current_stats['raw_aggregates'] = raw
            current_stats['analyzedGamesCount'] = new_count

            med_endgame_ply = raw['endgame_ply']
            med_fast_ratio = raw['fast_ratio']
            med_pawn_grabs = raw['pawn_grabs']

            user_elos = []
            for g in raw_games:
                elo = get_elo_from_pgn(g.get('pgn', ''), g.get('user_side', 'white'))
                if elo > 0: user_elos.append(elo)
            
            avg_elo = statistics.median(user_elos) if user_elos else 1500
            current_stats['avg_elo'] = int(avg_elo) # Save it to track over time

            elo_baseline = max(10, 35 + (avg_elo / 50.0)) # Added max(10) to prevent negative OVR for extreme edge cases
            
            # Blended Normalization: 30% Engine Accuracy + 70% ELO Base
            current_stats['normalized_metrics'] = {}
            for key, raw_val in current_stats['metrics'].items():
                norm_val = min(99, int((raw_val * 0.2) + (elo_baseline * 0.8)))
                current_stats['normalized_metrics'][key] = norm_val

            meds = current_stats['normalized_metrics'] 
            candidates = {}
            
            if meds.get('ACC', 100) < 40: candidates['Blunder Master'] = 100 + (40 - meds.get('ACC'))
            if med_endgame_ply < 55: candidates['The Simplifier'] = 100 + (55 - med_endgame_ply)
            if med_fast_ratio >= 0.80: candidates['Speed Demon'] = 100 + ((med_fast_ratio - 0.80) * 100)
            if med_pawn_grabs >= 6.5: candidates['The Pawn Grabber'] = 80 + (med_pawn_grabs * 5)
            if meds.get('OPN', 0) > 95: candidates['The Theoretician'] = meds.get('OPN')
            if meds.get('ATK', 0) > 90 and meds.get('DEF', 100) < 90: candidates['Trouble Maker'] = meds.get('ATK')
            if meds.get('ATK', 0) > 90: candidates['Aggressive Attacker'] = meds.get('ATK')
            if meds.get('DEF', 0) > 90: candidates['Solid Defender'] = meds.get('DEF')
            if meds.get('TAC', 0) > 90: candidates['Tactical Wizard'] = meds.get('TAC')
            if meds.get('CAL', 0) > 90: candidates['Deep Calculator'] = meds.get('CAL')

            if candidates:
                current_stats['playstyle_title'] = max(candidates, key=candidates.get)

    return current_stats


def process_insights_batch(data, opening_book, client, evaluator):
    """
    Main entry point. Routes games into appropriate platform buckets 
    and updates the master stats dictionary.
    """
    raw_games = data.get('games', [])
    analyzed_games = data.get('analyzed_games', [])
    saved_stats = data.get('current_stats', {})

    empty_stat = {
        "totalGames": 0, "analyzedGamesCount": 0, "wins": 0,
        "tcStats": { "bullet": {"w": 0, "l": 0, "d": 0, "streak": 0}, "blitz": {"w": 0, "l": 0, "d": 0, "streak": 0}, "rapid": {"w": 0, "l": 0, "d": 0, "streak": 0} },
        "metrics": { "ACC": 0, "OPN": 0, "MID": 0, "END": 0, "TAC": 0, "CAL": 0, "STR": 0, "INT": 0, "ATK": 0, "DEF": 0, "TMG": 0, "RES": 0 },
        "openings": {}, "endgames": {}, "galleryFens": [], "playstyle_title": "Balanced Player",
        "raw_aggregates": {"endgame_ply": 100, "fast_ratio": 0.5, "pawn_grabs": 0}
    }

    # 1. Backwards Compatibility & Initialization
    if not saved_stats or 'all' not in saved_stats:
        migrated_all = saved_stats if saved_stats.get('totalGames') else copy.deepcopy(empty_stat)
        current_stats = {
            'all': migrated_all,
            'chesscom': copy.deepcopy(empty_stat),
            'lichess': copy.deepcopy(empty_stat)
        }
    else:
        current_stats = saved_stats

    # 2. Filter payload into buckets
    games_dict = {
        'all': {
            'raw': raw_games, 
            'analyzed': analyzed_games
        },
        'chesscom': {
            'raw': [g for g in raw_games if g.get('platform') == 'chesscom'], 
            'analyzed': [g for g in analyzed_games if g.get('platform') == 'chesscom']
        },
        'lichess': {
            'raw': [g for g in raw_games if g.get('platform') == 'lichess'], 
            'analyzed': [g for g in analyzed_games if g.get('platform') == 'lichess']
        }
    }

    # 3. Process each bucket independently
    for platform, p_data in games_dict.items():
        if not p_data['raw'] and not p_data['analyzed']:
            continue
        
        current_stats[platform] = update_single_stat_bucket(
            current_stats[platform], 
            p_data['raw'], 
            p_data['analyzed'], 
            opening_book, 
            client, 
            evaluator
        )

    return current_stats