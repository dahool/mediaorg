import os
import re
import json
from pathlib import Path

RESOLUTION_PATTERNS = ["2160p", "1080p", "720p", "480p"]

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

# --- Manejo de Archivos JSON ---

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Construcción de Nombres ---

def build_dir_name(title_norm: str, source_tag: str, year: str | None):
    dir_name = f"{title_norm}_{source_tag}"
    if year: dir_name += f"_({year})"
    return dir_name

def build_video_base(dir_name: str, resolution: str | None):
    return f"{dir_name}_[{resolution}]" if resolution else dir_name

def build_extra_name(extra_name: str, video_base: str) -> str:
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