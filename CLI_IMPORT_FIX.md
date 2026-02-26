# CLI Import Fix

**Issue:** `ImportError: attempted relative import with no known parent package` when running CLI directly

**Root Cause:** The CLI script (`topology-tools/scripts/generators/docs/cli.py`) used relative imports (`.generator`) which only work when the module is imported as part of a package, not when run as a direct script.

## Solution Applied

Changed imports in `cli.py` from relative to absolute with path handling:

```python
# Before (relative import)
from .generator import DocumentationGenerator

# After (absolute import with path handling)
if __name__ == "__main__" and __package__ is None:
    # Add project root to path when running as script
    project_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(project_root))

from scripts.generators.docs.generator import DocumentationGenerator
```

## Files Modified

1. **`topology-tools/scripts/generators/docs/cli.py`**
   - Added path handling for direct script execution
   - Changed from relative to absolute imports

2. **`topology-tools/scripts/generators/docs/generator.py`**
   - Removed unused `copy` import (no longer needed after DataResolver extraction)

## Testing

**Direct script execution (now works):**
```cmd
python topology-tools\scripts\generators\docs\cli.py --topology topology.yaml --output generated\docs
```

**Module execution (still works):**
```cmd
python -m scripts.generators.docs.cli --topology topology.yaml --output generated\docs
```

**Programmatic import (still works):**
```python
from scripts.generators.docs import DocumentationGenerator, DocumentationCLI
```

## Related Files

- `REFACTORING_PROGRESS_DIAGRAMS_DATA.md` - Full refactoring progress report
- `NEXT_STEPS.md` - Updated priorities and status
- `TODO.md` - Updated with completed work and next tasks
