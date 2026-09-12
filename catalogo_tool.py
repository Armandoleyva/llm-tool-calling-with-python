import os
import time
import unicodedata

import requests
from dotenv import load_dotenv


load_dotenv()

SHEET_URL = os.getenv(
    "SHEET_URL",
    "https://opensheet.elk.sh/1yzJ296P_qcP0fJTOG2PcLCRaP9h3VikgTvQD2eXcGAA/1",
)

MAX_RESULTS = 8
CACHE_SECONDS = 300
_catalog_cache: list[dict] | None = None
_catalog_cache_expires = 0.0


def normalizar(valor) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(char for char in texto if not unicodedata.combining(char))


def convertir_numero(valor) -> float:
    try:
        return float(
            str(valor or "")
            .replace("$", "")
            .replace(",", "")
            .strip()
        )
    except (TypeError, ValueError):
        return 0.0


def cargar_catalogo() -> list[dict]:
    global _catalog_cache, _catalog_cache_expires

    if _catalog_cache is not None and time.monotonic() < _catalog_cache_expires:
        return _catalog_cache

    respuesta = requests.get(SHEET_URL, timeout=15)
    respuesta.raise_for_status()
    datos = respuesta.json()

    if not isinstance(datos, list):
        raise ValueError("El endpoint del catálogo no devolvió una lista JSON.")

    _catalog_cache = datos
    _catalog_cache_expires = time.monotonic() + CACHE_SECONDS
    return datos


CATEGORY_ALIASES = {
    "exterior": ("plantas sol", "exterior"),
    "plantas de exterior": ("plantas sol", "exterior"),
    "plantas de sol": ("plantas sol", "exterior"),
    "interior": ("plantas sombra", "interior"),
    "plantas de interior": ("plantas sombra", "interior"),
    "plantas de sombra": ("plantas sombra", "interior"),
}


def consultar_catalogo(
    categoria: str | None = None,
    texto: str | None = None,
    precio_max: float | None = None,
    solo_disponibles: bool = False,
) -> dict:
    """Busca productos del catálogo de Vida Verde.

    La función está diseñada como tool para Gemini. Devuelve un máximo de
    ocho productos y utiliza una caché de cinco minutos para evitar descargar
    el Google Sheet repetidamente.
    """

    print("\n[TOOL EJECUTADO] consultar_catalogo")
    print(
        f"Filtros: categoria={categoria}, texto={texto}, "
        f"precio_max={precio_max}, solo_disponibles={solo_disponibles}"
    )

    if not categoria and not texto and precio_max is None:
        mensaje = (
            "La búsqueda necesita al menos una categoría, texto o precio máximo. "
            "No se consultó todo el catálogo."
        )
        print(mensaje)
        return {"total_encontrados": 0, "productos": [], "mensaje": mensaje}

    categoria_normalizada = normalizar(categoria)
    texto_normalizado = normalizar(texto)

    categorias_busqueda = CATEGORY_ALIASES.get(
        categoria_normalizada,
        (categoria_normalizada,) if categoria_normalizada else (),
    )

    if texto_normalizado in CATEGORY_ALIASES and not categoria_normalizada:
        categorias_busqueda = CATEGORY_ALIASES[texto_normalizado]
        texto_normalizado = ""

    resultados = []

    for producto in cargar_catalogo():
        categoria_producto = normalizar(producto.get("categoria"))
        nombre = normalizar(producto.get("nombre"))
        descripcion = normalizar(producto.get("desc"))
        precio = convertir_numero(producto.get("precio"))
        stock = convertir_numero(producto.get("stock"))

        if categorias_busqueda and not any(
            categoria_opcion in categoria_producto
            for categoria_opcion in categorias_busqueda
        ):
            continue

        if texto_normalizado and (
            texto_normalizado not in nombre and texto_normalizado not in descripcion
        ):
            continue

        if precio_max is not None and precio > float(precio_max):
            continue

        if solo_disponibles and stock <= 0:
            continue

        resultados.append(producto)

    print(f"Resultados encontrados: {len(resultados)}")

    productos_resumidos = [
        {
            "nombre": producto.get("nombre"),
            "descripcion": producto.get("desc"),
            "precio": producto.get("precio"),
            "stock": producto.get("stock"),
            "categoria": producto.get("categoria"),
        }
        for producto in resultados[:MAX_RESULTS]
    ]

    return {
        "total_encontrados": len(resultados),
        "mostrando": len(productos_resumidos),
        "productos": productos_resumidos,
    }
