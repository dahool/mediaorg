import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import utils
import main

# --- TESTS DE UTILS (Lógica de strings e idiomas) ---

@pytest.mark.parametrize("input_name, expected", [
    ("Spanish", "es"),
    ("spa", "es"),
    ("en", "en"),
    ("French", "fr"),
    ("desconocido", "desconocido"), # Fallback
])
def test_get_iso_language_code(input_name, expected):
    assert utils.get_iso_language_code(input_name) == expected

def test_normalize_name():
    assert utils.normalize_name("The.Matrix 1999") == "The_Matrix_1999"
    assert utils.normalize_name("Movie   Title") == "Movie_Title"

# --- TESTS DE PROCESAMIENTO (Archivos y lógica de negocio) ---

class TestProcessExtras:
    
    @pytest.fixture
    def mock_history(self):
        return set()

    def test_ignore_sdh_subtitles(self, mock_history):
        # Simulamos un video y un subtítulo SDH
        vfile = {"stem": "Movie", "name": "Movie.mp4", "full_path": "/src/Movie.mp4", "extension": ".mp4"}
        all_files = [
            vfile,
            {"stem": "Movie.en.sdh", "name": "Movie.en.sdh.srt", "full_path": "/src/Movie.en.sdh.srt", "extension": ".srt"}
        ]
        
        # Mock de transfer_file para ver si se llama
        with patch("main.transfer_file") as mock_transfer:
            processed = main.process_extras(all_files, vfile, "Movie", "Movie_Final", Path("/dst"), mock_history)
            
            # No debe haberse procesado nada porque es SDH
            assert len(processed) == 0
            mock_transfer.assert_not_called()

    def test_rename_subtitle_with_language(self, mock_history):
        vfile = {"stem": "Gladiator", "name": "Gladiator.mkv", "full_path": "/src/Gladiator.mkv", "extension": ".mkv"}
        all_files = [
            vfile,
            {"stem": "Gladiator_Spanish", "name": "Gladiator_Spanish.srt", "full_path": "/src/Gladiator_Spanish.srt", "extension": ".srt"}
        ]
        
        with patch("main.transfer_file", return_value=True):
            processed = main.process_extras(all_files, vfile, "Gladiator", "Gladiator_New", Path("/dst"), mock_history)
            
            # Debe haber renombrado a .es.srt
            assert "Gladiator_New.es.srt" in processed

# --- TEST DE INTEGRACIÓN (Simulando FileSystem) ---
def test_full_directory_scan(tmp_path):
    # 1. Crear estructura de archivos real en carpeta temporal
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    dest.mkdir()
    
    # Creamos archivos físicos reales para que os.walk y shutil funcionen
    video_path = source / "Matrix.1999.1080p.mkv"
    video_path.write_text("contenido de video")
    
    sub_path = source / "Matrix.Spanish.srt"
    sub_path.write_text("contenido de subtitulo")
    
    sdh_path = source / "Matrix.en.sdh.srt"
    sdh_path.write_text("contenido de subtitulo sdh")

    # 2. Mockear la API para que no haga peticiones reales
    mock_info = {
        "title": "The Matrix",
        "id": "603",
        "source": "tmdb",
        "year": "1999"
    }

    # 3. Ejecución del proceso
    # Parcheamos save_json para no ensuciar el disco con archivos de cache/history reales
    with patch("main.get_movie_info", return_value=mock_info), \
         patch("main.DRY_RUN", False), \
         patch("main.ACTION", "copy"), \
         patch("main.utils.save_json"):
        
        main.process_directory(str(source), str(dest))
        
    # 4. Verificaciones
    # Obtenemos la lista de carpetas creadas en el destino
    created_dirs = [d for d in dest.iterdir() if d.is_dir()]
    assert len(created_dirs) == 1, f"Se esperaba 1 carpeta, pero se encontraron: {created_dirs}"
    
    expected_dir = created_dirs[0]
    
    # Validamos que el nombre de la carpeta contenga la info clave
    # Según el error anterior, el nombre es 'The Matrix_[tmdbid-603]_(1999)'
    assert "The Matrix" in expected_dir.name
    assert "603" in expected_dir.name
    assert "1999" in expected_dir.name
    
    # Listamos los archivos dentro de la nueva carpeta
    generated_files = [f.name for f in expected_dir.glob("*")]
    
    # A. Verificar que el video existe (usamos in para ignorar si el tag de resolución cambió)
    assert any(".mkv" in f for f in generated_files), f"Video no encontrado en: {generated_files}"
    
    # B. Verificar que el subtítulo español fue procesado y renombrado a ISO 'es'
    # Debe ser algo como 'The Matrix...es.srt'
    assert any(".es.srt" in f for f in generated_files), f"Subtítulo 'es.srt' no encontrado en: {generated_files}"
    
    # C. Verificar que el SDH fue IGNORADO
    assert not any("sdh" in f.lower() for f in generated_files), "Error: El archivo SDH fue copiado y debería ser ignorado"

    # D. Verificar que no se copiaron archivos extra inesperados (solo video y sub es)
    # Total esperado: 2 archivos
    assert len(generated_files) == 2, f"Se esperaban 2 archivos, pero hay {len(generated_files)}: {generated_files}"

if __name__ == "__main__":
    import pytest
    pytest.main()        