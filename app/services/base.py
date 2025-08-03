"""
Base Service - базовый класс для всех сервисов
"""

from typing import Optional, List, Type, TypeVar, Generic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import DeclarativeBase

from app.core.exceptions import NotFoundError, ValidationError

ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base service with common CRUD operations"""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        """Get object by ID"""
        query = select(self.model).where(self.model.id == id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_or_404(self, db: AsyncSession, id: int) -> ModelType:
        """Get object by ID or raise 404"""
        obj = await self.get(db, id)
        if not obj:
            raise NotFoundError(f"{self.model.__name__} not found")
        return obj
    
    async def get_multi(
        self, 
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        """Get multiple objects with pagination"""
        query = select(self.model)
        
        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.where(getattr(self.model, field) == value)
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def create(self, db: AsyncSession, obj_in: CreateSchemaType, **kwargs) -> ModelType:
        """Create new object"""
        obj_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in
        obj_data.update(kwargs)
        
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self, 
        db: AsyncSession, 
        db_obj: ModelType, 
        obj_in: UpdateSchemaType
    ) -> ModelType:
        """Update object"""
        update_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, 'dict') else obj_in
        
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        await db.flush()
        await db.refresh(db_obj)
        return db_obj
    
    async def delete(self, db: AsyncSession, id: int) -> bool:
        """Delete object"""
        query = delete(self.model).where(self.model.id == id)
        result = await db.execute(query)
        return result.rowcount > 0
    
    async def count(self, db: AsyncSession, **filters) -> int:
        """Count objects"""
        query = select(func.count(self.model.id))
        
        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.where(getattr(self.model, field) == value)
        
        result = await db.execute(query)
        return result.scalar()
    
    async def exists(self, db: AsyncSession, id: int) -> bool:
        """Check if object exists"""
        query = select(self.model.id).where(self.model.id == id)
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None
