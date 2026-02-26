# MCQ Generator Refactoring Plan

## Issues Identified

### 1. Duplicate API Implementation
- There are two API implementations:
  - `/workspace/src/mcq_generator/api.py` (monolithic)
  - `/workspace/src/mcq_generator/api/` (modular but partially overlapping)
- Need to consolidate into a single, well-organized structure

### 2. File Sizes
- `generator.py`: 936 lines (very large)
- `state_manager.py`: 989 lines (very large)
- `api.py`: 371 lines (large)
- Other files are reasonably sized

### 3. Structure Issues
- Mixed concerns in some modules
- Inconsistent naming patterns
- Missing clear separation between API layer, business logic, and data access

## Proposed Refactoring

### 1. Consolidate API Implementation
- Remove `/workspace/src/mcq_generator/api.py` (monolithic)
- Keep and enhance the modular API structure under `/workspace/src/mcq_generator/api/`
- Ensure all legacy endpoints are properly migrated

### 2. Improve Service Layer
- Enhance service layer to better separate business logic
- Add proper error handling and validation
- Improve documentation

### 3. Modularize Large Files
- Split `generator.py` into smaller, focused modules
- Split `state_manager.py` into smaller components

### 4. Organize Project Structure
```
src/
└── mcq_generator/
    ├── __init__.py
    ├── asgi.py
    ├── config.py
    ├── utils.py
    ├── cache_manager.py
    ├── filters.py
    ├── metrics.py
    ├── inmem.py
    ├── dataset_search.py
    ├── provider_adapters.py
    ├── provider_client.py
    ├── generator/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── dataset_generator.py
    │   ├── text_processor.py
    │   └── validators.py
    ├── storage/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── duckdb_storage.py
    │   ├── memory_storage.py
    │   └── state_manager.py
    ├── exporters/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── csv_exporter.py
    │   ├── json_exporter.py
    │   ├── markdown_exporter.py
    │   └── pdf_exporter.py
    ├── api/
    │   ├── __init__.py
    │   ├── main.py
    │   ├── dependencies.py
    │   ├── schemas.py
    │   ├── client.py
    │   ├── tasks.py
    │   ├── routers/
    │   │   ├── __init__.py
    │   │   ├── health.py
    │   │   ├── datasets.py
    │   │   ├── jobs.py
    │   │   ├── exports.py
    │   │   ├── metrics.py
    │   │   └── audit_logs.py
    │   └── services/
    │       ├── __init__.py
    │       ├── dataset_service.py
    │       ├── job_service.py
    │       └── export_service.py
    └── tasks.py
```

### 5. Specific Improvements Needed
- Remove duplicate legacy endpoints from `main.py` since they're already in routers
- Add proper logging configuration
- Add type hints consistency
- Add docstrings where missing
- Follow PEP 8 standards consistently