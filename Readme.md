¡Claro! Aquí tienes el **README.md** en formato Markdown, listo para tu repositorio en GitHub:

---

```markdown
# API de Verificación Facial con DeepFace y AWS

Este proyecto es una API RESTful construida con **Flask** que realiza verificación facial entre dos imágenes. Utiliza la librería **DeepFace** para comparar el rostro de un documento de identidad con una selfie y determina si pertenecen a la misma persona.

La aplicación está contenerizada con **Docker** y se despliega en una arquitectura **serverless** en AWS, asegurando alta disponibilidad y escalabilidad.

---

## Tecnologías Utilizadas

- **Backend:** Python 3.10, Flask, Gunicorn, DeepFace, Pillow  
- **Contenerización:** Docker  
- **Despliegue en Cloud:** AWS IAM, AWS ECR (Elastic Container Registry), AWS App Runner

---

## Estructura del Proyecto

```

/
├── uploads/              # Carpeta temporal para imágenes (creada automáticamente)
├── app.py                # Código principal de la aplicación Flask
├── Dockerfile            # Instrucciones para construir la imagen de Docker
├── requirements.txt      # Lista de dependencias de Python
├── .dockerignore         # Archivos a ignorar por Docker
└── README.md             # Este archivo

````

---

## Prerrequisitos

Para ejecutar y desplegar este proyecto necesitas tener instalado:

- Python 3.10 o superior  
- Docker Desktop  
- AWS CLI

---

## Configuración y Ejecución Local

1. **Clona el repositorio**
   ```bash
   git clone <url-del-repositorio>
   cd <nombre-del-repositorio>
````

2. **Crea y activa un entorno virtual**

   * **macOS/Linux:**

     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   * **Windows (CMD o PowerShell):**

     ```cmd
     python -m venv venv
     venv\Scripts\activate
     ```

3. **Instala las dependencias**

   ```bash
   pip install -r requirements.txt
   ```

4. **Ejecuta la aplicación**

   ```bash
   python app.py
   ```

* La API estará disponible en [http://localhost:5001](http://localhost:5001)
* Documentación Swagger: [http://localhost:5001/apidocs/](http://localhost:5001/apidocs/)

---

## Uso de Docker

La contenerización garantiza que la aplicación se ejecute igual en cualquier entorno.

1. **Construir la Imagen de Docker**

   > **IMPORTANTE (Mac M1/M2/M3):**
   > Usa la bandera `--platform linux/amd64` para compatibilidad con AWS.

   ```bash
   docker build --platform linux/amd64 -t verificador-facial .
   ```

2. **Ejecutar el Contenedor Localmente**

   ```bash
   docker run -p 5001:5001 -it verificador-facial
   ```

* Accede a la API en [http://localhost:5001/apidocs/](http://localhost:5001/apidocs/)

---

## Despliegue en AWS

### 1. Configuración de AWS (Solo una vez)

* **Crea un usuario IAM:**
  En AWS IAM, crea un usuario (ej: `cli-deploy-user`) con permisos de `AdministratorAccess`.
  Genera Access Key ID y Secret Access Key.

* **Configura AWS CLI con un perfil nombrado:**

  ```bash
  aws configure --profile iamadmin
  ```

  Ingresa las credenciales del usuario IAM creado.

---

### 2. Subir la Imagen a Amazon ECR

* **Crea un repositorio privado en ECR** llamado `verificador-facial`.
* **Autentica y sube la imagen:**

  1. **Login (usando tu perfil):**

     ```bash
     aws --profile iamadmin ecr get-login-password --region <tu-region> | docker login --username AWS --password-stdin <tu-id-aws>.dkr.ecr.<tu-region>.amazonaws.com
     ```
  2. **Tag de la imagen:**

     ```bash
     docker tag verificador-facial:latest <tu-uri-ecr>/verificador-facial:latest
     ```
  3. **Push a ECR:**

     ```bash
     docker push <tu-uri-ecr>/verificador-facial:latest
     ```

---

### 3. Desplegar con AWS App Runner

1. En la consola AWS, navega a **App Runner**.

2. Crea un servicio:

   * **Source:** Container registry → Amazon ECR. Selecciona la imagen `verificador-facial:latest`.
   * **Deployment settings:** Automatic.
   * **Access role:** Create new service role.
   * **Service settings:**

     * Service name: `servicio-verificador-facial`
     * vCPU & Memory: 1 vCPU, 3 GB
     * Port: 5001

3. Haz clic en **Create & deploy**.

En minutos, tu servicio estará corriendo y tendrás una URL pública para tu API.

---

## Endpoint de la API

| Método | Ruta    | Descripción                                  | Body (form-data)                  |
| ------ | ------- | -------------------------------------------- | --------------------------------- |
| POST   | /verify | Compara dos imágenes y verifica los rostros. | `dni`: archivo, `selfie`: archivo |

* **Swagger:** `/apidocs/`

---

## Contacto

¿Dudas o sugerencias? Abre un issue o contacta al maintainer.

---

