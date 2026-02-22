#!/bin/bash
# FreeSurfer License Check Script
# Run this to verify your FreeSurfer license is properly configured

echo "Checking FreeSurfer License Configuration..."
echo

# Check if license file exists
if [ -f "license.txt" ]; then
    echo "License file found: license.txt"

    # Check if it's not the example file
    if grep -q "REPLACE THIS EXAMPLE CONTENT" license.txt 2>/dev/null || \
       grep -q "FreeSurfer License File - EXAMPLE" license.txt 2>/dev/null; then
        echo " License file contains example content"
        echo
        echo "To get a real FreeSurfer license:"
        echo "   1. Visit: https://surfer.nmr.mgh.harvard.edu/registration.html"
        echo "   2. Register (free for research/academic use)"
        echo "   3. Download the license.txt file you receive via email"
        echo "   4. Replace the content in license.txt with your real license"
        echo "   5. Run this script again to verify"
        exit 1
    else
        echo " License file appears to contain actual license content"

        # Basic format check
        line_count=$(wc -l < license.txt)
        if [ "$line_count" -ge 4 ]; then
            echo " License file has correct format ($line_count lines)"
            echo " FreeSurfer license is properly configured!"
        else
            echo "  Warning: License file format may be incorrect (expected 4+ lines, got $line_count)"
            echo "   Please verify your license content is complete"
        fi
    fi
else
    echo " License file not found: license.txt"
    echo
    echo "To set up your FreeSurfer license:"
    echo "   1. Visit: https://surfer.nmr.mgh.harvard.edu/registration.html"
    echo "   2. Register (free for research/academic use)"
    echo "   3. Download the license.txt file you receive"
    echo "   4. Save it as 'license.txt' in this directory (same folder as NeuroInsight)"
    echo "   5. Run this script again to verify"
    exit 1
fi

echo
echo "License check complete!"
