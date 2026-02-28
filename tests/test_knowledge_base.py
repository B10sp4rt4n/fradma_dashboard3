"""
Tests para el Knowledge Base engine (utils/knowledge_base.py).
"""

import os
import tempfile
import pytest
from pathlib import Path
from utils.knowledge_base import (
    MarkdownParser, SearchEngine, Document, SearchResult,
    get_search_engine, invalidate_cache,
)
from main.knowledge_base import _clean_anchor_links


# =====================================================================
# FIXTURES
# =====================================================================

SAMPLE_MD = """# Arquitectura del Sistema

## Resumen Ejecutivo

Este documento describe la **arquitectura** del sistema de dashboard.
La plataforma soporta múltiples módulos de visualización.

## Componentes Principales

### Backend
- Python 3.12
- Streamlit 1.52
- Pandas, Plotly

### Base de Datos
Neon PostgreSQL para almacenamiento de CFDIs.
Incluye tablas de usuarios y permisos.

## Roadmap

Versión: 2.0
Autor: Equipo Fradma

| Feature | Estado |
|---------|--------|
| KPIs    | ✅     |
| Heatmap | ✅     |

```python
def hello():
    return "world"
```
"""

SAMPLE_MD_2 = """# Guía de Testing

## Introducción

Guía para ejecutar y crear tests unitarios.

## Cómo Ejecutar Tests

Usa `pytest` desde la raíz del proyecto:

```bash
pytest tests/ -v
```

## Cobertura

Actualmente la cobertura es del 85%.
"""

SAMPLE_MD_3 = """# Estrategia de Pricing

## Índice

- [Resumen](#resumen)
- [Modelos](#modelos-de-precio)

## Resumen

El pricing se basa en segmentos de mercado.
Incluye análisis comparativo con competidores.

## Modelos de Precio

### PYME
$29-49/mes para empresas pequeñas.

### Enterprise
$199-499/mes para empresas grandes con soporte dedicado.
"""


