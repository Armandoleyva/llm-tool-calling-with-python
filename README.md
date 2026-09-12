# LLM Tool Calling with Python

## Asistente de ventas para Vida Verde

Aplicación web conversacional construida con Python, FastAPI y Gemini API. El asistente puede conversar con un cliente y consultar un catálogo de plantas almacenado en Google Sheets cuando necesita datos reales de productos, precios o disponibilidad.

La interfaz ya es un chatbot web. Para esta versión se usa FastAPI en lugar de Streamlit porque permite separar claramente el backend que ejecuta el tool del frontend que muestra la conversación y facilita publicarlo en un servidor como Hostinger VPS. Streamlit queda como alternativa válida para un prototipo interno, pero no es necesario para este proyecto.

## Qué demuestra

```text
Cliente → Gemini analiza la pregunta
             ↓
       ¿Necesita el catálogo?
        ├── No → respuesta directa
        └── Sí → consultar_catalogo()
                         ↓
                   Google Sheet
                         ↓
                   respuesta final
```

La aplicación usa un **tool local en Python**. Gemini corre en la nube mediante la Gemini API y la función `consultar_catalogo()` se ejecuta en el backend.

## Tecnologías

- Python 3.11+
- FastAPI
- HTML, CSS y JavaScript
- Google Gemini API
- Google GenAI SDK
- Google Sheets mediante OpenSheet

No requiere Ollama, ADK ni MCP.

## Estructura

```text
web-chatbot-vida-verde/
├── app.py
├── catalogo_tool.py
├── requirements.txt
├── .env.example
├── .gitignore
└── static/
    ├── index.html
    ├── app.js
    └── styles.css
```

## Requisitos

- Python 3.11 o superior.
- Una API key de Gemini.
- Internet para consultar Gemini y Google Sheets.
- Un Google Sheet accesible mediante OpenSheet.

## Instalación local en Windows

Abre PowerShell dentro de la carpeta del proyecto.

### 1. Crear el entorno virtual

Solo se realiza la primera vez:

```powershell
python -m venv .venv
```

### 2. Activar `.venv`

Cada vez que abras una terminal nueva:

```powershell
.\.venv\Scripts\Activate.ps1
```

La terminal debe mostrar `(.venv)`.

### 3. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 4. Configurar variables

Copia `.env.example` como `.env`:

```powershell
Copy-Item .env.example .env
```

Abre `.env` y reemplaza:

```text
GEMINI_API_KEY=tu_api_key_real
```

La clave debe ser creada específicamente en [Google AI Studio](https://aistudio.google.com/apikey). No uses una clave de Google Maps, Firebase, OpenAI u otro servicio. Si Windows oculta las extensiones, verifica que el archivo se llame exactamente `.env` y no `.env.txt`.

No subas `.env` a GitHub. Está incluido en `.gitignore`.

Puedes crear la API key desde [Google AI Studio](https://aistudio.google.com/apikey).

### 5. Ejecutar

```powershell
python -m uvicorn app:app --reload
```

Abre en el navegador:

```text
http://127.0.0.1:8000
```

También puedes revisar:

```text
http://127.0.0.1:8000/health
```

## Cómo funciona el control de llamadas

Cada mensaje pasa por dos etapas como máximo:

1. Gemini recibe la pregunta con la declaración del tool.
2. Si necesita datos, solicita `consultar_catalogo()`.
3. Python ejecuta el tool una sola vez.
4. Gemini recibe el resultado, pero la segunda petición se realiza sin tools habilitados.

Esto impide que una pregunta ambigua genere búsquedas repetidas como `flores`, `exterior`, catálogo completo y después otra categoría.

El catálogo también incluye:

- Caché de cinco minutos.
- Máximo de ocho productos enviados al modelo.
- Filtros por categoría, texto, precio máximo y disponibilidad.
- Alias para `interior → Plantas sombra` y `exterior → Plantas sol`.
- Protección contra consultas sin filtros que intentarían devolver todo el catálogo.

## Pruebas de evaluación

### Pregunta 1: debe usar el tool

```text
¿Qué suculentas tienen disponibles y cuánto cuestan?
```

En la terminal debe aparecer:

```text
[TOOL EJECUTADO] consultar_catalogo
```

### Pregunta 2: debe usar el tool

```text
¿Qué productos de la categoría Plantas sol tienen disponibles?
```

Debe aparecer nuevamente la ejecución del tool.

### Pregunta 3: no debe usar el tool

```text
¿Qué es la fotosíntesis y por qué es importante para las plantas?
```

Debe responder sin mostrar:

```text
[TOOL EJECUTADO]
```

## Ejecutar con Docker opcional

Si deseas desplegarlo con Docker, puedes crear un `Dockerfile` con:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Construcción y ejecución:

```bash
docker build -t vida-verde-chatbot .
docker run --env-file .env -p 8000:8000 vida-verde-chatbot
```

## Despliegue en Hostinger

### Si tienes un VPS

FastAPI puede ejecutarse en el VPS como un servicio Python. La idea general es:

```bash
sudo apt update
sudo apt install python3-venv nginx
git clone URL_DE_TU_REPOSITORIO
cd web-chatbot-vida-verde
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Prueba primero:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Después conviene configurarlo con `systemd` y Nginx para que permanezca activo y funcione mediante tu dominio.

### Si tienes hosting compartido

Confirma primero que tu plan permita ejecutar una aplicación Python/FastAPI de forma persistente. Un hosting que solo sirve archivos PHP o HTML no puede mantener este backend activo. En ese caso, el frontend puede estar en tu dominio, pero el backend debe ejecutarse en un VPS o servicio compatible.

