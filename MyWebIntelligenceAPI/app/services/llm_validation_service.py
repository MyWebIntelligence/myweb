"""
LLM Validation Service for expression relevance validation using OpenRouter.
Based on the legacy implementation with OpenRouter API integration.
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Expression, Land
from app.schemas.readable import ValidationResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LLMValidationService:
    """Service for validating expression relevance using LLM via OpenRouter API."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.timeout = 30.0
        self.max_retries = 3
    
    async def validate_expression_relevance(
        self,
        expression: Expression,
        land: Land,
        model: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate if an expression is relevant to the land's research topic.
        
        Args:
            expression: Expression to validate
            land: Land context for validation
            model: Optional model override
            
        Returns:
            ValidationResult with relevance determination
        """
        if not self._is_validation_enabled():
            return ValidationResult(
                is_relevant=True,  # Default to relevant if disabled
                model_used="disabled",
                error_message="LLM validation is disabled"
            )
        
        try:
            # Build validation prompt
            prompt = self._build_relevance_prompt(expression, land)
            
            # Determine model to use
            validation_model = model or settings.OPENROUTER_MODEL or "anthropic/claude-3.5-sonnet"
            
            # Call OpenRouter API
            response = await self._call_openrouter_api(prompt, validation_model)
            
            # Parse response
            is_relevant = self._parse_yes_no_response(response.get('content', ''))
            
            return ValidationResult(
                is_relevant=is_relevant,
                model_used=validation_model,
                prompt_tokens=response.get('usage', {}).get('prompt_tokens'),
                completion_tokens=response.get('usage', {}).get('completion_tokens')
            )
            
        except Exception as e:
            logger.error(f"LLM validation failed for expression {expression.id}: {e}")
            return ValidationResult(
                is_relevant=True,  # Default to relevant on error
                model_used=model or "error",
                error_message=str(e)
            )
    
    async def validate_batch_expressions(
        self,
        expression_ids: List[int],
        land_id: int,
        model: Optional[str] = None
    ) -> Dict[int, ValidationResult]:
        """
        Validate multiple expressions in a batch with concurrency control.
        
        Args:
            expression_ids: List of expression IDs to validate
            land_id: Land ID for context
            model: Optional model override
            
        Returns:
            Dictionary mapping expression_id to ValidationResult
        """
        results = {}
        
        if not self._is_validation_enabled():
            # Return all as relevant if disabled
            for expr_id in expression_ids:
                results[expr_id] = ValidationResult(
                    is_relevant=True,
                    model_used="disabled",
                    error_message="LLM validation is disabled"
                )
            return results
        
        try:
            # Get land context
            land = await self.db.get(Land, land_id)
            if not land:
                raise ValueError(f"Land {land_id} not found")
            
            # Get expressions
            expressions_query = select(Expression).where(Expression.id.in_(expression_ids))
            expressions_result = await self.db.execute(expressions_query)
            expressions = expressions_result.scalars().all()
            
            # Validate with concurrency limit
            semaphore = asyncio.Semaphore(3)  # Limit concurrent API calls
            
            async def validate_single(expr):
                async with semaphore:
                    return expr.id, await self.validate_expression_relevance(expr, land, model)
            
            # Run validations concurrently
            validation_tasks = [validate_single(expr) for expr in expressions]
            validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)
            
            # Process results
            for result in validation_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch validation error: {result}")
                    continue
                
                expr_id, validation_result = result
                results[expr_id] = validation_result
            
            return results
            
        except Exception as e:
            logger.error(f"Batch validation failed: {e}")
            # Return error results for all expressions
            for expr_id in expression_ids:
                results[expr_id] = ValidationResult(
                    is_relevant=True,
                    model_used="error",
                    error_message=str(e)
                )
            return results
    
    def _is_validation_enabled(self) -> bool:
        """Check if LLM validation is enabled."""
        return (
            getattr(settings, 'OPENROUTER_ENABLED', False) and
            getattr(settings, 'OPENROUTER_API_KEY', None) is not None
        )
    
    def _build_relevance_prompt(self, expression: Expression, land: Land) -> str:
        """
        Build the relevance validation prompt in French (like legacy).
        Based on the legacy implementation prompt.
        """
        # Get land description and keywords
        land_desc = land.description or "Pas de description disponible"
        
        # Extract keywords from land words
        terms = []
        if hasattr(land, 'words') and land.words:
            for word_data in land.words:
                if isinstance(word_data, dict) and 'word' in word_data:
                    terms.append(word_data['word'])
                elif isinstance(word_data, str):
                    terms.append(word_data)
        
        terms_str = ', '.join(terms) if terms else "Aucun mot-clé défini"
        
        # Get expression content
        title = expression.title or "Pas de titre"
        description = expression.description or "Pas de description"
        
        # Limit readable content to avoid token limits
        readable_text = ""
        if expression.readable:
            # Take first 1000 characters to stay within token limits
            readable_text = expression.readable[:1000]
            if len(expression.readable) > 1000:
                readable_text += "..."
        else:
            readable_text = "Pas de contenu lisible disponible"
        
        # Build the prompt (same structure as legacy)
        prompt = f"""Dans le cadre de la constitution d'un corpus de pages Web à des fins d'analyse de contenu,
nous voulons savoir si la page crawlée est pertinente pour le projet ou non.

Le projet a les caractéristiques suivantes :
- Nom du projet : {land.name}
- Description : {land_desc}
- Mots clés : {terms_str}

La page suivante :
- URL = {expression.url}
- Titre : {title}
- Description : {description}
- Readable (extrait) : {readable_text}

Tu répondras ABSOLUMENT et uniquement par "oui" ou "non" sans aucun commentaire."""
        
        return prompt
    
    async def _call_openrouter_api(
        self,
        prompt: str,
        model: str
    ) -> Dict[str, Any]:
        """
        Call OpenRouter API with retry logic.
        
        Args:
            prompt: The validation prompt
            model: Model to use for validation
            
        Returns:
            API response content
        """
        if not getattr(settings, 'OPENROUTER_API_KEY', None):
            raise ValueError("OpenRouter API key not configured")
        
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mywebintelligence.io",  # Required by OpenRouter
            "X-Title": "MyWebIntelligence API"  # Optional but recommended
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 10,  # Very short response expected (just "oui" or "non")
            "temperature": 0.1,  # Low temperature for consistency
            "top_p": 0.9,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        last_error = None
        
        # Retry logic
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.base_url,
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        
                        if 'choices' in response_data and len(response_data['choices']) > 0:
                            choice = response_data['choices'][0]
                            message = choice.get('message', {})
                            
                            return {
                                'content': message.get('content', ''),
                                'usage': response_data.get('usage', {})
                            }
                        else:
                            raise ValueError("No choices in API response")
                    
                    elif response.status_code == 429:
                        # Rate limit - wait and retry
                        wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                        logger.warning(f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}")
                        await asyncio.sleep(wait_time)
                        last_error = f"Rate limit (attempt {attempt + 1})"
                        continue
                    
                    else:
                        # Other HTTP error
                        error_text = response.text
                        raise ValueError(f"API error {response.status_code}: {error_text}")
            
            except httpx.TimeoutException:
                last_error = f"Timeout (attempt {attempt + 1})"
                logger.warning(f"OpenRouter API timeout on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                continue
            
            except Exception as e:
                last_error = str(e)
                logger.error(f"OpenRouter API error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                continue
        
        # All retries failed
        raise Exception(f"OpenRouter API failed after {self.max_retries} attempts. Last error: {last_error}")
    
    def _parse_yes_no_response(self, response_content: str) -> bool:
        """
        Parse the LLM response to extract yes/no decision.
        
        Args:
            response_content: Raw response from LLM
            
        Returns:
            True if relevant (response contains "oui"), False otherwise
        """
        if not response_content:
            return False
        
        content_lower = response_content.lower().strip()
        
        # Look for French "oui" or English "yes"
        if 'oui' in content_lower or 'yes' in content_lower:
            return True
        
        # Look for French "non" or English "no"
        if 'non' in content_lower or 'no' in content_lower:
            return False
        
        # Default to False if unclear
        logger.warning(f"Unclear LLM response: '{response_content}', defaulting to non-relevant")
        return False
    
    async def update_expression_validation(
        self,
        expression: Expression,
        validation_result: ValidationResult
    ) -> None:
        """
        Update expression with validation results.
        
        Args:
            expression: Expression to update
            validation_result: Validation result to apply
        """
        try:
            # Update LLM validation fields
            expression.valid_llm = 'oui' if validation_result.is_relevant else 'non'
            expression.valid_model = validation_result.model_used
            
            # If not relevant, set relevance to 0 (like legacy behavior)
            if not validation_result.is_relevant:
                expression.relevance = 0
                # Remove approval if it was previously approved
                expression.approved_at = None
            
            await self.db.flush()
            
        except Exception as e:
            logger.error(f"Failed to update expression {expression.id} with validation: {e}")
            raise