import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from catalogo_tool import consultar_catalogo


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
API_KEY = os.getenv("GEMINI_API_KEY", "").strip() or None

if API_KEY:
    client = genai.Client(api_key=API_KEY)
else:
    client = None


SYSTEM_INSTRUCTION = """
Eres un asistente de ventas de Vida Verde, un vivero ubicado en Oaxaca, México.

Ayudas a los clientes a encontrar plantas y artículos de jardinería.

Usa consultar_catalogo únicamente cuando el cliente pregunte por productos,
precios, disponibilidad, existencia, categorías o plantas específicas.

Para cada mensaje del usuario puedes llamar consultar_catalogo como máximo una
vez. Incluye todos los filtros relevantes en esa única llamada. Nunca llames
la herramienta sin al menos un criterio de búsqueda.

Categorías conocidas:
- interior o Plantas sombra
- exterior o Plantas sol
- arbustos
- suculentas
- frutales
- aromaticas

No uses la herramienta para preguntas generales de jardinería, como cuidados,
fotosíntesis o diferencias entre tipos de plantas.

Nunca inventes precios, existencia o productos. Usa únicamente los datos
devueltos por la herramienta. Responde siempre en español, de forma clara,
amable y breve.
"""


CATALOG_TOOL = types.Tool(
    function_declarations=[
        {
            "name": "consultar_catalogo",
            "description": (
                "Busca productos disponibles en el catálogo de Vida Verde. "
                "Úsala para consultar plantas, categorías, precios y stock. "
                "Devuelve como máximo ocho productos para evitar respuestas pesadas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {
                        "type": "string",
                        "description": (
                            "Categoría, por ejemplo suculentas, frutales, "
                            "interior, exterior, Plantas sombra o Plantas sol."
                        ),
                    },
                    "texto": {
                        "type": "string",
                        "description": "Nombre o palabra para buscar en el catálogo.",
                    },
                    "precio_max": {
                        "type": "number",
                        "description": "Precio máximo en pesos mexicanos.",
                    },
                    "solo_disponibles": {
                        "type": "boolean",
                        "description": "Excluye productos con stock cero.",
                    },
                },
            },
        }
    ]
)


MODEL_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION,
    tools=[CATALOG_TOOL],
)

# La respuesta posterior al tool se genera sin tools para impedir llamadas
# repetidas dentro del mismo turno.
FINAL_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION,
)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1200)


class ChatResponse(BaseModel):
    response: str
    tool_used: bool = False
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    result_count: int | None = None


# Historial en memoria: suficiente para una demo o un servidor pequeño.
# Para producción con múltiples workers se puede mover a Redis o una base de datos.
sessions: dict[str, list[types.Content]] = {}
MAX_HISTORY_ITEMS = 24


def get_function_call_part(response: Any):
    """Obtiene la primera parte de llamada solicitada por Gemini."""
    for candidate in response.candidates or []:
        content = candidate.content
        for part in content.parts or []:
            if part.function_call:
                return part
    return None


def trim_history(history: list[types.Content]) -> None:
    if len(history) > MAX_HISTORY_ITEMS:
        del history[:-MAX_HISTORY_ITEMS]


app = FastAPI(title="Vida Verde AI Chatbot")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if client is None:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY no está configurada en el archivo .env.",
        )

    print(f"\n[CLIENTE] {request.message}")

    history = sessions.setdefault(request.session_id, [])
    history.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=request.message)],
        )
    )

    try:
        first_response = client.models.generate_content(
            model=MODEL,
            contents=history,
            config=MODEL_CONFIG,
        )
    except Exception as exc:
        history.pop()
        raise HTTPException(status_code=502, detail=f"Error al consultar Gemini: {exc}")

    function_call_part = get_function_call_part(first_response)
    function_call = function_call_part.function_call if function_call_part else None

    if function_call is None:
        history.append(first_response.candidates[0].content)
        trim_history(history)
        response_text = first_response.text or "No pude generar una respuesta."
        print(f"[RESPUESTA] {response_text}")
        return ChatResponse(response=response_text)

    # Guardamos solamente la primera llamada solicitada. Conservamos la parte
    # original para mantener el id que Gemini necesita asociar a la respuesta.
    history.append(
        types.Content(
            role="model",
            parts=[function_call_part],
        )
    )

    tool_name = function_call.name
    tool_arguments = dict(function_call.args or {})

    if tool_name != "consultar_catalogo":
        trim_history(history)
        return ChatResponse(
            response="No tengo disponible esa herramienta.",
            tool_used=False,
        )

    try:
        tool_result = consultar_catalogo(**tool_arguments)
    except Exception as exc:
        tool_result = {"error": f"No se pudo consultar el catálogo: {exc}"}

    function_response = types.Part.from_function_response(
        name=tool_name,
        response={"result": tool_result},
        id=function_call.id,
    )
    history.append(
        types.Content(
            role="user",
            parts=[function_response],
        )
    )

    try:
        final_response = client.models.generate_content(
            model=MODEL,
            contents=history,
            config=FINAL_CONFIG,
        )
    except Exception as exc:
        trim_history(history)
        raise HTTPException(
            status_code=502,
            detail=f"El tool funcionó, pero Gemini no pudo generar la respuesta final: {exc}",
        )

    history.append(final_response.candidates[0].content)
    trim_history(history)

    response_text = final_response.text or "No pude generar una respuesta."
    print(f"[RESPUESTA] {response_text}")

    return ChatResponse(
        response=response_text,
        tool_used=True,
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        result_count=tool_result.get("total_encontrados")
        if isinstance(tool_result, dict)
        else None,
    )
