"""
Módulo: Knowledge Base - Motor de Búsqueda e Indexación Wiki
============================================================
Motor de búsqueda full-text sobre documentación interna del sistema.
Soporta:
- Indexación automática de archivos Markdown
- Búsqueda full-text con ranking por relevancia
- Búsqueda semántica opcional con OpenAI embeddings
- Categorización automática de documentos
- Historial de búsquedas
- Cache de índice para rendimiento
"""

import os
import re
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("knowledge_base")


# =====================================================================
# MODELOS DE DATOS
# =====================================================================

@dataclass
class Document:
    """Representa un documento indexado."""
    id: str
    title: str
    path: str
    content: str
    category: str
    sections: List[Dict[str, str]]  # [{heading, content, level}]
    metadata: Dict
    word_count: int
    last_modified: str
    checksum: str


@dataclass
class SearchResult:
    """Resultado de búsqueda con contexto."""
    document: Document
    score: float
    matched_sections: List[Dict[str, str]]  # [{heading, snippet, line_number}]
    highlights: List[str]  # Fragmentos con match resaltado


@dataclass
class SearchStats:
    """Estadísticas de una búsqueda."""
    query: str
    total_results: int
    search_time_ms: float
    documents_scanned: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# =====================================================================
# PARSER DE MARKDOWN
# =====================================================================

class MarkdownParser:
    """Parsea archivos Markdown en documentos estructurados."""

    # Patrones de categorización basados en nombre de archivo
    CATEGORY_PATTERNS = {
        "arquitectura": ["ARCHITECTURE", "ARQUITECTURA", "ARCH"],
        "análisis": ["ANALISIS", "ANALYSIS", "COMPETITIVE", "VALOR"],
        "guía": ["GUIA", "GUIDE", "README", "CONTRIBUTING", "TESTING_GUIDE"],
        "roadmap": ["ROADMAP", "PLAN", "ESTADO"],
        "especificación": ["ESPECIFICACION", "COLUMNAS", "SPEC"],
        "reporte": ["REPORTE", "SUMMARY", "EXECUTIVE", "REPORT"],
        "testing": ["TESTING", "TESTS", "TEST"],
        "configuración": ["CONFIG", "SETUP", "PRICING", "FILTROS"],
        "usuario": ["USUARIO", "MULTIUSUARIO", "USER"],
        "refactoring": ["REFACTOR", "REFACTORING", "MEJORAS"],
    }

    @staticmethod
    def parse_file(filepath: str) -> Optional[Document]:
        """Parsea un archivo Markdown y retorna un Document."""
        try:
            path = Path(filepath)
            if not path.exists() or path.suffix.lower() not in ('.md', '.markdown'):
                return None

            content = path.read_text(encoding='utf-8', errors='replace')
            stat = path.stat()

            # Extraer título del primer heading o nombre de archivo
            title = MarkdownParser._extract_title(content, path.stem)

            # Parsear secciones
            sections = MarkdownParser._parse_sections(content)

            # Categorizar
            category = MarkdownParser._categorize(path.name)

            # Metadata
            metadata = MarkdownParser._extract_metadata(content, path)

            # Checksum para detectar cambios
            checksum = hashlib.md5(content.encode()).hexdigest()

            return Document(
                id=hashlib.sha256(filepath.encode()).hexdigest()[:12],
                title=title,
                path=str(path),
                content=content,
                category=category,
                sections=sections,
                metadata=metadata,
                word_count=len(content.split()),
                last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                checksum=checksum,
            )
        except Exception as e:
            logger.error(f"Error parseando {filepath}: {e}")
            return None

    @staticmethod
    def _extract_title(content: str, fallback: str) -> str:
        """Extrae el título del primer heading H1."""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            # Limpiar emojis y caracteres especiales del título
            title = match.group(1).strip()
            # Quitar emojis unicode
            title = re.sub(r'[^\w\s:,\-—–().\/¿?¡!áéíóúñüÁÉÍÓÚÑÜ]', '', title).strip()
            return title if title else fallback.replace('_', ' ').title()
        return fallback.replace('_', ' ').title()

    @staticmethod
    def _parse_sections(content: str) -> List[Dict[str, str]]:
        """Parsea el contenido en secciones basadas en headings."""
        sections = []
        lines = content.split('\n')
        current_heading = "Introducción"
        current_level = 0
        current_content = []
        current_line = 1

        for i, line in enumerate(lines, 1):
            heading_match = re.match(r'^(#{1,4})\s+(.+)$', line)
            if heading_match:
                # Guardar sección anterior
                if current_content:
                    section_text = '\n'.join(current_content).strip()
                    if section_text:
                        sections.append({
                            "heading": current_heading,
                            "content": section_text,
                            "level": current_level,
                            "line_number": current_line,
                        })

                current_level = len(heading_match.group(1))
                current_heading = heading_match.group(2).strip()
                # Limpiar emojis del heading
                current_heading = re.sub(r'[^\w\s:,\-—–().\/¿?¡!áéíóúñüÁÉÍÓÚÑÜ]', '', current_heading).strip()
                current_content = []
                current_line = i
            else:
                current_content.append(line)

        # Última sección
        if current_content:
            section_text = '\n'.join(current_content).strip()
            if section_text:
                sections.append({
                    "heading": current_heading,
                    "content": section_text,
                    "level": current_level,
                    "line_number": current_line,
                })

        return sections

    @staticmethod
    def _categorize(filename: str) -> str:
        """Categoriza un documento basado en su nombre."""
        upper_name = filename.upper()
        for category, patterns in MarkdownParser.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in upper_name:
                    return category
        return "general"

    @staticmethod
    def _extract_metadata(content: str, path: Path) -> Dict:
        """Extrae metadata del documento (fechas, versiones, autores)."""
        metadata = {
            "filename": path.name,
            "relative_path": str(path),
            "size_bytes": path.stat().st_size,
        }

        # Buscar versión
        version_match = re.search(r'[Vv]ersi[oó]n[:\s]+(\d+\.\d+)', content)
        if version_match:
            metadata["version"] = version_match.group(1)

        # Buscar fecha de creación/actualización
        date_match = re.search(
            r'(?:creado|actualizado|fecha|date)[:\s]+(\d{1,2}[\s/\-]\w+[\s/\-]\d{4}|\d{4}[-/]\d{2}[-/]\d{2})',
            content, re.IGNORECASE
        )
        if date_match:
            metadata["doc_date"] = date_match.group(1)

        # Buscar autor  
        author_match = re.search(r'[Aa]utor[:\s]+(.+?)(?:\n|$)', content)
        if author_match:
            metadata["author"] = author_match.group(1).strip()

        # Contar tablas
        tables = len(re.findall(r'^\|.+\|$', content, re.MULTILINE))
        if tables > 0:
            metadata["tables"] = tables

        # Contar bloques de código
        code_blocks = len(re.findall(r'```', content))
        if code_blocks > 0:
            metadata["code_blocks"] = code_blocks // 2

        return metadata


