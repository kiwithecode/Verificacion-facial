import os
import uuid
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from deepface import DeepFace
from flasgger import Swagger, swag_from
from PIL import Image, ImageEnhance
import numpy as np
import cv2

# --- CONFIGURACIÓN ---

UPLOAD_FOLDER = 'uploads'
DETECTOR_BACKENDS = ["retinaface", "mtcnn"]
MODEL_NAME = "Facenet512"
CUSTOM_THRESHOLD = 0.80

BLUR_THRESHOLD_DNI = 40      # Puedes ajustar según tus pruebas
BLUR_THRESHOLD_SELFIE = 40   # Puedes usar valores distintos si lo deseas

# --- INICIALIZACIÓN DE LA APP ---

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
swagger = Swagger(app)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- FUNCIONES AUXILIARES ---

def is_blurry(image_path, threshold=40):
    """
    Devuelve True si la imagen es borrosa según la varianza del Laplaciano.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return True  # Si falla la carga, la tratamos como borrosa
    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    print(f"[BORROSIDAD] Laplacian var de {os.path.basename(image_path)}: {laplacian_var}")
    return laplacian_var < threshold

def improve_image(input_path):
    try:
        img = Image.open(input_path).convert('RGB')
        img.thumbnail((800, 800), Image.LANCZOS)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)
        sharpener = ImageEnhance.Sharpness(img)
        img = sharpener.enhance(2.0)
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_improved{ext}"
        img.save(output_path)
        return output_path
    except Exception:
        traceback.print_exc()
        return input_path

def crop_id_photo_ecuador(input_path, output_path=None):
    img = Image.open(input_path)
    width, height = img.size

    left = int(width * 0.045)
    top = int(height * 0.19)
    right = int(width * 0.32)
    bottom = int(height * 0.56)

    photo = img.crop((left, top, right, bottom))

    # Asegura tamaño mínimo
    if photo.width < 120 or photo.height < 120:
        photo = photo.resize((120, 120), Image.LANCZOS)

    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_foto_cedula{ext}"
    photo.save(output_path)
    return output_path

def detect_and_crop_id_photo_area(image_path, generated_files_list):
    try:
        cropped_path = crop_id_photo_ecuador(image_path)
        generated_files_list.append(cropped_path)

        # Mejora de imagen
        improved_cropped_path = improve_image(cropped_path)
        if improved_cropped_path != cropped_path:
            generated_files_list.append(improved_cropped_path)

        face_obj = None
        for backend in DETECTOR_BACKENDS:
            try:
                face_obj = DeepFace.extract_faces(
                    img_path=improved_cropped_path,
                    detector_backend=backend,
                    enforce_detection=True,
                    align=True
                )
                if face_obj and face_obj[0]['confidence'] > 0.8:
                    print(f"Rostro detectado en la foto de la cédula usando {backend}.")
                    break
                else:
                    face_obj = None
            except Exception:
                print(f"No se detectó rostro en la foto de cédula con {backend}. Intentando el siguiente...")
                continue

        if face_obj:
            face_img_np = face_obj[0]['face']
            if face_img_np.max() <= 1.0:
                face_img_np = (face_img_np * 255).astype('uint8')
            face_img_pil = Image.fromarray(face_img_np)
            base, ext = os.path.splitext(cropped_path)
            cropped_face_path = f"{base}_face{ext}"
            face_img_pil.save(cropped_face_path)
            generated_files_list.append(cropped_face_path)
            return cropped_face_path
        else:
            print("No se pudo detectar rostro en la foto recortada de la cédula. Devolviendo recorte para fallback.")
            return improved_cropped_path

    except Exception:
        traceback.print_exc()
        return None

def crop_face(image_path, generated_files_list, image_type="imagen"):
    try:
        improved_image_path = improve_image(image_path)
        if improved_image_path != image_path:
            generated_files_list.append(improved_image_path)

        face_obj = None
        for backend in DETECTOR_BACKENDS:
            try:
                face_obj = DeepFace.extract_faces(
                    img_path=improved_image_path,
                    detector_backend=backend,
                    enforce_detection=True,
                    align=True
                )
                if face_obj and face_obj[0]['confidence'] > 0.9:
                    print(f"Rostro detectado en '{os.path.basename(image_path)}' usando {backend}.")
                    break
                else:
                    face_obj = None
            except Exception:
                print(f"No se detectó rostro en la {image_type} con {backend}. Intentando con el siguiente...")
                continue

        if face_obj:
            face_img_np = face_obj[0]['face']
            if face_img_np.max() <= 1.0:
                face_img_np = (face_img_np * 255).astype('uint8')
            face_img_pil = Image.fromarray(face_img_np)
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
        400: {'description': 'Petición incorrecta (faltan imágenes, imagen borrosa, no se detectó rostro, etc.).'},
        500: {'description': 'Error interno del servidor.'}
    }
})
def verify():
    if 'dni' not in request.files or 'selfie' not in request.files:
        return jsonify({'error': 'Las dos imágenes (cédula y selfie) son requeridas.'}), 400

    request_id = str(uuid.uuid4())
    dni_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{request_id}_dni.jpg")
    selfie_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{request_id}_selfie.jpg")

    files_to_clean = [dni_path, selfie_path]

    try:
        request.files['dni'].save(dni_path)
        request.files['selfie'].save(selfie_path)

        # Chequeo de borrosidad
        if is_blurry(dni_path, threshold=BLUR_THRESHOLD_DNI):
            return jsonify({
                'error': 'La foto del documento está borrosa. Por favor, vuelve a tomar una foto asegurándote de que esté bien enfocada, con buena luz y sin reflejos.'
            }), 400

        if is_blurry(selfie_path, threshold=BLUR_THRESHOLD_SELFIE):
            return jsonify({
                'error': 'La selfie está borrosa. Por favor, vuelve a tomar la selfie asegurándote de que esté bien enfocada, con buena luz, sin objetos que tapen tu cara y de frente.'
            }), 400

        # Procesar cédula (recorte + mejora + rostro)
        dni_face_path = detect_and_crop_id_photo_area(dni_path, files_to_clean)

        # Procesar selfie (mejora + rostro)
        selfie_face_path = crop_face(selfie_path, files_to_clean, "selfie")

        # Validar si los rostros fueron detectados
        if not dni_face_path and not selfie_face_path:
            return jsonify({'error': 'No se pudo detectar un rostro claro en la cédula ni en la selfie. Por favor, intenta con fotos más nítidas y bien iluminadas.'}), 400
        if not dni_face_path:
            return jsonify({'error': 'No se pudo detectar un rostro claro en la foto de la cédula. Por favor, asegúrate de que no haya reflejos, sellos sobre la cara y que esté bien enfocada.'}), 400
        if not selfie_face_path:
            return jsonify({'error': 'No se pudo detectar un rostro claro en la selfie. Tómala de frente, bien iluminada y sin accesorios.'}), 400

        # Verificación facial
        result = DeepFace.verify(
            img1_path=dni_face_path,
            img2_path=selfie_face_path,
            model_name=MODEL_NAME,
            detector_backend='skip'
        )
        distance_value = float(result['distance'])
        is_verified_custom = bool(result['distance'] <= CUSTOM_THRESHOLD)

        if is_verified_custom:
            response = {
                "success": True,
                "verified": True,
                "message": "¡Verificación exitosa! La selfie coincide con la foto del documento.",
                "distance": round(distance_value, 4),
                "threshold": CUSTOM_THRESHOLD,
                "model": MODEL_NAME,
                "similarity_metric": "distance"
            }
        else:
            response = {
                "success": True,
                "verified": False,
                "message": (
                    "No pudimos validar que la selfie corresponda con la foto del documento. "
                    "Por favor, asegúrate de que ambos rostros sean de la misma persona, "
                    "toma fotos claras y de frente. Si el problema persiste, contacta soporte."
                ),
                "distance": round(distance_value, 4),
                "threshold": CUSTOM_THRESHOLD,
                "model": MODEL_NAME,
                "similarity_metric": "distance"
            }

        return jsonify(response), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Ocurrió un error interno del servidor.', 'details': str(e)}), 500

    finally:
        for file_path in files_to_clean:
            if os.path.exists(file_path):
                os.remove(file_path)

# --- EJECUCIÓN DE LA APP ---

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=False)
