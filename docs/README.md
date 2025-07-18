# Structure Details

| Folder         | Purpose                                         | Key Concepts Used                   |
|----------------|--------------------------------------------------|--------------------------------------|
| `api/`         | HTTP route handlers                             | FastAPI routing                      |
| `core/`        | App settings, global config                     | Pydantic `BaseSettings`              |
| `db/`          | DB connection & base class                      | SQLAlchemy `Session`, declarative base |
| `dependencies/`| Injectable shared logic (auth, pagination, etc) | FastAPI `Depends()`                  |
| `models/`      | SQLAlchemy models (tables)                      | ORM, relationships                   |
| `schemas/`     | Pydantic models for I/O                         | Validation, serialization            |
| `services/`    | Business logic (create, query, etc.)            | Decoupled logic layer                |
| `scripts/`     | CLI tools (e.g., DB init)                       | `sys.path`, `Base.metadata`          |
| `tests/`       | Pytest-based tests                              | Unit tests, integration tests        |
