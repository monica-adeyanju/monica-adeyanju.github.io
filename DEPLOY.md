# Deploy Your Portfolio to GitHub Pages (Free)

This guide walks you through hosting your personal website at `https://YOUR_USERNAME.github.io` for free.

## Quick Start (5 minutes)

### Step 1: Create a GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Name the repo **exactly**: `monica-adeyanju.github.io`
   - This special naming convention tells GitHub to serve it as your personal site
3. Set it to **Public**
4. Do NOT initialize with README (we already have files)
5. Click **Create repository**

### Step 2: Push Your Code

Open your terminal and run:

```bash
cd ~/Documents/portfolio-site

# Initialize git
git init
git add .
git commit -m "Initial portfolio site with AI chatbot project"

# Connect to your GitHub repo
git remote add origin https://github.com/monica-adeyanju/monica-adeyanju.github.io.git

# Push
git branch -M main
git push -u origin main
```

### Step 3: Enable GitHub Pages

1. Go to your repo on GitHub
2. Click **Settings** → **Pages** (left sidebar)
3. Under "Source", select **Deploy from a branch**
4. Branch: `main`, folder: `/ (root)`
5. Click **Save**

### Step 4: Visit Your Site

After 1–2 minutes, your site is live at:

```
https://monica-adeyanju.github.io
```

## Things to Customize Before Deploying

All personalizations are already done. You're ready to deploy.

## Custom Domain (Optional)

If you own a domain (e.g., `yourname.dev`):

1. In your repo, create a file called `CNAME` with your domain:
   ```
   yourname.dev
   ```

2. At your DNS provider, add these records:
   ```
   Type  Name    Value
   A     @       185.199.108.153
   A     @       185.199.109.153
   A     @       185.199.110.153
   A     @       185.199.111.153
   CNAME www     monica-adeyanju.github.io
   ```

3. In GitHub repo **Settings → Pages**, enter your custom domain and check **Enforce HTTPS**

## Updating Your Site

Any push to `main` automatically redeploys:

```bash
# Make changes, then:
git add .
git commit -m "Update project section"
git push
```

Site updates within 1–2 minutes.

## Project Structure

```
monica-adeyanju.github.io/
├── index.html                    # Main portfolio page
├── assets/
│   ├── css/style.css             # Styles (dark theme)
│   └── js/main.js               # Scroll animations
├── projects/
│   └── ai-chatbot/
│       ├── template.yaml         # CloudFormation stack
│       ├── lambda/
│       │   └── index.py          # Lambda function code
│       └── README.md             # Project docs + deploy button
├── DEPLOY.md                     # This file
└── .nojekyll                     # Tells GitHub to serve raw HTML
```

## Troubleshooting

**Site shows README instead of index.html:**
- Make sure `index.html` is in the root of the repo (not in a subfolder)
- Add a `.nojekyll` file to the repo root (already included)

**404 error:**
- Wait 2–3 minutes after first deploy
- Check Settings → Pages to confirm it's enabled
- Make sure the repo name matches `monica-adeyanju.github.io` exactly

**CSS/JS not loading:**
- Verify the paths in `index.html` use relative paths (`assets/css/style.css`, not `/assets/...`)

## Why GitHub Pages?

- Free forever for public repos
- HTTPS included
- Custom domain support
- Automatic deploys on git push
- Your source code (including CloudFormation templates) is visible to visitors
- Shows you use git professionally
