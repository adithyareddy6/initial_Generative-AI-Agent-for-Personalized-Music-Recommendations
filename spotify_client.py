# spotify_client.py
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging
import tenacity
import requests
import random
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

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

class SpotifyClient:
    def __init__(self, client_id=None, client_secret=None, redirect_uri=None):
        """Initialize Spotify client with credentials"""
        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv("REDIRECT_URI", "http://localhost:8000/callback")
        
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            logger.warning("Missing Spotify API credentials")
            
        # Audio feature mappings for each mood
        self.mood_feature_map = {
            "happy": {"target_valence": 0.8, "target_energy": 0.7, "min_valence": 0.6},
            "sad": {"target_valence": 0.3, "target_energy": 0.4, "max_valence": 0.4},
            "energetic": {"target_energy": 0.9, "min_energy": 0.8, "target_tempo": 150},
            "calm": {"target_energy": 0.2, "max_energy": 0.3, "target_acousticness": 0.8},
            "focused": {"target_energy": 0.5, "target_instrumentalness": 0.7, "max_speechiness": 0.1}
        }
        
        # Adjustments for playlist modifications
        self.adjustments = {
            "more energetic": {"target_energy": 0.2},
            "less energetic": {"target_energy": -0.2},
            "happier": {"target_valence": 0.2},
            "more acoustic": {"target_acousticness": 0.2},
            "more danceable": {"target_danceability": 0.2},
            "more instrumental": {"target_instrumentalness": 0.2},
            "more calm": {"target_energy": -0.3, "target_tempo": -20},
        }
    
    def get_oauth(self):
        """Get SpotifyOAuth instance"""
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope="user-library-read user-top-read playlist-modify-public playlist-modify-private"
        )
    
    def get_authorize_url(self):
        """Get authorization URL for OAuth flow"""
        sp_oauth = self.get_oauth()
        return sp_oauth.get_authorize_url()
    
    def get_access_token(self, code):
        """Exchange code for token"""
        sp_oauth = self.get_oauth()
        return sp_oauth.get_access_token(code)
    
    def refresh_token(self, refresh_token):
        """Refresh an expired token"""
        sp_oauth = self.get_oauth()
        return sp_oauth.refresh_access_token(refresh_token)
    
    def get_client(self, access_token):
        """Get authenticated Spotify client"""
        return spotipy.Spotify(auth=access_token)
    
    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type((requests.exceptions.RequestException, spotipy.SpotifyException)),
        reraise=True
    )
    def get_top_tracks(self, sp, limit=5):
        """Get user's top tracks with retry logic"""
        try:
            results = sp.current_user_top_tracks(limit=limit, time_range="medium_term")
            return [track["id"] for track in results["items"]]
        except Exception as e:
            logger.error(f"Error getting top tracks: {e}")
            # Fallback to random tracks from our dataset
            random_mood = random.choice(list(FALLBACK_TRACKS.keys()))
            return [track["id"] for track in FALLBACK_TRACKS[random_mood]]
    
    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type((requests.exceptions.RequestException, spotipy.SpotifyException)),
        reraise=True
    )
    def get_recommendations(self, sp, seed_tracks, audio_features, limit=15):
        """Get track recommendations with retry logic"""
        try:
            # Ensure we have valid seed tracks
            if not seed_tracks:
                logger.warning("No seed tracks available, using fallback")
                random_mood = random.choice(list(FALLBACK_TRACKS.keys()))
                seed_tracks = [track["id"] for track in FALLBACK_TRACKS[random_mood][:2]]
            
            # Limit to maximum 5 seed tracks as per Spotify API requirement
            if len(seed_tracks) > 5:
                seed_tracks = seed_tracks[:5]
                
            results = sp.recommendations(seed_tracks=seed_tracks, limit=limit, **audio_features)
            return results["tracks"]
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            # Use fallback tracks
            mood = "happy"  # Default mood
            # Try to determine mood from audio features
            if audio_features.get("target_valence", 0) > 0.6:
                mood = "happy"
            elif audio_features.get("target_energy", 0) > 0.8:
                mood = "energetic"
            elif audio_features.get("target_acousticness", 0) > 0.6:
                mood = "calm"
            elif audio_features.get("target_valence", 0) < 0.4:
                mood = "sad"
            elif audio_features.get("target_instrumentalness", 0) > 0.6:
                mood = "focused"
                
            return FALLBACK_TRACKS.get(mood, FALLBACK_TRACKS["happy"])
    
    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type((requests.exceptions.RequestException, spotipy.SpotifyException)),
        reraise=True
    )
    def create_playlist(self, sp, user_id, name, track_uris, description=""):
        """Create a playlist with retry logic"""
        try:
            playlist = sp.user_playlist_create(user_id, name, public=False, description=description)
            sp.playlist_add_items(playlist["id"], track_uris)
            return playlist
        except Exception as e:
            logger.error(f"Error creating playlist: {e}")
            return {"id": "fallback_playlist", "name": name, "tracks": track_uris, "error": str(e)}
    
    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type((requests.exceptions.RequestException, spotipy.SpotifyException)),
        reraise=True
    )
    def modify_playlist_tracks(self, sp, playlist_id, track_uris):
        """Replace playlist tracks with retry logic"""
        try:
            sp.playlist_replace_items(playlist_id, track_uris)
            playlist = sp.playlist(playlist_id)
            return playlist
        except Exception as e:
            logger.error(f"Error modifying playlist: {e}")
            return {"id": playlist_id, "error": str(e)}
    
    def get_audio_features_for_mood(self, mood):
        """Get audio features for a specific mood"""
        return self.mood_feature_map.get(mood, self.mood_feature_map["happy"])
    
    def adjust_audio_features(self, base_features, adjustment_type):
        """Adjust audio features based on user feedback"""
        if adjustment_type not in self.adjustments:
            return base_features
        
        adjusted_features = base_features.copy()
        for feature, value in self.adjustments[adjustment_type].items():
            if feature in adjusted_features:
                adjusted_features[feature] += value
            else:
                adjusted_features[feature] = value
                
            # Ensure values are within valid ranges (0.0 to 1.0 for most features)
            if feature in ["target_valence", "target_energy", "target_acousticness", 
                          "target_danceability", "target_instrumentalness"]:
                adjusted_features[feature] = max(0.0, min(1.0, adjusted_features[feature]))
        
        return adjusted_features
    
    def parse_adjustment_text(self, text):
        """Parse natural language adjustment text to find known adjustments"""
        text = text.lower().strip()
        
        # Check for exact matches
        for adjustment in self.adjustments:
            if adjustment in text:
                return adjustment
                
        # Check for semantic matches
        if any(word in text for word in ["energetic", "energy", "lively", "upbeat"]):
            return "more energetic" if not any(word in text for word in ["less", "lower", "down"]) else "less energetic"
        elif any(word in text for word in ["happy", "cheerful", "joyful"]):
            return "happier"
        elif any(word in text for word in ["acoustic", "unplugged"]):
            return "more acoustic"
        elif any(word in text for word in ["dance", "groove", "rhythm"]):
            return "more danceable"
        elif any(word in text for word in ["instrumental", "no vocals", "no singing"]):
            return "more instrumental"
        elif any(word in text for word in ["calm", "relaxing", "peaceful", "chill"]):
            return "more calm"
            
        # Default adjustment if no match found
        return "more energetic"
