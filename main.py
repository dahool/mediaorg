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

def get_all_files(source_path, destination_path):
    """Escanea el directorio y retorna una lista de diccionarios con info de archivos."""
    files_info = []
    logger.info(f"🔍 Escaneando: {source_path}...")
    
    for root, _, filenames in os.walk(source_path):
        # Evitar escanear el destino si está dentro del origen
        if os.path.abspath(root).startswith(str(destination_path)) and destination_path != source_path:
            continue
        for f in filenames:
            abs_f = os.path.abspath(os.path.join(root, f))
            files_info.append({
                "name": f, 
                "full_path": abs_f, 
                "stem": Path(f).stem,
                "extension": Path(f).suffix.lower()
            })
    return files_info

def process_single_video(vfile, all_files, cache, history, destination_path):
    """Lógica para procesar un video individual y sus extras."""
    info = get_movie_info(cache, vfile["name"])
    if not info:
        return []

    # Preparar rutas y nombres
    resolution = utils.extract_resolution(vfile["name"])
    _, title_key = utils.title_for_query_and_key(vfile["stem"])
    source_tag = f"[{info['source']}id-{info['id']}]"
    dir_name = utils.build_dir_name(info['title'], source_tag, info['year'])
    target_dir = Path(destination_path) / dir_name
    video_base = utils.build_video_base(dir_name, resolution)
    
    if not DRY_RUN: 
        target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Procesar el video principal
    new_video_name = f"{video_base}{vfile['extension']}"
    processed = []
    
    if transfer_file(vfile["full_path"], target_dir / new_video_name, history):
        processed.append(new_video_name)
        
        # 2. Procesar extras relacionados
        extras = process_extras(all_files, vfile, title_key, video_base, target_dir, history)
        processed.extend(extras)
        
    return processed

def transfer_file(source, target, history):
    """Maneja el movimiento/copia físico y actualiza el historial."""
    transfer_func = shutil.move if ACTION == "move" else shutil.copy2
    
    logger.info(f"🎬 {ACTION.capitalize()}: {Path(source).name} -> {target.name}")
    if DRY_RUN:
        logger.info(f"Dry run enabled")
        return True
        
    try:
        transfer_func(source, target)
        history.add(str(source))
        utils.save_json(HISTORY_FILE, list(history))
        return True
    except Exception as e:
        logger.error(f"❌ Error transfiriendo {source}: {e}")
        return False

def process_extras(all_files, vfile, title_key, video_base, target_dir, history):
    """Busca y transfiere archivos adjuntos (subs, nfo, etc)."""
    processed_extras = []
    for extra in all_files:
        if extra["full_path"] in history or extra["full_path"] == vfile["full_path"]:
            continue
        
        if utils.title_for_query_and_key(extra["stem"])[1].startswith(title_key):
            new_name = utils.build_extra_name(extra["name"], video_base)
            if transfer_file(extra["full_path"], target_dir / new_name, history):
                processed_extras.append(new_name)
    return processed_extras

def process_directory(source_path, destination_path):
    # Cargar estado
    cache = utils.load_json(CACHE_FILE, {})
    history = set(utils.load_json(HISTORY_FILE, []))
    
    # Obtener archivos
    all_files = get_all_files(source_path, destination_path)
    video_files = [f for f in all_files if f["extension"] in VIDEO_EXTENSIONS]
    
    results = []
    for vfile in video_files:
        if vfile["full_path"] in history:
            continue
            
        processed = process_single_video(vfile, all_files, cache, history, destination_path)
        results.extend(processed)
        
    logger.info(f"🏁 Proceso finalizado. Archivos procesados: {len(results)}")
    return results

if __name__ == "__main__":
    process_directory(MEDIA_DIR, OUTPUT_DIR)