#!/bin/bash
# Cleanup script to remove old Python versions
# Only Python 3.14 will remain

echo "🧹 Cleaning up old Python versions..."
echo ""

# Remove Python 3.13 from /Library/Frameworks (requires sudo)
echo "Removing Python 3.13 from /Library/Frameworks..."
sudo rm -rf /Library/Frameworks/Python.framework/Versions/3.13

# Update Current symlink if needed
if [ -L /Library/Frameworks/Python.framework/Versions/Current ]; then
    echo "Updating Current symlink..."
    sudo rm /Library/Frameworks/Python.framework/Versions/Current
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Remaining Python installations:"
which -a python python3 python3.14 2>/dev/null
echo ""
echo "Versions:"
/opt/homebrew/bin/python3.14 --version
/usr/bin/python3 --version
