# Tyrion

Capa de inteligencia documental sobre la gestión de trámites de vehículos ante DGT, para el Colegio de Gestores (cliente Alfa-Pyme).

Tyrion clasifica documentación entrante, la coteja contra el checklist de cada tipo de trámite, detecta lo que falta, avisa a las gestorías y prepara expedientes para que un administrativo los presente físicamente ante DGT. Los administrativos intervienen solo en excepciones escaladas.

## Estado

Fundamento inicial (sesión 1 de construcción):
- Schema PostgreSQL completo (`backend/migrations/001_initial_schema.sql`)
- Clasificador documental con Claude API (`backend/app/services/clasificador.py`) — primer módulo, identificado como el cuello de botella (80% del tiempo administrativo se va en cotejo documental)
- 15 tests pasando

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | FastAPI (Python 3.12) |
| Base de datos | PostgreSQL 15 |
| IA | Claude API (Haiku para clasificación masiva, Opus para conflictos/escalados) |
| Deploy | Hostinger KVM2 (autohosteado) |

## Principios de diseño

Cuatro capas documentales: un documento es **requerido** (lo pide el checklist), **recibido** (el archivo que llegó), **detectado** (lo que Tyrion interpreta, con confianza) y **válido** (el que efectivamente desbloquea ese trámite).

Regla de oro: **evidencia compatible ≠ documento válido**. Un Modelo 620 no sustituye un Permiso de circulación, aunque estén relacionados.

La validez vive en el **vínculo** documento-trámite, nunca en el documento. Un mismo documento puede ser válido en un trámite y evidencia compatible en otro.

Estados de trámite (confirmados): `PENDIENTE → EN_REVISION → PRESENTADO → FINALIZADO`.

Tyrion prepara; el humano presenta. Sin integración electrónica con DGT en v1: la presentación es siempre física.

## Estructura

```
backend/
├── app/
│   ├── core/config.py            # configuración central
│   ├── services/
│   │   ├── catalogo_documental.py  # tipos de documento del dominio DGT
│   │   └── clasificador.py         # clasificador con Claude (primer módulo)
│   └── schemas/clasificacion.py    # contratos de E/S
├── migrations/001_initial_schema.sql
└── tests/test_clasificador.py
```

## Desarrollo

```bash
cd backend
pip install -r requirements.txt
pytest                    # correr tests
```

Variables de entorno (`.env`):
```
DATABASE_URL=postgresql+asyncpg://tyrion:tyrion@localhost:5432/tyrion
ANTHROPIC_API_KEY=sk-ant-...
```

## Próximos pasos

- Motor de cotejo: documento detectado → válido/evidencia/rechazado contra el checklist del trámite
- Ingesta de email (entrada principal)
- Pantalla Control (6 macro-estados)
- Pendiente sesión 2: confirmar si existe estado de "observación DGT", flujo de matriculaciones, tiempos reales

## Demo en 1 comando (sin cuenta de Anthropic)

    git clone https://github.com/julionotaro/tyrion.git
    cd tyrion
    cp backend/.env.example backend/.env
    make demo
    # Abrir http://localhost:8000
    # Sin ANTHROPIC_API_KEY usa clasificador mock — perfecto para demo local
