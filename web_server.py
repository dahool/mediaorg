import os
from flask import Flask, request, jsonify
import config_loader as config
from main import process_directory
from pathlib import Path

app = Flask(__name__)

logger = config.logger

logger.info(f"🚀 Ready (Puerto: {config.PORT})")

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "online",
    }), 200

@app.route('/copy_torrent', methods=['POST'])
def copy_torrent():
    data = request.json if request.is_json else request.form
    
    name = data.get("name")
    category = data.get("category")
    folder = data.get("folder")

    if not all([category, folder]):
        return jsonify({"error": "Faltan parámetros obligatorios (category, folder)"}), 400

    if category in config.ALLOWED_CATEGORIES:
        logger.info(f"✅ Categoría '{category}'. Iniciando proceso para: {name}")
        
        try:
            result = process_directory(folder, config.OUTPUT_DIR)
            
            return jsonify({
                "status": "success", 
                "message": f"Procesamiento iniciado para {name}",
                "processed": result,
                "folder": folder
            }), 201
        except Exception as e:
            logger.error(f"❌ Error procesando {name}: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        logger.info(f"ℹ️ Categoría '{category}' no incluída.")
        return jsonify({"status": "ignored", "message": "Categoría no permitida"}), 200

@app.route('/directories', methods=['GET'])
def list_directories():
    try:
        base_path = Path(config.MEDIA_DIR)

        def build_tree(current_path):
            node = {
                "name": current_path.name if current_path.name else "root",
                "children": []
            }
            try:
                for item in sorted(current_path.iterdir()):
                    if item.is_dir():
                        node["children"].append(build_tree(item))
            except PermissionError:
                pass
                
            return node

        tree = build_tree(base_path)
        
        return jsonify(tree["children"]), 200
    except Exception as e:
        logger.error(f"❌ Error listando directorios: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)