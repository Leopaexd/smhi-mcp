# Push to GitHub Instructions

## Step 1: Create Repository on GitHub

1. Go to https://github.com/new
2. Repository name: `smhi-weather-mcp`
3. Description: `MCP server providing SMHI weather forecasts for daily planning in Sweden`
4. Make it **Public**
5. **Don't** initialize with README, .gitignore, or license (we have them)
6. Click "Create repository"

## Step 2: Push to GitHub

Run these commands from the `smhi-weather-mcp` directory:

```bash
# Add the remote
git remote add origin https://github.com/Leopaexd/smhi-weather-mcp.git

# Push to GitHub
git push -u origin main
```

## Step 3: Update Submodule URL in Parent Repo

From the parent `cursor_assistant_use` directory:

```bash
# Go back to parent repo
cd ..

# Update .gitmodules to use the GitHub URL
git config -f .gitmodules submodule.smhi-weather-mcp.url https://github.com/Leopaexd/smhi-weather-mcp.git

# Update the submodule configuration
git submodule sync

# Commit the change
git add .gitmodules
git commit -m "Update submodule URL to GitHub repository"
```

## Done!

Your repository is now:
- ✅ Published on GitHub
- ✅ Accessible to others
- ✅ Properly linked as a submodule

You can view it at: https://github.com/Leopaexd/smhi-weather-mcp
