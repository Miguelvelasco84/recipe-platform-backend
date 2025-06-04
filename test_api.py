# test_api.py - Pruebas para la API de recetas

import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, get_db, Base
import tempfile
import os
from io import BytesIO

# Configuración de base de datos de prueba
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Crear las tablas de prueba
Base.metadata.create_all(bind=engine)

client = TestClient(app)

# Datos de prueba
sample_recipe = {
    "name": "Pasta Carbonara",
    "description": "Deliciosa pasta italiana con huevos y panceta",
    "ingredients": "400g pasta\n200g panceta\n4 huevos\n100g queso parmesano\nPimienta negra\nSal",
    "instructions": "1. Hervir la pasta\n2. Freír la panceta\n3. Mezclar huevos con queso\n4. Combinar todo",
    "prep_time": 15,
    "cook_time": 20,
    "servings": 4,
    "difficulty": "medio",
    "category": "almuerzo",
    "tags": "italiana, pasta, rápida"
}

class TestRecipeAPI:
    
    def test_root_endpoint(self):
        """Probar endpoint raíz"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Recipe Platform API" in data["message"]

    def test_create_recipe(self):
        """Probar creación de receta"""
        response = client.post("/api/recipes", json=sample_recipe)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_recipe["name"]
        assert data["id"] is not None
        return data["id"]

    def test_create_recipe_invalid_data(self):
        """Probar creación de receta con datos inválidos"""
        invalid_recipe = {
            "name": "A",  # Muy corto
            "ingredients": "Pocos",  # Muy corto
            "instructions": "Muy corto"  # Muy corto
        }
        response = client.post("/api/recipes", json=invalid_recipe)
        assert response.status_code == 422

    def test_get_all_recipes(self):
        """Probar obtención de todas las recetas"""
        # Primero crear una receta
        client.post("/api/recipes", json=sample_recipe)
        
        response = client.get("/api/recipes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_recipe_by_id(self):
        """Probar obtención de receta por ID"""
        # Crear receta primero
        create_response = client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["id"]
        
        response = client.get(f"/api/recipes/{recipe_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_recipe["name"]

    def test_get_recipe_not_found(self):
        """Probar obtención de receta no existente"""
        response = client.get("/api/recipes/99999")
        assert response.status_code == 404

    def test_update_recipe(self):
        """Probar actualización completa de receta"""
        # Crear receta primero
        create_response = client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["id"]
        
        updated_recipe = sample_recipe.copy()
        updated_recipe["name"] = "Pasta Carbonara Deluxe"
        updated_recipe["servings"] = 6
        
        response = client.put(f"/api/recipes/{recipe_id}", json=updated_recipe)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Pasta Carbonara Deluxe"
        assert data["servings"] == 6

    def test_patch_recipe(self):
        """Probar actualización parcial de receta"""
        # Crear receta primero
        create_response = client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["id"]
        
        patch_data = {"name": "Pasta Carbonara Premium", "servings": 8}
        
        response = client.patch(f"/api/recipes/{recipe_id}", json=patch_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Pasta Carbonara Premium"
        assert data["servings"] == 8
        # Verificar que otros campos no cambiaron
        assert data["ingredients"] == sample_recipe["ingredients"]

    def test_delete_recipe(self):
        """Probar eliminación de receta"""
        # Crear receta primero
        create_response = client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["id"]
        
        response = client.delete(f"/api/recipes/{recipe_id}")
        assert response.status_code == 200
        
        # Verificar que la receta ya no se puede obtener
        get_response = client.get(f"/api/recipes/{recipe_id}")
        assert get_response.status_code == 404

    def test_search_recipes_by_name(self):
        """Probar búsqueda de recetas por nombre"""
        # Crear receta primero
        client.post("/api/recipes", json=sample_recipe)
        
        response = client.get("/api/recipes/search?q=Carbonara&type=name")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "Carbonara" in data[0]["name"]

    def test_search_recipes_by_ingredient(self):
        """Probar búsqueda de recetas por ingrediente"""
        # Crear receta primero
        client.post("/api/recipes", json=sample_recipe)
        
        response = client.get("/api/recipes/search?q=pasta&type=ingredient")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_search_recipes_by_category(self):
        """Probar búsqueda de recetas por categoría"""
        # Crear receta primero
        client.post("/api/recipes", json=sample_recipe)
        
        response = client.get("/api/recipes/search?q=almuerzo&type=category")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_search_invalid_type(self):
        """Probar búsqueda con tipo inválido"""
        response = client.get("/api/recipes/search?q=test&type=invalid")
        assert response.status_code == 422

    def test_get_stats(self):
        """Probar obtención de estadísticas"""
        # Crear algunas recetas primero
        client.post("/api/recipes", json=sample_recipe)
        
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_recipes" in data
        assert "categories" in data
        assert data["total_recipes"] >= 1

    def test_restore_recipe(self):
        """Probar restauración de receta eliminada"""
        # Crear y eliminar receta
        create_response = client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["id"]
        client.delete(f"/api/recipes/{recipe_id}")
        
        # Restaurar receta
        response = client.patch(f"/api/recipes/{recipe_id}/restore")
        assert response.status_code == 200
        
        # Verificar que la receta es accesible nuevamente
        get_response = client.get(f"/api/recipes/{recipe_id}")
        assert get_response.status_code == 200

    def test_get_deleted_recipes(self):
        """Probar obtención de recetas eliminadas"""
        # Crear y eliminar receta
        create_response = client.post("/api/recipes", json=sample_recipe)
        recipe_id = create_response.json()["id"]
        client.delete(f"/api/recipes/{recipe_id}")
        
        response = client.get("/api/recipes/deleted")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

class TestImageUpload:
    
    def test_upload_image_success(self):
        """Probar subida exitosa de imagen"""
        # Crear una imagen de prueba
        image_data = BytesIO()
        # Simular datos de imagen PNG básica
        image_data.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xddS\xf9\x07\x00\x00\x00\x00IEND\xaeB`\x82')
        image_data.seek(0)
        
        files = {"image": ("test.png", image_data, "image/png")}
        response = client.post("/api/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "image_url" in data
        assert data["image_url"].endswith(".png")

    def test_upload_invalid_file_type(self):
        """Probar subida de archivo con tipo inválido"""
        text_data = BytesIO(b"Este es un archivo de texto")
        files = {"image": ("test.txt", text_data, "text/plain")}
        
        response = client.post("/api/upload", files=files)
        assert response.status_code == 400

class TestValidation:
    
    def test_name_too_short(self):
        """Probar validación de nombre muy corto"""
        invalid_recipe = sample_recipe.copy()
        invalid_recipe["name"] = "AB"
        
        response = client.post("/api/recipes", json=invalid_recipe)
        assert response.status_code == 422

    def test_negative_numbers(self):
        """Probar validación de números negativos"""
        invalid_recipe = sample_recipe.copy()
        invalid_recipe["prep_time"] = -5
        
        response = client.post("/api/recipes", json=invalid_recipe)
        assert response.status_code == 422

    def test_missing_required_fields(self):
        """Probar validación de campos requeridos faltantes"""
        invalid_recipe = {
            "name": "Test Recipe"
            # Faltan ingredients e instructions
        }
        
        response = client.post("/api/recipes", json=invalid_recipe)
        assert response.status_code == 422

def test_pagination():
    """Probar paginación de recetas"""
    # Crear múltiples recetas
    for i in range(15):
        recipe = sample_recipe.copy()
        recipe["name"] = f"Receta {i}"
        client.post("/api/recipes", json=recipe)
    
    # Probar primera página
    response = client.get("/api/recipes?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    
    # Probar segunda página
    response = client.get("/api/recipes?skip=10&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5

# Ejecutar las pruebas
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# test_frontend.py - Pruebas para JavaScript (usando Selenium)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import unittest

class TestFrontend(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Configurar el driver de Selenium"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Ejecutar sin interfaz gráfica
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        cls.driver = webdriver.Chrome(options=chrome_options)
        cls.driver.implicitly_wait(10)
        
        # URL base del frontend (cambiar según tu configuración)
        cls.base_url = "http://localhost:8080"  # GitHub Pages o servidor local
    
    @classmethod
    def tearDownClass(cls):
        """Cerrar el driver"""
        cls.driver.quit()
    
    def test_homepage_loads(self):
        """Probar que la página principal carga correctamente"""
        self.driver.get(self.base_url)
        
        # Verificar título
        self.assertIn("RecipeHub", self.driver.title)
        
        # Verificar elementos principales
        hero_title = self.driver.find_element(By.TAG_NAME, "h1")
        self.assertIn("Bienvenido", hero_title.text)
        
        # Verificar navegación
        nav_links = self.driver.find_elements(By.CLASS_NAME, "nav-link")
        self.assertTrue(len(nav_links) >= 5)
    
    def test_navigation_works(self):
        """Probar que la navegación funciona"""
        self.driver.get(self.base_url)
        
        # Hacer clic en "Todas las Recetas"
        all_recipes_link = self.driver.find_element(By.LINK_TEXT, "Todas las Recetas")
        all_recipes_link.click()
        
        # Verificar que cambió la página
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "all-recipes-container"))
        )
        
        self.assertIn("all-recipes.html", self.driver.current_url)
    
    def test_responsive_menu(self):
        """Probar menú responsivo"""
        self.driver.get(self.base_url)
        
        # Redimensionar ventana para móvil
        self.driver.set_window_size(375, 667)
        
        # Verificar que el hamburger menu aparece
        hamburger = self.driver.find_element(By.CLASS_NAME, "hamburger")
        self.assertTrue(hamburger.is_displayed())
        
        # Hacer clic en el hamburger
        hamburger.click()
        time.sleep(0.5)
        
        # Verificar que el menú se abre
        nav_menu = self.driver.find_element(By.CLASS_NAME, "nav-menu")
        self.assertIn("active", nav_menu.get_attribute("class"))
    
    def test_add_recipe_form(self):
        """Probar formulario de agregar receta"""
        self.driver.get(f"{self.base_url}/pages/add-recipe.html")
        
        # Llenar el formulario
        name_input = self.driver.find_element(By.ID, "name")
        name_input.send_keys("Receta de Prueba")
        
        ingredients_textarea = self.driver.find_element(By.ID, "ingredients")
        ingredients_textarea.send_keys("Ingrediente 1\nIngrediente 2\nIngrediente 3")
        
        instructions_textarea = self.driver.find_element(By.ID, "instructions")
        instructions_textarea.send_keys("Paso 1: Hacer algo\nPaso 2: Hacer otra cosa\nPaso 3: Terminar")
        
        # Verificar que el formulario tiene los campos llenos
        self.assertEqual(name_input.get_attribute("value"), "Receta de Prueba")
        self.assertIn("Ingrediente 1", ingredients_textarea.get_attribute("value"))
    
    def test_search_functionality(self):
        """Probar funcionalidad de búsqueda"""
        self.driver.get(f"{self.base_url}/pages/search.html")
        
        # Buscar algo
        search_input = self.driver.find_element(By.ID, "search-input")
        search_input.send_keys("pasta")
        
        search_button = self.driver.find_element(By.CLASS_NAME, "search-btn")
        search_button.click()
        
        # Verificar que se muestra el contenedor de resultados
        results_container = self.driver.find_element(By.ID, "search-results-container")
        self.assertTrue(results_container.is_displayed())
    
    def test_form_validation(self):
        """Probar validación de formularios"""
        self.driver.get(f"{self.base_url}/pages/add-recipe.html")
        
        # Intentar enviar formulario vacío
        submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()
        
        # Verificar que aparecen mensajes de validación HTML5
        name_input = self.driver.find_element(By.ID, "name")
        validation_message = name_input.get_attribute("validationMessage")
        self.assertTrue(len(validation_message) > 0)

# test_performance.py - Pruebas de rendimiento

import time
import requests
import concurrent.futures
from statistics import mean, median

class PerformanceTests:
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.endpoints = [
            "/",
            "/api/recipes",
            "/api/stats"
        ]
    
    def test_response_time(self):
        """Probar tiempo de respuesta de endpoints"""
        results = {}
        
        for endpoint in self.endpoints:
            times = []
            
            for _ in range(10):  # 10 requests por endpoint
                start_time = time.time()
                try:
                    response = requests.get(f"{self.base_url}{endpoint}")
                    end_time = time.time()
                    
                    if response.status_code == 200:
                        times.append(end_time - start_time)
                except requests.RequestException:
                    pass
            
            if times:
                results[endpoint] = {
                    "avg_time": mean(times),
                    "median_time": median(times),
                    "max_time": max(times),
                    "min_time": min(times)
                }
        
        return results
    
    def test_concurrent_requests(self, num_requests=50):
        """Probar carga concurrente"""
        def make_request():
            try:
                start_time = time.time()
                response = requests.get(f"{self.base_url}/api/recipes")
                end_time = time.time()
                return {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200
                }
            except requests.RequestException as e:
                return {
                    "status_code": None,
                    "response_time": None,
                    "success": False,
                    "error": str(e)
                }
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        successful_requests = [r for r in results if r["success"]]
        success_rate = len(successful_requests) / num_requests * 100
        
        if successful_requests:
            avg_response_time = mean([r["response_time"] for r in successful_requests])
        else:
            avg_response_time = 0
        
        return {
            "total_requests": num_requests,
            "successful_requests": len(successful_requests),
            "success_rate": success_rate,
            "avg_response_time": avg_response_time
        }

# Manual test checklist (test_manual.md)
manual_test_checklist = """
# Lista de Verificación Manual - RecipeHub

