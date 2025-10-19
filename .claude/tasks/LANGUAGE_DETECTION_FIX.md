# Correction du Bug de Détection de Langue

**Date**: 2025-10-18
**Statut**: ✅ CORRIGÉ

## Symptôme

Le champ `language` restait systématiquement `null` dans la base de données après chaque crawl, malgré :
- Une fonction complète de détection de langue (`detect_language()`)
- Du contenu textuel valide dans le champ `readable`
- Aucune erreur apparente dans les logs

## Cause Racine Identifiée

**Incohérence de nommage entre le code et le modèle SQLAlchemy** :

### Dans le modèle SQLAlchemy ([models.py:216](../MyWebIntelligenceAPI/app/db/models.py#L216))
```python
lang = Column("language", String(10), nullable=True)
```
- **Attribut Python**: `expr.lang`
- **Colonne DB**: `"language"`

### Dans les crawlers (AVANT correction)
```python
update_data["language"] = final_lang  # ❌ ERREUR
```

Le code écrivait dans `update_data["language"]`, puis faisait :
```python
for field, value in update_data.items():
    setattr(expr, field, value)  # Essaie expr.language (n'existe pas !)
```

Résultat : `setattr(expr, "language", final_lang)` créait un attribut Python non-mappé qui n'était jamais écrit en base de données.

## Corrections Appliquées

### 1. Crawler Synchrone ([crawler_engine_sync.py:259](../MyWebIntelligenceAPI/app/core/crawler_engine_sync.py#L259))

**AVANT** :
```python
update_data.update({
    "title": metadata.get("title"),
    "description": metadata.get("description"),
    "keywords": metadata.get("keywords"),
    "language": final_lang,  # ❌ Mauvaise clé
    "readable": readable_content,
    # ...
})
```

**APRÈS** :
```python
update_data.update({
    "title": metadata.get("title"),
    "description": metadata.get("description"),
    "keywords": metadata.get("keywords"),
    "lang": final_lang,  # ✅ Bonne clé qui mappe l'attribut SQLAlchemy
    "readable": readable_content,
    # ...
})
```

### 2. Crawler Asynchrone ([crawler_engine.py:206](../MyWebIntelligenceAPI/app/core/crawler_engine.py#L206))

**AVANT** :
```python
update_data["language"] = final_lang  # ❌
```

**APRÈS** :
```python
update_data["lang"] = final_lang  # ✅
```

### 3. Améliorations Supplémentaires de Détection

En plus de la correction principale, nous avons amélioré la robustesse de la détection :

#### [text_utils.py](../MyWebIntelligenceAPI/app/utils/text_utils.py)

**`detect_language()` (lignes 40-103)** :
- Seuil réduit : 20 → 10 caractères
- Logs `DEBUG` → `INFO`/`WARNING` pour visibilité
- Ajout de logs détaillés sur la longueur du texte

**`_detect_language_fallback()` (lignes 105-170)** :
- Seuil réduit : 20 → 10 caractères, 5 → 3 mots
- Retour de 'en' par défaut au lieu de `None` pour texte > 50 chars
- Logs détaillés à chaque étape de détection

#### Logs de Diagnostic ([crawler_engine_sync.py:243](../MyWebIntelligenceAPI/app/core/crawler_engine_sync.py#L243))

```python
logger.info(f"Language detection for {expr_url}: "
            f"detected_lang={detected_lang}, "
            f"html_lang={html_lang}, "
            f"final_lang={final_lang}, "
            f"word_count={word_count}")
```

## Comment Tester

### Test 1 : Vérifier la base de données

```bash
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
SELECT
    COUNT(*) FILTER (WHERE readable IS NOT NULL) as with_readable,
    COUNT(*) FILTER (WHERE language IS NOT NULL) as with_language
FROM expressions;"
```

### Test 2 : Re-crawler une expression existante

```bash
# 1. Trouver une expression
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
SELECT id, LEFT(url, 50), language, word_count
FROM expressions
WHERE readable IS NOT NULL
LIMIT 1;"

# 2. Réinitialiser pour forcer le re-crawl
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
UPDATE expressions
SET approved_at = NULL, language = NULL
WHERE id = <ID_EXPRESSION>;"

# 3. Lancer le crawl (via Celery worker ou API selon votre config)

# 4. Vérifier le résultat
docker exec mywebclient-db-1 psql -U mwi_user -d mwi_db -c "
SELECT id, language, word_count
FROM expressions
WHERE id = <ID_EXPRESSION>;"
```

### Test 3 : Vérifier les logs

```bash
# Logs de détection de langue
docker logs mywebintelligenceapi 2>&1 | grep -i "language detection"

# Logs de langdetect
docker logs mywebintelligenceapi 2>&1 | grep -i "langdetect"
```

## Résultat Attendu

Après les corrections :

1. ✅ Le champ `language` est correctement rempli dans la base de données
2. ✅ Les logs `INFO` montrent la détection de langue pour chaque crawl
3. ✅ La langue est détectée même pour des textes courts (>10 chars)
4. ✅ Un fallback raisonnable ('en') est appliqué pour les textes non identifiés

## Impact

- **Fichiers modifiés** : 3
  - `app/core/crawler_engine_sync.py`
  - `app/core/crawler_engine.py`
  - `app/utils/text_utils.py`

- **Tests** : Scripts créés dans `tests/`
  - `test_language_detection_fix.sh`
  - `test_language_quick.sh`
  - `test_lang_simple.sh`

## Prochaines Étapes

1. **Re-crawler les expressions existantes** pour remplir le champ `language` :
   ```sql
   UPDATE expressions SET approved_at = NULL WHERE readable IS NOT NULL AND language IS NULL;
   ```

2. **Surveiller les statistiques** de détection :
   ```sql
   SELECT
       language,
       COUNT(*) as count
   FROM expressions
   WHERE language IS NOT NULL
   GROUP BY language
   ORDER BY count DESC;
   ```

3. **Ajuster le fallback** si nécessaire selon les statistiques réelles

## Leçons Apprises

- ⚠️ **Toujours vérifier la correspondance entre les clés de dict et les attributs SQLAlchemy**
- ⚠️ **Les attributs Python non-mappés ne génèrent pas d'erreur avec `setattr()` mais ne sont jamais persistés**
- ✅ **Utiliser des logs `INFO` pour les opérations critiques** (pas seulement `DEBUG`)
- ✅ **Tester l'écriture en base, pas seulement la logique métier**
