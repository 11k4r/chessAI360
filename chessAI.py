import chess
import json

from material import MaterialExtractor
from pawn_structure import PawnStructureExtractor
from mobility import MobilityExtractor
from king_safety import KingSafetyExtractor
from game_state import GameStateExtractor
from pst import PSTExtractor
from tactics import TacticsExtractor
from advanced_piece import AdvancedPieceExtractor
from battery import BatteryExtractor
from development import DevelopmentExtractor
from endgame_features import EndgameExtractor
from coordination import CoordinationExtractor

class chessAIExtractor:
    """
    Master class that takes a FEN and aggregates features from all 
    domain-specific extractors into a single, unified flat dictionary.
    """
    def __init__(self, fen: str, opening_book=None):
        self.fen = fen
        
        self.extractors = [
            MaterialExtractor(fen),
            PawnStructureExtractor(fen),
            MobilityExtractor(fen),
            KingSafetyExtractor(fen),
            GameStateExtractor(fen, 'w', opening_book),
            PSTExtractor(fen),
            TacticsExtractor(fen),
            AdvancedPieceExtractor(fen),
            BatteryExtractor(fen),
            DevelopmentExtractor(fen),
            EndgameExtractor(fen),
            CoordinationExtractor(fen)
        ]

    def extract_all(self) -> dict:
        master_features = {}
        
        for extractor in self.extractors:
            sub_features = extractor.extract_all()
            
            for feature_name, player_values in sub_features.items():
                if feature_name in master_features:
                    raise ValueError(f"Key collision detected: '{feature_name}' already exists in the master dictionary.")
                
                master_features[feature_name] = player_values
                
        return master_features