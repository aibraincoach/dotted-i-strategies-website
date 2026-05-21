#!/usr/bin/env python3
"""
Restructure the scraped dottedistrategies.com mirror into a clean Vercel-deployable
static site. Handles:
  - Moving HTML pages to root
  - Moving assets into assets/{images,fonts,js}/ and downloads/
  - Renaming URL-encoded files to human-readable names
  - Updating all internal references in HTML files
  - Creating vercel.json and .gitignore
  - Deleting old messy folders
"""

import os, re, shutil, json, sys

REPO = "/home/ubuntu/Projects/dotted-i-strategies"
OLD_HTML_DIR = os.path.join(REPO, "dottedistrategies.com")
OLD_IMG_DIR  = os.path.join(REPO, "img1.wsimg.com")
OLD_CDN_DIR  = os.path.join(REPO, "cdn.trustedsite.com")

# New structure
DIRS = {
    "assets/images": os.path.join(REPO, "assets", "images"),
    "assets/fonts":  os.path.join(REPO, "assets", "fonts"),
    "assets/js":     os.path.join(REPO, "assets", "js"),
    "downloads":     os.path.join(REPO, "downloads"),
}

HTML_FILES = ["index.html", "services.html", "purpose.html", "access-to.html", "insights.html", "connect.html"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dir(d):
    os.makedirs(d, exist_ok=True)

def strip_query_params(path):
    """Remove ?... and #... from a file path string."""
    return path.split("?")[0].split("#")[0]

def safe_name(name):
    """Replace %20 with spaces, then spaces with dashes for filesystem safety."""
    name = name.replace("%20", " ")
    name = name.replace(" ", "-")
    return name

def file_hash(filepath):
    """Quick md5 of file contents for dedup."""
    import hashlib
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

# ---------------------------------------------------------------------------
# 1. Create directories
# ---------------------------------------------------------------------------
for d in DIRS.values():
    ensure_dir(d)

# ---------------------------------------------------------------------------
# 2. Move HTML pages to root
# ---------------------------------------------------------------------------
for html in HTML_FILES:
    src = os.path.join(OLD_HTML_DIR, html)
    dst = os.path.join(REPO, html)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"[HTML] {src} -> {dst}")
    else:
        print(f"[WARN] Missing {src}")

# Also copy manifest if present
manifest_src = os.path.join(OLD_HTML_DIR, "manifest.webmanifest")
if os.path.exists(manifest_src):
    shutil.copy2(manifest_src, os.path.join(REPO, "manifest.webmanifest"))
    print("[HTML] manifest.webmanifest -> root")

# ---------------------------------------------------------------------------
# 3. Build mapping of old paths -> new clean paths
# ---------------------------------------------------------------------------
# We'll walk the old directories and decide where each file goes.

mapping = {}   # old relative path (from repo root) -> new relative path
seen_hashes = {}  # hash -> new relative path (for dedup)

def add_mapping(old_rel, new_rel):
    """Register a mapping. old_rel and new_rel are relative to REPO root."""
    mapping[old_rel] = new_rel

def process_file(old_abspath, old_relpath, dest_folder, new_basename=None):
    """Copy a file from old location to new, with optional rename."""
    if new_basename is None:
        new_basename = os.path.basename(old_abspath)
    new_basename = safe_name(new_basename)
    new_abspath = os.path.join(dest_folder, new_basename)
    # dedup by content
    h = file_hash(old_abspath)
    if h in seen_hashes:
        # point to existing file
        add_mapping(old_relpath, seen_hashes[h])
        print(f"[DEDUP] {old_relpath} -> {seen_hashes[h]}")
        return
    # copy
    shutil.copy2(old_abspath, new_abspath)
    new_relpath = os.path.relpath(new_abspath, REPO)
    seen_hashes[h] = new_relpath
    add_mapping(old_relpath, new_relpath)
    print(f"[COPY] {old_relpath} -> {new_relpath}")

# ---------------------------------------------------------------------------
# 3a. Images under img1.wsimg.com/isteam/...
# ---------------------------------------------------------------------------
# We need to handle:
#   - favicons
#   - logos (noBgColor.png, Blue-Wordmark, CRIN-Logo, Studio-Project, blob-*.png)
#   - stock photos (getty/..., stock/...)
#   - hero background (getty/1759595524)
#   - blobs
#
# Strategy: group by "semantic name" and keep the highest-resolution variant
#           as the canonical file, mapping all variants to it.

image_groups = {}  # semantic_name -> list of (old_relpath, old_abspath)

