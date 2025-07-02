"""
Fonctions CRUD pour les Lands
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import models
from app.schemas.land import LandCreate, LandUpdate
from app.schemas.job import JobStatus
from app.db.models import CrawlStatus

async def get_land(db: AsyncSession, land_id: int) -> Optional[models.Land]:
    """Récupère un land par son ID, en préchargeant son dictionnaire."""
    result = await db.execute(
        select(models.Land)
        .options(selectinload(models.Land.words))
        .filter(models.Land.id == land_id)
    )
    return result.scalar_one_or_none()

async def get_lands_by_owner(db: AsyncSession, owner_id: int, skip: int = 0, limit: int = 100) -> List[models.Land]:
    """Récupère les lands d'un utilisateur."""
    query = (
        select(models.Land)
        .where(models.Land.owner_id == owner_id)
        .offset(skip)
        .limit(limit)
        .order_by(models.Land.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())

async def create_land(db: AsyncSession, *, land_in: LandCreate, owner_id: int) -> models.Land:
    """Crée un nouveau land."""
    land_data = land_in.model_dump()
    # Convertir la liste de langues en une chaîne de caractères
    if 'lang' in land_data and isinstance(land_data['lang'], list):
        land_data['lang'] = ','.join(land_data['lang'])
    
    db_land = models.Land(**land_data, owner_id=owner_id)
    db.add(db_land)
    await db.commit()
    await db.refresh(db_land, attribute_names=["words"])
    return db_land

async def update_land(db: AsyncSession, *, db_land: models.Land, land_in: LandUpdate) -> models.Land:
    """Met à jour un land."""
    update_data = land_in.model_dump(exclude_unset=True)
    
    # Convertir la liste de langues en une chaîne de caractères si elle est présente
    if 'lang' in update_data and isinstance(update_data['lang'], list):
        update_data['lang'] = ','.join(update_data['lang'])
        
    for field, value in update_data.items():
        setattr(db_land, field, value)
        
    db.add(db_land)
    await db.commit()
    await db.refresh(db_land)
    return db_land

async def delete_land(db: AsyncSession, *, land_id: int) -> Optional[models.Land]:
    """Supprime un land."""
    land = await get_land(db, land_id)
    if land:
        await db.delete(land)
        await db.commit()
    return land

async def update_land_status(db: AsyncSession, land_id: int, status: CrawlStatus):
    """Met à jour le statut de crawling d'un land."""
    land = await get_land(db, land_id)
    if land:
        land.crawl_status = status.value  # type: ignore
        await db.commit()

async def add_terms_to_land(db: AsyncSession, *, land: models.Land, terms: List[str]) -> models.Land:
    """Ajoute des termes à un land avec lemmatisation multilingue."""
    from nltk.stem.snowball import SnowballStemmer
    from langdetect import detect, LangDetectException
    import nltk

    # Initialiser NLTK si nécessaire
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

    # Cache pour les stemmers
    if not hasattr(add_terms_to_land, "stemmers"):
        setattr(add_terms_to_land, "stemmers", {})
    stemmers = getattr(add_terms_to_land, "stemmers")

    # Récupérer les langues du land
    land_langs_str = land.lang or ""
    land_langs = [lang.strip() for lang in land_langs_str.split(',') if lang.strip()]
    
    # Mapping des codes de langue de langdetect aux noms de langue de SnowballStemmer
    lang_mapping = {
        'en': 'english',
        'fr': 'french',
        'es': 'spanish',
        'de': 'german',
        'it': 'italian',
        'pt': 'portuguese',
        'ru': 'russian',
        'sv': 'swedish',
        'nl': 'dutch',
        'fi': 'finnish',
        'da': 'danish',
        'no': 'norwegian',
        'hu': 'hungarian',
        'ro': 'romanian',
        'ar': 'arabic',
    }
    
    # Déterminer la langue par défaut
    default_lang_code = land_langs[0] if land_langs else "fr"
    default_lang_name = lang_mapping.get(default_lang_code, "french")


    for term_text in terms:
        lang_to_use = default_lang_name
        try:
            detected_lang_code = detect(term_text)
            detected_lang_name = lang_mapping.get(detected_lang_code)
            
            if detected_lang_name and detected_lang_name in SnowballStemmer.languages and detected_lang_code in land_langs:
                lang_to_use = detected_lang_name

        except LangDetectException:
            # La langue n'a pas pu être détectée, on utilise la langue par défaut
            pass

        if lang_to_use not in stemmers:
            stemmers[lang_to_use] = SnowballStemmer(lang_to_use)
        
        stemmer = stemmers[lang_to_use]
        lemma = stemmer.stem(term_text.lower())
        
        # Vérifier si le mot existe déjà
        result = await db.execute(select(models.Word).filter(models.Word.word == term_text))
        word = result.scalar_one_or_none()
        
        if not word:
            # Créer le mot avec la lemmatisation détectée
            word = models.Word(word=term_text, lemma=lemma)
            db.add(word)
            await db.flush()

        # Vérifier si l'association existe déjà pour éviter les doublons
        result = await db.execute(
            select(models.LandDictionary)
            .filter(models.LandDictionary.land_id == land.id)
            .filter(models.LandDictionary.word_id == word.id)
        )
        existing_association = result.scalar_one_or_none()

        if not existing_association:
            # Créer l'association dans LandDictionary
            association = models.LandDictionary(land_id=land.id, word_id=word.id)
            db.add(association)
            await db.flush()

    await db.commit()
    await db.refresh(land, attribute_names=["words"])
    return land

async def get_land_dictionary(db: AsyncSession, land_id: int) -> List[models.Word]:
    """Récupère les mots du dictionnaire pour un land donné."""
    result = await db.execute(
        select(models.Word)
        .join(models.LandDictionary)
        .filter(models.LandDictionary.land_id == land_id)
        .order_by(models.Word.word)
    )
    return list(result.scalars().all())
