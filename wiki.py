"""
Fleet Wiki — Fleet documentation and knowledge management engine.

Stores API docs, architecture guides, runbooks, and agent manuals.
Markdown files in organized directory structure at ~/.superinstance/wiki/
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


WIKI_ROOT = Path(os.path.expanduser("~/.superinstance/wiki"))

CATEGORIES = [
    "api-docs",
    "architecture",
    "runbooks",
    "agent-manuals",
    "glossary",
    "general",
]

CATEGORY_DISPLAY = {
    "api-docs": "API Documentation",
    "architecture": "Architecture Guides",
    "runbooks": "Runbooks",
    "agent-manuals": "Agent Manuals",
    "glossary": "Glossary",
    "general": "General",
}

TEMPLATES = {
    "api-doc": """# {title}

> API Documentation

## Endpoint
`{title}`

### Method
`GET/POST/PUT/DELETE /api/{title_lower}`

### Description
Describe what this endpoint does.

### Parameters
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `param` | string | Yes | Parameter description |

### Response
```json
{{"status": "ok"}}
```

### Errors
| Code | Description |
|------|-------------|
| 400 | Bad Request |

### Examples
```bash
curl -X GET http://localhost:3000/api/{title_lower}
```
""",
    "architecture": """# {title}

> Architecture Guide

## Overview
Describe the component or system.

## Components
- **Component A**: Description
- **Component B**: Description

## Data Flow
```
Input -> Process -> Output
```

## Dependencies
- Dependency 1
- Dependency 2

## Design Decisions
1. Decision one
2. Decision two
""",
    "runbook": """# {title}

> Runbook

## Purpose
Describe the purpose of this runbook.

## Prerequisites
- [ ] Prerequisite 1
- [ ] Prerequisite 2

## Steps
1. Step one
2. Step two
3. Step three

## Verification
Describe how to verify the operation succeeded.

## Rollback
Describe rollback procedure if something goes wrong.

## Troubleshooting
| Symptom | Cause | Solution |
|---------|-------|----------|
| Symptom | Root cause | Fix |
""",
    "agent-manual": """# {title}

> Agent Manual

## Agent Overview
Describe the agent.

## Capabilities
- Capability 1
- Capability 2

## Configuration
```yaml
agent:
  name: {title}
```

## Commands
| Command | Description |
|---------|-------------|
| `start` | Start the agent |

## Integration Points
- Integration 1
- Integration 2
""",
    "glossary": """# {title}

> Glossary Entry

## Definition
A clear definition of the term.

## Context
Where this term is used in the fleet.

## Related Terms
- [[Related Term 1]]
- [[Related Term 2]]

## See Also
- [Related Documentation](link)
""",
    "general": """# {title}

> General Documentation

## Overview
Write your content here.

## Details
Add detailed information.