for root, dirs, files in os.walk(OLD_IMG_DIR):
    for f in files:
        old_abspath = os.path.join(root, f)
        old_relpath = os.path.relpath(old_abspath, REPO)
        # strip query params for analysis
        clean_name = strip_query_params(f)
        # Determine semantic group
        semantic = None
        lower = clean_name.lower()
        if "favicon" in lower:
            semantic = "favicon"
        elif "nobgcolor" in lower or "logo" in lower and "wordmark" not in lower and "crin" not in lower:
            semantic = "logo-main"
        elif "blue-wordmark" in lower:
            semantic = "logo-wordmark"
        elif "crin-logo-stacked" in lower:
            semantic = "logo-crin"
        elif "studio-project" in lower:
            semantic = "logo-studio"
        elif "blob-0004" in lower:
            semantic = "blob-0004"
        elif "blob-b53a5e9" in lower:
            semantic = "blob-b53a5e9"
        elif "getty/1759595524" in lower:
            semantic = "hero-background"
        elif "/stock/5206" in lower:
            semantic = "stock-business-meeting"
        elif "/stock/v8j01on" in lower:
            semantic = "stock-financial-docs"
        elif "/stock/4687" in lower:
            semantic = "stock-handshake"
        elif "/stock/5227" in lower:
            semantic = "stock-5227"
        elif "/stock/87420" in lower:
            semantic = "stock-87420"
        elif "/stock/87433" in lower:
            semantic = "stock-87433"
        elif "/stock/ovqron8" in lower:
            semantic = "stock-ovqron8"
        else:
            # fallback: use the last path component
            semantic = safe_name(clean_name)
        image_groups.setdefault(semantic, []).append((old_relpath, old_abspath))

# For each semantic group, pick the "best" file (largest size, or highest res)
# and copy it once. Map all old variants to the new canonical file.
import hashlib

def pick_best(files):
    """Pick the largest file as the canonical representative."""
    best = max(files, key=lambda x: os.path.getsize(x[1]))
    return best

for semantic, files in image_groups.items():
    best_relpath, best_abspath = pick_best(files)
    # determine extension
    ext = os.path.splitext(strip_query_params(os.path.basename(best_abspath)))[1] or ".png"
    if semantic == "favicon":
        new_name = f"favicon{ext}"
    elif semantic == "logo-main":
        new_name = f"logo{ext}"
    elif semantic == "logo-wordmark":
        new_name = f"logo-wordmark{ext}"
    elif semantic == "logo-crin":
        new_name = f"logo-crin{ext}"
    elif semantic == "logo-studio":
        new_name = f"logo-studio{ext}"
    elif semantic.startswith("stock-"):
        new_name = f"{semantic}{ext}"
    elif semantic.startswith("blob-"):
        new_name = f"{semantic}{ext}"
    elif semantic == "hero-background":
        new_name = f"hero-background{ext}"
    else:
        new_name = f"{semantic}{ext}"
    # copy canonical
    process_file(best_abspath, best_relpath, DIRS["assets/images"], new_name)
    # map all other variants to the same new file
    canonical_new = mapping[best_relpath]
    for old_relpath, old_abspath in files:
        if old_relpath != best_relpath:
            mapping[old_relpath] = canonical_new
            print(f"[MAP]  {old_relpath} -> {canonical_new}")

# ---------------------------------------------------------------------------
# 3b. Fonts
# ---------------------------------------------------------------------------
font_dir = os.path.join(OLD_IMG_DIR, "gfonts", "s")
if os.path.isdir(font_dir):
    for root, dirs, files in os.walk(font_dir):
        for f in files:
            if f.endswith(".woff2"):
                old_abspath = os.path.join(root, f)
                old_relpath = os.path.relpath(old_abspath, REPO)
                # Keep original filename (it's already reasonably named)
                process_file(old_abspath, old_relpath, DIRS["assets/fonts"])

# ---------------------------------------------------------------------------
# 3c. JavaScript files
# ---------------------------------------------------------------------------
# gpub scripts + UX widget + scc-c2 + trustedsite
js_locations = [
    (os.path.join(OLD_IMG_DIR, "blobby", "go", "95d9e6a5-f074-4441-8eb4-5a9d4c6113db", "gpub"), "gpub-"),
    (os.path.join(OLD_IMG_DIR, "ceph-p3-01", "website-builder-data-prod", "static", "widgets"), "widget-"),
    (os.path.join(OLD_IMG_DIR, "signals", "js", "clients", "scc-c2"), ""),
    (OLD_CDN_DIR, "trusted-"),
]

