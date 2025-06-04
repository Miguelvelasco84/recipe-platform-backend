# main.py - Backend FastAPI para Plataforma de Recetas CORREGIDO

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional, List
import os
import uuid
import shutil
from pathlib import Path
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./recipes.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLAlchemy setup
from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de la base de datos
class Recipe(Base):
    __tablename__ = "recipes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    ingredients = Column(Text, nullable=False)
    instructions = Column(Text, nullable=False)
    prep_time = Column(Integer)  # en minutos
    cook_time = Column(Integer)  # en minutos
    servings = Column(Integer)
    difficulty = Column(String(50))  # facil, medio, dificil
    category = Column(String(100))
    tags = Column(String(500))
    image_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(String(10), default="false")  # Para historial de eliminación

# Crear las tablas
Base.metadata.create_all(bind=engine)

# Modelos Pydantic
class RecipeBase(BaseModel):
    name: str
    description: Optional[str] = None
    ingredients: str
    instructions: str
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    servings: Optional[int] = None
    difficulty: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    image_url: Optional[str] = None

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('El nombre debe tener al menos 3 caracteres')
        return v.strip()

    @validator('ingredients')
    def validate_ingredients(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Los ingredientes deben tener al menos 10 caracteres')
        return v.strip()

    @validator('instructions')
    def validate_instructions(cls, v):
        if not v or len(v.strip()) < 20:
            raise ValueError('Las instrucciones deben tener al menos 20 caracteres')
        return v.strip()

    @validator('prep_time', 'cook_time', 'servings')
    def validate_positive_numbers(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Debe ser un número mayor a 0')
        return v

class RecipeCreate(RecipeBase):
    pass

class RecipeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ingredients: Optional[str] = None
    instructions: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    servings: Optional[int] = None
    difficulty: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    image_url: Optional[str] = None

class RecipeResponse(RecipeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ImageUploadResponse(BaseModel):
    image_url: str
    message: str

# Dependencia para obtener la sesión de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Crear la aplicación FastAPI
app = FastAPI(
    title="Recipe Platform API",
    description="API para la plataforma de recetas - Desarrollado con FastAPI",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear directorio para imágenes
UPLOAD_DIR = Path("static/images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Funciones auxiliares
def get_recipe_by_id(db: Session, recipe_id: int):
    return db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.is_deleted == "false").first()

def get_recipes(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Recipe).filter(Recipe.is_deleted == "false").offset(skip).limit(limit).all()

def search_recipes_by_name(db: Session, name: str):
    return db.query(Recipe).filter(
        Recipe.name.contains(name), 
        Recipe.is_deleted == "false"
    ).all()

def search_recipes_by_ingredient(db: Session, ingredient: str):
    return db.query(Recipe).filter(
        Recipe.ingredients.contains(ingredient),
        Recipe.is_deleted == "false"
    ).all()

def search_recipes_by_category(db: Session, category: str):
    return db.query(Recipe).filter(
        Recipe.category.contains(category),
        Recipe.is_deleted == "false"
    ).all()

# Endpoints de la API

@app.get("/")
async def root():
    return {
        "message": "Recipe Platform API",
        "version": "1.0.0",
        "endpoints": {
            "recipes": "/api/recipes",
            "search": "/api/recipes/search",
            "upload": "/api/upload",
            "docs": "/docs"
        }
    }

@app.get("/api/recipes", response_model=List[RecipeResponse])
async def get_all_recipes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Obtener todas las recetas con paginación"""
    try:
        recipes = get_recipes(db, skip=skip, limit=limit)
        return recipes
    except Exception as e:
        logger.error(f"Error getting recipes: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/api/recipes/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    """Obtener una receta por ID"""
    recipe = get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return recipe

@app.post("/api/recipes", response_model=RecipeResponse)
async def create_recipe(recipe: RecipeCreate, db: Session = Depends(get_db)):
    """Crear una nueva receta"""
    try:
        db_recipe = Recipe(**recipe.dict())
        db.add(db_recipe)
        db.commit()
        db.refresh(db_recipe)
        logger.info(f"Receta creada: {db_recipe.id}")
        return db_recipe
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating recipe: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/recipes/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: int, 
    recipe_update: RecipeBase, 
    db: Session = Depends(get_db)
):
    """Actualizar completamente una receta"""
    recipe = get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    
    try:
        for field, value in recipe_update.dict().items():
            setattr(recipe, field, value)
        
        recipe.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(recipe)
        logger.info(f"Receta actualizada: {recipe_id}")
        return recipe
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating recipe: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/recipes/{recipe_id}", response_model=RecipeResponse)
async def patch_recipe(
    recipe_id: int, 
    recipe_update: RecipeUpdate, 
    db: Session = Depends(get_db)
):
    """Actualizar parcialmente una receta"""
    recipe = get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    
    try:
        update_data = recipe_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(recipe, field, value)
        
        recipe.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(recipe)
        logger.info(f"Receta parcialmente actualizada: {recipe_id}")
        return recipe
    except Exception as e:
        db.rollback()
        logger.error(f"Error patching recipe: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/recipes/{recipe_id}")
async def delete_recipe(recipe_id: int, db: Session = Depends(get_db)):
    """Eliminar una receta (soft delete para historial)"""
    recipe = get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    
    try:
        # Soft delete - marcar como eliminada pero mantener en BD
        recipe.is_deleted = "true"
        recipe.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"Receta eliminada (soft delete): {recipe_id}")
        return {"message": "Receta eliminada exitosamente"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting recipe: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/api/recipes/search", response_model=List[RecipeResponse])
async def search_recipes(
    q: str = Query(..., min_length=1),
    type: str = Query("name", regex="^(name|ingredient|category)$"),
    db: Session = Depends(get_db)
):
    """Buscar recetas por nombre, ingrediente o categoría"""
    try:
        if type == "name":
            recipes = search_recipes_by_name(db, q)
        elif type == "ingredient":
            recipes = search_recipes_by_ingredient(db, q)
        elif type == "category":
            recipes = search_recipes_by_category(db, q)
        else:
            raise HTTPException(status_code=400, detail="Tipo de búsqueda no válido")
        
        return recipes
    except Exception as e:
        logger.error(f"Error searching recipes: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/api/upload", response_model=ImageUploadResponse)
async def upload_image(image: UploadFile = File(...)):
    """Subir imagen para una receta"""
    # Validar tipo de archivo
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail="Tipo de archivo no válido. Use JPEG, PNG, GIF o WebP"
        )
    
    # Validar tamaño (5MB máximo)
    if image.size and image.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande. Máximo 5MB")
    
    try:
        # Generar nombre único para el archivo
        file_extension = image.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = UPLOAD_DIR / unique_filename
        
        # Guardar el archivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        # URL para acceder a la imagen
        image_url = f"/static/images/{unique_filename}"
        
        logger.info(f"Imagen subida: {unique_filename}")
        return ImageUploadResponse(
            image_url=image_url,
            message="Imagen subida exitosamente"
        )
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail="Error al subir la imagen")

# Endpoint para servir archivos estáticos
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

# Endpoint para obtener estadísticas
@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Obtener estadísticas de la plataforma"""
    try:
        total_recipes = db.query(Recipe).filter(Recipe.is_deleted == "false").count()
        total_deleted = db.query(Recipe).filter(Recipe.is_deleted == "true").count()
        
        # Recetas por categoría
        categories = db.query(Recipe.category).filter(Recipe.is_deleted == "false").distinct().all()
        category_counts = {}
        for (category,) in categories:
            if category:
                count = db.query(Recipe).filter(
                    Recipe.category == category,
                    Recipe.is_deleted == "false"
                ).count()
                category_counts[category] = count
        
        return {
            "total_recipes": total_recipes,
            "total_deleted": total_deleted,
            "categories": category_counts,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# Manejo de errores
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "status_code": 500}
    )

# Middleware para logging
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = datetime.utcnow()
    response = await call_next(request)
    process_time = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
