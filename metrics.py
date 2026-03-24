import chess


def get_kaufman_material(fen: str) -> tuple[float, float]:
    """
    Calculates the material value for White and Black based on 
    IM Larry Kaufman's "The Evaluation of Material Imbalances".
    """
    
    # 1. Isolate the board state from the FEN string
    board = fen.split()[0]
    
    # 2. Count the pieces for both sides
    counts = {
        'P': board.count('P'), 'N': board.count('N'), 'B': board.count('B'), 
        'R': board.count('R'), 'Q': board.count('Q'),
        'p': board.count('p'), 'n': board.count('n'), 'b': board.count('b'), 
        'r': board.count('r'), 'q': board.count('q')
    }
    
    # 3. Apply Kaufman's pawn-dependency refinements
    # Knights gain value with more pawns (+1/16 per pawn over 5)
    # Rooks lose value with more pawns (-1/8 per pawn over 5)
    w_knight_val = 3.25 + (1/16) * (counts['P'] - 5)
    w_rook_val   = 5.00 - (1/8)  * (counts['P'] - 5)
    
    b_knight_val = 3.25 + (1/16) * (counts['p'] - 5)
    b_rook_val   = 5.00 - (1/8)  * (counts['p'] - 5)
    
    # 4. Calculate total base material
    white_material = (
        (counts['P'] * 1.0) +
        (counts['N'] * w_knight_val) +
        (counts['B'] * 3.25) +
        (counts['R'] * w_rook_val) +
        (counts['Q'] * 9.75)
    )
    
    black_material = (
        (counts['p'] * 1.0) +
        (counts['n'] * b_knight_val) +
        (counts['b'] * 3.25) +
        (counts['r'] * b_rook_val) +
        (counts['q'] * 9.75)
    )
    
    # 5. Apply the Bishop Pair Bonus
    if counts['B'] >= 2:
        white_material += 0.5
    if counts['b'] >= 2:
        black_material += 0.5
        
    return round(white_material, 4), round(black_material, 4)



def is_endgame(fen, color):
    # 1. Parse FEN and count pieces
    board = fen.split()[0]
    
    w_q, b_q = board.count('Q'), board.count('q')
    w_r, b_r = board.count('R'), board.count('r')
    w_b, b_b = board.count('B'), board.count('b')
    w_n, b_n = board.count('N'), board.count('n')
    
    # 2. Calculate material 
    white_material = (w_q * 9) + (w_r * 5) + (w_b * 3) + (w_n * 3)
    black_material = (b_q * 9) + (b_r * 5) + (b_b * 3) + (b_n * 3)
    
    # 3. Decide if it is an Endgame
    is_end = (white_material <= 13 and black_material <= 13) or \
             (white_material <= 3) or (black_material <= 3)
    
    if not is_end:
        return {"is_endgame": False, "type": "Middlegame or Opening"}

    # Helper function to dynamically name a side's pieces
    def get_piece_string(q, r, b, n):
        pieces = []
        if q == 1: pieces.append("Queen")
        elif q > 1: pieces.append(f"{q} Queens")
        
        if r == 1: pieces.append("Rook")
        elif r > 1: pieces.append(f"{r} Rooks")
        
        if b == 1: pieces.append("Bishop")
        elif b > 1: pieces.append(f"{b} Bishops")
        
        if n == 1: pieces.append("Knight")
        elif n > 1: pieces.append(f"{n} Knights")
        
        if not pieces:
            return "King"
            
        if len(pieces) == 1:
            return pieces[0]
        elif len(pieces) == 2:
            return f"{pieces[0]} and {pieces[1]}"
        else:
            return ", ".join(pieces[:-1]) + f" and {pieces[-1]}"

    # Helper function to calculate square colors of the bishops
    def get_bishop_type(board_fen):
        w_color, b_color = None, None
        rows = board_fen.split('/')
        
        # Ranks go 8 down to 1. Files go 1 up to 8.
        for row_idx, row in enumerate(rows):
            rank = 8 - row_idx 
            file = 1
            for char in row:
                if char.isdigit():
                    file += int(char) # Empty squares, skip ahead
                else:
                    if char == 'B':
                        w_color = (rank + file) % 2
                    elif char == 'b':
                        b_color = (rank + file) % 2
                    file += 1 # Move one square right for the piece
                    
        if w_color is not None and b_color is not None:
            return "Same-colored Bishops" if w_color == b_color else "Opposite-colored Bishops"
        return None

    # 4. Generate the piece strings for both sides
    white_str = get_piece_string(w_q, w_r, w_b, w_n)
    black_str = get_piece_string(b_q, b_r, b_b, b_n)
    
    # 5. Build the base perspective-based type
    if white_str == "King" and black_str == "King":
        endgame_type = "Pawn Endgame"
    else:
        if color.lower() == 'w':
            endgame_type = f"{white_str} vs {black_str}"
        elif color.lower() == 'b':
            endgame_type = f"{black_str} vs {white_str}"
        else:
            return {"error": "Color parameter must be 'w' or 'b'"}

    # 6. Apply Bishop Color Logic (Only highly relevant if both sides have exactly 1 Bishop)
    if w_b == 1 and b_b == 1:
        bishop_type = get_bishop_type(board)
        if bishop_type:
            # If it's a pure bishop endgame, fully replace "Bishop vs Bishop"
            if w_q == 0 and w_r == 0 and w_n == 0 and b_q == 0 and b_r == 0 and b_n == 0:
                endgame_type = bishop_type
            # If there are other pieces, append the bishop context nicely to the end
            else:
                endgame_type += f" ({bishop_type})"

    return {
        "is_endgame": True, 
        "type": endgame_type
    }


def is_not_opening(fen):
    board = chess.Board(fen)
    
    # --- 1. The Development Test ---
    # Minor pieces that are captured/traded off their starting squares 
    # automatically count as "developed" because they are no longer there.
    def is_developed(color):
        if color == chess.WHITE:
            minors = [(chess.B1, chess.KNIGHT), (chess.G1, chess.KNIGHT),
                      (chess.C1, chess.BISHOP), (chess.F1, chess.BISHOP)]
        else:
            minors = [(chess.B8, chess.KNIGHT), (chess.G8, chess.KNIGHT),
                      (chess.C8, chess.BISHOP), (chess.F8, chess.BISHOP)]
        
        undeveloped_count = 0
        for sq, piece_type in minors:
            piece = board.piece_at(sq)
            if piece and piece.piece_type == piece_type and piece.color == color:
                undeveloped_count += 1
                
        return undeveloped_count <= 1

    both_developed = is_developed(chess.WHITE) and is_developed(chess.BLACK)

    # --- 2. The Connected (or Traded) Rooks Test ---
    def rooks_connected_or_traded(color):
        rooks = list(board.pieces(chess.ROOK, color))
        
        # THE FIX: If a player has less than 2 rooks, they were traded or captured.
        # This means the game has bypassed the opening phase.
        if len(rooks) < 2:
            return True
        
        for sq in rooks:
            attacks = board.attacks(sq)
            for other_sq in rooks:
                if sq != other_sq and other_sq in attacks:
                    return True
        return False

    # True if either White OR Black has connected their rooks (or traded one away)
    rooks_passed = rooks_connected_or_traded(chess.WHITE) or rooks_connected_or_traded(chess.BLACK)

    # --- 3. The Traded Queens Test ---
    w_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
    b_queens = len(board.pieces(chess.QUEEN, chess.BLACK))
    queens_traded = (w_queens == 0) and (b_queens == 0)

    # --- Final Logic Evaluation ---
    return both_developed and (rooks_passed or queens_traded)