@pytest.fixture
def temp_docs_dir():
    """Crea un directorio temporal con documentos Markdown de prueba."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Archivo principal
        Path(tmpdir, "ARCHITECTURE.md").write_text(SAMPLE_MD, encoding="utf-8")
        Path(tmpdir, "TESTING_GUIDE.md").write_text(SAMPLE_MD_2, encoding="utf-8")
        Path(tmpdir, "PRICING_STRATEGY.md").write_text(SAMPLE_MD_3, encoding="utf-8")

        # Subdirectorio
        subdir = Path(tmpdir, "docs")
        subdir.mkdir()
        Path(subdir, "README.md").write_text("# README\n\nDocumentación general.", encoding="utf-8")

        # Archivo vacío (debería ignorarse)
        Path(tmpdir, "empty.md").write_text("", encoding="utf-8")

        # Archivo no-md (debería ignorarse)
        Path(tmpdir, "notes.txt").write_text("Esto no es markdown", encoding="utf-8")

        yield tmpdir


@pytest.fixture
def engine(temp_docs_dir):
    """Motor de búsqueda con documentos de prueba indexados."""
    eng = SearchEngine()
    eng.index_directory(temp_docs_dir)
    # También indexar archivos sueltos en la raíz
    for md in Path(temp_docs_dir).glob("*.md"):
        eng.index_file(str(md))
    return eng


# =====================================================================
# TESTS: MarkdownParser
# =====================================================================

class TestMarkdownParser:
    """Tests para el parser de Markdown."""

    def test_parse_file_valid(self, temp_docs_dir):
        doc = MarkdownParser.parse_file(os.path.join(temp_docs_dir, "ARCHITECTURE.md"))
        assert doc is not None
        assert doc.title == "Arquitectura del Sistema"
        assert doc.category == "arquitectura"
        assert doc.word_count > 0
        assert len(doc.sections) >= 3
        assert doc.checksum  # md5 no vacío
        assert doc.id  # sha256[:12] no vacío

    def test_parse_file_nonexistent(self):
        doc = MarkdownParser.parse_file("/nonexistent/path/file.md")
        assert doc is None

    def test_parse_file_non_markdown(self, temp_docs_dir):
        doc = MarkdownParser.parse_file(os.path.join(temp_docs_dir, "notes.txt"))
        assert doc is None

    def test_extract_title_from_heading(self):
        content = "# Mi Título\n\nContenido"
        title = MarkdownParser._extract_title(content, "fallback")
        assert "Mi" in title and "tulo" in title

    def test_extract_title_fallback(self):
        content = "Sin heading válido\n\nContenido"
        title = MarkdownParser._extract_title(content, "mi_archivo")
        assert title == "Mi Archivo"

    def test_parse_sections(self):
        content = "# Título\n\nIntro\n\n## Sección 1\n\nTexto 1\n\n## Sección 2\n\nTexto 2"
        sections = MarkdownParser._parse_sections(content)
        assert len(sections) >= 2
        headings = [s["heading"] for s in sections]
        assert any("1" in h for h in headings)
        assert any("2" in h for h in headings)

    def test_parse_sections_levels(self):
        content = "# H1\n\n## H2\n\nTexto\n\n### H3\n\nMás texto"
        sections = MarkdownParser._parse_sections(content)
        levels = [s["level"] for s in sections]
        assert 2 in levels
        assert 3 in levels

    def test_categorize_architecture(self):
        assert MarkdownParser._categorize("ARCHITECTURE.md") == "arquitectura"
        assert MarkdownParser._categorize("ARQUITECTURA_ESCALABLE.md") == "arquitectura"

    def test_categorize_testing(self):
        # "TESTING" puro sin otros keywords que matcheen antes
        assert MarkdownParser._categorize("TESTING_MULTIUSUARIO.md") == "testing"
        assert MarkdownParser._categorize("TESTS_PENDIENTES.md") == "testing"

    def test_categorize_guide(self):
        # TESTING_GUIDE matchea "GUIDE" primero → categoría "guía"
        assert MarkdownParser._categorize("TESTING_GUIDE.md") == "guía"

    def test_categorize_general(self):
        assert MarkdownParser._categorize("random_file.md") == "general"

    def test_extract_metadata_version(self, temp_docs_dir):
        doc = MarkdownParser.parse_file(os.path.join(temp_docs_dir, "ARCHITECTURE.md"))
        assert doc.metadata.get("version") == "2.0"

    def test_extract_metadata_author(self, temp_docs_dir):
        doc = MarkdownParser.parse_file(os.path.join(temp_docs_dir, "ARCHITECTURE.md"))
        assert "Fradma" in doc.metadata.get("author", "")

    def test_extract_metadata_tables(self, temp_docs_dir):
        doc = MarkdownParser.parse_file(os.path.join(temp_docs_dir, "ARCHITECTURE.md"))
        assert doc.metadata.get("tables", 0) > 0

    def test_extract_metadata_code_blocks(self, temp_docs_dir):
        doc = MarkdownParser.parse_file(os.path.join(temp_docs_dir, "ARCHITECTURE.md"))
        assert doc.metadata.get("code_blocks", 0) >= 1


# =====================================================================
# TESTS: SearchEngine
# =====================================================================

class TestSearchEngine:
    """Tests para el motor de búsqueda."""

    def test_index_directory(self, temp_docs_dir):
        eng = SearchEngine()
        count = eng.index_directory(temp_docs_dir)
        assert count >= 3  # ARCHITECTURE, TESTING_GUIDE, PRICING + docs/README

    def test_index_directory_nonexistent(self):
        eng = SearchEngine()
        count = eng.index_directory("/nonexistent/dir")
        assert count == 0

    def test_index_file(self, temp_docs_dir):
        eng = SearchEngine()
        doc = eng.index_file(os.path.join(temp_docs_dir, "ARCHITECTURE.md"))
        assert doc is not None
        assert doc.id in eng.documents

    def test_inverted_index_built(self, engine):
        assert len(engine._inverted_index) > 0

    def test_search_basic(self, engine):
        results = engine.search("arquitectura")
        assert len(results) > 0
        assert results[0].document.title == "Arquitectura del Sistema"

    def test_search_multi_token(self, engine):
        results = engine.search("tests cobertura")
        assert len(results) > 0
        titles = [r.document.title for r in results]
        assert any("Testing" in t for t in titles)

    def test_search_no_results(self, engine):
        results = engine.search("xyzqwerty123nonexistent")
        assert len(results) == 0

    def test_search_empty_query(self, engine):
        results = engine.search("")
        assert len(results) == 0
        results2 = engine.search("   ")
        assert len(results2) == 0

    def test_search_by_category(self, engine):
        results = engine.search("sistema", category="arquitectura")
        assert all(r.document.category == "arquitectura" for r in results)

    def test_search_max_results(self, engine):
        results = engine.search("sistema", max_results=1)
        assert len(results) <= 1

    def test_search_has_matched_sections(self, engine):
        results = engine.search("backend python")
        if results:
            assert isinstance(results[0].matched_sections, list)

    def test_search_has_highlights(self, engine):
        results = engine.search("pricing")
        if results:
            assert isinstance(results[0].highlights, list)

    def test_search_score_ranking(self, engine):
        results = engine.search("arquitectura dashboard")
        if len(results) > 1:
            # Scores deben estar en orden descendente
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    def test_search_history_recorded(self, engine):
        engine.search("test query")
        history = engine.get_search_history(1)
        assert len(history) == 1
        assert history[0].query == "test query"
        assert history[0].search_time_ms >= 0

    def test_tokenize(self, engine):
        tokens = engine._tokenize("La Arquitectura del Sistema v2.0")
        assert "arquitectura" in tokens
        assert "sistema" in tokens
        # Stopwords filtradas
        assert "la" not in tokens
        assert "del" not in tokens

    def test_tokenize_empty(self, engine):
        assert engine._tokenize("") == []
        assert engine._tokenize(None) == []

    def test_get_categories(self, engine):
        cats = engine.get_categories()
        assert isinstance(cats, dict)
        assert len(cats) > 0
        assert "arquitectura" in cats

    def test_get_document_by_id(self, engine):
        # Obtener un doc existente
        for doc_id in engine.documents:
            doc = engine.get_document_by_id(doc_id)
            assert doc is not None
            assert doc.id == doc_id
            break

    def test_get_document_by_id_nonexistent(self, engine):
        doc = engine.get_document_by_id("nonexistent_id")
        assert doc is None

    def test_get_all_documents(self, engine):
        docs = engine.get_all_documents()
        assert len(docs) >= 3
        # Verificar que están ordenados por título
        titles = [d.title for d in docs]
        assert titles == sorted(titles)

    def test_get_all_documents_filtered(self, engine):
        docs = engine.get_all_documents(category="arquitectura")
        assert all(d.category == "arquitectura" for d in docs)

    def test_get_stats(self, engine):
        stats = engine.get_stats()
        assert stats["total_documents"] >= 3
        assert stats["total_words"] > 0
        assert stats["total_sections"] > 0
        assert stats["unique_tokens"] > 0
        assert isinstance(stats["categories"], dict)

    def test_get_related_documents(self, engine):
        # Buscar doc de arquitectura
        arch_doc = None
        for doc in engine.documents.values():
            if doc.category == "arquitectura":
                arch_doc = doc
                break
        if arch_doc:
            related = engine.get_related_documents(arch_doc.id)
            assert isinstance(related, list)
            # Cada elemento es (Document, score)
            for rel_doc, score in related:
                assert isinstance(rel_doc, Document)
                assert score > 0
                assert rel_doc.id != arch_doc.id

    def test_get_related_nonexistent(self, engine):
        related = engine.get_related_documents("fake_id")
        assert related == []

    def test_extract_snippet(self, engine):
        content = "Esto es un texto largo sobre la arquitectura del sistema que incluye varios módulos."
        snippet = engine._extract_snippet(content, ["arquitectura"])
        assert "arquitectura" in snippet.lower()

    def test_extract_snippet_no_match(self, engine):
        content = "Texto sin coincidencias con la consulta."
        snippet = engine._extract_snippet(content, ["xyznonexistent"])
        assert len(snippet) > 0  # Devuelve inicio del contenido


# =====================================================================
# TESTS: Singleton / Cache
# =====================================================================

class TestSingleton:
    """Tests para el mecanismo de cache singleton."""

    def test_invalidate_cache(self):
        invalidate_cache()
        # Después de invalidar, _engine_instance debería ser None
        from utils.knowledge_base import _engine_instance
        assert _engine_instance is None


# =====================================================================
# TESTS: UI Helper — _clean_anchor_links
# =====================================================================

class TestCleanAnchorLinks:
    """Tests para la función de limpieza de anchor links."""

    def test_basic_anchor(self):
        assert _clean_anchor_links("[Intro](#intro)") == "**Intro**"

    def test_multiple_anchors(self):
        text = "1. [Sec 1](#sec-1)\n2. [Sec 2](#sec-2)"
        expected = "1. **Sec 1**\n2. **Sec 2**"
        assert _clean_anchor_links(text) == expected

    def test_external_link_preserved(self):
        text = "[Google](https://google.com)"
        assert _clean_anchor_links(text) == text

    def test_mixed_links(self):
        text = "[Intro](#intro) y [Google](https://google.com)"
        result = _clean_anchor_links(text)
        assert "**Intro**" in result
        assert "https://google.com" in result

    def test_no_links(self):
        text = "Texto sin links"
        assert _clean_anchor_links(text) == text

    def test_empty_string(self):
        assert _clean_anchor_links("") == ""

    def test_complex_anchor(self):
        text = "[Modelos de Precio](#modelos-de-precio)"
        assert _clean_anchor_links(text) == "**Modelos de Precio**"


# =====================================================================
# TESTS: save_document y create_document
# =====================================================================

class TestDocumentCRUD:
    """Tests para guardar y crear documentos."""

    def test_save_document(self, engine, temp_docs_dir):
        # Obtener un doc existente
        doc = list(engine.documents.values())[0]
        original_content = doc.content
        new_content = original_content + "\n\n## Sección Nueva\n\nContenido agregado por test."

        result = engine.save_document(doc.id, new_content)
        assert result is True

        # Verificar que el archivo se actualizó
        saved_content = Path(doc.path).read_text(encoding='utf-8')
        assert "Sección Nueva" in saved_content

        # Verificar que el documento en memoria se actualizó
        updated_doc = engine.get_document_by_id(doc.id)
        assert updated_doc.word_count > doc.word_count

    def test_save_nonexistent_document(self, engine):
        result = engine.save_document("fake_id", "content")
        assert result is False

    def test_create_document(self, engine, temp_docs_dir):
        content = "# Test Doc\n\n## Sección 1\n\nContenido de prueba."
        doc = engine.create_document(temp_docs_dir, "TEST_NEW", content)

        assert doc is not None
        assert doc.title == "Test Doc"
        assert doc.id in engine.documents
        assert os.path.exists(os.path.join(temp_docs_dir, "TEST_NEW.md"))

    def test_create_duplicate_document(self, engine, temp_docs_dir):
        # ARCHITECTURE.md ya existe
        doc = engine.create_document(temp_docs_dir, "ARCHITECTURE", "contenido")
        assert doc is None

    def test_create_document_adds_md_extension(self, engine, temp_docs_dir):
        content = "# Auto Extension\n\nTest."
        doc = engine.create_document(temp_docs_dir, "NO_EXTENSION", content)
        assert doc is not None
        assert os.path.exists(os.path.join(temp_docs_dir, "NO_EXTENSION.md"))


# =====================================================================
# TESTS: get_document_history
# =====================================================================

class TestDocumentHistory:
    """Tests para historial git."""

    def test_history_nonexistent_doc(self, engine):
        result = engine.get_document_history("fake_id")
        assert result == []

    def test_history_returns_list(self, engine):
        doc = list(engine.documents.values())[0]
        result = engine.get_document_history(doc.id)
        # Puede estar vacío si el temp dir no es un repo git
        assert isinstance(result, list)
