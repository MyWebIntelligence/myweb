#!/bin/bash

# Test simple : utiliser un land existant avec des expressions déjà crawlées
# pour vérifier que les métadonnées et le contenu HTML sont bien extraits

# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changethispassword" \
  | jq -r '.access_token')

echo "✅ Token obtained"
echo ""

# Get the first land (should be LecornuTest from previous tests)
LANDS=$(curl -s -X GET "http://localhost:8000/api/v2/lands/?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN")

LAND_ID=$(echo "$LANDS" | jq -r '.items[0].id')
LAND_NAME=$(echo "$LANDS" | jq -r '.items[0].name')

if [ "$LAND_ID" == "null" ] || [ -z "$LAND_ID" ]; then
  echo "❌ No lands found"
  exit 1
fi

echo "Using existing land: $LAND_NAME (ID: $LAND_ID)"
echo ""

# Get expressions for this land
echo "Fetching expressions for land $LAND_ID..."
EXPRESSIONS=$(curl -s -X GET "http://localhost:8000/api/v1/lands/$LAND_ID/expressions?page=1&per_page=3" \
  -H "Authorization: Bearer $TOKEN")

TOTAL_EXPRESSIONS=$(echo "$EXPRESSIONS" | jq '.total // 0')
echo "Total expressions: $TOTAL_EXPRESSIONS"

if [ "$TOTAL_EXPRESSIONS" -eq 0 ]; then
  echo "⚠️  No expressions in this land, trying another land..."

  LAND_ID=$(echo "$LANDS" | jq -r '.items[1].id')
  LAND_NAME=$(echo "$LANDS" | jq -r '.items[1].name')

  if [ "$LAND_ID" == "null" ]; then
    echo "❌ No other lands available"
    exit 1
  fi

  echo "Trying land: $LAND_NAME (ID: $LAND_ID)"
  EXPRESSIONS=$(curl -s -X GET "http://localhost:8000/api/v1/lands/$LAND_ID/expressions?page=1&per_page=3" \
    -H "Authorization: Bearer $TOKEN")
  TOTAL_EXPRESSIONS=$(echo "$EXPRESSIONS" | jq '.total // 0')
fi

if [ "$TOTAL_EXPRESSIONS" -eq 0 ]; then
  echo "❌ No expressions found in any land"
  exit 1
fi

echo ""
echo "========================================="
echo "Analyzing First 3 Expressions"
echo "========================================="

# Analyze each expression
for i in 0 1 2; do
  EXPR=$(echo "$EXPRESSIONS" | jq ".items[$i]")

  if [ "$EXPR" == "null" ]; then
    break
  fi

  EXPR_ID=$(echo "$EXPR" | jq -r '.id')
  EXPR_URL=$(echo "$EXPR" | jq -r '.url')
  EXPR_TITLE=$(echo "$EXPR" | jq -r '.title')
  EXPR_DESC=$(echo "$EXPR" | jq -r '.description')
  EXPR_KEYWORDS=$(echo "$EXPR" | jq -r '.keywords')
  EXPR_READABLE=$(echo "$EXPR" | jq -r '.readable')

  echo ""
  echo "--- Expression #$((i+1)) ---"
  echo "ID: $EXPR_ID"
  echo "URL: $EXPR_URL"
  echo "Title: $EXPR_TITLE"
  echo "Description: ${EXPR_DESC:0:100}..."
  echo "Keywords: $EXPR_KEYWORDS"
  echo "Readable length: ${#EXPR_READABLE} chars"
  echo ""

  # Check metadata extraction
  if [ "$EXPR_TITLE" != "null" ] && [ -n "$EXPR_TITLE" ] && [ "$EXPR_TITLE" != "$EXPR_URL" ]; then
    echo "  ✅ Title: EXTRACTED"
  else
    echo "  ⚠️  Title: MISSING or fallback to URL"
  fi

  if [ "$EXPR_DESC" != "null" ] && [ -n "$EXPR_DESC" ]; then
    echo "  ✅ Description: EXTRACTED"
  else
    echo "  ⚠️  Description: MISSING"
  fi

  if [ "$EXPR_KEYWORDS" != "null" ] && [ -n "$EXPR_KEYWORDS" ]; then
    echo "  ✅ Keywords: EXTRACTED"
  else
    echo "  ⚠️  Keywords: MISSING"
  fi

  if [ ${#EXPR_READABLE} -gt 100 ]; then
    echo "  ✅ Readable content: PRESENT"
  else
    echo "  ⚠️  Readable content: TOO SHORT or MISSING"
  fi
done

echo ""
echo "========================================="
echo "Checking 'content' field via export"
echo "========================================="

# Export to JSON to check the 'content' field (raw HTML)
EXPORT_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v2/export/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"land_id\": $LAND_ID, \"depth\": 999, \"minrel\": 0}")

EXPORT_JOB_ID=$(echo "$EXPORT_RESPONSE" | jq -r '.job_id')

if [ "$EXPORT_JOB_ID" == "null" ] || [ -z "$EXPORT_JOB_ID" ]; then
  echo "❌ Failed to start export"
  echo "$EXPORT_RESPONSE" | jq '.'
  exit 1
fi

echo "Export job ID: $EXPORT_JOB_ID"
echo "Waiting for export to complete..."

# Wait for export to complete
MAX_WAIT=20
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
  sleep 2
  WAITED=$((WAITED + 2))

  EXPORT_JOB=$(curl -s -X GET "http://localhost:8000/api/v1/jobs/$EXPORT_JOB_ID" \
    -H "Authorization: Bearer $TOKEN")

  JOB_STATUS=$(echo "$EXPORT_JOB" | jq -r '.status')
  echo "  Export status: $JOB_STATUS"

  if [ "$JOB_STATUS" == "completed" ]; then
    break
  fi
done

if [ "$JOB_STATUS" == "completed" ]; then
  echo "✅ Export completed"

  EXPORT_FILE=$(echo "$EXPORT_JOB" | jq -r '.result.file_path // .result.output_file // empty')

  if [ -n "$EXPORT_FILE" ] && [ "$EXPORT_FILE" != "null" ]; then
    echo "Export file: $EXPORT_FILE"
    echo ""

    # Check the first expression in the export
    docker exec mywebintelligenceapi cat "$EXPORT_FILE" 2>/dev/null | jq -r '.[0] | "URL: \(.url)\nTitle: \(.title)\nDescription: \(.description // "N/A")\nKeywords: \(.keywords // "N/A")\nContent (HTML) length: \(.content | length) chars\nReadable length: \(.readable | length) chars"' 2>/dev/null

    # Check if content field contains HTML
    HAS_HTML=$(docker exec mywebintelligenceapi cat "$EXPORT_FILE" 2>/dev/null | jq -r '.[0].content | select(. != null) | contains("<html") or contains("<!DOCTYPE") or contains("<body")' 2>/dev/null)

    if [ "$HAS_HTML" == "true" ]; then
      echo ""
      echo "✅ 'content' field contains HTML"
    else
      echo ""
      echo "⚠️  'content' field may not contain HTML or is empty"
    fi
  else
    echo "⚠️  Export file not accessible"
  fi
else
  echo "⚠️  Export did not complete in time"
fi

echo ""
echo "Test completed!"