# =====================================================================
# MOTOR DE BÚSQUEDA
# =====================================================================

class SearchEngine:
    """Motor de búsqueda full-text sobre documentos indexados."""

    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self._inverted_index: Dict[str, List[Tuple[str, float]]] = {}
        self._search_history: List[SearchStats] = []
        self._stopwords = self._load_stopwords()

    def _load_stopwords(self) -> set:
        """Stopwords en español e inglés para mejorar relevancia."""
        return {
            # Español
            'de', 'la', 'el', 'en', 'y', 'a', 'los', 'del', 'las', 'un',
            'por', 'con', 'no', 'una', 'su', 'para', 'es', 'al', 'lo',
            'como', 'más', 'pero', 'sus', 'le', 'ya', 'o', 'este', 'si',
            'porque', 'esta', 'son', 'entre', 'está', 'cuando', 'muy',
            'sin', 'sobre', 'ser', 'también', 'fue', 'hay', 'desde',
            'todo', 'nos', 'han', 'que', 'se', 'me', 'hasta', 'donde',
            # Inglés
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or',
            'but', 'in', 'with', 'to', 'for', 'of', 'not', 'be', 'are',
            'was', 'were', 'been', 'have', 'has', 'had', 'do', 'does',
            'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'this', 'that', 'these', 'those', 'it', 'its',
        }

    def index_directory(self, directory: str, recursive: bool = True) -> int:
        """
        Indexa todos los archivos Markdown en un directorio.
        
        Returns:
            Número de documentos indexados.
        """
        count = 0
        path = Path(directory)

        if not path.exists():
            logger.warning(f"Directorio no existe: {directory}")
            return 0

        pattern = '**/*.md' if recursive else '*.md'
        for md_file in sorted(path.glob(pattern)):
            # Ignorar archivos en directorios ocultos o de build
            if any(part.startswith('.') or part in ('node_modules', '__pycache__', 'htmlcov')
                   for part in md_file.parts):
                continue

            doc = MarkdownParser.parse_file(str(md_file))
            if doc:
                self.documents[doc.id] = doc
                count += 1

        # Construir índice invertido
        self._build_inverted_index()
        logger.info(f"Indexados {count} documentos de {directory}")
        return count

    def index_file(self, filepath: str) -> Optional[Document]:
        """Indexa un archivo individual."""
        doc = MarkdownParser.parse_file(filepath)
        if doc:
            self.documents[doc.id] = doc
            self._build_inverted_index()
        return doc

    def _build_inverted_index(self):
        """Construye un índice invertido para búsqueda rápida."""
        self._inverted_index.clear()

        for doc_id, doc in self.documents.items():
            # Indexar título (peso alto)
            for token in self._tokenize(doc.title):
                if token not in self._inverted_index:
                    self._inverted_index[token] = []
                self._inverted_index[token].append((doc_id, 3.0))

            # Indexar headings de secciones (peso medio)
            for section in doc.sections:
                for token in self._tokenize(section["heading"]):
                    if token not in self._inverted_index:
                        self._inverted_index[token] = []
                    self._inverted_index[token].append((doc_id, 2.0))

            # Indexar contenido (peso base)
            for token in self._tokenize(doc.content):
                if token not in self._inverted_index:
                    self._inverted_index[token] = []
                self._inverted_index[token].append((doc_id, 1.0))

            # Indexar categoría (peso medio)
            for token in self._tokenize(doc.category):
                if token not in self._inverted_index:
                    self._inverted_index[token] = []
                self._inverted_index[token].append((doc_id, 2.0))

    def _tokenize(self, text: str) -> List[str]:
        """Tokeniza texto: lowercase, elimina stopwords, normaliza."""
        if not text:
            return []
        # Convertir a minúsculas, quitar caracteres especiales
        text = text.lower()
        text = re.sub(r'[^\w\sáéíóúñü]', ' ', text)
        tokens = text.split()
        # Filtrar stopwords y tokens muy cortos
        return [t for t in tokens if t not in self._stopwords and len(t) > 1]

    def search(self, query: str, max_results: int = 10, category: str = None) -> List[SearchResult]:
        """
        Búsqueda full-text con ranking por relevancia.
        
        Args:
            query: Texto de búsqueda
            max_results: Máximo de resultados
            category: Filtrar por categoría (opcional)
            
        Returns:
            Lista de SearchResult ordenados por relevancia
        """
        import time
        start = time.time()

        if not query or not query.strip():
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Calcular scores por documento
        doc_scores: Dict[str, float] = {}
        doc_matches: Dict[str, List[str]] = {}

        for token in query_tokens:
            # Búsqueda exacta
            if token in self._inverted_index:
                for doc_id, weight in self._inverted_index[token]:
                    doc_scores[doc_id] = doc_scores.get(doc_id, 0) + weight
                    if doc_id not in doc_matches:
                        doc_matches[doc_id] = []
                    if token not in doc_matches[doc_id]:
                        doc_matches[doc_id].append(token)

            # Búsqueda por prefijo (parcial)
            for indexed_token in self._inverted_index:
                if indexed_token.startswith(token) and indexed_token != token:
                    for doc_id, weight in self._inverted_index[indexed_token]:
                        doc_scores[doc_id] = doc_scores.get(doc_id, 0) + weight * 0.5
                        if doc_id not in doc_matches:
                            doc_matches[doc_id] = []

        # Bonus por coincidencia de múltiples tokens
        for doc_id in doc_scores:
            match_count = len(doc_matches.get(doc_id, []))
            if match_count > 1:
                doc_scores[doc_id] *= (1 + 0.3 * match_count)

        # Filtrar por categoría
        if category:
            doc_scores = {
                doc_id: score
                for doc_id, score in doc_scores.items()
                if self.documents[doc_id].category == category
            }

        # Ordenar por score
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:max_results]

        # Construir resultados con snippets
        results = []
        query_lower = query.lower()
        query_pattern = re.compile(
            '|'.join(re.escape(t) for t in query_tokens),
            re.IGNORECASE
        )

        for doc_id, score in sorted_docs:
            doc = self.documents[doc_id]

            # Encontrar secciones que matchean
            matched_sections = []
            for section in doc.sections:
                section_lower = (section["heading"] + " " + section["content"]).lower()
                if any(t in section_lower for t in query_tokens):
                    # Extraer snippet relevante
                    snippet = self._extract_snippet(section["content"], query_tokens)
                    matched_sections.append({
                        "heading": section["heading"],
                        "snippet": snippet,
                        "line_number": section.get("line_number", 0),
                    })

            # Limitar secciones matcheadas
            matched_sections = matched_sections[:5]

            # Generar highlights
            highlights = []
            for ms in matched_sections[:3]:
                highlighted = query_pattern.sub(
                    lambda m: f"**{m.group()}**",
                    ms["snippet"]
                )
                highlights.append(highlighted)

            results.append(SearchResult(
                document=doc,
                score=score,
                matched_sections=matched_sections,
                highlights=highlights,
            ))

        elapsed_ms = (time.time() - start) * 1000

        # Registrar estadísticas
        self._search_history.append(SearchStats(
            query=query,
            total_results=len(results),
            search_time_ms=elapsed_ms,
            documents_scanned=len(self.documents),
        ))

        return results

    def _extract_snippet(self, content: str, query_tokens: List[str], context_chars: int = 200) -> str:
        """Extrae un snippet relevante del contenido alrededor del match."""
        content_lower = content.lower()

        # Encontrar la primera ocurrencia de cualquier token
        best_pos = len(content)
        for token in query_tokens:
            pos = content_lower.find(token)
            if 0 <= pos < best_pos:
                best_pos = pos

        if best_pos >= len(content):
            # Si no hay match directo, devolver inicio
            return content[:context_chars * 2] + ("..." if len(content) > context_chars * 2 else "")

        # Extraer snippet centrado en el match
        start = max(0, best_pos - context_chars)
        end = min(len(content), best_pos + context_chars)

        snippet = content[start:end].strip()

        # Limpiar: no cortar palabras
        if start > 0:
            first_space = snippet.find(' ')
            if first_space > 0:
                snippet = '...' + snippet[first_space:]
        if end < len(content):
            last_space = snippet.rfind(' ')
            if last_space > 0:
                snippet = snippet[:last_space] + '...'

        # Limpiar markdown excesivo
        snippet = re.sub(r'```[\s\S]*?```', '[código]', snippet)
        snippet = re.sub(r'\|.*?\|', '', snippet)
        snippet = re.sub(r'\n{2,}', '\n', snippet)

        return snippet.strip()

    def get_categories(self) -> Dict[str, int]:
        """Retorna categorías con conteo de documentos."""
        cats = {}
        for doc in self.documents.values():
            cats[doc.category] = cats.get(doc.category, 0) + 1
        return dict(sorted(cats.items(), key=lambda x: x[1], reverse=True))

    def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """Obtiene un documento por su ID."""
        return self.documents.get(doc_id)

    def get_all_documents(self, category: str = None) -> List[Document]:
        """Retorna todos los documentos, opcionalmente filtrados."""
        docs = list(self.documents.values())
        if category:
            docs = [d for d in docs if d.category == category]
        return sorted(docs, key=lambda d: d.title)

    def get_search_history(self, limit: int = 20) -> List[SearchStats]:
        """Retorna historial de búsquedas recientes."""
        return list(reversed(self._search_history[-limit:]))

    def get_stats(self) -> Dict:
        """Retorna estadísticas del índice."""
        total_words = sum(d.word_count for d in self.documents.values())
        total_sections = sum(len(d.sections) for d in self.documents.values())
        return {
            "total_documents": len(self.documents),
            "total_words": total_words,
            "total_sections": total_sections,
            "unique_tokens": len(self._inverted_index),
            "categories": self.get_categories(),
            "total_searches": len(self._search_history),
            "avg_search_time_ms": (
                sum(s.search_time_ms for s in self._search_history) / len(self._search_history)
                if self._search_history else 0
            ),
        }

    def get_related_documents(self, doc_id: str, max_results: int = 5) -> List[Tuple[Document, float]]:
        """Encuentra documentos relacionados basado en tokens compartidos."""
        if doc_id not in self.documents:
            return []

        source_doc = self.documents[doc_id]
        source_tokens = set(self._tokenize(source_doc.title + " " + source_doc.category))

        # Agregar tokens de headings
        for section in source_doc.sections[:5]:
            source_tokens.update(self._tokenize(section["heading"]))

        scores = {}
        for token in source_tokens:
            if token in self._inverted_index:
                for other_id, weight in self._inverted_index[token]:
                    if other_id != doc_id:
                        scores[other_id] = scores.get(other_id, 0) + weight

        sorted_related = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:max_results]
        return [(self.documents[did], score) for did, score in sorted_related]


