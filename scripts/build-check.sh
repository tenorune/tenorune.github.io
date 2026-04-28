#!/usr/bin/env bash
# Local Jekyll build wrapper that asserts the homepage passed through
# byte-identically. Run before pushing layout or config changes.
set -euo pipefail

bundle exec jekyll build

# Verify homepage assets passed through verbatim.
diff -q index.html _site/index.html
diff -q style.css _site/style.css
diff -q CNAME _site/CNAME
diff -q favicon.ico _site/favicon.ico
diff -rq media/ _site/media/

echo "build-check: OK"