script_counter = {}
for base_dir, prefix in js_locations:
    if not os.path.isdir(base_dir):
        continue
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith(".js"):
                old_abspath = os.path.join(root, f)
                old_relpath = os.path.relpath(old_abspath, REPO)
                # Use the UUID folder name as a hint for gpub scripts
                if "gpub" in old_relpath:
                    # e.g. e2301a81b8c7eb11 -> script-e2301a81.js
                    uuid = os.path.basename(os.path.dirname(old_abspath))
                    new_name = f"script-{uuid}.js"
                elif "widgets" in old_relpath:
                    new_name = f"widget-{safe_name(f)}"
                elif "scc-c2" in old_relpath:
                    new_name = "scc-c2.min.js"
                elif "trustedsite" in old_relpath:
                    new_name = "trustedsite.js"
                else:
                    new_name = f"{prefix}{safe_name(f)}"
                process_file(old_abspath, old_relpath, DIRS["assets/js"], new_name)

# ---------------------------------------------------------------------------
# 3d. PDF downloads
# ---------------------------------------------------------------------------
downloads_dir = os.path.join(OLD_IMG_DIR, "blobby", "go", "95d9e6a5-f074-4441-8eb4-5a9d4c6113db", "downloads")
if os.path.isdir(downloads_dir):
    for root, dirs, files in os.walk(downloads_dir):
        for f in files:
            old_abspath = os.path.join(root, f)
            old_relpath = os.path.relpath(old_abspath, REPO)
            clean = strip_query_params(f)
            # The PDFs have descriptive names already
            new_name = safe_name(clean)
            process_file(old_abspath, old_relpath, DIRS["downloads"], new_name)

# ---------------------------------------------------------------------------
# 4. Update all HTML files at root
# ---------------------------------------------------------------------------
# We need to replace every old relative reference with the new one.
# The old references look like:
#   ../img1.wsimg.com/isteam/.../foo.png/:/rs=w:100,h:100?ver=123
#   ../img1.wsimg.com/gfonts/s/.../foo.woff2
#   ../img1.wsimg.com/blobby/.../script.js
#   ../cdn.trustedsite.com/js/1.js?position=bottomLeft&offset=15
#
# Because the HTML files moved from dottedistrategies.com/ to root,
# the old references were already ../img1.wsimg.com/... which is correct
# relative to dottedistrategies.com/index.html. Now that files are at root,
# we need ./assets/... paths.

# Build a regex -> replacement mapping. We need to match the old path
# including any query params that may follow.

replacements = []
for old_rel, new_rel in mapping.items():
    # old_rel is like: img1.wsimg.com/isteam/ip/.../foo.png/:/rs=w:100,h:100
    # In HTML it appears as: ../img1.wsimg.com/... or img1.wsimg.com/...
    # We need to match the base path plus any query string.
    # Strategy: escape the old_rel for regex, then allow optional ?... or &...
    # But the old_rel itself may contain regex-special chars.
    # Simpler: just do a literal string replacement on the file contents
    # for the "base" part (without query params) and let the query params
    # be consumed by the replacement.
    # Actually, since we stripped query params from the old_rel when building
    # the mapping, the old_rel in mapping is the *file path on disk* (no ?).
    # In HTML, the reference includes the query params. So we need to match
    # the file path prefix and any trailing ?... or &... or /:... stuff.
    #
    # Let's construct a pattern that matches:
    #   (../)?img1.wsimg.com/.../foo.png  followed by anything up to a quote or space
    #
    # Actually, the simplest robust approach: for each old file path, find all
    # occurrences in HTML where that path prefix appears, and replace the entire
    # URL (from the prefix start to the next quote/space) with the new path.
    pass

# Better approach: read each HTML file, find all URLs that contain "img1.wsimg.com"
# or "cdn.trustedsite.com", match them against our mapping keys (with fuzzy prefix
# matching), and replace.

def find_old_path_in_url(url):
    """Given a URL string from HTML, find which old_rel it corresponds to."""
    # Strip leading ../ or ./
    clean_url = url.lstrip(".")
    clean_url = clean_url.lstrip("/")
    # Try exact match first
    if clean_url in mapping:
        return clean_url
    # Try stripping query params
    noq = strip_query_params(clean_url)
    if noq in mapping:
        return noq
    # Try matching by prefix: find the longest mapping key that is a prefix of clean_url
    best = None
    best_len = 0
    for key in mapping:
        if clean_url.startswith(key) or noq.startswith(key):
            if len(key) > best_len:
                best_len = len(key)
                best = key
    return best

