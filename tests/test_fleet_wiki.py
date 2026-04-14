"""
Fleet Wiki Test Suite — Comprehensive tests for the wiki engine, search, and generator.
"""

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from wiki import FleetWiki
from search import WikiSearch


class TestWikiPage(unittest.TestCase):
    """Tests for WikiPage model."""

    def test_slugify_basic(self):
        from wiki import WikiPage
        self.assertEqual(WikiPage._slugify("Hello World"), "hello-world")

    def test_slugify_special_chars(self):
        from wiki import WikiPage
        self.assertEqual(WikiPage._slugify("API Reference!"), "api-reference")

    def test_slugify_empty(self):
        from wiki import WikiPage
        self.assertEqual(WikiPage._slugify(""), "untitled")

    def test_page_creation(self):
        from wiki import WikiPage
        page = WikiPage(title="Test Page", content="Hello", category="api-docs")
        self.assertEqual(page.title, "Test Page")
        self.assertEqual(page.content, "Hello")
        self.assertEqual(page.category, "api-docs")
        self.assertEqual(page.page_id, "test-page")
        self.assertEqual(page.author, "system")
        self.assertEqual(page.tags, [])

    def test_page_to_dict(self):
        from wiki import WikiPage
        page = WikiPage(title="Test", tags=["a", "b"], related_pages=["other"])
        d = page.to_dict()
        self.assertEqual(d["title"], "Test")
        self.assertEqual(d["tags"], ["a", "b"])
        self.assertEqual(d["related_pages"], ["other"])
        self.assertIn("page_id", d)
        self.assertIn("created", d)

    def test_page_custom_author(self):
        from wiki import WikiPage
        page = WikiPage(title="Test", author="alice")
        self.assertEqual(page.author, "alice")

    def test_page_custom_id(self):
        from wiki import WikiPage
        page = WikiPage(title="Test", page_id="custom-id")
        self.assertEqual(page.page_id, "custom-id")
        self.assertEqual(page.slug, "custom-id")


