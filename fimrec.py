import os
import pickle
from functools import lru_cache

import pandas as pd
import requests
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

# ---------------- LOAD ENV ----------------

load_dotenv()

APP_NAME = "CineVista Prime"

MOVIE_DICT_ID = "1c5bKp7Dij-sjd4Y61ywcOnZA3uJMa-v4"
SIMILARITY_ID = "10wtuqpLK3RKAy19x_GYLuHOIgmk9cyQI"

MOVIE_DICT_FILE = "movie_dict.pkl"
SIMILARITY_FILE = "similarity.pkl"

PLACEHOLDER_POSTER = "https://via.placeholder.com/500x750?text=No+Image"

OMDB_API_KEY = os.environ.get("OMDB_API_KEY")

# ---------------- DOWNLOAD FILES ----------------

def download_if_missing(file_id, filename):

    if os.path.exists(filename):
        return

    try:
        import gdown
    except ImportError:
        raise RuntimeError(
            "Install gdown using: pip install gdown"
        )

    url = f"https://drive.google.com/uc?id={file_id}"

    print(f"Downloading {filename}...")

    gdown.download(url, filename, quiet=False)

# ---------------- LOAD DATA ----------------

def load_assets():

    download_if_missing(MOVIE_DICT_ID, MOVIE_DICT_FILE)
    download_if_missing(SIMILARITY_ID, SIMILARITY_FILE)

    with open(MOVIE_DICT_FILE, "rb") as movie_file:
        movies_dict = pickle.load(movie_file)

    with open(SIMILARITY_FILE, "rb") as sim_file:
        similarity_matrix = pickle.load(sim_file)

    return pd.DataFrame(movies_dict), similarity_matrix

movies, similarity = load_assets()

movie_options = sorted(
    movies["title"].dropna().unique().tolist()
)

# ---------------- FLASK APP ----------------

app = Flask(__name__)

# ---------------- MOVIE DETAILS ----------------

@lru_cache(maxsize=4096)
def get_movie_details(movie_title):

    if not OMDB_API_KEY:
        return {
            "imdb_id": None,
            "poster": PLACEHOLDER_POSTER,
            "year": "N/A",
            "rating": "N/A",
            "genre": "N/A",
        }

    try:

        response = requests.get(
            "http://www.omdbapi.com/",
            params={
                "t": movie_title,
                "apikey": OMDB_API_KEY
            },
            timeout=6
        )

        data = response.json()

        if data.get("Response") == "True":

            poster = data.get("Poster")

            return {
                "imdb_id": data.get("imdbID"),
                "poster": poster if poster != "N/A" else PLACEHOLDER_POSTER,
                "year": data.get("Year", "N/A"),
                "rating": data.get("imdbRating", "N/A"),
                "genre": data.get("Genre", "N/A"),
            }

    except:
        pass

    return {
        "imdb_id": None,
        "poster": PLACEHOLDER_POSTER,
        "year": "N/A",
        "rating": "N/A",
        "genre": "N/A",
    }

# ---------------- RECOMMEND FUNCTION ----------------

def recommend(movie_title, top_n=15):

    try:
        movie_index = movies[movies["title"] == movie_title].index[0]
    except:
        return []

    distances = similarity[movie_index]

    similar_movies = sorted(
        list(enumerate(distances)),
        reverse=True,
        key=lambda x: x[1]
    )[1:top_n+1]

    recommendations = []

    for idx, _ in similar_movies:

        title = movies.iloc[idx].title

        details = get_movie_details(title)

        recommendations.append({
            "title": title,
            **details
        })

    return recommendations

# ---------------- HTML PAGE ----------------

