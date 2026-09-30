#!/bin/bash
# HTML -> PDF A4 com Chrome headless. Uso: html_to_pdf.sh relatorio.html relatorio.pdf
# No HTML use @page { size: A4; margin: 14mm } e page-break-before/inside para seções e tabelas.
set -e
IN="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"; OUT="$2"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CH" ] || CH="$(command -v google-chrome || command -v chromium || command -v chromium-browser)"
"$CH" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$OUT" "file://$IN" 2>/dev/null
echo "PDF: $OUT"
