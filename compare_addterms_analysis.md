# Analyse Critique : AddTerms - Ancien vs Nouveau Système

## 🚨 **PROBLÈME MAJEUR IDENTIFIÉ**

Notre implémentation actuelle d'addterms est **INCOMPLÈTE** et ne respecte pas l'algorithme de calcul de pertinence de l'ancien système.

## 🔍 **Analyse de l'Ancien Système (model.py)**

### **Structure des modèles critiques :**
```python
class Word(BaseModel):
    term = CharField(max_length=30)      # Terme original
    lemma = CharField(max_length=30)     # Forme lemmatisée/stemmed

class LandDictionary(BaseModel):
    land = ForeignKeyField(Land, backref='words', on_delete='CASCADE')
    word = ForeignKeyField(Word, backref='lands', on_delete='CASCADE')
    # Table de liaison many-to-many entre Land et Word
```

### **Fonctions critiques dans core.py :**

#### `stem_word(word)` - Lemmatisation française
```python
def stem_word(word: str) -> str:
    if not hasattr(stem_word, "stemmer"):
        setattr(stem_word, "stemmer", FrenchStemmer())
    return str(getattr(stem_word, "stemmer").stem(word.lower()))
```

#### `expression_relevance(dictionary, expression)` - Calcul de pertinence
```python
def expression_relevance(dictionary, expression: model.Expression) -> int:
    lemmas = [w.lemma for w in dictionary]  # ⚠️ CRUCIAL: utilise les lemmas
    
    def get_relevance(text, weight) -> list:
        stems = [stem_word(w) for w in word_tokenize(text, language='french')]
        stemmed_text = " ".join(stems)
        return [sum(weight for _ in re.finditer(r'\b%s\b' % re.escape(lemma), stemmed_text)) for lemma in lemmas]

    title_relevance = get_relevance(expression.title, 10)    # Poids 10 pour titre
    content_relevance = get_relevance(expression.readable, 1) # Poids 1 pour contenu
    return sum(title_relevance) + sum(content_relevance)
```

#### Usage dans controller.py :
```python
# Dans l'ajout de termes
lemma = ' '.join([core.stem_word(w) for w in term.split(' ')])
word, _ = model.Word.get_or_create(term=term, lemma=lemma)
```

## ❌ **DÉFAUTS DE NOTRE IMPLÉMENTATION ACTUELLE**

### 1. **Structure identique ✅**
Notre modèle est correct :
```python
class Word(Base):
    word = Column(String(30))      # équivalent à 'term'
    lemma = Column(String(30))     # lemma

class LandDictionary(Base):
    land_id = Column(Integer, ForeignKey("lands.id"))
    word_id = Column(Integer, ForeignKey("words.id"))
```

### 2. **Lemmatisation incorrecte ❌**
```python
# ❌ NOTRE VERSION (incorrecte)
word = models.Word(word=term_text, lemma=term_text.lower())

# ✅ VERSION CORRECTE NÉCESSAIRE  
from nltk.stem.snowball import FrenchStemmer
stemmer = FrenchStemmer()
word = models.Word(word=term_text, lemma=stemmer.stem(term_text.lower()))
```

### 3. **Absence de calcul de pertinence ❌**
- L'ancien système utilise les words pour calculer la pertinence des expressions
- Notre système stocke les words mais ne les utilise pas
- Cela casse complètement l'algorithme de relevance

## 🔧 **CORRECTIONS URGENTES NÉCESSAIRES**

### 1. **✅ CORRECTION APPLIQUÉE - add_terms_to_land**
- Implémentation de la vraie lemmatisation française avec FrenchStemmer
- Compatibilité avec l'algorithme de l'ancien système

### 2. **⚠️ ACTIONS FUTURES REQUISES**
- Ajouter `nltk>=3.8` dans requirements.txt
- Implémenter `get_land_dictionary()` équivalent
- Implémenter `expression_relevance()` équivalent  
- Intégrer dans le système de crawling

## ✅ **CONCLUSION**

**Statut actuel après corrections :**
1. ✅ **Stockage** : Les termes sont stockés (test réussi)
2. ✅ **Lemmatisation** : Corrigée avec FrenchStemmer
3. ✅ **Structure** : Compatible avec l'ancien système
4. ⚠️ **Utilisation** : À implémenter dans le système de crawling

L'endpoint addterms est maintenant **correctement implémenté** avec la vraie lemmatisation française et est **compatible** avec l'architecture de l'ancien système.
