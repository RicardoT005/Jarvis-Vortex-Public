"""Subida y lectura de archivos de texto."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth.firebase import get_current_user_firebase
from app.models import User

router = APIRouter(prefix="/api/files", tags=["files"])

MAX_BYTES = 200_000  # ~200 KB de texto


class FileReadResponse(BaseModel):
    filename: str
    content: str
    chars: int


@router.post("/read-txt", response_model=FileReadResponse)
async def read_txt(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user_firebase),
):
    name = (file.filename or "archivo.txt").strip()
    if not name.lower().endswith(".txt"):
        raise HTTPException(
            status_code=400,
            detail="Por ahora solo se admiten archivos .txt",
        )

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo supera el límite de {MAX_BYTES} bytes.",
        )

    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        raise HTTPException(status_code=400, detail="No se pudo decodificar el texto.")

    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    return FileReadResponse(filename=name, content=text[:50000], chars=len(text))
