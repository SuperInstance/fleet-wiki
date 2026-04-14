"""
Fleet Wiki CLI — Command-line interface for the fleet wiki.

Subcommands:
  serve                  Start wiki HTTP server
  get <page>             Get a wiki page
  edit <page>            Create or edit a page
  search "<query>"       Search pages
  list [--category cat]  List pages
  tags                   List all tags
  backlinks <page>       Show backlinks to a page
  generate-api <agent>   Generate API docs for an agent
  generate-architecture  Generate architecture overview
  export [--format fmt]  Export wiki
  onboard                Set up initial wiki structure
"""

import argparse
import http.server
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wiki import FleetWiki, WIKI_ROOT, CATEGORY_DISPLAY, TEMPLATES
from search import WikiSearch
from generator import DocGenerator


def cmd_serve(args):
    """Start the wiki HTTP server."""
    wiki = FleetWiki(args.wiki_root)
    search = WikiSearch(wiki=wiki)
    port = args.port

    class WikiHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send_json(self, data, status=200):
            body = json.dumps(data, indent=2, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            path = parsed.path.rstrip("/")

            if path == "/" or path == "/index":
                pages = wiki.list_pages()
                self._send_json({
                    "wiki": "Fleet Wiki",
                    "total_pages": len(pages),
                    "categories": wiki.list_categories(),
                    "pages": [
                        {"id": p.page_id, "title": p.title, "category": p.category}
                        for p in pages
                    ],
                })
            elif path == "/search":
                query = params.get("q", [""])[0]
                tag_param = params.get("tags", [None])[0]
                tags = tag_param.split(",") if tag_param else None
                results = search.search(query, tags=tags)
                self._send_json({"results": results, "total": len(results)})
            elif path == "/tags":
                self._send_json({"tags": wiki.get_all_tags()})
            elif path == "/categories":
                self._send_json({"categories": wiki.list_categories()})
            elif path.startswith("/page/"):
                page_id = path[6:]
                page = wiki.get_page(page_id)
                if page:
                    backlinks = wiki.get_backlinks(page_id)
                    self._send_json({
                        "page_id": page.page_id,
                        "title": page.title,
                        "category": page.category,
                        "author": page.author,
                        "tags": page.tags,
                        "related_pages": page.related_pages,
                        "content": page.content,
                        "created": page.created,
                        "last_modified": page.last_modified,
                        "backlinks": backlinks,
                    })
                else:
                    self._send_json({"error": "Page not found"}, 404)
            elif path.startswith("/backlinks/"):
                page_id = path[11:]
                backlinks = wiki.get_backlinks(page_id)
                self._send_json({"page_id": page_id, "backlinks": backlinks})
            elif path.startswith("/history/"):
                page_id = path[9:]
                history = wiki.get_history(page_id)
                self._send_json({"page_id": page_id, "history": history})
            else:
                self._send_json({"error": "Not found"}, 404)

        def do_POST(self):
            from urllib.parse import urlparse
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, 400)
                return

            if path == "/page":
                title = data.get("title", "")
                content = data.get("content", "")
                category = data.get("category", "general")
                author = data.get("author", "cli")
                tags = data.get("tags", [])
                template = data.get("template")
                try:
                    page = wiki.create_page(
                        title=title, content=content, category=category,
                        author=author, tags=tags, template=template,
                    )
                    search.build_index()
                    self._send_json({"success": True, "page_id": page.page_id})
                except (ValueError, FileExistsError) as e:
                    self._send_json({"error": str(e)}, 400)
            elif path.startswith("/page/"):
                page_id = path[6:]
                try:
                    page = wiki.edit_page(
                        page_id,
                        content=data.get("content"),
                        title=data.get("title"),
                        tags=data.get("tags"),
                        author=data.get("author", "cli"),
                    )
                    search.build_index()
                    self._send_json({"success": True, "page_id": page.page_id})
                except FileNotFoundError as e:
                    self._send_json({"error": str(e)}, 404)
            else:
                self._send_json({"error": "Not found"}, 404)

        def do_DELETE(self):
            from urllib.parse import urlparse
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            if path.startswith("/page/"):
                page_id = path[6:]
                if wiki.delete_page(page_id):
                    search.build_index()
                    self._send_json({"success": True})
                else:
                    self._send_json({"error": "Page not found"}, 404)
            else:
                self._send_json({"error": "Not found"}, 404)

    server = http.server.HTTPServer(("0.0.0.0", port), WikiHandler)
    print(f"📚 Fleet Wiki server running on http://localhost:{port}")
    print(f"   Wiki root: {wiki.root}")
    print(f"   Pages: {len(wiki.list_pages())}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")
        server.server_close()