## References
- Reference 1
""",
}


class WikiPage:
    """Represents a single wiki page with metadata."""

    def __init__(
        self,
        title: str,
        content: str = "",
        category: str = "general",
        author: str = "system",
        tags: Optional[list[str]] = None,
        related_pages: Optional[list[str]] = None,
        page_id: Optional[str] = None,
        created: Optional[str] = None,
        last_modified: Optional[str] = None,
    ):
        self.title = title
        self.content = content
        self.category = category
        self.author = author
        self.tags = tags or []
        self.related_pages = related_pages or []
        self.page_id = page_id or self._slugify(title)
        self.created = created or datetime.now(timezone.utc).isoformat()
        self.last_modified = last_modified or datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _slugify(text: str) -> str:
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug or "untitled"

    @property
    def slug(self) -> str:
        return self.page_id

    def to_dict(self) -> dict:
        return {
            "page_id": self.page_id,
            "title": self.title,
            "category": self.category,
            "author": self.author,
            "tags": self.tags,
            "related_pages": self.related_pages,
            "created": self.created,
            "last_modified": self.last_modified,
        }

    def to_meta_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class FleetWiki:
    """Fleet documentation and knowledge management.

    Stores API docs, architecture guides, runbooks, and agent manuals.
    """

    def __init__(self, wiki_root: Optional[str | Path] = None):
        self.root = Path(wiki_root) if wiki_root else WIKI_ROOT
        self.pages_dir = self.root / "pages"
        self.history_dir = self.root / "history"
        self.meta_file = self.root / "meta.json"
        self.index_file = self.root / "index.json"
        self._ensure_structure()

    def _ensure_structure(self):
        """Create directory structure if it doesn't exist."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        for cat in CATEGORIES:
            cat_dir = self.pages_dir / cat
            cat_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_file.exists():
            self._write_index({})

    def _write_index(self, index: dict):
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, default=str)

    def _read_index(self) -> dict:
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _page_path(self, page: WikiPage) -> Path:
        cat_dir = self.pages_dir / page.category
        return cat_dir / f"{page.page_id}.md"

    def _history_path(self, page: WikiPage, version: str) -> Path:
        hist_dir = self.history_dir / page.category / page.page_id
        hist_dir.mkdir(parents=True, exist_ok=True)
        return hist_dir / f"{version}.md"

    def _save_version(self, page: WikiPage):
        """Save current content to version history."""
        version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        hist_path = self._history_path(page, version)
        version_data = {
            "page_id": page.page_id,
            "title": page.title,
            "version": version,
            "author": page.author,
            "timestamp": page.last_modified,
            "content": page.content,
            "category": page.category,
            "tags": page.tags,
        }
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(version_data, f, indent=2)
        return version

    def create_page(
        self,
        title: str,
        content: str = "",
        category: str = "general",
        author: str = "system",
        tags: Optional[list[str]] = None,
        related_pages: Optional[list[str]] = None,
        template: Optional[str] = None,
    ) -> WikiPage:
        """Create a new wiki page."""
        if category not in CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. Must be one of: {CATEGORIES}"
            )
        index = self._read_index()
        page = WikiPage(
            title=title,
            content=content,
            category=category,
            author=author,
            tags=tags,
            related_pages=related_pages,
        )
        if template and template in TEMPLATES:
            page.content = TEMPLATES[template].format(
                title=title,
                title_lower=title.lower().replace(" ", "-"),
            )
        page_path = self._page_path(page)
        if page_path.exists():
            raise FileExistsError(
                f"Page '{title}' already exists. Use edit_page to modify."
            )
        self._write_page(page)
        index[page.page_id] = page.to_dict()
        self._write_index(index)
        return page

    def edit_page(
        self,
        page_id: str,
        content: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
        category: Optional[str] = None,
        author: str = "system",
    ) -> WikiPage:
        """Edit an existing wiki page. Saves version history."""
        page = self.get_page(page_id)
        if page is None:
            raise FileNotFoundError(f"Page '{page_id}' not found.")
        self._save_version(page)
        if content is not None:
            page.content = content
        if title is not None:
            page.title = title
        if tags is not None:
            page.tags = tags
        if category is not None and category in CATEGORIES:
            page.category = category
        page.author = author
        page.last_modified = datetime.now(timezone.utc).isoformat()
        self._write_page(page)
        index = self._read_index()
        index[page.page_id] = page.to_dict()
        self._write_index(index)
        return page

    def _write_page(self, page: WikiPage):
        """Write page content with YAML-like front matter."""
        page_path = self._page_path(page)
        page_path.parent.mkdir(parents=True, exist_ok=True)
        front_matter = (
            f"---\n"
            f"title: {page.title}\n"
            f"category: {page.category}\n"
            f"author: {page.author}\n"
            f"tags: {json.dumps(page.tags)}\n"
            f"related: {json.dumps(page.related_pages)}\n"
            f"created: {page.created}\n"
            f"last_modified: {page.last_modified}\n"
            f"---\n\n"
        )
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(front_matter)
            f.write(page.content)

    def _read_page_file(self, page_path: Path) -> Optional[dict]:
        """Read page file and parse front matter."""
        try:
            with open(page_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except FileNotFoundError:
            return None
        meta = {}
        content = raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip()
                        if key in ("tags", "related"):
                            try:
                                meta[key] = json.loads(value)
                            except json.JSONDecodeError:
                                meta[key] = []
                        else:
                            meta[key] = value
                content = parts[2].strip()
        return {"meta": meta, "content": content}

    def get_page(self, page_id: str) -> Optional[WikiPage]:
        """Get a page by its slug ID."""
        index = self._read_index()
        if page_id not in index:
            for cat in CATEGORIES:
                page_file = self.pages_dir / cat / f"{page_id}.md"
                if page_file.exists():
                    return self._load_page_from_file(page_file)
            return None
        return self._load_page_from_id(page_id)

    def _load_page_from_id(self, page_id: str) -> Optional[WikiPage]:
        index = self._read_index()
        info = index.get(page_id)
        if not info:
            return None
        cat = info.get("category", "general")
        page_file = self.pages_dir / cat / f"{page_id}.md"
        if not page_file.exists():
            return None
        return self._load_page_from_file(page_file)

    def _load_page_from_file(self, page_file: Path) -> Optional[WikiPage]:
        data = self._read_page_file(page_file)
        if data is None:
            return None
        meta = data["meta"]
        return WikiPage(
            title=meta.get("title", page_file.stem),
            content=data["content"],
            category=meta.get("category", "general"),
            author=meta.get("author", "system"),
            tags=meta.get("tags", []),
            related_pages=meta.get("related", []),
            page_id=page_file.stem,
            created=meta.get("created"),
            last_modified=meta.get("last_modified"),
        )

    def delete_page(self, page_id: str) -> bool:
        """Delete a wiki page."""
        index = self._read_index()
        if page_id not in index:
            return False
        cat = index[page_id].get("category", "general")
        page_file = self.pages_dir / cat / f"{page_id}.md"
        if page_file.exists():
            page_file.unlink()
        del index[page_id]
        self._write_index(index)
        return True

    def list_pages(self, category: Optional[str] = None) -> list[WikiPage]:
        """List all pages, optionally filtered by category."""
        pages = []
        index = self._read_index()
        for page_id, info in index.items():
            if category and info.get("category") != category:
                continue
            page = self._load_page_from_id(page_id)
            if page:
                pages.append(page)
        return sorted(pages, key=lambda p: p.title.lower())

    def list_categories(self) -> dict[str, int]:
        """List all categories with page counts."""
        counts: dict[str, int] = {cat: 0 for cat in CATEGORIES}
        index = self._read_index()
        for info in index.values():
            cat = info.get("category", "general")
            if cat in counts:
                counts[cat] += 1
        return counts

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags with their page counts."""
        tags: dict[str, int] = {}
        index = self._read_index()
        for info in index.values():
            for tag in info.get("tags", []):
                tags[tag] = tags.get(tag, 0) + 1
        return dict(sorted(tags.items(), key=lambda x: x[1], reverse=True))

    def get_backlinks(self, page_id: str) -> list[dict]:
        """Find all pages that link to the given page."""
        backlinks = []
        index = self._read_index()
        target = page_id.replace("-", " ").lower()
        for other_id, info in index.items():
            if other_id == page_id:
                continue
            page = self._load_page_from_id(other_id)
            if not page:
                continue
            links = self._extract_links(page.content)
            for link in links:
                link_lower = link.replace("-", " ").lower()
                if link_lower == target or link == page_id:
                    backlinks.append(
                        {
                            "page_id": other_id,
                            "title": info.get("title", other_id),
                            "category": info.get("category", "general"),
                        }
                    )
                    break
        return backlinks

    def _extract_links(self, content: str) -> list[str]:
        """Extract wiki-style [[links]] from content."""
        return re.findall(r"\[\[([^\]]+)\]\]", content)

    def get_history(self, page_id: str) -> list[dict]:
        """Get version history for a page."""
        versions = []
        index = self._read_index()
        if page_id not in index:
            return versions
        cat = index[page_id].get("category", "general")
        hist_dir = self.history_dir / cat / page_id
        if not hist_dir.exists():
            return versions
        for vfile in sorted(hist_dir.iterdir(), reverse=True):
            if vfile.suffix == ".md":
                try:
                    with open(vfile, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    versions.append(
                        {
                            "version": data.get("version", vfile.stem),
                            "author": data.get("author", "unknown"),
                            "timestamp": data.get("timestamp", ""),
                        }
                    )
                except (json.JSONDecodeError, OSError):
                    continue
        return versions

    def export_single_html(self, page_id: str) -> str:
        """Export a single page as a self-contained HTML file."""
        page = self.get_page(page_id)
        if not page:
            raise FileNotFoundError(f"Page '{page_id}' not found")
        html_content = self._markdown_to_html(page.content)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page.title} — Fleet Wiki</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6;
         color: #1a1a2e; background: #fafafa; }}
  h1 {{ color: #16213e; border-bottom: 2px solid #0f3460; padding-bottom: 0.5rem; }}
  h2 {{ color: #16213e; margin-top: 1.5rem; }}
  code {{ background: #e8e8e8; padding: 0.2rem 0.4rem; border-radius: 3px;
          font-size: 0.9em; }}
  pre {{ background: #1a1a2e; color: #e0e0e0; padding: 1rem; border-radius: 6px;
        overflow-x: auto; }}
  pre code {{ background: transparent; padding: 0; color: inherit; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; }}
  th {{ background: #0f3460; color: white; }}
  blockquote {{ border-left: 4px solid #0f3460; padding-left: 1rem;
               color: #555; margin: 1rem 0; }}
  .meta {{ color: #888; font-size: 0.85rem; margin-bottom: 1rem; }}
  .tags {{ margin-top: 1rem; }}
  .tag {{ display: inline-block; background: #0f3460; color: white;
          padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem;
          margin-right: 0.3rem; }}
</style>
</head>
<body>
<h1>{page.title}</h1>
<div class="meta">
  Category: {CATEGORY_DISPLAY.get(page.category, page.category)} |
  Author: {page.author} |
  Last modified: {page.last_modified}
</div>
{html_content}
<div class="tags">
  {' '.join(f'<span class="tag">{t}</span>' for t in page.tags)}
</div>
</body>
</html>"""

    def export_full_site(self, output_dir: Optional[str] = None) -> str:
        """Export the entire wiki as a static HTML site."""
        out = Path(output_dir) if output_dir else self.root / "export"
        out.mkdir(parents=True, exist_ok=True)
        pages = self.list_pages()
        index_html_parts = ["<!DOCTYPE html><html><head><meta charset='UTF-8'>",
                            "<title>Fleet Wiki</title><style>",
                            "body{font-family:sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;}",
                            "a{color:#0f3466;text-decoration:none;}",
                            "a:hover{text-decoration:underline;}",
                            ".page{border:1px solid #eee;padding:1rem;margin:0.5rem 0;border-radius:6px;}",
                            ".tag{display:inline-block;background:#0f3460;color:#fff;padding:0.15rem 0.5rem;border-radius:10px;font-size:0.8rem;margin-right:0.2rem;}",
                            "</style></head><body>",
                            "<h1>📚 Fleet Wiki</h1><p>All documentation pages.</p>"]
        for page in pages:
            html = self.export_single_html(page.page_id)
            safe_id = page.page_id.replace("/", "_")
            page_file = out / f"{safe_id}.html"
            with open(page_file, "w", encoding="utf-8") as f:
                f.write(html)
            tag_str = " ".join(f"<span class='tag'>{t}</span>" for t in page.tags)
            index_html_parts.append(
                f'<div class="page"><a href="{safe_id}.html"><h3>{page.title}</h3></a>'
                f"<p><small>{page.category} · {page.author} · {page.last_modified[:10]}</small></p>"
                f"<div>{tag_str}</div></div>"
            )
        index_html_parts.append("</body></html>")
        index_path = out / "index.html"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(index_html_parts))
        return str(out)

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        """Convert basic Markdown to HTML (no external deps)."""
        lines = md.split("\n")
        html_lines: list[str] = []
        in_code_block = False
        in_table = False
        in_list = False
        for line in lines:
            if line.startswith("```"):
                in_code_block = not in_code_block
                tag = "pre><code" if in_code_block else "code></pre"
                html_lines.append(f"<{tag}>")
                continue
            if in_code_block:
                html_lines.append(line)
                continue
            if line.startswith("| ") and "|" in line[2:]:
                cells = [c.strip() for c in line.strip("|").split("|")]
                tag = "th" if not in_table else "td"
                row = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
                if not in_table:
                    html_lines.append("<table>")
                    in_table = True
                html_lines.append(f"<tr>{row}</tr>")
                continue
            elif in_table and not line.startswith("|"):
                html_lines.append("</table>")
                in_table = False
            if line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_lines.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("#### "):
                html_lines.append(f"<h4>{line[5:]}</h4>")
            elif re.match(r"^[-*] ", line):
                item = re.sub(r"^[-*] ", "", line)
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                html_lines.append(f"<li>{item}</li>")
            elif re.match(r"^\d+\. ", line):
                item = re.sub(r"^\d+\. ", "", line)
                if not in_list:
                    html_lines.append("<ol>")
                    in_list = True
                html_lines.append(f"<li>{item}</li>")
            else:
                if in_list:
                    html_lines.append("</ul>" if True else "</ol>")
                    in_list = False
                if line.startswith("> "):
                    html_lines.append(f"<blockquote><p>{line[2:]}</p></blockquote>")
                elif line.strip() == "":
                    html_lines.append("<br>")
                else:
                    processed = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
                    processed = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", processed)
                    processed = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href='\2'>\1</a>", processed)
                    processed = re.sub(r"\[\[([^\]]+)\]\]", r"<a href='\1'>\1</a>", processed)
                    html_lines.append(f"<p>{processed}</p>")
        if in_table:
            html_lines.append("</table>")
        if in_list:
            html_lines.append("</ul>")
        return "\n".join(html_lines)

    def onboard(self):
        """Set up initial wiki structure with helpful pages."""
        self.create_page(
            "Home",
            "# Welcome to Fleet Wiki\n\n"
            "> The knowledge base for the fleet.\n\n"
            "## Getting Started\n"
            "- [[Getting Started Guide]]\n"
            "- [[Fleet Architecture]]\n"
            "- [[Glossary]]\n\n"
            "## Categories\n"
            "- API Documentation\n"
            "- Architecture Guides\n"
            "- Runbooks\n"
            "- Agent Manuals\n",
            category="general",
            author="system",
            tags=["welcome", "home"],
        )
        self.create_page(
            "Fleet Architecture",
            "## Overview\n\n"
            "The fleet is a collection of autonomous AI agents that coordinate "
            "to accomplish complex tasks.\n\n"
            "## Core Components\n\n"
            "- **Fleet Wiki** (this system) — Knowledge management\n"
            "- **Lighthouse** — Fleet monitoring\n"
            "- **Orchestrator** — Task coordination\n\n"
            "## Communication\n\n"
            "Agents communicate via a message bus using JSON payloads.",
            category="architecture",
            author="system",
            tags=["architecture", "fleet"],
        )
        self.create_page(
            "Glossary",
            "## Fleet Terms\n\n"
            "- **Agent**: An autonomous AI unit in the fleet\n"
            "- **Fleet**: A group of coordinated agents\n"
            "- **Wiki**: This documentation system\n"
            "- **Lighthouse**: Fleet health monitoring service\n"
            "- **Runbook**: Step-by-step operational procedure",
            category="glossary",
            author="system",
            tags=["glossary", "terms"],
        )
        self.create_page(
            "Getting Started Guide",
            "## Quick Start\n\n"
            "1. Navigate the wiki using the sidebar\n"
            "2. Search for topics using the search command\n"
            "3. Use `fleet-wiki edit <page>` to add content\n\n"
            "## Contributing\n\n"
            "All fleet members can contribute to the wiki.\n"
            "Follow the existing templates for consistency.",
            category="runbooks",
            author="system",
            tags=["getting-started", "guide"],
        )
