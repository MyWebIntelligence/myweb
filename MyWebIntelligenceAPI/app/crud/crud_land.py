from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import Land, Word, LandDictionary
from app.schemas.land import LandCreate, LandUpdate
from app.core.text_processing import get_lemma

class CRUDLand:
    async def get(self, db: AsyncSession, id: int):
        result = await db.execute(select(Land).filter(Land.id == id))
        return result.scalars().first()

    async def get_by_name(self, db: AsyncSession, name: str):
        result = await db.execute(select(Land).filter(Land.name == name))
        return result.scalars().first()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100):
        result = await db.execute(select(Land).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj_in: LandCreate, owner_id: int):
        db_obj = Land(
            name=obj_in.name,
            description=obj_in.description,
            owner_id=owner_id,
            start_urls=obj_in.start_urls,
            lang=obj_in.lang,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, db_obj: Land, obj_in: LandUpdate):
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, id: int):
        obj = await self.get(db, id=id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def add_terms_to_land(self, db: AsyncSession, land_id: int, terms: list[str]):
        land = await self.get(db, id=land_id)
        if not land:
            return None

        for term in terms:
            lemma = get_lemma(term, land.lang)
            result = await db.execute(select(Word).filter(Word.lemma == lemma))
            word = result.scalars().first()
            
            if not word:
                word = Word(word=term, lemma=lemma, lang=land.lang)
                db.add(word)
                await db.commit()
                await db.refresh(word)

            result = await db.execute(
                select(LandDictionary).filter_by(land_id=land.id, word_id=word.id)
            )
            association = result.scalars().first()
            if not association:
                new_association = LandDictionary(land_id=land.id, word_id=word.id, weight=1.0)
                db.add(new_association)
        
        await db.commit()
        await db.refresh(land)
        return land

land = CRUDLand()
