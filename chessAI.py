import chess
import json

from pawn_structure import PawnStructureExtractor
from material import MaterialExtractor
from mobility import MobilityExtractor
from king_safety import KingSafetyExtractor
from game_state import GameStateExtractor

class chessAIExtractor:
    """
    Master class that takes a FEN and aggregates features from all four 
    domain-specific extractors into a single, unified flat dictionary.
    """
    def __init__(self, fen: str, opening_book=None):
        self.fen = fen
        
        # Initialize all four sub-extractors with the same FEN
        self.extractors = [
            MaterialExtractor(fen),
            PawnStructureExtractor(fen),
            MobilityExtractor(fen),
            KingSafetyExtractor(fen),
            GameStateExtractor(fen, 'w', opening_book)
        ]

    def extract_all(self) -> dict:
        """
        Executes all sub-extractors and merges their results.
        Returns a single dictionary containing all ~65+ features.
        """
        master_features = {}
        
        for extractor in self.extractors:
            sub_features = extractor.extract_all()
            
            for feature_name, player_values in sub_features.items():
                # Optional safety check: ensures we don't accidentally overwrite a feature 
                # if you add new features with overlapping names in the future.
                if feature_name in master_features:
                    raise ValueError(f"Key collision detected: '{feature_name}' already exists in the master dictionary.")
                
                master_features[feature_name] = player_values
                
        return master_features
