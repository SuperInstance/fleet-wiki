# Fleet Wiki

**The brain wiki of the fleet** — a documentation and knowledge management engine that maintains fleet-wide documentation, API references, and architecture guides.

## Features

### Wiki Engine (`wiki.py`)
- **Page storage**: Markdown files in organized directory structure
- **Page metadata**: title, author, last_modified, tags, related_pages
- **Page versioning**: Full edit history with timestamps
- **Categories**: API docs, architecture, runbooks, agent manuals, glossary, general
- **Templates**: Pre-built page templates for common doc types
- **Backlinks**: Automatic `[[wiki-link]]` detection between pages
- **Export**: Single-page HTML with CSS, full-site static export

### Full-Text Search (`search.py`)
- Inverted word index with stop word filtering
- Boolean queries: AND (implicit), OR, NOT
- Quoted phrase matching: `"fleet architecture"`
- Title-only search mode
- Tag and category filtering
- BM25 relevance ranking with title boosting
- Search suggestions / autocomplete

### Documentation Generator (`generator.py`)
- Scan agent repos for `README.md`
- Extract docstrings from Python modules via AST
- Generate API reference pages from Python codebases
- Generate architecture diagrams from fleet config
- Generate agent status pages from lighthouse data
- Generate changelogs from git history

### CLI (`cli.py`)
- `serve` — Start wiki HTTP server (REST API)
- `get <page>` — Get and display a page
- `edit <page>` — Create or edit a page
- `search "<query>"` — Search with boolean support
- `list [--category <cat>]` — List all pages
- `tags` — List all tags with counts
- `backlinks <page>` — Show pages linking to a page
- `generate-api <agent> --repo <path>` — Generate API docs
- `generate-architecture` — Generate architecture overview
- `export [--format html|md]` — Export entire wiki
- `onboard` — Set up initial wiki with starter pages

## Architecture

```
~/.superinstance/wiki/
├── index.json          # Page index
├── pages/
│   ├── api-docs/       # API documentation
│   ├── architecture/   # Architecture guides
│   ├── runbooks/       # Operational runbooks
│   ├── agent-manuals/  # Agent usage manuals
│   ├── glossary/       # Term definitions
│   └── general/        # General docs
├── history/            # Version history
│   └── <category>/
│       └── <page_id>/
│           └── <timestamp>.md
└── export/             # Static site exports
```

## Quick Start

```bash
# Initialize wiki
fleet-wiki onboard

# Create a page
echo "# My Doc\n\nContent here." | fleet-wiki edit my-doc --title "My Document" --category api-docs --tags "api,docs"

# Search
fleet-wiki search "python API"

# List pages
fleet-wiki list --category api-docs

# Generate API docs from an agent repo
fleet-wiki generate-api my-agent --repo /path/to/agent

# Start HTTP server
fleet-wiki serve --port 8001

# Export
fleet-wiki export --format html --output ./wiki-site
```

## HTTP API

When serving via `fleet-wiki serve`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all pages |
| GET | `/page/<id>` | Get a page |
| POST | `/page` | Create a page |
| POST | `/page/<id>` | Update a page |
| DELETE | `/page/<id>` | Delete a page |
| GET | `/search?q=<query>` | Search pages |
| GET | `/tags` | List all tags |
| GET | `/categories` | List categories |
| GET | `/backlinks/<id>` | Get backlinks |
| GET | `/history/<id>` | Get page history |

## Design Principles

- **Zero dependencies**: Python stdlib only, no pip installs needed
- **File-based storage**: Plain markdown files, human-readable, git-friendly
- **Versioned**: Every edit is saved with full history
- **Searchable**: Full-text BM25 search with boolean operators
- **Generative**: Auto-generate docs from source code and git history
- **Exportable**: Static HTML export with clean CSS for offline reading
