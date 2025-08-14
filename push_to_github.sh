#!/bin/bash

# Script to push the repository to GitHub after creating it
# Run this after creating the repository on github.com

echo "🚀 Pushing Google Calendar Meeting Prep Agent to GitHub..."

# Push to GitHub
git push -u origin main

if [ $? -eq 0 ]; then
    echo "✅ Successfully pushed to GitHub!"
    echo "🔗 Repository URL: https://github.com/leeahnduk/google-calendar-agent"
    echo ""
    echo "📋 Your repository is now live with:"
    echo "   - Complete Meeting Prep Agent code"
    echo "   - AI-powered analysis features"
    echo "   - Comprehensive README.md"
    echo "   - Feature update documentation"
    echo "   - Production deployment guide"
    echo ""
    echo "🎯 Next steps:"
    echo "   1. Visit: https://github.com/leeahnduk/google-calendar-agent"
    echo "   2. Add any additional documentation"
    echo "   3. Configure repository settings (if needed)"
    echo "   4. Share your project!"
else
    echo "❌ Push failed. Make sure you've created the repository on GitHub first."
    echo "   Go to: https://github.com/new"
    echo "   Repository name: google-calendar-agent"
    echo "   Don't initialize with README (we have one already)"
fi