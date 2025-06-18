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

# --- CONFIGURACIÓN MEJORADA ---

UPLOAD_FOLDER = 'uploads'
# Más backends para mayor robustez
DETECTOR_BACKENDS = ["retinaface", "mtcnn", "opencv", "ssd", "dlib"]
MODEL_NAME = "Facenet512"
CUSTOM_THRESHOLD = 0.80

# Umbrales muy permisivos para fotos reales
BLUR_THRESHOLD_DNI = 15      # Muy bajo para cédulas de baja calidad
BLUR_THRESHOLD_SELFIE = 20   # Bajo para selfies normales

# Configuración muy permisiva para detección
MIN_FACE_CONFIDENCE = 0.3    # Muy bajo para aceptar más rostros
MIN_FACE_SIZE = 40          # Tamaño mínimo muy pequeño

# --- INICIALIZACIÓN DE LA APP ---

app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
swagger = Swagger(app)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- FUNCIONES AUXILIARES MEJORADAS ---

def is_blurry(image_path, threshold=20):
    """
    Devuelve True si la imagen es borrosa según la varianza del Laplaciano.
    Incluye validaciones adicionales.
    """
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"[ERROR] No se pudo cargar la imagen: {image_path}")
            return True
        
        # Verificar que la imagen no esté vacía
        if img.size == 0:
            print(f"[ERROR] Imagen vacía: {image_path}")
            return True
            
        laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
        print(f"[BORROSIDAD] Laplacian var de {os.path.basename(image_path)}: {laplacian_var}")
        return laplacian_var < threshold
    except Exception as e:
        print(f"[ERROR] Error al verificar borrosidad: {e}")
        return True

def improve_image(input_path):
    """
    Mejora la calidad de la imagen, especialmente para fotos de cédula en B&N.
    """
    try:
        img = Image.open(input_path).convert('RGB')
        
        # Redimensionar para mejorar procesamiento
        original_size = img.size
        img.thumbnail((800, 800), Image.LANCZOS)
        
        # Mejoras muy suaves para no destruir fotos de baja calidad
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)  # Muy suave
        
        sharpener = ImageEnhance.Sharpness(img)
        img = sharpener.enhance(1.2)  # Muy suave
        
        # Para fotos de cédula en B&N, mejorar un poco el brillo
        brightness_enhancer = ImageEnhance.Brightness(img)
        img = brightness_enhancer.enhance(1.05)  # Muy sutil
        
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_improved{ext}"
        img.save(output_path, quality=85)  # Calidad moderada
        
        print(f"[MEJORA] Imagen mejorada guardada en: {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Error al mejorar imagen: {e}")
        traceback.print_exc()
        return input_path

def crop_id_photo_ecuador(input_path, output_path=None):
    """
    Recorta la foto de la cédula ecuatoriana con parámetros ajustados.
    """
    try:
        img = Image.open(input_path)
        width, height = img.size
        print(f"[RECORTE] Dimensiones originales: {width}x{height}")

        # Coordenadas ajustadas para mejor captura
        left = int(width * 0.04)   # Ligeramente más a la izquierda
        top = int(height * 0.18)   # Ligeramente más arriba
        right = int(width * 0.33)  # Ligeramente más a la derecha
        bottom = int(height * 0.58) # Ligeramente más abajo

        photo = img.crop((left, top, right, bottom))
        print(f"[RECORTE] Dimensiones recortadas: {photo.width}x{photo.height}")

        # Asegurar tamaño mínimo con mejor calidad
        if photo.width < MIN_FACE_SIZE or photo.height < MIN_FACE_SIZE:
            new_size = max(MIN_FACE_SIZE, photo.width, photo.height)
            photo = photo.resize((new_size, new_size), Image.LANCZOS)
            print(f"[RECORTE] Redimensionado a: {new_size}x{new_size}")

        if not output_path:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_foto_cedula{ext}"
        
        photo.save(output_path, quality=95)
        print(f"[RECORTE] Foto de cédula guardada en: {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Error al recortar foto de cédula: {e}")
        traceback.print_exc()
        return input_path

def detect_face_with_multiple_backends(image_path, image_type="imagen"):
    """
    Intenta detectar rostros usando múltiples backends con configuración MUY permisiva.
    """
    print(f"[DETECCIÓN] Iniciando detección de rostro en {image_type}: {os.path.basename(image_path)}")
    
    for backend in DETECTOR_BACKENDS:
        try:
            print(f"[DETECCIÓN] Probando backend: {backend}")
            
            # Configuración MUY permisiva
            enforce_detection = False  # Siempre permisivo
            
            face_obj = DeepFace.extract_faces(
                img_path=image_path,
                detector_backend=backend,
                enforce_detection=enforce_detection,
                align=True,
                grayscale=False
            )
            
            if face_obj and len(face_obj) > 0:
                # Para cédulas y fotos de baja calidad, ser muy permisivo
                confidence = face_obj[0].get('confidence', 1.0)
                print(f"[DETECCIÓN] Rostro detectado con {backend}, confianza: {confidence}")
                
                # Aceptar casi cualquier detección
                if confidence >= MIN_FACE_CONFIDENCE or image_type == "cédula":
                    print(f"[DETECCIÓN] ✓ Rostro aceptado en {image_type} usando {backend}")
                    return face_obj, backend
                else:
                    print(f"[DETECCIÓN] ⚠ Confianza baja ({confidence}) pero continuando...")
                    # Aún así, intentemos con este resultado si no hay mejor opción
                    if backend == DETECTOR_BACKENDS[-1]:  # Si es el último backend
                        print(f"[DETECCIÓN] ✓ Aceptando por ser último intento")
                        return face_obj, backend
            else:
                print(f"[DETECCIÓN] ✗ No se detectó rostro con {backend}")
                
        except Exception as e:
            print(f"[DETECCIÓN] ✗ Error con {backend}: {str(e)}")
            continue
    
    print(f"[DETECCIÓN] ✗ No se pudo detectar rostro en {image_type} con ningún backend")
    return None, None

