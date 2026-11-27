"""CODEOWNERS pattern engine (#79): matching, rule order, example-path search."""

import pytest

from agenraci.codeowners import (
    UnsupportedPattern,
    compile_pattern,
    find_example,
    last_match,
    parse_rules,
)


@pytest.mark.parametrize("pattern,path,expected", [
    # "*" matches every file at any depth (GitHub's default-owner rule).
    ("*", "README.md", True),
    ("*", "a/b/c.py", True),
    # Unanchored extension patterns match at any depth.
    ("*.js", "x.js", True),
    ("*.js", "a/b/x.js", True),
    ("*.js", "x.jsx", False),
    # GitHub: `docs/*` matches docs/getting-started.md, not nested files.
    ("docs/*", "docs/getting-started.md", True),
    ("docs/*", "docs/build-app/troubleshooting.md", False),
    ("docs/*", "x/docs/a.md", False),
    # A trailing slash means "inside this directory", at any depth when unanchored.
    ("apps/", "apps/a", True),
    ("apps/", "x/apps/a/b", True),
    ("apps/", "apps", False),
    ("/docs/", "docs/a", True),
    ("/docs/", "x/docs/a", False),
    # A plain last segment also covers a directory of that name.
    ("/apps/github", "apps/github", True),
    ("/apps/github", "apps/github/x/y", True),
    ("/apps/github", "apps/githubx", False),
    ("**/logs", "logs/a", True),
    ("**/logs", "a/b/logs/c", True),
    ("/build/logs/", "build/logs/a/b", True),
    ("/build/logs/", "build/logs", False),
    ("a/**/b", "a/b", True),
    ("a/**/b", "a/x/y/b", True),
    ("/src/**", "src/a/b", True),
    ("/src/**", "src", False),
    ("**", "a/b", True),
    ("?.md", "a.md", True),
    ("?.md", "ab.md", False),
    # Case-sensitive, as on GitHub.
    ("/Docs/", "docs/a", False),
])
def test_pattern_matching(pattern, path, expected):
    assert compile_pattern(pattern).matches(path) is expected


@pytest.mark.parametrize("pattern", ["!docs/", "[ab].md", "\\#file", "//", "a//b"])
def test_unsupported_patterns_are_rejected(pattern):
    with pytest.raises(UnsupportedPattern):
        compile_pattern(pattern)


def test_parse_rules_keeps_order_ownerless_rules_and_unsupported_lines():
    text = ("# comment\n"
            "* @alice\n"
            "\n"
            "/docs/            # no owners: removes ownership\n"
            "*.md @bob @carol\n"
            "[a].md @x\n")
    rules = parse_rules(text)
    assert [(r.line, r.pattern, r.owners) for r in rules] == [
        (2, "*", ["@alice"]),
        (4, "/docs/", []),
        (5, "*.md", ["@bob", "@carol"]),
        (6, "[a].md", ["@x"]),
    ]
    assert rules[3].unsupported and rules[3].nfa is None


def test_last_match_wins():
    rules = parse_rules("* @alice\n/docs/\n*.md @bob\n")
    assert last_match(rules, "src/a.py").pattern == "*"
    assert last_match(rules, "docs/a.txt").pattern == "/docs/"
    assert last_match(rules, "docs/a.md").pattern == "*.md"


def test_find_example_finds_overlaps_and_proves_disjointness():
    star, docs, md = (compile_pattern(p) for p in ("*", "/docs/", "*.md"))
    src = compile_pattern("src/**")
    assert find_example([star, docs]) == "docs/x"
    assert find_example([src, md]) is not None      # e.g. src/x.md
    assert find_example([src, docs]) is None         # different top directory
    assert find_example([compile_pattern("*.py"), md]) is None
    # Excluding a later rule that covers everything leaves nothing.
    assert find_example([src], [star]) is None
    example = find_example([star], [docs])
    assert example is not None and not example.startswith("docs/")


def test_find_example_only_returns_well_formed_paths():
    example = find_example([compile_pattern("docs/*")])
    assert example and not example.endswith("/") and "//" not in example
