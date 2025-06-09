import os
import uuid
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from deepface import DeepFace
from flasgger import Swagger, swag_from
from PIL import Image, ImageEnhance
from deepface.commons import functions

# --- CONFIGURACIÓN ---

# Carpeta para almacenar archivos temporales
UPLOAD_FOLDER = 'uploads'

# Backends de detección a probar, en orden de preferencia.
# 'retinaface' es rápido, 'mtcnn' es más robusto pero más lento.
DETECTOR_BACKENDS = ["retinaface", "mtcnn"] 

# Modelo de DeepFace para la verificación. ArcFace es el estándar de oro.
MODEL_NAME = "ArcFace"

# Umbral de distancia personalizado. La distancia es una medida de qué tan diferentes son dos caras.
# Un valor más bajo significa que son más similares.
# El umbral recomendado por ArcFace es 0.68. Puedes ajustarlo según tus necesidades.
# Un umbral más alto (ej. 0.75) es más permisivo (acepta más), uno más bajo es más estricto.
CUSTOM_THRESHOLD = 0.70 


# --- INICIALIZACIÓN DE LA APP ---

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
swagger = Swagger(app)

# Crear la carpeta de subidas si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- FUNCIONES AUXILIARES ---

def improve_image(input_path):
    try:
        img = Image.open(input_path).convert('RGB')
        img.thumbnail((800, 800), Image.LANCZOS)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        sharpener = ImageEnhance.Sharpness(img)
        img = sharpener.enhance(1.5)
        
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_improved{ext}"
        img.save(output_path)
        
        return output_path
    except Exception:
        traceback.print_exc()
        return input_path

def detect_and_crop_id_photo_area(image_path, generated_files_list):
   
    print("Usando método de detección genérico para la cédula. Para mayor precisión, implemente 'detect_and_crop_id_photo_area'.")
    return crop_face(image_path, generated_files_list, "cédula")

def crop_face(image_path, generated_files_list, image_type="imagen"):
    
    try:
        improved_image_path = improve_image(image_path)
        if improved_image_path != image_path:
             generated_files_list.append(improved_image_path)

        face_obj = None
        for backend in DETECTOR_BACKENDS:
            try:
                # `extract_faces` es más directo para obtener el rostro
                face_obj = DeepFace.extract_faces(
                    img_path=improved_image_path,
                    detector_backend=backend,
                    enforce_detection=True,
                    align=True
                )
                if face_obj and face_obj[0]['confidence'] > 0.9: # Solo aceptar detecciones de alta confianza
                    print(f"Rostro detectado en '{os.path.basename(image_path)}' usando {backend}.")
                    break
                else:
                    face_obj = None # Descartar si la confianza es baja
            except Exception:
                print(f"No se detectó rostro en la {image_type} con {backend}. Intentando con el siguiente...")
                continue

        if face_obj:
            face_img_np = face_obj[0]['face']
            face_img_pil = Image.fromarray((face_img_np * 255).astype('uint8'))
            
            base, ext = os.path.splitext(image_path)
            cropped_path = f"{base}_face{ext}"
            face_img_pil.save(cropped_path)
            generated_files_list.append(cropped_path)
            
            return cropped_path
        else:
            return None
    except Exception:
        traceback.print_exc()
        return None

# --- RUTA DE LA API ---

@app.route('/verify', methods=['POST'])
@swag_from({
    'summary': 'Verifica si dos imágenes (cédula y selfie) pertenecen a la misma persona.',
    'consumes': ['multipart/form-data'],
    'parameters': [
        {
            'name': 'dni', 'in': 'formData', 'type': 'file', 'required': True,
            'description': 'Foto del documento de identidad (JPG/JPEG/PNG)'
        },
        {
            'name': 'selfie', 'in': 'formData', 'type': 'file', 'required': True,
            'description': 'Selfie de la persona (JPG/JPEG/PNG)'
        }
    ],
    'responses': {
        200: {'description': 'Resultado de la verificación facial.'},
        400: {'description': 'Petición incorrecta (faltan imágenes, no se detectó rostro, etc.).'},
        500: {'description': 'Error interno del servidor.'}
    }
})
def verify():
    if 'dni' not in request.files or 'selfie' not in request.files:
        return jsonify({'error': 'Las dos imágenes (dni y selfie) son requeridas.'}), 400

    # Generar nombres de archivo únicos para esta petición
    request_id = str(uuid.uuid4())
    dni_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{request_id}_dni.jpg")
    selfie_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{request_id}_selfie.jpg")

    files_to_clean = [dni_path, selfie_path]

    try:
        request.files['dni'].save(dni_path)
        request.files['selfie'].save(selfie_path)

        # 1. Procesar la cédula
        dni_face_path = detect_and_crop_id_photo_area(dni_path, files_to_clean)
        
        # 2. Procesar la selfie
        selfie_face_path = crop_face(selfie_path, files_to_clean, "selfie")

        # 3. Validar si los rostros fueron detectados con errores específicos
        if not dni_face_path and not selfie_face_path:
            return jsonify({'error': 'No se pudo detectar un rostro claro en la cédula ni en la selfie. Por favor, intente con mejores fotos.'}), 400
        if not dni_face_path:
            return jsonify({'error': 'No se pudo detectar un rostro claro en la foto de la cédula. Intente con una foto sin reflejos y donde el sello no cubra la cara.'}), 400
        if not selfie_face_path:
            return jsonify({'error': 'No se pudo detectar un rostro claro en la selfie. Por favor, tómela en un lugar bien iluminado, de frente y sin accesorios.'}), 400
            
        # 4. Realizar la verificación con el modelo ArcFace
        result = DeepFace.verify(
            img1_path=dni_face_path,
            img2_path=selfie_face_path,
            model_name=MODEL_NAME,
            detector_backend='skip' # Ya hemos detectado y recortado el rostro
        )
        
        # 5. Aplicar nuestra lógica de decisión personalizada
        is_verified_custom = bool(result['distance'] <= CUSTOM_THRESHOLD)
        
        # 6. Preparar una respuesta completa y útil
        response = {
            "success": True,
            "verified": is_verified_custom,
            # Convertimos el numpy.float64 a un float de Python antes de redondear
            "distance": round(float(result['distance']), 4),
            "threshold": CUSTOM_THRESHOLD,
            "model": MODEL_NAME,
            "similarity_metric": "distance"
        }
        
        return jsonify(response), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Ocurrió un error interno del servidor.', 'details': str(e)}), 500

    finally:
        # Limpiar todos los archivos generados para esta petición
        for file_path in files_to_clean:
            if os.path.exists(file_path):
                os.remove(file_path)

# --- EJECUCIÓN DE LA APP ---
if __name__ == "__main__":
    # Para producción, usa un servidor WSGI como Gunicorn o uWSGI
    # Ejemplo: gunicorn --bind 0.0.0.0:5001 wsgi:app
    app.run(host='0.0.0.0', port=5001, debug=False)