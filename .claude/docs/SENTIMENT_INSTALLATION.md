# Sentiment Analysis - Installation Guide

**Quick Setup Guide for Sentiment Analysis Feature**

---

## ⚡ Quick Installation (5 minutes)

### Step 1: Install Dependencies

```bash
cd MyWebIntelligenceAPI

# Install Python packages
pip install textblob==0.17.1 textblob-fr==0.2.0

# Download TextBlob corpora (required for sentiment analysis)
python -m textblob.download_corpora
```

**Expected output**:
```
[nltk_data] Downloading package brown to...
[nltk_data] Downloading package punkt to...
[nltk_data] Downloading package wordnet to...
[nltk_data] Downloading package averaged_perceptron_tagger to...
[nltk_data] Download complete!
```

### Step 2: Run Database Migration

```bash
# Apply migration to add sentiment fields
docker exec -i mywebclient-db-1 psql -U mwi_user -d mwi_db < migrations/add_sentiment_fields.sql
```

**Expected output**:
```
BEGIN
ALTER TABLE
ALTER TABLE
ALTER TABLE
ALTER TABLE
ALTER TABLE
ALTER TABLE
COMMENT
COMMENT
...
CREATE INDEX
CREATE INDEX
COMMIT
```

### Step 3: Configure Environment

Add to your `.env` file (or create if it doesn't exist):

```bash
# Sentiment Analysis Configuration
ENABLE_SENTIMENT_ANALYSIS=true
SENTIMENT_MIN_CONFIDENCE=0.5
SENTIMENT_SUPPORTED_LANGUAGES=fr,en

# Optional: OpenRouter for high-quality LLM sentiment
# OPENROUTER_ENABLED=false
# OPENROUTER_API_KEY=sk-or-v1-your-key-here
# OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

### Step 4: Restart Services

```bash
# Restart API and Celery workers
docker compose restart api celery_worker

# Verify services are running
docker compose ps
```

### Step 5: Verify Installation

Test sentiment analysis is working:

```bash
# Test sentiment provider
docker exec -it mywebclient-api-1 python3 << 'EOF'
from app.core.sentiment_provider import SentimentModelProvider
import asyncio

async def test():
    provider = SentimentModelProvider()
    result = await provider.analyze_sentiment("This is amazing!", "en")
    print(f"✅ Sentiment Analysis Working!")
    print(f"   Score: {result['score']}")
    print(f"   Label: {result['label']}")
    print(f"   Model: {result['model']}")

asyncio.run(test())
EOF
```

**Expected output**:
```
✅ TextBlob sentiment provider available
✅ Sentiment Analysis Working!
   Score: 0.625
   Label: positive
   Model: textblob
```

---

## ✅ Verification Checklist

After installation, verify:

- [ ] Dependencies installed (`textblob`, `textblob-fr`)
- [ ] TextBlob corpora downloaded
- [ ] Database migration completed (6 new fields added)
- [ ] Environment variables configured
- [ ] Services restarted successfully
- [ ] Test script runs without errors

---

## 🔧 Troubleshooting

### Issue: "No module named 'textblob'"

**Solution**:
```bash
pip install textblob textblob-fr
```

### Issue: "Resource punkt not found"

**Solution**:
```bash
python -m textblob.download_corpora
```

### Issue: "relation expressions does not exist"

**Solution**: Database migration not applied. Run:
```bash
docker exec -i mywebclient-db-1 psql -U mwi_user -d mwi_db < migrations/add_sentiment_fields.sql
```

### Issue: Sentiment fields are always `null`

**Causes & Solutions**:

1. **Feature disabled**:
   ```bash
   # Check .env
   grep ENABLE_SENTIMENT_ANALYSIS .env
   # Should show: ENABLE_SENTIMENT_ANALYSIS=true
   ```

2. **Services not restarted**:
   ```bash
   docker compose restart api celery_worker
   ```

3. **Check logs**:
   ```bash
   docker logs mywebclient-api-1 | grep -i sentiment
   ```

---

## 🚀 Next Steps

1. **Crawl with Sentiment**: The next crawl will automatically include sentiment analysis
   ```bash
   curl -X POST "http://localhost:8000/api/v2/lands/36/crawl" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"limit": 10}'
   ```

2. **Check Results**:
   ```sql
   SELECT id, url, sentiment_score, sentiment_label, sentiment_status
   FROM expressions
   WHERE land_id = 36
   ORDER BY id DESC
   LIMIT 5;
   ```

3. **Read Full Documentation**: See [SENTIMENT_ANALYSIS_FEATURE.md](./SENTIMENT_ANALYSIS_FEATURE.md)

---

## 📊 Optional: Enable OpenRouter for High-Quality Sentiment

For better accuracy (especially for complex or nuanced content):

1. **Get API Key**: Sign up at https://openrouter.ai/

2. **Configure `.env`**:
   ```bash
   OPENROUTER_ENABLED=true
   OPENROUTER_API_KEY=sk-or-v1-your-actual-key
   OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
   ```

3. **Restart**:
   ```bash
   docker compose restart api celery_worker
   ```

4. **Crawl with LLM**:
   ```bash
   curl -X POST "http://localhost:8000/api/v2/lands/36/crawl" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"limit": 10, "llm_validation": true}'  # Enables LLM for sentiment
   ```

**Note**: OpenRouter costs ~$0.003 per analysis. Use for critical content only.

---

## 🎉 Success!

You've successfully installed sentiment analysis! Your crawled content will now automatically include sentiment scores.

**Feature Status**: ✅ Active
**Method**: TextBlob (fast, free)
**Languages**: French, English
**Performance**: ~30-50ms per expression

---

**Installation Time**: ~5 minutes
**Last Updated**: 18 octobre 2025
