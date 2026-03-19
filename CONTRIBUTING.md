# Contributing to ThomsonLint-KiCad

## Getting Started

```bash
git clone git@github.com:paky12/ThomsonLint-KiCad.git
cd ThomsonLint-KiCad
uv sync --dev
uv run pytest tests/ -v
```

## Project Structure

This fork has two distinct layers:

1. **Upstream (do not modify):** Ontology, knowledge base, examples, report generator — synced from `holla2040/ThomsonLint`
2. **KiCad layer (our code):** Everything under `kicad/`, the MCP server, export schemas, and KiCad-specific tests

## Development Workflow

1. Create a feature branch from `development`
2. Write tests first (`tests/test_*.py`)
3. Implement the feature
4. Run the full test suite: `uv run pytest tests/ -v`
5. Commit with a descriptive message
6. Push and open a PR against `development`

## What to Contribute

### KiCad parser improvements
- Support for more `.kicad_pcb` elements (arcs in board outline, keepout zones)
- Better hierarchical schematic handling
- KiCad version-specific quirks

### Analyzer enhancements
- More signal classification patterns
- Better decoupling proximity heuristics
- Thermal via detection

### Ontology/knowledge base extensions
- New design rules (RF, automotive, safety-critical)
- More examples mapping to existing rules
- Improved rule descriptions

**Note:** If you modify `ontology/ontology.json`, `examples/examples.json`, or the knowledge base, regenerate the review instructions:
```bash
./gen_context.sh > review_instructions.txt
```

## Code Guidelines

- Pure Python — no heavy dependencies beyond `mcp` and `jsonschema`
- Dataclasses for models, not Pydantic
- All parsers take a file path and return a dataclass
- All analyzers take a dataclass and return a dict
- All exporters take a dataclass + analysis dict and return a JSON-compatible dict
- Test against the JSON export schemas (`tests/sch_export_schema.json`, `tests/brd_export_schema.json`)

## Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Single file
uv run pytest tests/test_net_classifier.py -v

# With coverage
uv run pytest --cov=kicad --cov-report=html tests/
```

Tests that need `kicad-cli` installed use mocked subprocess calls so they run anywhere.
