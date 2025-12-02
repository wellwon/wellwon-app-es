# Python Interpreter Setup for WellWon

## Problem
IDE shows "Python version 2.7 does not support this syntax" errors, even though Python 3.14 is installed.

## Solution

### For PyCharm:

1. **Open PyCharm Settings:**
   - Mac: `PyCharm` → `Preferences` (or `⌘,`)
   - Windows/Linux: `File` → `Settings`

2. **Navigate to Python Interpreter:**
   - `Project: WellWon` → `Python Interpreter`

3. **Add/Change Interpreter:**
   - Click the gear icon ⚙️ on the right
   - Select `Add Interpreter` → `Add Local Interpreter`
   - Choose `Existing environment`
   - Browse and select:
     ```
     /Users/macbookpro/PycharmProjects/WellWon/.venv/bin/python3.14
     ```
   - Click `OK`

4. **Verify:**
   - Check that interpreter shows: `Python 3.14.0 (.venv)`
   - All packages should be listed below

### For VS Code:

1. **Open Command Palette:**
   - Mac: `⌘⇧P`
   - Windows/Linux: `Ctrl+Shift+P`

2. **Select Python Interpreter:**
   - Type: `Python: Select Interpreter`
   - Choose: `Python 3.14.0 64-bit ('.venv': venv)`
   - Path: `/Users/macbookpro/PycharmProjects/WellWon/.venv/bin/python`

3. **Verify:**
   - Bottom left corner should show: `Python 3.14.0 64-bit ('.venv')`

## Verification Commands

Run these in the terminal to verify:

```bash
# Check Python version in terminal
python --version
# Output: Python 3.14.0

# Check which Python is being used
which python
# Output: /Users/macbookpro/PycharmProjects/WellWon/.venv/bin/python

# Verify packages are installed
pip list | head -20
```

## Current Configuration

✅ **Virtual Environment:** `/Users/macbookpro/PycharmProjects/WellWon/.venv`
✅ **Python Version:** 3.14.0
✅ **Location:** `/opt/homebrew/opt/python@3.14/bin/python3.14`
✅ **Pip Version:** 25.3
✅ **All packages:** Installed and up to date

## Why This Happens

- PyCharm/VS Code may default to system Python (which could be 2.7)
- Project needs to be explicitly configured to use the virtual environment
- `.venv` directory exists but IDE isn't automatically detecting it

## After Fixing

Once the interpreter is configured correctly:
- ✅ Syntax errors will disappear
- ✅ Autocomplete will work with Python 3.14 features
- ✅ Type hints will be properly recognized
- ✅ All installed packages will be available

## Need Help?

If errors persist after changing the interpreter:
1. Restart the IDE completely
2. Invalidate caches: `File` → `Invalidate Caches / Restart`
3. Rebuild indexes: `File` → `Repair IDE`
