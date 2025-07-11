"""OpenAI embeddings implementation with retry logic and rate limiting."""

import time
from typing import List, Dict, Any, Optional
from .base import RetryableEmbedder, EmbeddingResult

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class OpenAIEmbedder(RetryableEmbedder):
    """OpenAI embeddings with retry logic and rate limiting."""
    
    # Model configurations with current 2025 pricing
    MODELS = {
        "text-embedding-3-small": {
            "dimensions": 1536,
            "max_tokens": 8191,
            "cost_per_1k_tokens": 0.00002  # $0.00002/1K tokens (current 2025)
        },
        "text-embedding-3-large": {
            "dimensions": 3072,
            "max_tokens": 8191,
            "cost_per_1k_tokens": 0.00013   # $0.00013/1K tokens (current 2025)
        },
        "text-embedding-ada-002": {
            "dimensions": 1536,
            "max_tokens": 8191,
            "cost_per_1k_tokens": 0.0001    # $0.0001/1K tokens (legacy model)
        }
    }
    
    def __init__(self, api_key: str = None, openai_api_key: str = None,
                 model: str = "text-embedding-3-small",
                 max_retries: int = 3, base_delay: float = 1.0,
                 base_url: Optional[str] = None, **kwargs):
        
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not available. Install with: pip install openai")
        
        # Support both parameter names for backward compatibility
        # Accept any non-empty string as an API key (custom endpoints may use arbitrary formats)
        final_api_key = api_key or openai_api_key
        if not final_api_key:
            raise ValueError("Valid OpenAI API key required")  # Only require a value, no format restriction
        
        if model not in self.MODELS:
            raise ValueError(f"Unsupported model: {model}. Available: {list(self.MODELS.keys())}")
        
        super().__init__(max_retries=max_retries, base_delay=base_delay)
        
        self.model = model
        self.model_config = self.MODELS[model]
        
        # Configure client with optional base_url
        client_args = {
            "api_key": final_api_key,
            "timeout": 30.0,
        }
        if base_url:
            client_args["base_url"] = base_url
            
        self.client = openai.OpenAI(**client_args)
        
        # Debugging: Log the client configuration
        self.logger.debug(f"OpenAI client initialized with base_url: {client_args.get('base_url', 'default')}, API key starts with: {final_api_key[:5]}...")
        
        # Rate limiting
        self._requests_per_minute = 3000  # Conservative limit
        self._tokens_per_minute = 1000000
        self._request_times: List[float] = []
        self._token_counts: List[tuple[float, int]] = []
    
    def _check_rate_limits(self, estimated_tokens: int = 1000):
        """Check and enforce rate limits."""
        current_time = time.time()
        
        # Clean old entries (older than 1 minute)
        self._request_times = [t for t in self._request_times if current_time - t < 60]
        self._token_counts = [(t, tokens) for t, tokens in self._token_counts if current_time - t < 60]
        
        # Check request rate limit
        if len(self._request_times) >= self._requests_per_minute:
            sleep_time = 60 - (current_time - self._request_times[0]) + 1
            if sleep_time > 0:
                print(f"Rate limit reached. Sleeping for {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
        
        # Check token rate limit
        total_tokens = sum(tokens for _, tokens in self._token_counts) + estimated_tokens
        if total_tokens >= self._tokens_per_minute:
            sleep_time = 60 - (current_time - self._token_counts[0][0]) + 1
            if sleep_time > 0:
                print(f"Token rate limit reached. Sleeping for {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text using accurate tiktoken counting."""
        return self.get_accurate_token_count(text)
    
    def _calculate_cost(self, token_count: int) -> float:
        """Calculate estimated cost for token count."""
        cost_per_token = self.model_config["cost_per_1k_tokens"] / 1000
        return token_count * cost_per_token
    
    def embed_text(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text."""
        start_time = time.time()
        estimated_tokens = self._estimate_tokens(text)
        
        # Truncate if necessary
        text = self.truncate_text(text)
        
        def _embed():
            self._check_rate_limits(estimated_tokens)
            
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            
            # Record request for rate limiting
            current_time = time.time()
            self._request_times.append(current_time)
            
            usage = response.usage
            actual_tokens = usage.total_tokens
            self._token_counts.append((current_time, actual_tokens))
            
            return EmbeddingResult(
                text=text,
                embedding=response.data[0].embedding,
                model=self.model,
                token_count=actual_tokens,
                processing_time=time.time() - start_time,
                cost_estimate=self._calculate_cost(actual_tokens)
            )
        
        try:
            result = self._embed_with_retry(_embed)
            return result
        except Exception as e:
            self.logger.error(f"❌ Error embedding text with OpenAI: {e}")
            return EmbeddingResult(
                text=text,
                embedding=[],
                model=self.model,
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        
        # For batch requests, we can send up to 2048 texts at once
        batch_size = min(500, len(texts))  # Increased batch size for better performance
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = self._embed_batch(batch)
            results.extend(batch_results)
        
        return results
    
    def _embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Embed a single batch of texts with smart batch splitting."""
        start_time = time.time()
        
        # Truncate texts if necessary
        truncated_texts = [self.truncate_text(text) for text in texts]
        
        # Validate and split batch if necessary
        validated_batches = self._validate_and_split_batch(truncated_texts)
        
        all_results = []
        for batch_texts in validated_batches:
            batch_results = self._embed_single_batch(batch_texts, start_time)
            all_results.extend(batch_results)
        
        return all_results
    
    def _validate_and_split_batch(self, texts: List[str]) -> List[List[str]]:
        """Validate batch token count and split if necessary."""
        # Calculate accurate token counts for all texts
        token_counts = [self.get_accurate_token_count(text) for text in texts]
        total_tokens = sum(token_counts)
        max_single_token = max(token_counts) if token_counts else 0
        
        # Set conservative batch limits
        max_batch_tokens = 40000  # Conservative total batch limit
        max_single_text_tokens = 7500  # Conservative individual text limit (well below 8192)
        
        self.logger.debug(f"📊 Batch validation: {len(texts)} texts, total_tokens: {total_tokens}, max_single: {max_single_token}")
        
        # Check for oversized individual texts and re-truncate if needed
        safe_texts = []
        for i, (text, token_count) in enumerate(zip(texts, token_counts)):
            if token_count > max_single_text_tokens:
                self.logger.warning(f"📏 Re-truncating oversized text (idx {i}): {token_count} → {max_single_text_tokens} tokens")
                # More aggressive truncation
                re_truncated = self.truncate_text(text, max_single_text_tokens + 200)  # Small buffer
                safe_texts.append(re_truncated)
            else:
                safe_texts.append(text)
        
        # If total batch is within limits, return as single batch
        if total_tokens <= max_batch_tokens:
            return [safe_texts]
        
        # Split into multiple batches
        self.logger.info(f"🔄 Splitting large batch: {total_tokens} tokens → multiple smaller batches")
        batches = []
        current_batch = []
        current_tokens = 0
        
        for text in safe_texts:
            text_tokens = self.get_accurate_token_count(text)
            
            # If adding this text would exceed batch limit, start new batch
            if current_tokens + text_tokens > max_batch_tokens and current_batch:
                batches.append(current_batch)
                current_batch = [text]
                current_tokens = text_tokens
            else:
                current_batch.append(text)
                current_tokens += text_tokens
        
        # Add final batch
        if current_batch:
            batches.append(current_batch)
        
        self.logger.info(f"📦 Split into {len(batches)} batches with max {max(sum(self.get_accurate_token_count(t) for t in batch) for batch in batches)} tokens each")
        
        return batches
    
    def _embed_single_batch(self, texts: List[str], start_time: float) -> List[EmbeddingResult]:
        """Embed a single validated batch of texts."""
        estimated_tokens = sum(self._estimate_tokens(text) for text in texts)
        
        def _embed():
            self._check_rate_limits(estimated_tokens)
            
            # Final token validation before API call
            token_counts = [self.get_accurate_token_count(text) for text in texts]
            max_tokens_in_batch = max(token_counts)
            total_tokens = sum(token_counts)
            avg_tokens_in_batch = total_tokens / len(token_counts)
            
            self.logger.debug(f"📊 Final batch stats: {len(texts)} texts, total: {total_tokens}, max: {max_tokens_in_batch}, avg: {avg_tokens_in_batch:.1f}")
            
            # Emergency check - should not happen with validation
            if max_tokens_in_batch > 8000:
                self.logger.error(f"🚨 EMERGENCY: Oversized text detected after validation: {max_tokens_in_batch} tokens")
                raise ValueError(f"Text exceeds token limit after validation: {max_tokens_in_batch} tokens")
            
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
                encoding_format="float"
            )
            
            # Record request for rate limiting
            current_time = time.time()
            self._request_times.append(current_time)
            
            usage = response.usage
            actual_tokens = usage.total_tokens
            self._token_counts.append((current_time, actual_tokens))
            
            # Log successful batch processing
            self.logger.debug(f"✅ Batch processed successfully: {actual_tokens} actual tokens vs {estimated_tokens} estimated")
            if abs(actual_tokens - estimated_tokens) > estimated_tokens * 0.2:  # 20% difference
                self.logger.debug(f"📊 Token estimation variance: {((actual_tokens - estimated_tokens) / estimated_tokens * 100):.1f}%")
            
            # Create results for each text
            processing_time = time.time() - start_time
            total_cost = self._calculate_cost(actual_tokens)
            cost_per_text = total_cost / len(texts)
            tokens_per_text = actual_tokens // len(texts)
            
            results = []
            for i, (text, embedding_data) in enumerate(zip(texts, response.data)):
                results.append(EmbeddingResult(
                    text=text,
                    embedding=embedding_data.embedding,
                    model=self.model,
                    token_count=tokens_per_text,
                    processing_time=processing_time / len(texts),
                    cost_estimate=cost_per_text
                ))
            
            return results
        
        try:
            return self._embed_with_retry(_embed)
        except Exception as e:
            error_msg = str(e)
            self.logger.warning(f"⚠️ Batch embedding failed: {error_msg}")
            
            # Check if this is a token limit error that requires individual retry
            if "maximum context length" in error_msg.lower() or "token" in error_msg.lower():
                self.logger.info(f"🔄 Attempting individual text embedding fallback for {len(texts)} texts")
                return self._embed_individual_fallback(texts, start_time)
            else:
                # For other errors, return error results for all texts
                self.logger.error(f"❌ Non-recoverable embedding error: {error_msg}")
                return [
                    EmbeddingResult(
                        text=text,
                        embedding=[],
                        model=self.model,
                        processing_time=0.0,
                        error=error_msg
                    )
                    for text in texts
                ]
    
    def _embed_individual_fallback(self, texts: List[str], start_time: float) -> List[EmbeddingResult]:
        """Fallback to individual text embedding when batch fails."""
        results = []
        successful = 0
        failed = 0
        
        for i, text in enumerate(texts):
            try:
                # Use single text embedding with more aggressive truncation
                individual_result = self.embed_text(text)
                results.append(individual_result)
                if individual_result.success:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                error_msg = str(e)
                self.logger.warning(f"❌ Individual embedding failed for text {i+1}/{len(texts)}: {error_msg}")
                results.append(EmbeddingResult(
                    text=text,
                    embedding=[],
                    model=self.model,
                    processing_time=0.0,
                    error=error_msg
                ))
        
        self.logger.info(f"🎯 Individual fallback completed: {successful}/{len(texts)} successful, {failed} failed")
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model."""
        return {
            "provider": "openai",
            "model": self.model,
            "dimensions": self.model_config["dimensions"],
            "max_tokens": self.model_config["max_tokens"],
            "cost_per_1k_tokens": self.model_config["cost_per_1k_tokens"],
            "supports_batch": True,
            "rate_limits": {
                "requests_per_minute": self._requests_per_minute,
                "tokens_per_minute": self._tokens_per_minute
            }
        }
    
    def get_max_tokens(self) -> int:
        """Get maximum token limit for input text."""
        return self.model_config["max_tokens"]
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        current_time = time.time()
        
        # Recent requests (last minute)
        recent_requests = [t for t in self._request_times if current_time - t < 60]
        recent_tokens = sum(tokens for t, tokens in self._token_counts if current_time - t < 60)
        
        # Total usage
        total_requests = len(self._request_times)
        total_tokens = sum(tokens for _, tokens in self._token_counts)
        total_cost = sum(self._calculate_cost(tokens) for _, tokens in self._token_counts)
        
        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost_estimate": total_cost,
            "recent_requests_per_minute": len(recent_requests),
            "recent_tokens_per_minute": recent_tokens,
            "average_tokens_per_request": total_tokens / max(total_requests, 1)
        }
