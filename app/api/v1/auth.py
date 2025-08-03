"""
Authentication Endpoints - авторизация и управление пользователями
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.user_service import user_service
from app.schemas.user import User, UserCreate, UserUpdate, UserWithStats
from app.core.exceptions import UserNotFoundError, ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # For now, simple token validation
    # В production здесь будет JWT validation
    token = credentials.credentials
    
    # Extract user_id from token (simplified)
    try:
        # Простая валидация токена - в production используйте JWT
        if not token.startswith("user_"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format"
            )
        
        user_id = int(token.replace("user_", ""))
        user = await user_service.get_or_404(db, user_id)
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        return user
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )


@router.post("/telegram-auth", response_model=dict)
async def telegram_auth(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user via Telegram ID
    В production здесь будет проверка Telegram Login Widget
    """
    try:
        # Get or create user by telegram_id
        user = await user_service.get_user_by_telegram_id(db, telegram_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please use the Telegram bot first."
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        # Create simple token (в production - JWT)
        token = f"user_{user.id}"
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user
        }
        
    except Exception as e:
        logger.error(f"Telegram auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/me", response_model=UserWithStats)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user information with statistics"""
    try:
        # Get user stats
        stats = await user_service.get_user_stats(db, current_user.id)
        
        return UserWithStats(
            **current_user.__dict__,
            stats=stats
        )
        
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )


@router.put("/me", response_model=User)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user information"""
    try:
        updated_user = await user_service.update_user(
            db, current_user.id, user_update
        )
        
        await db.commit()
        return updated_user
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.post("/deactivate")
async def deactivate_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate user account"""
    try:
        success = await user_service.deactivate_user(db, current_user.id)
        
        if success:
            await db.commit()
            return {"message": "Account deactivated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to deactivate account"
            )
            
    except Exception as e:
        logger.error(f"Error deactivating account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate account"
        )


@router.get("/validate-token")
async def validate_token(current_user: User = Depends(get_current_user)):
    """Validate current token"""
    return {
        "valid": True,
        "user_id": current_user.id,
        "telegram_id": current_user.telegram_id
    }
