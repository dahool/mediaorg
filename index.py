import os
import re
import json
import shutil
import requests
from pathlib import Path

CACHE_FILE = "movie_cache.json"
CONFIG_FILE = "config.json"
HISTORY_FILE = "processed_history.json"

VIDEO_EXTENSIONS = [".mp4", ".mkv"]
RESOLUTION_PATTERNS = ["2160p", "1080p", "720p", "480p"]

# -------------------------------
# Configuración
# -------------------------------

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"No se encontró {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()
TMDB_API_KEY = config.get("tmdb_api_key")
OMDB_API_KEY = config.get("omdb_api_key")
MEDIA_DIR = os.path.abspath(config.get("media_directory", "."))
OUTPUT_DIR = os.path.abspath(config.get("output_directory", MEDIA_DIR))
ACTION = config.get("action", "move").lower()
DRY_RUN = config.get("dry_run", True)

# -------------------------------
# Registro de Historial (Usa rutas absolutas ahora)
# -------------------------------

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f)) # Usamos set para búsqueda O(1)
    return set()

def save_to_history(full_path):
    history = load_history()
    if full_path not in history:
        history.add(full_path)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(history), f, indent=2, ensure_ascii=False)

# -------------------------------
# Utilidades y Consultas (Sin cambios)
# -------------------------------

def normalize_name(name: str) -> str:
    name = re.sub(r"[ .]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")

def extract_resolution(filename: str):
    for pat in RESOLUTION_PATTERNS:
        if re.search(pat, filename, re.IGNORECASE):
            return pat.upper()
    return None

def extract_year_resolution(filename: str):
    year_match = re.search(r"(19|20)\d{2}", filename)
    year = year_match.group(0) if year_match else None
    return year, extract_resolution(filename)

def title_for_query_and_key(filename_stem: str):
    m = re.search(r"(19|20)\d{2}", filename_stem)
    cut = filename_stem[:m.start()] if m else filename_stem
    title_query = re.sub(r"[^\w]", " ", cut).strip()
    return title_query, normalize_name(title_query)

def load_cache():
    return json.load(open(CACHE_FILE, "r", encoding="utf-8")) if os.path.exists(CACHE_FILE) else {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def query_tmdb(title: str, year: str | None):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": title}
    if year:
        params["year"] = year
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
    return None

def query_omdb(title: str, year: str | None):
    url = "http://www.omdbapi.com/"
    params = {"apikey": OMDB_API_KEY, "t": title}
    if year:
        params["y"] = year
    r = requests.get(url, params=params, timeout=15)
    data = r.json()
    if data.get("Response") == "True":
        return {
            "source": "omdb",
            "id": data.get("imdbID"),
            "title": data.get("Title"),
            "year": data.get("Year")
        }
    return None

def get_movie_info(cache: dict, filename: str):
    base_stem = Path(filename).stem
    if base_stem in cache:
        return cache[base_stem]

    year, _ = extract_year_resolution(base_stem)
    title_query, _ = title_for_query_and_key(base_stem)

    info = query_tmdb(title_query, year) or query_omdb(title_query, year)
    if not info:
        return None

    # Normalizar título
    title_norm = normalize_name(info.get("title"))

    # Guardar en cache
    cache[base_stem] = {
        "source": info["source"],
        "id": info["id"],
        "title": title_norm,
        "year": year
    }
    save_cache(cache)
    return cache[base_stem]

# -------------------------------
# Lógica de Construcción
# -------------------------------

def build_dir_name(title_norm: str, source_tag: str, year: str | None):
    dir_name = f"{title_norm}_{source_tag}"
    if year: dir_name += f"_({year})"
    return dir_name

def build_video_base(dir_name: str, resolution: str | None):
    return f"{dir_name}_[{resolution}]" if resolution else dir_name

def build_extra_name(extra_name: str, video_base: str, dir_name: str, resolution: str | None) -> str:
    suffixes = Path(extra_name).suffixes
    if "".join(suffixes).lower().endswith(".srt"):
        new_name = video_base
        if len(suffixes) >= 2 and re.fullmatch(r"\.[a-zA-Z]{2}", suffixes[-2]):
            new_name += suffixes[-2] + ".srt"
        else:
            new_name += ".srt"
        return new_name
    
    ext = Path(extra_name).suffix
    stem = Path(extra_name).stem
    suffix_part = stem.split("-")[-1] if "-" in stem else "extra"
    return f"{video_base}-{normalize_name(suffix_part)}{ext}"

# -------------------------------
# Procesamiento
# -------------------------------

def process_directory(source_path: str, destination_path: str):
    cache = load_cache()
    history = load_history()
    all_files_info = []

    print(f"🔍 Escaneando recursivamente: {source_path}...")
    for root, _, filenames in os.walk(source_path):
        if os.path.abspath(root).startswith(destination_path) and destination_path != source_path:
            continue
        for f in filenames:
            abs_f = os.path.abspath(os.path.join(root, f))
            all_files_info.append({"name": f, "full_path": abs_f, "stem": Path(f).stem})

    video_files = [fi for fi in all_files_info if Path(fi["name"]).suffix.lower() in VIDEO_EXTENSIONS]
    transfer_func = shutil.move if ACTION == "move" else shutil.copy2

    for vfile in video_files:
        if vfile["full_path"] in history: continue

        info = get_movie_info(cache, vfile["name"]) 
        if not info: continue

        # Control de duplicados en la carpeta de destino de ESTA película
        processed_destinations = set()

        resolution = extract_resolution(vfile["name"])
        _, title_key = title_for_query_and_key(vfile["stem"])
        
        source_tag = f"[{info['source']}id-{info['id']}]"
        dir_name = build_dir_name(info['title'], source_tag, info['year'])
        target_dir = Path(destination_path) / dir_name
        
        if not DRY_RUN: target_dir.mkdir(parents=True, exist_ok=True)

        video_base = build_video_base(dir_name, resolution)
        new_video_name = f"{video_base}{Path(vfile['name']).suffix.lower()}"
        
        print(f"🎬 {ACTION.capitalize()}: {vfile['name']} -> {new_video_name}")
        if not DRY_RUN:
            transfer_func(vfile["full_path"], target_dir / new_video_name)
            save_to_history(vfile["full_path"])
            processed_destinations.add(new_video_name)

        # Buscar extras
        for extra_file in all_files_info:
            if extra_file["full_path"] in history or extra_file["full_path"] == vfile["full_path"]:
                continue
            
            if title_for_query_and_key(extra_file["stem"])[1].startswith(title_key):
                new_extra_name = build_extra_name(extra_file["name"], video_base, dir_name, resolution)
                
                # --- EVITAR EXTRAS DUPLICADOS ---
                if new_extra_name in processed_destinations:
                    print(f"  ⚠️ Ignorando extra duplicado en destino: {extra_file['name']}")
                    continue
                
                print(f"  📎 Extra: {extra_file['name']} -> {new_extra_name}")
                if not DRY_RUN:
                    try:
                        transfer_func(extra_file["full_path"], target_dir / new_extra_name)
                        save_to_history(extra_file["full_path"])
                        processed_destinations.add(new_extra_name)
                    except Exception as e:
                        print(f"  Error: {e}")

if __name__ == "__main__":
    process_directory(MEDIA_DIR, OUTPUT_DIR)