@app.route("/")
def home():

    movie_list = ""

    for movie in movie_options[:500]:
        movie_list += f'<option value="{movie}">'

    return f"""
<!DOCTYPE html>
<html>

<head>

<title>{APP_NAME}</title>

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>

body {{
    margin: 0;
    padding: 0;
    background: #0f172a;
    font-family: Arial;
    color: white;
}}

.container {{
    width: 90%;
    max-width: 1200px;
    margin: auto;
    padding: 20px;
    text-align: center;
}}

h1 {{
    font-size: 40px;
    color: #38bdf8;
}}

.search-box {{
    margin-top: 30px;
}}

input {{
    width: 60%;
    padding: 14px;
    border-radius: 10px;
    border: none;
    font-size: 16px;
}}

button {{
    padding: 14px 25px;
    border: none;
    border-radius: 10px;
    background: #38bdf8;
    color: black;
    font-size: 16px;
    cursor: pointer;
    margin-left: 10px;
    font-weight: bold;
}}

button:hover {{
    background: #0ea5e9;
}}

#results {{
    margin-top: 40px;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 20px;
}}

.card {{
    background: #1e293b;
    width: 220px;
    border-radius: 15px;
    overflow: hidden;
    transition: 0.3s;
}}

.card:hover {{
    transform: scale(1.04);
}}

.card img {{
    width: 100%;
    height: 320px;
    object-fit: cover;
}}

.card-content {{
    padding: 12px;
}}

.movie-title {{
    font-size: 18px;
    font-weight: bold;
}}

.info {{
    color: #cbd5e1;
    margin-top: 6px;
    font-size: 14px;
}}

.footer {{
    margin-top: 40px;
    color: gray;
}}

</style>

</head>

<body>

<div class="container">

<h1>{APP_NAME}</h1>

<p>AI Based Movie Recommendation System</p>

<div class="search-box">

<input 
    type="text"
    id="movieInput"
    list="movies"
    placeholder="Enter movie name..."
>

<datalist id="movies">
    {movie_list}
</datalist>

<button onclick="getRecommendations()">
    Recommend
</button>

</div>

<div id="results"></div>

<div class="footer">
    Powered By OMDB API
</div>

</div>

<script>

async function getRecommendations() {{

    let movie = document.getElementById("movieInput").value;

    if(movie.trim() === "") {{
        alert("Enter movie name");
        return;
    }}

    let response = await fetch("/api/recommend", {{

        method: "POST",

        headers: {{
            "Content-Type": "application/json"
        }},

        body: JSON.stringify({{
            movie_title: movie,
            top_n: 15
        }})

    }});

    let data = await response.json();

    let results = document.getElementById("results");

    results.innerHTML = "";

    if(data.error) {{

        results.innerHTML = `
            <h2 style="color:red;">${{data.error}}</h2>
        `;

        return;
    }}

    data.recommendations.forEach(movie => {{

        results.innerHTML += `

        <div class="card">

            <img src="${{movie.poster}}">

            <div class="card-content">

                <div class="movie-title">
                    ${{movie.title}}
                </div>

                <div class="info">
                    ⭐ Rating: ${{movie.rating}}
                </div>

                <div class="info">
                    📅 Year: ${{movie.year}}
                </div>

                <div class="info">
                    🎭 Genre: ${{movie.genre}}
                </div>

            </div>

        </div>

        `;
    }});
}}

</script>

</body>
</html>
"""

# ---------------- API ----------------

@app.get("/api/movies")
def list_movies():
    return jsonify({"movies": movie_options})

@app.post("/api/recommend")
def api_recommend():

    payload = request.get_json(silent=True) or {}

    movie_title = payload.get("movie_title", "").strip()

    top_n = payload.get("top_n", 15)

    try:
        top_n = int(top_n)
    except:
        top_n = 15

    top_n = max(1, min(top_n, 25))

    if not movie_title:
        return jsonify({
            "error": "movie_title is required"
        }), 400

    if movie_title not in movie_options:
        return jsonify({
            "error": "Movie not found in catalog"
        }), 404

    recommendations = recommend(movie_title, top_n)

    return jsonify({
        "app_name": APP_NAME,
        "query": movie_title,
        "count": len(recommendations),
        "recommendations": recommendations
    })

# ---------------- RUN APP ----------------

if __name__ == "__main__":

    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug_mode
    )