## Funcionalidades Básicas
- [ ] La página principal carga correctamente
- [ ] Todos los enlaces de navegación funcionan
- [ ] El menú responsivo funciona en móvil
- [ ] Se pueden agregar recetas nuevas
- [ ] Se pueden ver todas las recetas
- [ ] Se puede buscar recetas por nombre
- [ ] Se puede buscar recetas por ingrediente
- [ ] Se puede buscar recetas por categoría
- [ ] Se pueden editar recetas existentes
- [ ] Se pueden eliminar recetas
- [ ] Se puede ver el detalle de una receta

## Validaciones
- [ ] No se puede crear receta sin nombre
- [ ] No se puede crear receta sin ingredientes
- [ ] No se puede crear receta sin instrucciones
- [ ] Los campos numéricos solo aceptan números positivos
- [ ] La validación de imagen funciona (tamaño y tipo)
- [ ] Los mensajes de error se muestran correctamente
- [ ] Los mensajes de éxito se muestran correctamente

## Diseño Responsivo
- [ ] La página se ve bien en escritorio (1920x1080)
- [ ] La página se ve bien en tablet (768x1024)
- [ ] La página se ve bien en móvil (375x667)
- [ ] Las imágenes se adaptan correctamente
- [ ] Los formularios son usables en móvil
- [ ] Los botones tienen el tamaño adecuado para táctil

