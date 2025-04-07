# Mood-based Music Recommender System

An AI-powered music recommendation system that integrates with the Spotify API to generate personalized playlists based on user mood.

## Features

- **OAuth2 Authentication**: Securely authenticate with Spotify using OAuth2.
- **Mood Detection**: Uses NLP to detect user mood from text input.
- **Personalized Playlists**: Creates playlists based on detected mood and user preferences.
- **Real-time Modifications**: Adjust playlists on-the-fly with natural language feedback.
- **Robust Error Handling**: Implements retries and fallback mechanisms for API failures.

## System Architecture

- **Backend**: FastAPI 
- **Authentication**: Spotify OAuth2
- **NLP Model**: Hugging Face's DistilBERT for mood detection
- **Playlist Generation**: Maps moods to Spotify audio features

## Setup Instructions

### Prerequisites

- Python 3.9 or higher
- Spotify Developer Account
- Spotify API Credentials (Client ID and Client Secret)

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/mood-music-recommender.git
   cd mood-music-recommender
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with your Spotify credentials:
   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   REDIRECT_URI=http://localhost:8000/callback
   SECRET_KEY=your_secret_key
   ```

### Running the Application

1. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

2. Access the API documentation at:
   ```
   http://localhost:8000/docs
   ```

### Using Docker

1. Build the Docker image:
   ```bash
   docker build -t mood-music-recommender .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 --env-file .env mood-music-recommender
   ```

## API Endpoints

### Authentication
- `GET /authorize`: Get the Spotify authorization URL
- `GET /callback`: Handle the OAuth2 callback

### Mood Detection
- `POST /detect-mood`: Detect mood from text input

### Playlist Management
- `POST /generate-playlist`: Create a new playlist based on mood
- `POST /modify-playlist`: Modify an existing playlist based on feedback

## Example Usage

### Mood Detection

```python
import requests

response = requests.post(
    "http://localhost:8000/detect-mood",
    json={"text": "I'm feeling happy today!"}
)
print(response.json())
# Output: {"mood": "happy", "confidence": 0.92}
```

### Generate Playlist

```python
import requests

response = requests.post(
    "http://localhost:8000/generate-playlist",
    json={"mood": "happy", "name": "My Happy Playlist", "limit": 15},
    headers={"Authorization": "Bearer your_access_token"}
)
print(response.json())
```

### Modify Playlist

```python
import requests

response = requests.post(
    "http://localhost:8000/modify-playlist",
    json={"playlist_id": "your_playlist_id", "adjustment": "more energetic", "limit": 15},
    headers={"Authorization": "Bearer your_access_token"}
)
print(response.json())
```

## Testing

Run the unit tests with pytest:

```bash
pytest
```

## License

MIT License