class TestFleetWiki(unittest.TestCase):
    """Tests for FleetWiki core engine."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.wiki = FleetWiki(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_creates_structure(self):
        root = Path(self.test_dir)
        self.assertTrue(root.exists())
        self.assertTrue((root / "pages").exists())
        self.assertTrue((root / "history").exists())
        self.assertTrue((root / "pages" / "api-docs").exists())
        self.assertTrue((root / "pages" / "architecture").exists())
        self.assertTrue((root / "index.json").exists())

    def test_create_page(self):
        page = self.wiki.create_page(
            title="Test Page",
            content="Hello world",
            category="general",
            author="tester",
            tags=["test", "hello"],
        )
        self.assertEqual(page.title, "Test Page")
        self.assertEqual(page.page_id, "test-page")
        self.assertEqual(page.category, "general")

    def test_create_page_invalid_category(self):
        with self.assertRaises(ValueError):
            self.wiki.create_page(title="Bad", category="nonexistent")

    def test_create_duplicate_page(self):
        self.wiki.create_page(title="Dup", category="general")
        with self.assertRaises(FileExistsError):
            self.wiki.create_page(title="Dup", category="general")

    def test_get_page(self):
        self.wiki.create_page(title="My Page", content="Content here")
        page = self.wiki.get_page("my-page")
        self.assertIsNotNone(page)
        self.assertEqual(page.title, "My Page")
        self.assertEqual(page.content, "Content here")

    def test_get_nonexistent_page(self):
        page = self.wiki.get_page("does-not-exist")
        self.assertIsNone(page)

    def test_edit_page(self):
        self.wiki.create_page(title="Edit Me", content="Old content")
        page = self.wiki.edit_page("edit-me", content="New content", author="editor")
        self.assertEqual(page.content, "New content")
        self.assertEqual(page.author, "editor")

    def test_edit_page_history(self):
        self.wiki.create_page(title="Hist", content="v1")
        self.wiki.edit_page("hist", content="v2")
        history = self.wiki.get_history("hist")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["author"], "system")

    def test_edit_nonexistent_page(self):
        with self.assertRaises(FileNotFoundError):
            self.wiki.edit_page("nope", content="x")

    def test_delete_page(self):
        self.wiki.create_page(title="Delete Me", category="general")
        self.assertTrue(self.wiki.delete_page("delete-me"))
        self.assertIsNone(self.wiki.get_page("delete-me"))

    def test_delete_nonexistent_page(self):
        self.assertFalse(self.wiki.delete_page("nope"))

    def test_list_pages(self):
        self.wiki.create_page(title="Alpha", category="api-docs")
        self.wiki.create_page(title="Beta", category="general")
        self.wiki.create_page(title="Gamma", category="api-docs")
        pages = self.wiki.list_pages()
        self.assertEqual(len(pages), 3)
        titles = [p.title for p in pages]
        self.assertIn("Alpha", titles)
        self.assertIn("Beta", titles)
        self.assertIn("Gamma", titles)

    def test_list_pages_by_category(self):
        self.wiki.create_page(title="A", category="api-docs")
        self.wiki.create_page(title="B", category="general")
        pages = self.wiki.list_pages(category="api-docs")
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].title, "A")

    def test_list_categories(self):
        self.wiki.create_page(title="A", category="api-docs")
        self.wiki.create_page(title="B", category="api-docs")
        self.wiki.create_page(title="C", category="general")
        cats = self.wiki.list_categories()
        self.assertEqual(cats["api-docs"], 2)
        self.assertEqual(cats["general"], 1)

    def test_get_all_tags(self):
        self.wiki.create_page(title="T1", tags=["python", "api"])
        self.wiki.create_page(title="T2", tags=["python", "web"])
        self.wiki.create_page(title="T3", tags=["api"])
        tags = self.wiki.get_all_tags()
        self.assertEqual(tags["python"], 2)
        self.assertEqual(tags["api"], 2)
        self.assertEqual(tags["web"], 1)

    def test_backlinks(self):
        self.wiki.create_page(
            title="Target",
            content="Target page",
            category="general",
        )
        self.wiki.create_page(
            title="Linker",
            content="See [[Target]] for details",
            category="general",
        )
        self.wiki.create_page(
            title="Unrelated",
            content="No links here",
            category="general",
        )
        backlinks = self.wiki.get_backlinks("target")
        self.assertEqual(len(backlinks), 1)
        self.assertEqual(backlinks[0]["page_id"], "linker")

    def test_backlinks_case_insensitive(self):
        self.wiki.create_page(title="API Reference", content="API docs")
        self.wiki.create_page(
            title="Other", content="Check the [[api-reference]] page",
            category="general",
        )
        backlinks = self.wiki.get_backlinks("api-reference")
        self.assertEqual(len(backlinks), 1)

    def test_create_with_template(self):
        page = self.wiki.create_page(
            title="My API",
            category="api-docs",
            template="api-doc",
        )
        self.assertIn("Endpoint", page.content)
        self.assertIn("My API", page.content)
        self.assertIn("Parameters", page.content)

    def test_export_single_html(self):
        self.wiki.create_page(
            title="Export Test",
            content="## Section\n\nParagraph with `code`.",
            category="general",
        )
        html = self.wiki.export_single_html("export-test")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Export Test", html)
        self.assertIn("<h2>Section</h2>", html)
        self.assertIn("<code>code</code>", html)

    def test_export_full_site(self):
        self.wiki.create_page(title="Page 1", content="Content 1")
        self.wiki.create_page(title="Page 2", content="Content 2")
        out = self.wiki.export_full_site()
        out_path = Path(out)
        self.assertTrue(out_path.exists())
        self.assertTrue((out_path / "index.html").exists())
        self.assertTrue((out_path / "page-1.html").exists())
        self.assertTrue((out_path / "page-2.html").exists())

    def test_markdown_to_html(self):
        md = "# Title\n\nParagraph with **bold** and `code`.\n\n- Item 1\n- Item 2"
        html = FleetWiki._markdown_to_html(md)
        self.assertIn("<h1>Title</h1>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>code</code>", html)
        self.assertIn("<li>Item 1</li>", html)

    def test_markdown_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = FleetWiki._markdown_to_html(md)
        self.assertIn("<table>", html)
        self.assertIn("<th>A</th>", html)
        self.assertIn("<td>1</td>", html)

    def test_onboard(self):
        self.wiki.onboard()
        pages = self.wiki.list_pages()
        titles = [p.title for p in pages]
        self.assertIn("Home", titles)
        self.assertIn("Fleet Architecture", titles)
        self.assertIn("Glossary", titles)
        self.assertIn("Getting Started Guide", titles)
        self.assertGreaterEqual(len(pages), 4)

    def test_front_matter_parsing(self):
        self.wiki.create_page(
            title="FM Test",
            content="Hello",
            category="api-docs",
            author="test-author",
            tags=["fm"],
        )
        page = self.wiki.get_page("fm-test")
        self.assertEqual(page.author, "test-author")
        self.assertEqual(page.tags, ["fm"])
        self.assertEqual(page.category, "api-docs")


class TestWikiSearch(unittest.TestCase):
    """Tests for WikiSearch engine."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.wiki = FleetWiki(self.test_dir)
        self.wiki.create_page(
            title="Python API",
            content="This page describes the Python API endpoints for the fleet.",
            category="api-docs",
            tags=["python", "api"],
        )
        self.wiki.create_page(
            title="Architecture Guide",
            content="The fleet architecture uses microservices and message buses.",
            category="architecture",
            tags=["architecture", "design"],
        )
        self.wiki.create_page(
            title="Python Setup",
            content="How to set up Python development environment.",
            category="runbooks",
            tags=["python", "setup"],
        )
        self.search = WikiSearch(wiki=self.wiki)
        self.search.build_index()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_basic_search(self):
        results = self.search.search("python")
        self.assertGreater(len(results), 0)
        titles = [r["title"] for r in results]
        self.assertIn("Python API", titles)

    def test_search_returns_score(self):
        results = self.search.search("python")
        for r in results:
            self.assertIn("score", r)
            self.assertGreater(r["score"], 0)

    def test_search_returns_snippet(self):
        results = self.search.search("python")
        for r in results:
            self.assertIn("snippet", r)
            self.assertIsInstance(r["snippet"], str)

    def test_boolean_and(self):
        results = self.search.search("python API")
        titles = [r["title"] for r in results]
        self.assertIn("Python API", titles)

    def test_boolean_or(self):
        results = self.search.search("microservices OR setup")
        titles = [r["title"] for r in results]
        self.assertTrue(
            "Architecture Guide" in titles or "Python Setup" in titles
        )

    def test_boolean_not(self):
        results = self.search.search("python NOT API")
        titles = [r["title"] for r in results]
        self.assertNotIn("Python API", titles)

    def test_tag_filter(self):
        results = self.search.search("python", tags=["api"])
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("api", r["tags"])

    def test_category_filter(self):
        results = self.search.search("python", category="api-docs")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r["category"], "api-docs")

    def test_title_only_search(self):
        results = self.search.search("python", title_only=True)
        titles = [r["title"] for r in results]
        self.assertIn("Python API", titles)

    def test_empty_query(self):
        results = self.search.search("")
        self.assertEqual(len(results), 0)

    def test_limit_results(self):
        results = self.search.search("python", limit=1)
        self.assertLessEqual(len(results), 1)

    def test_suggest(self):
        suggestions = self.search.suggest("pyth")
        self.assertIsInstance(suggestions, list)
        self.assertIn("python", suggestions)

    def test_tokenizer(self):
        tokens = WikiSearch.tokenize("Hello, World! This is a TEST-123.")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)
        self.assertIn("test", tokens)
        self.assertIn("123", tokens)

    def test_stop_words_filtered(self):
        tokens = WikiSearch.normalize_tokens(
            WikiSearch.tokenize("the quick brown fox and the lazy dog")
        )
        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)
        self.assertIn("quick", tokens)
        self.assertIn("fox", tokens)

    def test_quoted_phrase_search(self):
        self.wiki.create_page(
            title="Exact Match",
            content="This page contains the fleet architecture pattern.",
            category="general",
        )
        self.search.build_index()
        results = self.search.search('"fleet architecture"')
        self.assertGreater(len(results), 0)

    def test_ranking_relevance(self):
        results = self.search.search("python")
        if len(results) > 1:
            self.assertGreaterEqual(
                results[0]["score"], results[-1]["score"]
            )