## Usabilidad
- [ ] La navegación es intuitiva
- [ ] Los formularios son fáciles de llenar
- [ ] Los mensajes de estado son claros
- [ ] Las imágenes cargan correctamente
- [ ] Los tiempos de carga son aceptables
- [ ] No hay errores de JavaScript en consola
- [ ] Los estilos CSS se aplican correctamente

## Backend API
- [ ] GET /api/recipes funciona
- [ ] POST /api/recipes funciona
- [ ] PUT /api/recipes/{id} funciona
- [ ] PATCH /api/recipes/{id} funciona
- [ ] DELETE /api/recipes/{id} funciona
- [ ] GET /api/recipes/search funciona
- [ ] POST /api/upload funciona
- [ ] GET /api/stats funciona
- [ ] Los códigos de estado HTTP son correctos
- [ ] Los errores se manejan adecuadamente

## Persistencia de Datos
- [ ] Las recetas se guardan en la base de datos
- [ ] Las recetas editadas se actualizan correctamente
- [ ] Las recetas eliminadas no aparecen en la lista
- [ ] La búsqueda encuentra recetas existentes
- [ ] Las imágenes se suben y se guardan correctamente
- [ ] Los metadatos (fechas) se actualizan correctamente

## Rendimiento
- [ ] La página principal carga en menos de 3 segundos
- [ ] Las imágenes se optimizan automáticamente
- [ ] La API responde en menos de 1 segundo
- [ ] La aplicación funciona con 50+ recetas
- [ ] No hay pérdidas de memoria evidentes
- [ ] La aplicación es estable durante uso prolongado
"""

if __name__ == "__main__":
    # Ejecutar pruebas de rendimiento
    perf_tests = PerformanceTests()
    
    print("=== Pruebas de Tiempo de Respuesta ===")
    response_times = perf_tests.test_response_time()
    for endpoint, stats in response_times.items():
        print(f"{endpoint}: {stats['avg_time']:.3f}s promedio")
    
    print("\n=== Pruebas de Carga Concurrente ===")
    load_results = perf_tests.test_concurrent_requests()
    print(f"Tasa de éxito: {load_results['success_rate']:.1f}%")
    print(f"Tiempo promedio: {load_results['avg_response_time']:.3f}s")
    
    print("\n=== Lista de Verificación Manual ===")
    print(manual_test_checklist)