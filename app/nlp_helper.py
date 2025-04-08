# nlp_helper.py
from transformers import pipeline
import logging
import random
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class MoodDetector:
    def __init__(self):
        self.model = None
        self.initialize_model()
        
        # Define fallback moods
        self.available_moods = [
            "happy", "sad", "energetic", "calm", "focused"
        ]
        
        # Mapping from model's emotion labels to our mood categories
        self.emotion_to_mood = {
            "joy": "happy",
            "sadness": "sad",
            "anger": "energetic",
            "fear": "sad",
            "love": "happy",
            "surprise": "energetic",
        }
    
    def initialize_model(self):
        """Initialize the NLP model for mood detection"""
        try:
            self.model = pipeline(
                "text-classification", 
                model="bhadresh-savani/distilbert-base-uncased-emotion",
                top_k=1
            )
            logger.info("NLP model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load NLP model: {e}")
            self.model = None
            return False
    
    def predict_mood(self, text: str) -> Dict:
        """
        Predict mood from text input
        
        Args:
            text: User's text input
            
        Returns:
            Dict with mood and confidence score
        """
        if not self.model:
            # Try initializing again
            success = self.initialize_model()
            if not success:
                # If still not available, use fallback
                logger.warning("NLP model not available, using random mood")
                return {"mood": random.choice(self.available_moods), "confidence": 0.5}
        
        try:
            # Get emotion prediction
            result = self.model(text)
            emotion = result[0][0]['label']
            confidence = result[0][0]['score']
            
            # Map to our mood categories
            mood = self.emotion_to_mood.get(emotion, "happy")
            
            return {"mood": mood, "confidence": confidence}
        except Exception as e:
            logger.error(f"Error predicting mood: {e}")
            # Fallback to a default mood
            return {"mood": "happy", "confidence": 0.0}
