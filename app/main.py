# main.py
import os
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pydantic import BaseModel
import uvicorn
import logging
from logging.handlers import RotatingFileHandler
import json
from typing import Dict, List, Optional, Any
import random
import requests
from transformers import pipeline
import tenacity
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler("app.log", maxBytes=10000000, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

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

# Models
class UserInput(BaseModel):
    text: str

class MoodResponse(BaseModel):
    mood: str
    confidence: float

class PlaylistRequest(BaseModel):
    mood: str
    name: Optional[str] = None
    limit: Optional[int] = 15

class PlaylistModificationRequest(BaseModel):
    playlist_id: str
    adjustment: str
    limit: Optional[int] = 15

class SpotifyTokens(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int

# Setup NLP model at startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize NLP model
    try:
        app.state.nlp_model = pipeline(
            "text-classification", 
            model="bhadresh-savani/distilbert-base-uncased-emotion",
            top_k=1
        )
        logger.info("NLP model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load NLP model: {e}")
        app.state.nlp_model = None
    
    yield
    
    # Cleanup
    logger.info("Shutting down application")

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# Authentication Helpers
# ----------------------

def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="user-library-read user-top-read playlist-modify-public playlist-modify-private"
    )

def get_spotify_client(access_token: str):
    return spotipy.Spotify(auth=access_token)

async def get_current_user(request: Request):
    token_info = request.session.get("token_info")
    if not token_info:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    sp_oauth = get_spotify_oauth()
    if sp_oauth.is_token_expired(token_info):
        try:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            request.session["token_info"] = token_info
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise HTTPException(status_code=401, detail="Authentication expired")
    
    return token_info["access_token"]

# ----------------------
# NLP Mood Detection
# ----------------------

def map_emotion_to_mood(emotion: str) -> str:
    """Map emotion labels from the model to our predefined moods"""
    emotion_to_mood = {
        "joy": "happy",
        "sadness": "sad",
        "anger": "energetic",
        "fear": "sad",
        "love": "happy",
        "surprise": "energetic",
    }
    return emotion_to_mood.get(emotion, "happy")  # Default to happy if unknown

def predict_mood(text: str, nlp_model) -> Dict:
    """Predict mood from text input"""
    if not nlp_model:
        # Fallback if model failed to load
        logger.warning("NLP model not available, using random mood")
        moods = list(MOOD_TO_AUDIO_FEATURES.keys())
        return {"mood": random.choice(moods), "confidence": 0.5}
    
    try:
        # Get emotion prediction
        result = nlp_model(text)
        emotion = result[0][0]['label']
        confidence = result[0][0]['score']
        
        # Map to our mood categories
        mood = map_emotion_to_mood(emotion)
        
        return {"mood": mood, "confidence": confidence}
    except Exception as e:
        logger.error(f"Error predicting mood: {e}")
        # Fallback to a default mood
        return {"mood": "happy", "confidence": 0.0}

# ----------------------
# Spotify API Functions
# ----------------------

@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception_type((requests.exceptions.RequestException, spotipy.SpotifyException)),
    reraise=True
)
def get_top_tracks(sp, limit=5):
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
def get_recommendations(sp, seed_tracks, audio_features, limit=15):
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
        mood = next(iter(audio_features.get("target_valence", 0.5) > 0.5 and "happy" or "sad"))
        return FALLBACK_TRACKS.get(mood, FALLBACK_TRACKS["happy"])

@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception_type((requests.exceptions.RequestException, spotipy.SpotifyException)),
    reraise=True
)
def create_playlist(sp, user_id, name, track_uris, description=""):
    """Create a playlist with retry logic"""
    try:
        playlist = sp.user_playlist_create(user_id, name, public=False, description=description)
        sp.playlist_add_items(playlist["id"], track_uris)
        return playlist
    except Exception as e:
        logger.error(f"Error creating playlist: {e}")
        return {"id": "fallback_playlist", "name": name, "tracks": track_uris}

@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception_type((requests.exceptions.RequestException, spotipy.SpotifyException)),
    reraise=True
)
def modify_playlist_tracks(sp, playlist_id, track_uris):
    """Replace playlist tracks with retry logic"""
    try:
        sp.playlist_replace_items(playlist_id, track_uris)
        playlist = sp.playlist(playlist_id)
        return playlist
    except Exception as e:
        logger.error(f"Error modifying playlist: {e}")
        return {"id": playlist_id, "error": str(e)}

def adjust_audio_features(base_features, adjustment_type):
    """Adjust audio features based on user feedback"""
    if adjustment_type not in ADJUSTMENTS:
        return base_features
    
    adjusted_features = base_features.copy()
    for feature, value in ADJUSTMENTS[adjustment_type].items():
        if feature in adjusted_features:
            adjusted_features[feature] += value
        else:
            adjusted_features[feature] = value
            
        # Ensure values are within valid ranges (0.0 to 1.0 for most features)
        if feature in ["target_valence", "target_energy", "target_acousticness", 
                        "target_danceability", "target_instrumentalness"]:
            adjusted_features[feature] = max(0.0, min(1.0, adjusted_features[feature]))
    
    return adjusted_features

