import os
import shutil
from pathlib import Path

import utils
import api_client
import config_loader as config

logger = config.logger

CACHE_FILE = config.CACHE_FILE
HISTORY_FILE = config.HISTORY_FILE
VIDEO_EXTENSIONS = [".mp4", ".mkv"]

TMDB_API_KEY = config.TMDB_API_KEY
OMDB_API_KEY = config.OMDB_API_KEY
MEDIA_DIR = config.MEDIA_DIR
OUTPUT_DIR = config.OUTPUT_DIR
ACTION = config.ACTION
DRY_RUN = config.DRY_RUN

def get_movie_info(cache, filename):
    base_stem = Path(filename).stem
    if base_stem in cache:
        return cache[base_stem]

    year, _ = utils.extract_year_resolution(base_stem)
    title_query, _ = utils.title_for_query_and_key(base_stem)

    info = (api_client.query_tmdb(title_query, year, TMDB_API_KEY) or 
            api_client.query_omdb(title_query, year, OMDB_API_KEY))
    
    if not info: return None

    info["title"] = utils.normalize_name(info["title"])
    info["year"] = year # Mantener año original si es necesario
    
    cache[base_stem] = info
    utils.save_json(CACHE_FILE, cache)
    return info

def process_directory(source_path, destination_path):
    cache = utils.load_json(CACHE_FILE, {})
    history = set(utils.load_json(HISTORY_FILE, []))
    all_files_info = []

    logger.info(f"🔍 Escaneando: {source_path}...")
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

        processed_destinations = set()
        resolution = utils.extract_resolution(vfile["name"])
        _, title_key = utils.title_for_query_and_key(vfile["stem"])
        
        source_tag = f"[{info['source']}id-{info['id']}]"
        dir_name = utils.build_dir_name(info['title'], source_tag, info['year'])
        target_dir = Path(destination_path) / dir_name
        
        if not DRY_RUN: target_dir.mkdir(parents=True, exist_ok=True)

        video_base = utils.build_video_base(dir_name, resolution)
        new_video_name = f"{video_base}{Path(vfile['name']).suffix.lower()}"
        
        logger.info(f"🎬 {ACTION.capitalize()}: {vfile['name']} -> {new_video_name}")
        if not DRY_RUN:
            transfer_func(vfile["full_path"], target_dir / new_video_name)
            history.add(vfile["full_path"])
            utils.save_json(HISTORY_FILE, list(history))
            processed_destinations.add(new_video_name)

        # Extras
        for extra_file in all_files_info:
            if extra_file["full_path"] in history or extra_file["full_path"] == vfile["full_path"]:
                continue
            
            if utils.title_for_query_and_key(extra_file["stem"])[1].startswith(title_key):
                new_extra_name = utils.build_extra_name(extra_file["name"], video_base)
                
                if new_extra_name in processed_destinations:
                    continue
                
                logger.info(f"  📎 Extra: {extra_file['name']} -> {new_extra_name}")
                if not DRY_RUN:
                    try:
                        transfer_func(extra_file["full_path"], target_dir / new_extra_name)
                        history.add(extra_file["full_path"])
                        utils.save_json(HISTORY_FILE, list(history))
                        processed_destinations.add(new_extra_name)
                    except Exception as e:
                        logger.error(f"  Error: {e}")

if __name__ == "__main__":
    process_directory(MEDIA_DIR, OUTPUT_DIR)