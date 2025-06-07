API de Verificación Facial con DeepFace y AWS
Este proyecto consiste en una API RESTful, construida con Flask, que realiza una verificación facial entre dos imágenes. Utiliza la librería DeepFace para comparar el rostro de un documento de identidad con una selfie y determina si pertenecen a la misma persona.
La aplicación está completamente contenerizada con Docker para asegurar su portabilidad y se despliega en una arquitectura serverless en AWS para una alta disponibilidad y escalabilidad.
Tecnologías Utilizadas
Backend: Python 3.10, Flask, Gunicorn, DeepFace, Pillow
Contenerización: Docker
Despliegue en Cloud: AWS IAM, AWS ECR (Elastic Container Registry), AWS App Runner
Prerrequisitos
Para ejecutar y desplegar este proyecto, necesitarás tener instalado lo siguiente en tu máquina local:
Python 3.10 o superior
Docker Desktop
AWS CLI
Estructura del Proyecto
/
├── uploads/              # Carpeta temporal para imágenes (creada automáticamente)
├── app.py                # El código principal de la aplicación Flask
├── Dockerfile            # Instrucciones para construir la imagen de Docker
├── requirements.txt      # Lista de dependencias de Python
├── .dockerignore         # Archivos a ignorar por Docker
└── README.md             # Este archivo


Configuración y Ejecución Local
Para probar la aplicación en tu máquina local sin Docker:
# 1. Clona el repositorio (si está en GitHub)
# git clone <url-del-repositorio>
# cd <nombre-del-repositorio>

# 2. Crea y activa un entorno virtual (recomendado)
# Un entorno virtual (venv) aísla las dependencias de este proyecto para evitar conflictos.
python3 -m venv venv

# Para activar el entorno en macOS o Linux:
source venv/bin/activate

# Para activar el entorno en Windows (usa Command Prompt o PowerShell):
# venv\Scripts\activate

# 3. Instala las dependencias
pip install -r requirements.txt

# 4. Ejecuta la aplicación en modo de desarrollo
python app.py


La API estará disponible en http://localhost:5001. Puedes acceder a la documentación de Swagger en http://localhost:5001/apidocs/.
Uso de Docker
La contenerización asegura que la aplicación se ejecute de la misma forma en cualquier entorno.
1. Construir la Imagen de Docker
Este comando lee el Dockerfile y empaqueta la aplicación.
⚠️ Importante para usuarios de Mac con Apple Silicon (M1/M2/M3): Es crucial usar la bandera --platform linux/amd64 para construir una imagen compatible con los servidores de AWS.
docker build --platform linux/amd64 -t verificador-facial .


2. Ejecutar el Contenedor Localmente
Este comando inicia el contenedor y mapea el puerto para que puedas acceder a él desde tu navegador.
docker run -p 5001:5001 -it verificador-facial


La API volverá a estar disponible en http://localhost:5001/apidocs/, pero esta vez corriendo dentro de un contenedor Docker aislado.
Despliegue en AWS
Este es el flujo de trabajo para desplegar la aplicación en la nube.
Paso 1: Configuración de AWS (Solo se hace una vez)
Crear Usuario IAM: Por seguridad, no uses tu cuenta raíz. En la consola de AWS, ve a IAM, crea un nuevo usuario (ej: cli-deploy-user), asígnale la política AdministratorAccess directamente, y genera un Access Key ID y un Secret Access Key. Guarda estas credenciales en un lugar seguro.
Configurar AWS CLI: En tu terminal, configura un perfil nombrado para usar estas nuevas credenciales. Esto evita conflictos y es más seguro.
aws configure --profile iamadmin
(Introduce las claves del usuario IAM que acabas de crear).
Paso 2: Subir la Imagen a Amazon ECR
Crear Repositorio ECR: En la consola de AWS, ve al servicio ECR y crea un nuevo repositorio privado llamado verificador-facial.
Autenticar y Subir: Selecciona el repositorio recién creado y haz clic en "View push commands". Ejecuta los comandos que te proporciona AWS, asegurándote de usar tu perfil de IAM en el primer comando.
# 1. Login (usando el perfil)
aws --profile iamadmin ecr get-login-password --region tu-region | docker login --username AWS --password-stdin tu-id-de-aws.dkr.ecr.tu-region.amazonaws.com

# 2. Tag (copiado de la consola)
docker tag verificador-facial:latest <tu-uri-de-ecr>/verificador-facial:latest

# 3. Push (copiado de la consola)
docker push <tu-uri-de-ecr>/verificador-facial:latest


Paso 3: Desplegar con AWS App Runner
Ir a App Runner: En la consola de AWS, navega al servicio App Runner.
Crear Servicio:
Source: Elige Container registry y luego Amazon ECR. Usa el botón Browse para seleccionar tu imagen verificador-facial:latest.
Deployment settings: Déjalo en Automatic.
Access role: Elige Create new service role.
Service settings:
Service name: servicio-verificador-facial
Virtual CPU & Memory: 1 vCPU y 3 GB (recomendado para empezar)
Port: 5001
Lanzar: Revisa la configuración y haz clic en Create & deploy.
Tras unos minutos, el estado del servicio cambiará a Running y tendrás una URL pública para acceder a tu API.
Endpoint de la API
Método
Ruta
Descripción
Body (form-data)
POST
/verify
Compara dos imágenes y verifica si los rostros coinciden.
dni: archivo de imagen<br>selfie: archivo de imagen

La documentación interactiva de Swagger está disponible en la ruta /apidocs/.