def cmd_get(args):
    """Get and display a wiki page."""
    wiki = FleetWiki(args.wiki_root)
    page = wiki.get_page(args.page)
    if not page:
        print(f"❌ Page '{args.page}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"📄 {page.title}")
    print(f"   Category: {CATEGORY_DISPLAY.get(page.category, page.category)}")
    print(f"   Author: {page.author}")
    print(f"   Tags: {', '.join(page.tags) or 'none'}")
    print(f"   Modified: {page.last_modified}")
    print(f"   Created: {page.created}")
    print()
    print(page.content)


def cmd_edit(args):
    """Create or edit a wiki page."""
    wiki = FleetWiki(args.wiki_root)
    content = ""
    if not sys.stdin.isatty():
        content = sys.stdin.read()
    tags = args.tags.split(",") if args.tags else []
    template = args.template if hasattr(args, "template") else None
    try:
        page = wiki.edit_page(
            args.page,
            content=content or None,
            title=args.title,
            tags=tags if tags else None,
            author=args.author,
        )
        print(f"✅ Updated page: {page.title} ({page.page_id})")
    except FileNotFoundError:
        try:
            page = wiki.create_page(
                title=args.title or args.page,
                content=content,
                category=args.category,
                author=args.author,
                tags=tags if tags else None,
                template=template,
            )
            print(f"✅ Created page: {page.title} ({page.page_id})")
        except (ValueError, FileExistsError) as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)


def cmd_search(args):
    """Search wiki pages."""
    wiki = FleetWiki(args.wiki_root)
    search = WikiSearch(wiki=wiki)
    tags = args.tags.split(",") if args.tags else None
    results = search.search(args.query, tags=tags, category=args.category)
    if not results:
        print(f"🔍 No results for: {args.query}")
        return
    print(f"🔍 Found {len(results)} result(s) for: {args.query}\n")
    for r in results:
        print(f"  📄 {r['title']} ({r['page_id']})")
        print(f"     Category: {r['category']} | Score: {r['score']}")
        print(f"     {r['snippet']}")
        print()


def cmd_list(args):
    """List wiki pages."""
    wiki = FleetWiki(args.wiki_root)
    pages = wiki.list_pages(category=args.category)
    if not pages:
        print("📭 No pages found.")
        return
    cat_display = CATEGORY_DISPLAY if args.category else wiki.list_categories()
    if not args.category:
        print("📂 Categories:")
        for cat, count in cat_display.items():
            print(f"   {CATEGORY_DISPLAY.get(cat, cat)}: {count} pages")
        print()
    print(f"📄 Pages ({len(pages)}):\n")
    for page in pages:
        tag_str = f" [{', '.join(page.tags)}]" if page.tags else ""
        print(f"  • {page.title} ({page.page_id}){tag_str}")
        print(f"    {page.category} · {page.author} · {page.last_modified[:10]}")


def cmd_tags(args):
    """List all tags."""
    wiki = FleetWiki(args.wiki_root)
    tags = wiki.get_all_tags()
    if not tags:
        print("🏷️  No tags found.")
        return
    print(f"🏷️  Tags ({len(tags)}):\n")
    for tag, count in tags.items():
        print(f"  {tag}: {count} page(s)")


def cmd_backlinks(args):
    """Show backlinks to a page."""
    wiki = FleetWiki(args.wiki_root)
    links = wiki.get_backlinks(args.page)
    if not links:
        print(f"🔗 No backlinks to '{args.page}' found.")
        return
    print(f"🔗 Backlinks to '{args.page}' ({len(links)}):\n")
    for link in links:
        print(f"  • {link['title']} ({link['page_id']}) [{link['category']}]")


def cmd_generate_api(args):
    """Generate API docs for an agent."""
    wiki = FleetWiki(args.wiki_root)
    gen = DocGenerator(wiki=wiki)
    result = gen.generate_api_page(args.agent, args.repo)
    if result["success"]:
        action = "Updated" if result.get("updated") else "Created"
        print(f"✅ {action} API docs: {result['title']} ({result['page_id']})")
    else:
        print(f"❌ Error: {result['error']}", file=sys.stderr)
        sys.exit(1)


def cmd_generate_architecture(args):
    """Generate architecture overview."""
    wiki = FleetWiki(args.wiki_root)
    gen = DocGenerator(wiki=wiki)
    config = None
    if args.config and os.path.exists(args.config):
        with open(args.config, "r") as f:
            config = json.load(f)
    result = gen.generate_architecture_overview(fleet_config=config)
    if result["success"]:
        print(f"✅ Generated: {result['title']} ({result['page_id']})")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown')}", file=sys.stderr)
        sys.exit(1)


