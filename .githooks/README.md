# Git hooks

`commit-msg` strips AI attribution trailers (`Co-authored-by: Cursor`,
`Made-with: Cursor`, `Co-Authored-By: Claude`, `Generated with [Claude Code]`)
from every commit message, so they don't appear on GitHub. Tools keep working —
only the commit stamp is removed.

**Enable once per clone:**

```bash
git config core.hooksPath .githooks
```