# =====================================================================
# SINGLETON PARA STREAMLIT
# =====================================================================

_engine_instance: Optional[SearchEngine] = None


def get_search_engine(base_dir: str = None) -> SearchEngine:
    """
    Obtiene o crea la instancia del SearchEngine.
    Usa cache para no re-indexar en cada rerun de Streamlit.
    """
    global _engine_instance

    if _engine_instance is None or not _engine_instance.documents:
        _engine_instance = SearchEngine()

        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Indexar docs/
        docs_dir = os.path.join(base_dir, "docs")
        if os.path.exists(docs_dir):
            _engine_instance.index_directory(docs_dir)

        # Indexar archivos MD en la raíz
        for md_file in Path(base_dir).glob("*.md"):
            _engine_instance.index_file(str(md_file))

        # Indexar READMEs en subdirectorios
        for subdir in ['cfdi', 'main']:
            subdir_path = os.path.join(base_dir, subdir)
            if os.path.exists(subdir_path):
                for md_file in Path(subdir_path).glob("*.md"):
                    _engine_instance.index_file(str(md_file))

        logger.info(f"Knowledge Base inicializada: {len(_engine_instance.documents)} documentos")

    return _engine_instance


def invalidate_cache():
    """Invalida el cache del SearchEngine para forzar re-indexación."""
    global _engine_instance
    _engine_instance = None