def cmd_export(args):
    """Export the wiki."""
    wiki = FleetWiki(args.wiki_root)
    fmt = args.format
    if fmt == "html":
        out = wiki.export_full_site(args.output)
        print(f"✅ Exported full site to: {out}")
    elif fmt == "md":
        pages = wiki.list_pages()
        out = Path(args.output) if args.output else wiki.root / "export"
        out.mkdir(parents=True, exist_ok=True)
        for page in pages:
            safe_id = page.page_id.replace("/", "_")
            with open(out / f"{safe_id}.md", "w") as f:
                f.write(f"# {page.title}\n\n")
                f.write(f"Category: {page.category}\n")
                f.write(f"Author: {page.author}\n")
                f.write(f"Tags: {', '.join(page.tags)}\n\n")
                f.write(page.content)
        print(f"✅ Exported {len(pages)} pages to: {out}")
    else:
        print(f"❌ Unknown format: {fmt}. Use 'html' or 'md'.", file=sys.stderr)
        sys.exit(1)


def cmd_onboard(args):
    """Set up the initial wiki structure."""
    wiki = FleetWiki(args.wiki_root)
    existing = wiki.list_pages()
    if existing:
        print(f"⚠️  Wiki already has {len(existing)} pages.")
        print("   Skipping onboard to avoid overwriting existing content.")
        print("   Use --force to re-onboard.")
        if not args.force:
            return
    wiki.onboard()
    pages = wiki.list_pages()
    print(f"✅ Wiki onboarded at: {wiki.root}")
    print(f"   Created {len(pages)} starter pages:")
    for p in pages:
        print(f"   • {p.title} [{p.category}]")
    print(f"\n   Ready to use! Try: fleet-wiki list")


def main():
    parser = argparse.ArgumentParser(
        prog="fleet-wiki",
        description="📚 Fleet Wiki — Documentation & Knowledge Management",
    )
    parser.add_argument("--wiki-root", default=None, help="Wiki root directory")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    sub = subparsers.add_parser("serve", help="Start wiki HTTP server")
    sub.add_argument("--port", type=int, default=8001, help="Server port")
    sub.set_defaults(func=cmd_serve)

    sub = subparsers.add_parser("get", help="Get a wiki page")
    sub.add_argument("page", help="Page ID or slug")
    sub.set_defaults(func=cmd_get)

    sub = subparsers.add_parser("edit", help="Create or edit a page")
    sub.add_argument("page", help="Page ID or title")
    sub.add_argument("--title", help="Page title")
    sub.add_argument("--category", default="general", help="Page category")
    sub.add_argument("--author", default="cli", help="Author name")
    sub.add_argument("--tags", help="Comma-separated tags")
    sub.add_argument("--template", help="Page template to use")
    sub.set_defaults(func=cmd_edit)

    sub = subparsers.add_parser("search", help="Search wiki pages")
    sub.add_argument("query", help="Search query")
    sub.add_argument("--tags", help="Filter by tags (comma-separated)")
    sub.add_argument("--category", help="Filter by category")
    sub.set_defaults(func=cmd_search)

    sub = subparsers.add_parser("list", help="List all pages")
    sub.add_argument("--category", help="Filter by category")
    sub.set_defaults(func=cmd_list)

    subparsers.add_parser("tags", help="List all tags").set_defaults(func=cmd_tags)

    sub = subparsers.add_parser("backlinks", help="Show backlinks")
    sub.add_argument("page", help="Page ID")
    sub.set_defaults(func=cmd_backlinks)

    sub = subparsers.add_parser("generate-api", help="Generate API docs")
    sub.add_argument("agent", help="Agent name")
    sub.add_argument("--repo", required=True, help="Path to agent repository")
    sub.set_defaults(func=cmd_generate_api)

    sub = subparsers.add_parser("generate-architecture", help="Generate architecture overview")
    sub.add_argument("--config", help="Path to fleet config JSON")
    sub.set_defaults(func=cmd_generate_architecture)

    sub = subparsers.add_parser("export", help="Export wiki")
    sub.add_argument("--format", choices=["html", "md"], default="html", help="Export format")
    sub.add_argument("--output", help="Output directory")
    sub.set_defaults(func=cmd_export)

    sub = subparsers.add_parser("onboard", help="Set up initial wiki structure")
    sub.add_argument("--force", action="store_true", help="Force re-onboard")
    sub.set_defaults(func=cmd_onboard)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
