"""
Generador de Wiki Activo — Fradma Dashboard
=============================================
Inspecciona el codebase en tiempo real y genera documentación
actualizada automáticamente. Se ejecuta desde el Knowledge Base
o como script independiente.

Uso:
    python scripts/generate_wiki.py          # Genera docs/WIKI_ACTIVO.md
    python scripts/generate_wiki.py --json   # Salida JSON para API
"""

import os
import re
import ast
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent.parent


# =====================================================================
# INSPECCIÓN DE CÓDIGO
# =====================================================================

def _count_lines(filepath: str) -> int:
    try:
        return sum(1 for _ in open(filepath, encoding='utf-8', errors='replace'))
    except Exception:
        return 0


def _extract_functions_and_classes(filepath: str) -> Dict:
    """Extrae funciones y clases de un archivo Python usando AST."""
    try:
        source = Path(filepath).read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(source)
    except Exception:
        return {"functions": [], "classes": []}

    functions = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node) or ""
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "doc": doc.split('\n')[0][:120] if doc else "",
                "args": len(node.args.args),
            })
        elif isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            methods = [
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "doc": doc.split('\n')[0][:120] if doc else "",
                "methods": methods,
            })

    return {"functions": functions, "classes": classes}


def _extract_module_docstring(filepath: str) -> str:
    """Extrae el docstring del módulo."""
    try:
        source = Path(filepath).read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(source)
        doc = ast.get_docstring(tree)
        return doc.split('\n')[0][:150] if doc else ""
    except Exception:
        return ""


def scan_directory(directory: str, pattern: str = "*.py") -> List[Dict]:
    """Escanea un directorio y extrae metadata de cada archivo Python."""
    results = []
    dir_path = Path(directory)
    if not dir_path.exists():
        return results

    for pyfile in sorted(dir_path.glob(pattern)):
        if pyfile.name == "__init__.py":
            continue
        if "__pycache__" in str(pyfile):
            continue

        info = _extract_functions_and_classes(str(pyfile))
        docstring = _extract_module_docstring(str(pyfile))
        lines = _count_lines(str(pyfile))

        results.append({
            "name": pyfile.stem,
            "filename": pyfile.name,
            "path": str(pyfile.relative_to(BASE_DIR)),
            "lines": lines,
            "docstring": docstring,
            "functions": info["functions"],
            "classes": info["classes"],
            "function_count": len(info["functions"]),
            "class_count": len(info["classes"]),
        })

    return results


# =====================================================================
# GIT STATS
# =====================================================================