def update_html(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    original = content

    # Find all URLs referencing old domains
    # Pattern: match strings inside quotes that contain img1.wsimg.com or cdn.trustedsite.com
    # We need to be careful not to break HTML structure.
    # Regex to find URLs in src, href, srcSet, url(...)
    patterns = [
        r'\b(src|href|srcSet|data-src|content|url)\s*=\s*["\']([^"\']*(?:img1\.wsimg\.com|cdn\.trustedsite\.com)[^"\']*)["\']',
        r'\burl\(["\']?([^"\']*(?:img1\.wsimg\.com|cdn\.trustedsite\.com)[^"\']*)["\']?\)',
    ]

    import re
    replacements_made = 0
    for pattern in patterns:
        def replacer(m):
            nonlocal replacements_made
            full_match = m.group(0)
            url = m.group(2) if m.lastindex >= 2 else m.group(1)
            # Determine which old path this corresponds to
            old_key = find_old_path_in_url(url)
            if old_key and old_key in mapping:
                new_url = mapping[old_key]
                # Adjust relative path based on where the HTML file is (root)
                # The new paths are relative to repo root, e.g. assets/images/...
                # Since HTML is at root, we just use ./ or no prefix.
                if not new_url.startswith("./"):
                    new_url = "./" + new_url
                # Reconstruct the match with new URL
                # We need to preserve the attribute name and quotes
                if m.group(1) in ("src", "href", "data-src", "content"):
                    return f'{m.group(1)}="{new_url}"'
                elif m.group(1) == "srcSet":
                    return f'srcSet="{new_url}"'
                elif m.group(1) == "url":
                    return f'url({new_url})'
                else:
                    return full_match.replace(url, new_url)
            return full_match

        # We need a different approach because replacer needs to know which group is the URL
        # Let's just do a simpler regex per pattern
        pass

    # Simpler: iterate over all mapping keys and do a global replace of the URL prefix.
    # Since URLs in HTML may have query params, we replace the prefix + everything up to
    # the next quote or space or closing paren.
    # But this is tricky. Let's do it character-by-character with a custom scanner.

    # Actually, the easiest way: for each mapping, construct a regex that matches
    # the old path (with optional ../ prefix) followed by any non-quote characters.
    # Then replace the whole thing.
    for old_key, new_val in mapping.items():
        # old_key is like: img1.wsimg.com/isteam/...
        # In HTML it may appear as: ../img1.wsimg.com/... or img1.wsimg.com/...
        # We need to match the entire URL including query params.
        # Pattern: (\.\./)? + re.escape(old_key) + [^"\'\s\)]*
        esc = re.escape(old_key)
        # Also match with ../ prefix
        pattern = re.compile(r'\.\./' + esc + r'[^"\'\s\)]*')
        def sub_fn(m):
            nonlocal replacements_made
            replacements_made += 1
            nv = new_val
            if not nv.startswith("./"):
                nv = "./" + nv
            return nv
        content, count = pattern.subn(sub_fn, content)
        replacements_made += count

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[UPDATED] {filepath} ({replacements_made} replacements)")
    else:
        print(f"[OK] {filepath} (no changes)")

for html in HTML_FILES:
    filepath = os.path.join(REPO, html)
    if os.path.exists(filepath):
        update_html(filepath)

# Also update manifest if copied
manifest_path = os.path.join(REPO, "manifest.webmanifest")
if os.path.exists(manifest_path):
    update_html(manifest_path)

# ---------------------------------------------------------------------------
# 5. Create vercel.json
# ---------------------------------------------------------------------------
vercel_config = {
    "version": 2,
    "public": True,
    "github": {
        "enabled": False
    },
    "routes": [
        {"src": "/", "dest": "/index.html"},
        {"src": "/services", "dest": "/services.html"},
        {"src": "/purpose", "dest": "/purpose.html"},
        {"src": "/access-to", "dest": "/access-to.html"},
        {"src": "/insights", "dest": "/insights.html"},
        {"src": "/connect", "dest": "/connect.html"},
        {"src": "/([^/]+)", "dest": "/$1.html"}
    ]
}
with open(os.path.join(REPO, "vercel.json"), "w") as f:
    json.dump(vercel_config, f, indent=2)
print("[CREATE] vercel.json")

# ---------------------------------------------------------------------------
# 6. Create .gitignore
# ---------------------------------------------------------------------------
gitignore = """# Static site
.DS_Store
*.log
node_modules/
.vercel
.env
"""
with open(os.path.join(REPO, ".gitignore"), "w") as f:
    f.write(gitignore)
print("[CREATE] .gitignore")

# ---------------------------------------------------------------------------
# 7. Delete old messy folders
# ---------------------------------------------------------------------------
for old_dir in [OLD_HTML_DIR, OLD_IMG_DIR, OLD_CDN_DIR]:
    if os.path.isdir(old_dir):
        shutil.rmtree(old_dir)
        print(f"[DELETE] {old_dir}")

print("\nDone! Verify by opening index.html in a browser.")
