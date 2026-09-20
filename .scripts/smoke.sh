#!/usr/bin/env bash
# Acceptance check for the wired frontend (spec 3 §6.3): drives agent-browser through
# the RUNNING stack. Not part of CI (needs the stack). Usage:
#   ./.scripts/smoke.sh                       # against http://localhost (Traefik)
#   BASE_URL=http://localhost:3010 ./.scripts/smoke.sh
#   HEADED=1 ./.scripts/smoke.sh              # watch it in a window
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost}"
QUERY="${QUERY:-پژو ۲۰۶ تیپ ۲ تهران}"
MODEL="${MODEL:-پژو 206}"
AB=(agent-browser)
[[ "${HEADED:-0}" == "1" ]] && AB+=(--headed)
encode() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1"; }

step() { printf '\n== %s\n' "$*"; }
page_text() { "${AB[@]}" get text body; }
expect_text() { # expect_text <needle> <label>
  if page_text | grep -q -- "$1"; then echo "ok: $2"; else echo "FAIL: $2 (missing «$1»)"; "${AB[@]}" screenshot smoke-fail.png; exit 1; fi
}
first_href() { "${AB[@]}" get attr "$1" href; }

trap '"${AB[@]}" close >/dev/null 2>&1 || true' EXIT

step "home stats"
"${AB[@]}" open "$BASE_URL/"
"${AB[@]}" wait --load networkidle
expect_text "آگهی فعال" "home shows the live listing count"
expect_text "به‌روزرسانی" "home shows the data snapshot time"

step "natural-language search"
"${AB[@]}" open "$BASE_URL/results?q=$(encode "$QUERY")"
"${AB[@]}" wait "a[href^='/listing/']"
expect_text "از جست‌وجوت فهمیدم" "parsed chips are shown"

step "near-miss labels"
divider_seen=0
for attempt in 0 1 2 3 4 5; do
  if page_text | grep -q -- "آگهی‌های مشابه"; then divider_seen=1; break; fi
  [[ "$attempt" -eq 5 ]] && break
  "${AB[@]}" find text "بیشتر" click || true
  "${AB[@]}" wait --load networkidle
done
if [[ "$divider_seen" -eq 1 ]]; then
  echo "ok: near-miss divider after the exact matches"
else
  echo "FAIL: near-miss divider after the exact matches (missing «آگهی‌های مشابه» after 5 clicks)"
  "${AB[@]}" screenshot smoke-fail.png
  exit 1
fi

step "listing page + similar"
LISTING="$(first_href "a[href^='/listing/']")"
[[ -n "$LISTING" ]] || { echo "FAIL: no listing link"; exit 1; }
"${AB[@]}" open "$BASE_URL$LISTING"
"${AB[@]}" wait --load networkidle
expect_text "مشاهده آگهی" "price card links to the source ad"
expect_text "مشخصات" "specs grid"
expect_text "آگهی‌های مشابه" "similar listings"
expect_text "متن آگهی فروشنده" "seller text"
if page_text | grep -Eq '(^|[^0-9۰-۹])0?9[0-9]{9}|۰۹[۰-۹]{9}'; then echo "FAIL: a phone number leaked into the page"; exit 1; else echo "ok: no phone numbers on the listing page"; fi

step "compare two listings"
"${AB[@]}" find text "+ مقایسه" click
SECOND="$(first_href "a[href^='/listing/']")"   # the first similar listing
"${AB[@]}" open "$BASE_URL$SECOND"
"${AB[@]}" wait --load networkidle
"${AB[@]}" find text "+ مقایسه" click
"${AB[@]}" open "$BASE_URL/compare"
"${AB[@]}" wait --load networkidle
expect_text "ویژگی" "compare table renders"
expect_text "ارزش خرید" "compare table has the deal-score row"

step "estimate"
"${AB[@]}" open "$BASE_URL/estimate"
"${AB[@]}" find label "برند و مدل" fill "$MODEL"
"${AB[@]}" wait "[role='listbox'] button"
"${AB[@]}" find first "[role='listbox'] button" click
"${AB[@]}" wait --load networkidle
cat <<'EOF' | "${AB[@]}" eval --stdin
const year = [...document.querySelectorAll("select")].find((el) => !el.disabled && el.options.length > 2 && el.value === "");
if (year) { const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set; setter.call(year, year.options[1].value); year.dispatchEvent(new Event("change", { bubbles: true })); }
EOF
"${AB[@]}" find text "تخمین بزن" click
"${AB[@]}" wait --load networkidle
expect_text "بازهٔ منطقی" "estimate result card"
expect_text "چطور حساب شد" "estimate breakdown"

step "assistant question"
"${AB[@]}" find role button click --name "دستیار"
"${AB[@]}" find label "پیام" fill "$QUERY"
"${AB[@]}" press Enter
"${AB[@]}" wait --load networkidle
expect_text "آگهی پیدا کردم" "assistant replied with a real count"

step "422 message"
"${AB[@]}" open "$BASE_URL/results?q=x&year=1200"
"${AB[@]}" wait "[role='alert']"
expect_text "Invalid search filters" "422 envelope message is shown inline"

echo
echo "SMOKE PASSED against $BASE_URL"