def get_git_stats() -> Dict:
    """Obtiene estadísticas de git."""
    stats = {}
    try:
        r = subprocess.run(
            ["git", "log", "--oneline"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=10
        )
        stats["total_commits"] = len(r.stdout.strip().split('\n')) if r.stdout.strip() else 0

        r2 = subprocess.run(
            ["git", "log", "--format=%ai", "-1"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=5
        )
        stats["last_commit"] = r2.stdout.strip()[:19] if r2.stdout.strip() else "N/A"

        r3 = subprocess.run(
            ["git", "log", "--format=%ai", "--reverse"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=10
        )
        lines = r3.stdout.strip().split('\n')
        stats["first_commit"] = lines[0][:10] if lines else "N/A"

        # Contribuidores
        r4 = subprocess.run(
            ["git", "shortlog", "-sn", "--no-merges"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=10
        )
        contributors = []
        for line in r4.stdout.strip().split('\n'):
            if line.strip():
                parts = line.strip().split('\t')
                if len(parts) == 2:
                    contributors.append({
                        "name": parts[1],
                        "commits": int(parts[0].strip())
                    })
        stats["contributors"] = contributors

    except Exception:
        stats.setdefault("total_commits", 0)
        stats.setdefault("last_commit", "N/A")
        stats.setdefault("first_commit", "N/A")
        stats.setdefault("contributors", [])

    return stats


# =====================================================================
# TEST STATS
# =====================================================================

def get_test_stats() -> Dict:
    """Cuenta tests y archivos de test."""
    test_dir = BASE_DIR / "tests"
    total_tests = 0
    test_files = 0
    coverage_pct = None

    for pyfile in test_dir.rglob("test_*.py"):
        test_files += 1
        try:
            content = pyfile.read_text(encoding='utf-8', errors='replace')
            total_tests += len(re.findall(r'def test_', content))
        except Exception:
            pass

    # Intentar leer coverage
    cov_xml = BASE_DIR / "coverage.xml"
    if cov_xml.exists():
        try:
            content = cov_xml.read_text()
            match = re.search(r'line-rate="([\d.]+)"', content)
            if match:
                coverage_pct = float(match.group(1)) * 100
        except Exception:
            pass

    return {
        "total_tests": total_tests,
        "test_files": test_files,
        "coverage_pct": coverage_pct,
    }


# =====================================================================
# DEPENDENCY STATS
# =====================================================================

def get_dependencies() -> Dict[str, List[str]]:
    """Lee los archivos de dependencias."""
    deps = {"production": [], "development": []}

    req_file = BASE_DIR / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text().strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                deps["production"].append(line)

    req_dev = BASE_DIR / "requirements-dev.txt"
    if req_dev.exists():
        for line in req_dev.read_text().strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('-r'):
                deps["development"].append(line)

    return deps


# =====================================================================
# MENU ITEMS (app.py)
# =====================================================================

def get_menu_items() -> List[str]:
    """Extrae los items del menú lateral de app.py (array opciones_menu)."""
    app_file = BASE_DIR / "app.py"
    if not app_file.exists():
        return []

    content = app_file.read_text(encoding='utf-8', errors='replace')
    # Buscar el bloque opciones_menu = [ ... ]
    match = re.search(r'opciones_menu\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not match:
        return []

    block = match.group(1)
    items = re.findall(r'"([^"]+)"', block)

    # También capturar las opciones admin (.extend)
    ext_match = re.search(r'opciones_menu\.extend\(\s*\[(.*?)\]\s*\)', content, re.DOTALL)
    if ext_match:
        items += re.findall(r'"([^"]+)"', ext_match.group(1))

    return items


# =====================================================================
# GENERADOR PRINCIPAL
# =====================================================================

def generate_inventory() -> Dict:
    """Genera el inventario completo del proyecto."""
    now = datetime.now().isoformat()[:19]

    main_modules = scan_directory(str(BASE_DIR / "main"))
    utils_modules = scan_directory(str(BASE_DIR / "utils"))
    cfdi_modules = scan_directory(str(BASE_DIR / "cfdi"))

    app_lines = _count_lines(str(BASE_DIR / "app.py"))
    app_info = _extract_functions_and_classes(str(BASE_DIR / "app.py"))

    total_main = sum(m["lines"] for m in main_modules)
    total_utils = sum(m["lines"] for m in utils_modules)
    total_cfdi = sum(m["lines"] for m in cfdi_modules)

    git = get_git_stats()
    tests = get_test_stats()
    deps = get_dependencies()
    menu = get_menu_items()

    return {
        "generated_at": now,
        "project": {
            "name": "Fradma Dashboard (Cima Analytics)",
            "total_python_lines": total_main + total_utils + total_cfdi + app_lines,
            "total_modules": len(main_modules) + len(utils_modules) + len(cfdi_modules) + 1,
            "menu_items": menu,
        },
        "main": {"modules": main_modules, "total_lines": total_main},
        "utils": {"modules": utils_modules, "total_lines": total_utils},
        "cfdi": {"modules": cfdi_modules, "total_lines": total_cfdi},
        "app": {"lines": app_lines, "info": app_info},
        "git": git,
        "tests": tests,
        "dependencies": deps,
    }


def generate_markdown(inventory: Dict) -> str:
    """Genera la wiki en formato Markdown a partir del inventario."""
    p = inventory["project"]
    git = inventory["git"]
    tests = inventory["tests"]
    now = inventory["generated_at"]

    lines = []
    lines.append(f"# Wiki Activo — {p['name']}")
    lines.append("")
    lines.append(f"> Generado automáticamente: **{now}**")
    lines.append(f"> Este documento se regenera desde el código fuente real.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Resumen Ejecutivo ──
    lines.append("## Resumen Ejecutivo")
    lines.append("")
    lines.append(f"| Métrica | Valor |")
    lines.append(f"|---------|-------|")
    lines.append(f"| Líneas de código Python | **{p['total_python_lines']:,}** |")
    lines.append(f"| Módulos Python | **{p['total_modules']}** |")
    lines.append(f"| Tests | **{tests['total_tests']}** en {tests['test_files']} archivos |")
    if tests.get("coverage_pct"):
        lines.append(f"| Cobertura | **{tests['coverage_pct']:.1f}%** |")
    lines.append(f"| Commits | **{git['total_commits']}** |")
    lines.append(f"| Último commit | {git['last_commit']} |")
    lines.append(f"| Inicio del proyecto | {git['first_commit']} |")
    lines.append(f"| Items del menú | **{len(p['menu_items'])}** módulos |")
    lines.append("")

    # ── Menú de la App ──
    lines.append("## Menú de la Aplicación")
    lines.append("")
    for i, item in enumerate(p["menu_items"], 1):
        lines.append(f"{i}. {item}")
    lines.append("")

    # ── Módulos principales ──
    for section_key, section_title, section_icon in [
        ("main", "Módulos Principales (main/)", "📊"),
        ("utils", "Utilidades (utils/)", "🔧"),
        ("cfdi", "CFDI (cfdi/)", "📄"),
    ]:
        data = inventory[section_key]
        if not data["modules"]:
            continue

        lines.append(f"## {section_icon} {section_title}")
        lines.append("")
        lines.append(f"**Total: {data['total_lines']:,} líneas en {len(data['modules'])} módulos**")
        lines.append("")

        for mod in data["modules"]:
            func_count = mod["function_count"]
            class_count = mod["class_count"]
            desc = mod["docstring"] or "_Sin docstring_"

            lines.append(f"### `{mod['filename']}` ({mod['lines']:,} líneas)")
            lines.append(f"_{desc}_")
            lines.append("")

            if mod["classes"]:
                for cls in mod["classes"]:
                    methods_str = ", ".join(f"`{m}`" for m in cls["methods"][:8])
                    extra = f" +{len(cls['methods'])-8} más" if len(cls["methods"]) > 8 else ""
                    lines.append(f"- **class `{cls['name']}`** (línea {cls['line']}): {cls['doc'][:80]}")
                    if cls["methods"]:
                        lines.append(f"  - Métodos: {methods_str}{extra}")

            if mod["functions"]:
                pub_funcs = [f for f in mod["functions"] if not f["name"].startswith("_")]
                priv_funcs = [f for f in mod["functions"] if f["name"].startswith("_")]

                if pub_funcs:
                    lines.append(f"- **Funciones públicas ({len(pub_funcs)}):**")
                    for f in pub_funcs[:15]:
                        doc_part = f" — _{f['doc']}_" if f["doc"] else ""
                        lines.append(f"  - `{f['name']}()` (L{f['line']}){doc_part}")

                if priv_funcs:
                    names = ", ".join(f"`{f['name']}`" for f in priv_funcs[:10])
                    extra = f" +{len(priv_funcs)-10}" if len(priv_funcs) > 10 else ""
                    lines.append(f"- Funciones privadas ({len(priv_funcs)}): {names}{extra}")

            lines.append("")

    # ── Dependencias ──
    deps = inventory["dependencies"]
    lines.append("## 📦 Dependencias")
    lines.append("")
    lines.append("### Producción")
    lines.append("")
    for dep in deps["production"]:
        lines.append(f"- `{dep}`")
    lines.append("")
    if deps["development"]:
        lines.append("### Desarrollo")
        lines.append("")
        for dep in deps["development"]:
            lines.append(f"- `{dep}`")
        lines.append("")

    # ── Contributors ──
    if git.get("contributors"):
        lines.append("## 👥 Contribuidores")
        lines.append("")
        lines.append("| Autor | Commits |")
        lines.append("|-------|---------|")
        for c in git["contributors"]:
            lines.append(f"| {c['name']} | {c['commits']} |")
        lines.append("")

    # ── Tests ──
    lines.append("## 🧪 Estado de Tests")
    lines.append("")
    lines.append(f"- **{tests['total_tests']} tests** en {tests['test_files']} archivos")
    if tests.get("coverage_pct"):
        lines.append(f"- Cobertura: **{tests['coverage_pct']:.1f}%**")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"_Wiki generado por `scripts/generate_wiki.py` el {now}_")
    lines.append(f"_Para regenerar: `python scripts/generate_wiki.py`_")
    lines.append("")

    return "\n".join(lines)


# =====================================================================
# CLI
# =====================================================================

def main():
    import sys

    inventory = generate_inventory()

    if "--json" in sys.argv:
        print(json.dumps(inventory, indent=2, ensure_ascii=False, default=str))
    else:
        markdown = generate_markdown(inventory)
        output_path = BASE_DIR / "docs" / "WIKI_ACTIVO.md"
        output_path.write_text(markdown, encoding='utf-8')
        print(f"✅ Wiki generado: {output_path}")
        print(f"   {inventory['project']['total_python_lines']:,} líneas · "
              f"{inventory['project']['total_modules']} módulos · "
              f"{inventory['tests']['total_tests']} tests · "
              f"{inventory['git']['total_commits']} commits")


if __name__ == "__main__":
    main()
