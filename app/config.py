# config.py
import os
from pydantic import BaseSettings, Field
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings"""
    # Spotify API credentials
    SPOTIFY_CLIENT_ID: str = Field(..., env="SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET: str = Field(..., env="SPOTIFY_CLIENT_SECRET")
    REDIRECT_URI: str = Field("http://localhost:8000/callback", env="REDIRECT_URI")
    
    # API settings
    API_BASE_URL: str = Field("http://localhost:8000", env="API_BASE_URL")
    DEBUG: bool = Field(False, env="DEBUG")
    
    # NLP model settings
    NLP_MODEL_NAME: str = Field("bhadresh-savani/distilbert-base-uncased-emotion", env="NLP_MODEL_NAME")
    
    # Security settings
    SECRET_KEY: str = Field("your-secret-key-change-in-production", env="SECRET_KEY")
    
    # Logging settings
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    """Get application settings with caching"""
    return Settings()

# Constants
MOOD_TO_AUDIO_FEATURES = {
    "happy": {"target_valence": 0.8, "target_energy": 0.7, "min_valence": 0.6},
    "sad": {"target_valence": 0.3, "target_energy": 0.4, "max_valence": 0.4},
    "energetic": {"target_energy": 0.9, "min_energy": 0.8, "target_tempo": 150},
    "calm": {"target_energy": 0.2, "max_energy": 0.3, "target_acousticness": 0.8},
    "focused": {"target_energy": 0.5, "target_instrumentalness": 0.7, "max_speechiness": 0.1}
}

# Adjustment mapping
ADJUSTMENTS = {
    "more energetic": {"target_energy": 0.2},
    "less energetic": {"target_energy": -0.2},
    "happier": {"target_valence": 0.2},
    "more acoustic": {"target_acousticness": 0.2},
    "more danceable": {"target_danceability": 0.2},
    "more instrumental": {"target_instrumentalness": 0.2},
    "more calm": {"target_energy": -0.3, "target_tempo": -20},
}

# Fallback dataset for when Spotify API is unavailable
FALLBACK_TRACKS = {
    "happy": [
        {"id": "4iV5W9uYEdYUVa79Axb7Rh", "name": "Uptown Funk", "artist": "Mark Ronson"},
        {"id": "0SiywuOBRcynK0uKGWdCnn", "name": "Happy", "artist": "Pharrell Williams"},
        {"id": "3MrRksHupTVEQ7YbA0FsZK", "name": "Can't Stop the Feeling!", "artist": "Justin Timberlake"},
    ],
    "sad": [
        {"id": "0pqnGHJpmpxLKifKRmU6WP", "name": "Imagine", "artist": "John Lennon"},
        {"id": "1BxfuPKGuaTgP7aM0Bbdwr", "name": "Hello", "artist": "Adele"},
        {"id": "6b2RcmUt1g9N9mQ3CbjX2Y", "name": "Skinny Love", "artist": "Bon Iver"},
    ],
    "energetic": [
        {"id": "7CZyCXKG6d5ALeq41sLzbP", "name": "The Middle", "artist": "Zedd"},
        {"id": "2KH16WveTQWT6KOG9Rg6e2", "name": "Eye of the Tiger", "artist": "Survivor"},
        {"id": "1zB4vmk8tFRmM9UULNzbLB", "name": "Thunder", "artist": "Imagine Dragons"},
    ],
    "calm": [
        {"id": "0WqIKmW4BTrj3eJFmnCKMv", "name": "River Flows In You", "artist": "Yiruma"},
        {"id": "2LTlO3NuNVN70lp2ZbVswF", "name": "Weightless", "artist": "Marconi Union"},
        {"id": "4NwJCTuBJ1RSeZyEwzfL1T", "name": "Gymnopédie No.1", "artist": "Erik Satie"},
    ],
    "focused": [
        {"id": "5wCKGrqU8rYvJfFYZJOxeN", "name": "Brain Waves", "artist": "Study Music"},
        {"id": "7MfxUR9vMuCIKjJ0tfhuJJ", "name": "Concentration", "artist": "Focus Music"},
        {"id": "6l8EbYRtQMgKOyc1gcDHF9", "name": "Deep Focus", "artist": "Alpha Waves"},
    ]
}
