import requests
import config_loader as config

logger = config.logger

def query_tmdb(title: str, year: str | None, api_key: str):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": api_key, "query": title}
    if year:
        params["year"] = year
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("results"):
                movie = data["results"][0]
                return {
                    "source": "tmdb",
                    "id": movie["id"],
                    "title": movie["title"],
                    "year": movie.get("release_date", "")[:4]
                }
    except Exception as e:
        logger.error(f"Error consultando TMDB: {e}")
    return None

def query_omdb(title: str, year: str | None, api_key: str):
    url = "http://www.omdbapi.com/"
    params = {"apikey": api_key, "t": title}
    if year:
        params["y"] = year
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("Response") == "True":
            return {
                "source": "omdb",
                "id": data.get("imdbID"),
                "title": data.get("Title"),
                "year": data.get("Year")
            }
    except Exception as e:
        logger.error(f"Error consultando OMDB: {e}")
    return None