def detect_and_crop_id_photo_area(image_path, generated_files_list):
    """
    Detecta y recorta el área de la foto en la cédula con mejor manejo de errores.
    """
    try:
        print(f"[PROCESAMIENTO] Procesando cédula: {os.path.basename(image_path)}")
        
        # Recortar área de la foto
        cropped_path = crop_id_photo_ecuador(image_path)
        generated_files_list.append(cropped_path)

        # Mejorar imagen recortada
        improved_cropped_path = improve_image(cropped_path)
        if improved_cropped_path != cropped_path:
            generated_files_list.append(improved_cropped_path)

        # Detectar rostro con múltiples backends
        face_obj, successful_backend = detect_face_with_multiple_backends(
            improved_cropped_path, "cédula"
        )

        if face_obj:
            # Guardar rostro extraído
            face_img_np = face_obj[0]['face']
            if face_img_np.max() <= 1.0:
                face_img_np = (face_img_np * 255).astype('uint8')
            
            face_img_pil = Image.fromarray(face_img_np)
            base, ext = os.path.splitext(cropped_path)
            cropped_face_path = f"{base}_face{ext}"
            face_img_pil.save(cropped_face_path, quality=95)
            generated_files_list.append(cropped_face_path)
            
            print(f"[PROCESAMIENTO] ✓ Rostro de cédula extraído exitosamente")
            return cropped_face_path
        else:
            print(f"[PROCESAMIENTO] ⚠ Usando imagen recortada mejorada como fallback")
            return improved_cropped_path

    except Exception as e:
        print(f"[ERROR] Error procesando cédula: {e}")
        traceback.print_exc()
        return None

def crop_face(image_path, generated_files_list, image_type="imagen"):
    """
    Extrae el rostro de una imagen con manejo mejorado de errores.
    """
    try:
        print(f"[PROCESAMIENTO] Procesando {image_type}: {os.path.basename(image_path)}")
        
        # Mejorar imagen original
        improved_image_path = improve_image(image_path)
        if improved_image_path != image_path:
            generated_files_list.append(improved_image_path)

        # Detectar rostro con múltiples backends
        face_obj, successful_backend = detect_face_with_multiple_backends(
            improved_image_path, image_type
        )

        if face_obj:
            # Guardar rostro extraído
            face_img_np = face_obj[0]['face']
            if face_img_np.max() <= 1.0:
                face_img_np = (face_img_np * 255).astype('uint8')
            
            face_img_pil = Image.fromarray(face_img_np)
            base, ext = os.path.splitext(image_path)
            cropped_path = f"{base}_face{ext}"
            face_img_pil.save(cropped_path, quality=95)
            generated_files_list.append(cropped_path)
            
            print(f"[PROCESAMIENTO] ✓ Rostro de {image_type} extraído exitosamente")
            return cropped_path
        else:
            print(f"[PROCESAMIENTO] ✗ No se pudo extraer rostro de {image_type}")
            return None
            
    except Exception as e:
        print(f"[ERROR] Error procesando {image_type}: {e}")
        traceback.print_exc()
        return None