# ----------------------
# API Endpoints
# ----------------------

@app.get("/")
async def root():
    return {"status": "running", "message": "Welcome to Mood-based Music Recommender API"}

@app.get("/authorize")
async def authorize():
    """Generate Spotify OAuth2 authorization URL"""
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return {"authorization_url": auth_url}

@app.get("/callback")
async def callback(request: Request, code: str = None, error: str = None):
    """Handle the callback from Spotify OAuth"""
    if error:
        return {"error": error}
    
    if not code:
        return {"error": "No authorization code provided"}
    
    try:
        sp_oauth = get_spotify_oauth()
        token_info = sp_oauth.get_access_token(code)
        
        # Store token info in session
        request.session["token_info"] = token_info
        
        # Redirect to frontend or return token info
        return {"access_token": token_info.get("access_token"),
                "expires_in": token_info.get("expires_in")}
    except Exception as e:
        logger.error(f"Error in callback: {e}")
        return {"error": str(e)}

@app.post("/detect-mood", response_model=MoodResponse)
async def detect_mood(user_input: UserInput, request: Request):
    """Detect mood from user text input"""
    text = user_input.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Input text cannot be empty")
    
    # Get mood prediction
    mood_data = predict_mood(text, request.app.state.nlp_model)
    
    return MoodResponse(
        mood=mood_data["mood"],
        confidence=mood_data["confidence"]
    )

@app.post("/generate-playlist")
async def generate_playlist(
    playlist_req: PlaylistRequest, 
    request: Request,
    access_token: str = Depends(get_current_user)
):
    """Generate a playlist based on user mood"""
    try:
        sp = get_spotify_client(access_token)
        user_id = sp.me()["id"]
        
        # Get mood-based audio features
        mood = playlist_req.mood
        if mood not in MOOD_TO_AUDIO_FEATURES:
            mood = "happy"  # Default to happy if mood not found
        
        audio_features = MOOD_TO_AUDIO_FEATURES[mood]
        
        # Get user's top tracks as seeds
        seed_tracks = get_top_tracks(sp)
        
        # Get recommendations
        recommended_tracks = get_recommendations(sp, seed_tracks, audio_features, playlist_req.limit)
        
        # Create playlist name if not provided
        playlist_name = playlist_req.name or f"{mood.capitalize()} Mood Playlist"
        
        # Create new playlist
        track_uris = [track["uri"] for track in recommended_tracks]
        playlist = create_playlist(
            sp, 
            user_id, 
            playlist_name, 
            track_uris, 
            description=f"A {mood} mood playlist generated by AI"
        )
        
        tracks_info = [
            {"id": track["id"], "name": track["name"], "artist": track["artists"][0]["name"]}
            for track in recommended_tracks
        ]
        
        return {
            "status": "success",
            "playlist_id": playlist["id"],
            "playlist_name": playlist["name"],
            "mood": mood,
            "tracks": tracks_info
        }
        
    except Exception as e:
        logger.error(f"Error generating playlist: {e}")
        # Use fallback data
        fallback_tracks = FALLBACK_TRACKS.get(mood, FALLBACK_TRACKS["happy"])
        return {
            "status": "fallback",
            "message": "Used fallback data due to API issues",
            "mood": mood,
            "tracks": fallback_tracks
        }

@app.post("/modify-playlist")
async def modify_playlist(
    mod_request: PlaylistModificationRequest,
    request: Request,
    access_token: str = Depends(get_current_user)
):
    """Modify an existing playlist based on adjustment request"""
    try:
        sp = get_spotify_client(access_token)
        
        # Get current playlist tracks
        playlist = sp.playlist(mod_request.playlist_id)
        current_tracks = [item["track"]["id"] for item in playlist["tracks"]["items"]]
        
        # Determine base audio features to adjust
        # We'll infer the current mood from the playlist description if possible
        description = playlist.get("description", "").lower()
        base_mood = "happy"  # Default
        for mood in MOOD_TO_AUDIO_FEATURES:
            if mood in description:
                base_mood = mood
                break
        
        base_features = MOOD_TO_AUDIO_FEATURES[base_mood].copy()
        
        # Adjust audio features based on requested adjustment
        adjusted_features = adjust_audio_features(base_features, mod_request.adjustment)
        
        # Get new recommendations
        recommended_tracks = get_recommendations(sp, current_tracks[:3], adjusted_features, mod_request.limit)
        
        # Update playlist
        track_uris = [track["uri"] for track in recommended_tracks]
        updated_playlist = modify_playlist_tracks(sp, mod_request.playlist_id, track_uris)
        
        tracks_info = [
            {"id": track["id"], "name": track["name"], "artist": track["artists"][0]["name"]}
            for track in recommended_tracks
        ]
        
        return {
            "status": "success",
            "playlist_id": updated_playlist["id"],
            "playlist_name": updated_playlist["name"],
            "adjustment": mod_request.adjustment,
            "tracks": tracks_info
        }
        
    except Exception as e:
        logger.error(f"Error modifying playlist: {e}")
        return {
            "status": "error",
            "message": f"Failed to modify playlist: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