class TestDocGenerator(unittest.TestCase):
    """Tests for DocGenerator."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.wiki_dir = tempfile.mkdtemp()
        from generator import DocGenerator
        self.wiki = FleetWiki(self.wiki_dir)
        self.gen = DocGenerator(wiki=self.wiki)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.wiki_dir, ignore_errors=True)

    def test_scan_readme(self):
        repo = Path(self.test_dir) / "test-agent"
        repo.mkdir()
        (repo / "README.md").write_text(
            "# Test Agent\n\nA great agent for testing.\n",
            encoding="utf-8",
        )
        info = self.gen.scan_readme(repo)
        self.assertIsNotNone(info)
        self.assertEqual(info["title"], "Test Agent")
        self.assertIn("great agent", info["description"])

    def test_scan_no_readme(self):
        repo = Path(self.test_dir) / "no-readme"
        repo.mkdir()
        info = self.gen.scan_readme(repo)
        self.assertIsNone(info)

    def test_extract_docstrings(self):
        repo = Path(self.test_dir) / "doc-agent"
        repo.mkdir()
        (repo / "main.py").write_text(
            textwrap.dedent('''\
                """Module docstring for main."""

                class MyAgent:
                    """Agent class docstring."""

                    def run(self, task: str) -> str:
                        """Execute the agent task."""
                        return "done"
            '''),
            encoding="utf-8",
        )
        docs = self.gen.extract_docstrings(repo / "main.py")
        kinds = [d["kind"] for d in docs]
        self.assertIn("module", kinds)
        self.assertIn("class", kinds)
        self.assertIn("function", kinds)
        module = [d for d in docs if d["kind"] == "module"][0]
        self.assertEqual(module["name"], "main")
        cls = [d for d in docs if d["kind"] == "class"][0]
        self.assertEqual(cls["name"], "MyAgent")
        func = [d for d in docs if d["kind"] == "function"][0]
        self.assertEqual(func["name"], "run")
        self.assertIn("task", func["args"])

    def test_extract_async_docstrings(self):
        repo = Path(self.test_dir) / "async-agent"
        repo.mkdir()
        (repo / "server.py").write_text(
            textwrap.dedent('''\
                class Server:
                    async def start(self):
                        """Start the server."""
                        pass
            '''),
            encoding="utf-8",
        )
        docs = self.gen.extract_docstrings(repo / "server.py")
        async_funcs = [d for d in docs if d.get("is_async")]
        self.assertEqual(len(async_funcs), 1)
        self.assertEqual(async_funcs[0]["name"], "start")

    def test_generate_api_page(self):
        repo = Path(self.test_dir) / "api-agent"
        repo.mkdir()
        (repo / "README.md").write_text("# API Agent\n\nREST API handler.\n", encoding="utf-8")
        (repo / "app.py").write_text(
            textwrap.dedent('''\
                """API Agent application."""
                class Handler:
                    """Request handler."""
                    def handle(self, request):
                        """Handle incoming request."""
                        pass
            '''),
            encoding="utf-8",
        )
        result = self.gen.generate_api_page("API Agent", repo)
        self.assertTrue(result["success"])
        page = self.wiki.get_page(result["page_id"])
        self.assertIsNotNone(page)
        self.assertIn("Handler", page.content)
        self.assertIn("handle", page.content)

    def test_generate_api_page_nonexistent_repo(self):
        result = self.gen.generate_api_page("Ghost", "/nonexistent/path")
        self.assertFalse(result["success"])

    def test_generate_architecture(self):
        config = {
            "agents": [
                {"name": "Agent A", "role": "Worker", "status": "active"},
                {"name": "Agent B", "role": "Monitor", "status": "idle"},
            ],
            "services": [
                {"name": "api", "port": 8000, "description": "REST API"},
            ],
        }
        result = self.gen.generate_architecture_overview(fleet_config=config)
        self.assertTrue(result["success"])
        page = self.wiki.get_page(result["page_id"])
        self.assertIsNotNone(page)
        self.assertIn("Agent A", page.content)
        self.assertIn("Agent B", page.content)

    def test_generate_status_page(self):
        lighthouse = {
            "timestamp": "2025-01-01 00:00 UTC",
            "agents": [
                {"name": "Wiki", "status": "healthy", "uptime": "99.9%",
                 "last_heartbeat": "2025-01-01 00:00", "tasks_completed": 10},
            ],
        }
        result = self.gen.generate_status_page(lighthouse_data=lighthouse)
        self.assertTrue(result["success"])
        page = self.wiki.get_page(result["page_id"])
        self.assertIsNotNone(page)
        self.assertIn("Wiki", page.content)
        self.assertIn("healthy", page.content)

    def test_ascii_diagram(self):
        from generator import DocGenerator
        config = {"agents": [{"name": "A"}], "services": [{"name": "s", "port": 80}]}
        diagram = DocGenerator._build_ascii_diagram(config)
        self.assertIn("FLEET", diagram)
        self.assertIn("A", diagram)
        self.assertIn("80", diagram)

    def test_changelog_generation(self):
        repo = Path(self.test_dir) / "git-repo"
        repo.mkdir()
        subprocess = __import__("subprocess")
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"],
                       cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"],
                       cwd=str(repo), capture_output=True)
        (repo / "file.txt").write_text("hello", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"],
                       cwd=str(repo), capture_output=True)
        result = self.gen.generate_changelog(repo)
        self.assertTrue(result["success"])
        page = self.wiki.get_page(result["page_id"])
        self.assertIsNotNone(page)
        self.assertIn("Initial commit", page.content)


class TestFrontMatter(unittest.TestCase):
    """Test front matter parsing edge cases."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.wiki = FleetWiki(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_unicode_in_content(self):
        page = self.wiki.create_page(
            title="Unicode Test",
            content="Hello 世界 🌍 café résumé",
            category="general",
        )
        loaded = self.wiki.get_page(page.page_id)
        self.assertEqual(loaded.content, "Hello 世界 🌍 café résumé")

    def test_code_blocks_preserved(self):
        content = '```python\nprint("hello")\n```'
        page = self.wiki.create_page(title="Code Test", content=content)
        loaded = self.wiki.get_page(page.page_id)
        self.assertIn('print("hello")', loaded.content)

    def test_empty_content(self):
        page = self.wiki.create_page(title="Empty", content="")
        loaded = self.wiki.get_page(page.page_id)
        self.assertEqual(loaded.content, "")


if __name__ == "__main__":
    unittest.main()
