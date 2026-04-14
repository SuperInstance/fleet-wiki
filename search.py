"""
Fleet Wiki Search — Full-text search across wiki pages.

Implements an inverted word index with boolean queries (AND, OR, NOT),
title vs content search, tag filtering, and simplified TF-IDF ranking.
"""

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional


class WikiSearch:
    """Full-text search across wiki pages."""

    STOP_WORDS = frozenset({
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "not", "no", "nor",
        "so", "if", "then", "than", "too", "very", "just", "about", "above",
        "after", "again", "all", "also", "am", "any", "as", "because",
        "before", "between", "both", "each", "few", "further", "get", "got",
        "he", "her", "here", "him", "his", "how", "i", "it", "its",
        "me", "more", "most", "my", "now", "only", "other", "our", "out",
        "own", "same", "she", "some", "such", "that", "their", "them",
        "there", "these", "they", "this", "those", "through", "under",
        "until", "up", "us", "we", "what", "when", "where", "which",
        "while", "who", "whom", "why", "you", "your",
    })

    def __init__(self, wiki=None, wiki_root: Optional[str | Path] = None):
        self._wiki = wiki
        self._wiki_root = Path(wiki_root) if wiki_root else None
        self._inverted_index: dict[str, set[str]] = defaultdict(set)
        self._title_index: dict[str, set[str]] = defaultdict(set)
        self._doc_lengths: dict[str, int] = {}
        self._doc_count = 0
        self._avg_doc_length = 0.0
        self._tag_index: dict[str, set[str]] = defaultdict(set)
        self._loaded = False

    def _get_wiki(self):
        if self._wiki is not None:
            return self._wiki
        if self._wiki_root:
            from wiki import FleetWiki
            self._wiki = FleetWiki(self._wiki_root)
            return self._wiki
        raise RuntimeError("WikiSearch needs either a wiki instance or wiki_root")

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Tokenize text into lowercase words."""
        text = text.lower()
        tokens = re.findall(r"[a-z0-9_]+", text)
        return tokens

    @staticmethod
    def normalize_tokens(tokens: list[str]) -> list[str]:
        """Remove stop words and return cleaned tokens."""
        return [t for t in tokens if t not in WikiSearch.STOP_WORDS and len(t) > 1]

    def build_index(self):
        """Build the inverted index from all wiki pages."""
        wiki = self._get_wiki()
        self._inverted_index.clear()
        self._title_index.clear()
        self._doc_lengths.clear()
        self._tag_index.clear()
        pages = wiki.list_pages()
        self._doc_count = len(pages)
        total_length = 0
        for page in pages:
            pid = page.page_id
            content_tokens = self.normalize_tokens(self.tokenize(page.content))
            title_tokens = self.normalize_tokens(self.tokenize(page.title))
            all_tokens = title_tokens + content_tokens
            self._doc_lengths[pid] = len(all_tokens)
            total_length += len(all_tokens)
            for token in set(all_tokens):
                self._inverted_index[token].add(pid)
            for token in set(title_tokens):
                self._title_index[token].add(pid)
            for tag in page.tags:
                self._tag_index[tag.lower()].add(pid)
        self._avg_doc_length = total_length / max(self._doc_count, 1)
        self._loaded = True

    def _ensure_index(self):
        if not self._loaded:
            self.build_index()

    def _tf(self, term: str, doc_id: str) -> float:
        """Calculate term frequency for a document."""
        wiki = self._get_wiki()
        page = wiki.get_page(doc_id)
        if not page:
            return 0.0
        tokens = self.normalize_tokens(self.tokenize(page.title + " " + page.content))
        if not tokens:
            return 0.0
        count = Counter(tokens)
        return count.get(term, 0) / len(tokens)

    def _idf(self, term: str) -> float:
        """Calculate inverse document frequency."""
        doc_freq = len(self._inverted_index.get(term, set()))
        if doc_freq == 0:
            return 0.0
        return math.log(self._doc_count / doc_freq) + 1.0

    def _bm25_score(self, term: str, doc_id: str, k1: float = 1.5, b: float = 0.75) -> float:
        """Calculate BM25 score for a term-document pair."""
        tf = self._tf(term, doc_id)
        idf = self._idf(term)
        doc_len = self._doc_lengths.get(doc_id, 0)
        avg_len = self._avg_doc_length
        if avg_len == 0:
            return 0.0
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * (doc_len / avg_len))
        return idf * (numerator / denominator)

    def _title_boost(self, term: str, doc_id: str) -> float:
        """Boost score if term appears in title."""
        if doc_id in self._title_index.get(term, set()):
            return 2.0
        return 1.0

    def search(
        self,
        query: str,
        tags: Optional[list[str]] = None,
        category: Optional[str] = None,
        title_only: bool = False,
        limit: int = 20,
    ) -> list[dict]:
        """Search wiki pages with boolean query support.

        Supports:
          - AND (implicit): `fleet architecture` matches pages with both words
          - OR: `fleet OR architecture`
          - NOT: `fleet NOT monitoring`
          - Quoted phrases: `"fleet wiki"`
        """
        self._ensure_index()
        if not query.strip():
            return []

        wiki = self._get_wiki()
        tokens = self._parse_query(query)

        if not tokens:
            return []

        scores: dict[str, float] = defaultdict(float)
        for token in tokens:
            term = token["term"]
            op = token.get("op", "and")

            if title_only:
                candidates = self._title_index.get(term, set())
            else:
                candidates = self._inverted_index.get(term, set())

            for doc_id in candidates:
                score = self._bm25_score(term, doc_id)
                score *= self._title_boost(term, doc_id)
                if op == "or":
                    scores[doc_id] += score
                elif op == "not":
                    scores[doc_id] -= score * 3
                else:
                    scores[doc_id] += score

        if tags:
            for tag in tags:
                tag_docs = self._tag_index.get(tag.lower(), set())
                for doc_id in list(scores.keys()):
                    if doc_id not in tag_docs:
                        del scores[doc_id]

        if category:
            for doc_id in list(scores.keys()):
                page = wiki.get_page(doc_id)
                if page and page.category != category:
                    del scores[doc_id]

        results = []
        for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            if score <= 0:
                continue
            page = wiki.get_page(doc_id)
            if page:
                results.append({
                    "page_id": doc_id,
                    "title": page.title,
                    "category": page.category,
                    "score": round(score, 4),
                    "tags": page.tags,
                    "snippet": self._snippet(page.content, query),
                })
            if len(results) >= limit:
                break
        return results

    def _parse_query(self, query: str) -> list[dict]:
        """Parse query string into token operations."""
        tokens: list[dict] = []
        quoted = re.findall(r'"([^"]+)"', query)
        remaining = re.sub(r'"[^"]*"', "", query)

        for phrase in quoted:
            phrase_tokens = self.normalize_tokens(self.tokenize(phrase))
            for pt in phrase_tokens:
                tokens.append({"term": pt, "op": "and"})

        parts = remaining.split()
        i = 0
        while i < len(parts):
            word = parts[i].lower()
            if word == "or" and i + 1 < len(parts):
                next_word = parts[i + 1].lower()
                next_tokens = self.normalize_tokens([next_word])
                for nt in next_tokens:
                    tokens.append({"term": nt, "op": "or"})
                i += 2
            elif word == "not" and i + 1 < len(parts):
                next_word = parts[i + 1].lower()
                next_tokens = self.normalize_tokens([next_word])
                for nt in next_tokens:
                    tokens.append({"term": nt, "op": "not"})
                i += 2
            else:
                word_tokens = self.normalize_tokens([word])
                for wt in word_tokens:
                    tokens.append({"term": wt, "op": "and"})
                i += 1
        return tokens

    @staticmethod
    def _snippet(content: str, query: str, max_length: int = 160) -> str:
        """Generate a text snippet showing matching context."""
        clean = re.sub(r"[#*>`\-\[\]\(\)]", " ", content)
        clean = re.sub(r"\s+", " ", clean).strip()
        query_lower = query.lower()
        query_pos = clean.lower().find(query_lower)
        if query_pos >= 0:
            start = max(0, query_pos - 40)
            end = min(len(clean), query_pos + max_length)
            snippet = clean[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(clean):
                snippet = snippet + "..."
            return snippet
        return clean[:max_length].strip() + "..."

    def suggest(self, prefix: str, limit: int = 10) -> list[str]:
        """Suggest completions for a prefix."""
        self._ensure_index()
        prefix = prefix.lower()
        matches = set()
        for term in self._inverted_index:
            if term.startswith(prefix):
                matches.add(term)
        return sorted(matches)[:limit]