# --- RUTA DE LA API MEJORADA ---

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
    
    print(f"[INICIO] Procesando solicitud {request_id}")

    try:
        # Guardar archivos subidos
        request.files['dni'].save(dni_path)
        request.files['selfie'].save(selfie_path)
        
        print(f"[ARCHIVO] DNI guardado: {os.path.getsize(dni_path)} bytes")
        print(f"[ARCHIVO] Selfie guardado: {os.path.getsize(selfie_path)} bytes")

        # Chequeo de borrosidad MUY permisivo - solo rechazar si están EXTREMADAMENTE borrosas
        dni_blurry = is_blurry(dni_path, threshold=BLUR_THRESHOLD_DNI)
        selfie_blurry = is_blurry(selfie_path, threshold=BLUR_THRESHOLD_SELFIE)
        
        # Solo rechazar si ambas están muy borrosas
        if dni_blurry and selfie_blurry:
            print("[WARNING] Ambas imágenes muy borrosas, pero intentando procesamiento...")
            # En lugar de rechazar, solo dar warning pero continuar

        # Procesar cédula (recorte + mejora + rostro)
        dni_face_path = detect_and_crop_id_photo_area(dni_path, files_to_clean)

        # Procesar selfie (mejora + rostro)
        selfie_face_path = crop_face(selfie_path, files_to_clean, "selfie")

        # Validar resultados de forma MUY permisiva
        if not dni_face_path and not selfie_face_path:
            return jsonify({
                'error': 'No se pudieron procesar las imágenes. Por favor, intenta con fotos donde se vea claramente el rostro.',
                'details': 'No se detectaron rostros en ninguna imagen'
            }), 400
        elif not dni_face_path:
            # Si no se detectó rostro en cédula, intentar con la imagen original mejorada
            print("[FALLBACK] Intentando verificación con imagen de cédula sin extracción de rostro")
            dni_face_path = improve_image(dni_path)
            files_to_clean.append(dni_face_path)
            
        elif not selfie_face_path:
            # Si no se detectó rostro en selfie, intentar con la imagen original mejorada
            print("[FALLBACK] Intentando verificación con selfie sin extracción de rostro")
            selfie_face_path = improve_image(selfie_path)
            files_to_clean.append(selfie_face_path)

        print(f"[VERIFICACIÓN] Iniciando comparación facial")
        print(f"[VERIFICACIÓN] Rostro cédula: {os.path.basename(dni_face_path)}")
        print(f"[VERIFICACIÓN] Rostro selfie: {os.path.basename(selfie_face_path)}")

        # Verificación facial con configuración muy permisiva
        verification_successful = False
        result = None
        
        try:
            # Intenta primero con detección automática
            result = DeepFace.verify(
                img1_path=dni_face_path,
                img2_path=selfie_face_path,
                model_name=MODEL_NAME,
                detector_backend='skip',  # Ya tenemos los rostros extraídos
                distance_metric='cosine',
                enforce_detection=False  # Muy permisivo
            )
            verification_successful = True
            print(f"[VERIFICACIÓN] ✓ Comparación completada exitosamente")
        except Exception as e:
            print(f"[VERIFICACIÓN] ⚠ Error en verificación con 'skip', intentando con detector automático: {e}")
            
            # Segundo intento con detector automático si falla el skip
            try:
                result = DeepFace.verify(
                    img1_path=dni_face_path,
                    img2_path=selfie_face_path,
                    model_name=MODEL_NAME,
                    detector_backend='opencv',  # Backend más permisivo
                    distance_metric='cosine',
                    enforce_detection=False
                )
                verification_successful = True
                print(f"[VERIFICACIÓN] ✓ Comparación completada con detector automático")
            except Exception as e2:
                print(f"[VERIFICACIÓN] ✗ Error final en verificación: {e2}")
                return jsonify({
                    'error': 'No se pudo completar la verificación. Las imágenes podrían no tener la calidad suficiente.',
                    'details': f"Error de verificación: {str(e2)}"
                }), 400

        if verification_successful and result:
            distance_value = float(result['distance'])
            is_verified_custom = bool(distance_value <= CUSTOM_THRESHOLD)
            
            print(f"[RESULTADO] Distancia: {distance_value}")
            print(f"[RESULTADO] Umbral: {CUSTOM_THRESHOLD}")
            print(f"[RESULTADO] Verificado: {is_verified_custom}")

            if is_verified_custom:
                confidence_percentage = max(0, min(100, (1 - distance_value) * 100))
                response = {
                    "success": True,
                    "verified": True,
                    "message": "¡Verificación exitosa! La selfie coincide con la foto del documento.",
                    "distance": round(distance_value, 4),
                    "confidence": round(confidence_percentage, 2),
                    "threshold": CUSTOM_THRESHOLD,
                    "model": MODEL_NAME,
                    "similarity_metric": "cosine_distance"
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
                    "similarity_metric": "cosine_distance"
                }

            return jsonify(response), 200
        else:
            return jsonify({
                'error': 'No se pudo completar la verificación facial.',
                'details': 'Error en el proceso de comparación'
            }), 500

    except Exception as e:
        print(f"[ERROR GENERAL] {e}")
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': 'Ocurrió un error interno del servidor. Por favor, intenta nuevamente.', 
            'details': str(e)
        }), 500

    finally:
        # Limpiar archivos temporales
        cleaned_count = 0
        for file_path in files_to_clean:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    cleaned_count += 1
                except Exception as e:
                    print(f"[LIMPIEZA] Error eliminando {file_path}: {e}")
        print(f"[LIMPIEZA] {cleaned_count} archivos temporales eliminados")



# --- EJECUCIÓN DE LA APP ---

if __name__ == "__main__":
    print(f"[INICIO] Iniciando servidor de reconocimiento facial")
    print(f"[CONFIG] Modelo: {MODEL_NAME}")
    print(f"[CONFIG] Umbral: {CUSTOM_THRESHOLD}")
    print(f"[CONFIG] Backends: {DETECTOR_BACKENDS}")
    app.run(host='0.0.0.0', port=5001, debug=True)  # Debug=True para mejor logging