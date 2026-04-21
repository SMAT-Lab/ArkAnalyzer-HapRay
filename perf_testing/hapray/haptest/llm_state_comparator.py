"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import base64
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from hapray.haptest.state_manager import StateComparisonResult, StateStackEntry, TestContext

Log = logging.getLogger('HapTest.LLMComparator')


class LLMStateComparator:
    """
    Handles LLM-based semantic state comparison

    Uses vision language models to compare UI states semantically rather than
    by exact hash matching. Supports parallel comparison and caching.
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        base_url: str = None,
        enable_parallel: bool = True,
        cache_ttl: int = 3600,
        fallback_to_hash: bool = True
    ):
        """
        Initialize LLM state comparator

        Args:
            api_key: OpenAI API key (from env if None)
            model: Model name (default: gpt-4o-mini for cost efficiency)
            base_url: API base URL
            enable_parallel: Enable parallel comparison
            cache_ttl: Cache time-to-live in seconds
            fallback_to_hash: Fall back to hash comparison on API failure
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.base_url = (base_url or os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')).rstrip('/')
        self.enable_parallel = enable_parallel
        self.cache_ttl = cache_ttl
        self.fallback_to_hash = fallback_to_hash

        # Cache for comparison results
        self.comparison_cache: dict = {}

        # Statistics
        self.stats = {
            'total_comparisons': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'fallback_used': 0,
            'parallel_batches': 0
        }

        # Store last comparison results for visualization
        self.last_comparison_results = []

        Log.info(f'[LLMComparator] Initialized - Model: {self.model}, Parallel: {enable_parallel}')

    def compare_with_stack(
        self,
        new_state,
        new_description: str,
        state_stack: list,
        test_context: TestContext
    ) -> tuple[bool, Optional[int]]:
        """
        Compare new state with all states in stack

        Args:
            new_state: New UI state to compare
            new_description: LLM-generated description of new state
            state_stack: List of existing StateStackEntry objects
            test_context: Test context for prompts

        Returns:
            (is_new_state, matching_index)
            - is_new_state: True if state is different from all in stack
            - matching_index: Index of matching state (None if new)
        """
        if not state_stack:
            return (True, None)

        if self.enable_parallel:
            # Parallel comparison with all states
            results = self._compare_parallel(new_state, new_description, state_stack, test_context)
        else:
            # Sequential comparison
            results = self._compare_sequential(new_state, new_description, state_stack, test_context)

        # Store results for visualization
        self.last_comparison_results = results

        # Find best match
        best_match_idx = None
        best_similarity = 0.0

        for idx, result in enumerate(results):
            if result.is_same_state and result.similarity_score > best_similarity:
                best_similarity = result.similarity_score
                best_match_idx = idx

        is_new_state = best_match_idx is None
        return (is_new_state, best_match_idx)

    def _compare_parallel(
        self,
        new_state,
        new_description: str,
        state_stack: list,
        test_context: TestContext
    ) -> list:
        """
        Compare new state with multiple states in parallel
        Uses ThreadPoolExecutor for parallel API calls
        """
        results = [None] * len(state_stack)

        with ThreadPoolExecutor(max_workers=min(5, len(state_stack))) as executor:
            # Submit all comparison tasks
            future_to_idx = {
                executor.submit(
                    self._compare_two_states,
                    new_state,
                    new_description,
                    stack_entry,
                    test_context
                ): idx
                for idx, stack_entry in enumerate(state_stack)
            }

            # Collect results as they complete
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    Log.error(f'[LLMComparator] Parallel comparison failed for index {idx}: {e}')
                    # Use fallback for this comparison
                    results[idx] = self._fallback_comparison(
                        new_state.state_hash,
                        state_stack[idx].state_hash
                    )

        self.stats['parallel_batches'] += 1
        return results

    def _compare_sequential(
        self,
        new_state,
        new_description: str,
        state_stack: list,
        test_context: TestContext
    ) -> list:
        """
        Compare new state with states sequentially
        Stops early if a match is found with high confidence
        """
        results = []

        for stack_entry in state_stack:
            result = self._compare_two_states(new_state, new_description, stack_entry, test_context)
            results.append(result)

            # Early exit optimization: if high confidence match found
            if result.is_same_state and result.confidence > 0.9:
                Log.debug('[LLMComparator] High confidence match found, stopping early')
                # Fill remaining with "not same" results
                remaining = len(state_stack) - len(results)
                for _ in range(remaining):
                    results.append(StateComparisonResult(
                        is_same_state=False,
                        confidence=1.0,
                        reasoning="Skipped due to early match",
                        similarity_score=0.0,
                        key_differences=[],
                        used_fallback=False
                    ))
                break

        return results

    def _compare_two_states(
        self,
        new_state,
        new_description: str,
        stack_entry: StateStackEntry,
        test_context: TestContext
    ) -> StateComparisonResult:
        """
        Compare two states using LLM
        """
        self.stats['total_comparisons'] += 1

        # # Check cache first
        # cache_key = self._get_cache_key(new_state.state_hash, stack_entry.state_hash)
        # if cache_key in self.comparison_cache:
        #     cached = self.comparison_cache[cache_key]
        #     if not self._is_cache_expired(cached['timestamp']):
        #         self.stats['cache_hits'] += 1
        #         Log.debug('[LLMComparator] Cache hit for comparison')
        #         return cached['result']

        # # Quick hash check for optimization
        # if new_state.state_hash == stack_entry.state_hash:
        #     result = StateComparisonResult(
        #         is_same_state=True,
        #         confidence=1.0,
        #         reasoning="Exact hash match",
        #         similarity_score=1.0,
        #         key_differences=[],
        #         hash_match=True
        #     )
        #     self._cache_result(new_state.state_hash, stack_entry.state_hash, result)
        #     return result

        # Call LLM API
        try:
            result = self._call_comparison_api(
                new_state,
                new_description,
                stack_entry,
                test_context
            )
            self.stats['api_calls'] += 1
            self._cache_result(new_state.state_hash, stack_entry.state_hash, result)
            return result

        except Exception as e:
            Log.error(f'[LLMComparator] API call failed: {e}')
            if self.fallback_to_hash:
                self.stats['fallback_used'] += 1
                return self._fallback_comparison(
                    new_state.state_hash,
                    stack_entry.state_hash
                )
            raise

    def _call_comparison_api(
        self,
        new_state,
        new_description: str,
        stack_entry: StateStackEntry,
        test_context: TestContext
    ) -> StateComparisonResult:
        """
        Call LLM API to compare two states
        """
        import requests

        # Build comparison prompt
        prompt = self._build_comparison_prompt(
            new_description,
            stack_entry.description,
            test_context
        )

        # Encode screenshots
        new_screenshot_b64 = self._encode_image(new_state.screenshot_path)
        old_screenshot_b64 = self._encode_image(stack_entry.screenshot_path)

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        payload = {
            'model': self.model,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/png;base64,{old_screenshot_b64}',
                                'detail': 'low'  # Use low detail for cost efficiency
                            }
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/png;base64,{new_screenshot_b64}',
                                'detail': 'low'
                            }
                        }
                    ]
                }
            ],
            'max_completion_tokens': 300,  # Keep response concise
            'temperature': 0.3   # Lower temperature for more consistent results
        }

        response = requests.post(
            f'{self.base_url}/chat/completions',
            headers=headers,
            json=payload,
            timeout=300
        )

        if response.status_code != 200:
            raise RuntimeError(f'API call failed: {response.status_code} - {response.text}')

        result = response.json()
        llm_response = result['choices'][0]['message']['content']

        # Log.debug(f'[LLMComparator] LLM prompt: {prompt}')
        # Log.debug(f'[LLMComparator] LLM response: {llm_response}')

        # Parse response
        return self._parse_comparison_response(llm_response)

    def _build_comparison_prompt(
        self,
        new_description: str,
        old_description: str,
        test_context: TestContext
    ) -> str:
        """
        Build prompt for state comparison with test context
        """
        # Handle case where new_description is empty (will be backfilled later)
        if not new_description:
            new_state_info = "Description: [Not yet generated - please analyze from the screenshot]"
        else:
            new_state_info = f"Description: {new_description}"

        prompt = f"""You are testing the app: {test_context.app_name} ({test_context.app_package})
Test goal: {test_context.test_goal}
Current exploration depth: {test_context.current_depth}/{test_context.target_depth}

Compare these two mobile app screens to determine if they represent the SAME page/state.

**Screen 1 (Previous State):**
Description: {old_description}

**Screen 2 (Current State):**
{new_state_info}

**Comparison Criteria:**
1. Same page structure and layout
2. Same navigation level (e.g., both are list views, both are detail pages)
3. Same functional purpose
4. Minor differences in content/data are acceptable (e.g., different list items, updated timestamps)

**Important:**
- Focus on SEMANTIC similarity, not pixel-perfect matching
- Different data on the same page template = SAME state 
- Different page types (list vs detail) = DIFFERENT states
- Scrolled versions of the same page = SAME state
- If Screen 2 has no description, analyze it directly from the screenshot

**Response Format (JSON only):**
{{
    "is_same_state": true/false,
    "confidence": 0.0-1.0,
    "similarity_score": 0.0-1.0,
    "reasoning": "Brief explanation",
    "key_differences": ["difference1", "difference2"]
}}

Respond with JSON only, no additional text."""

        return prompt

    def _parse_comparison_response(self, llm_response: str) -> StateComparisonResult:
        """
        Parse LLM comparison response
        """
        try:
            # Extract JSON from response
            llm_response = llm_response.strip()
            if '```json' in llm_response:
                llm_response = llm_response.split('```json')[1].split('```')[0].strip()
            elif '```' in llm_response:
                llm_response = llm_response.split('```')[1].split('```')[0].strip()

            data = json.loads(llm_response)

            return StateComparisonResult(
                is_same_state=data.get('is_same_state', False),
                confidence=float(data.get('confidence', 0.5)),
                reasoning=data.get('reasoning', ''),
                similarity_score=float(data.get('similarity_score', 0.0)),
                key_differences=data.get('key_differences', []),
                used_fallback=False,
                hash_match=False
            )

        except Exception as e:
            Log.error(f'[LLMComparator] Failed to parse response: {e}')
            # Return conservative result
            return StateComparisonResult(
                is_same_state=False,
                confidence=0.0,
                reasoning=f"Parse error: {str(e)}",
                similarity_score=0.0,
                key_differences=[],
                used_fallback=True
            )

    def _fallback_comparison(self, hash1: str, hash2: str) -> StateComparisonResult:
        """
        Fallback to hash-based comparison
        """
        is_same = hash1 == hash2
        return StateComparisonResult(
            is_same_state=is_same,
            confidence=1.0 if is_same else 0.0,
            reasoning="Fallback to hash comparison",
            similarity_score=1.0 if is_same else 0.0,
            key_differences=[] if is_same else ["Hash mismatch"],
            used_fallback=True,
            hash_match=is_same
        )

    def _encode_image(self, image_path: str) -> str:
        """
        Encode image to base64
        """
        try:
            with open(image_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            Log.error(f'[LLMComparator] Image encoding failed: {e}')
            raise

    def _get_cache_key(self, hash1: str, hash2: str) -> str:
        """
        Generate cache key for comparison
        """
        return f"{hash1}_{hash2}"

    def _cache_result(self, hash1: str, hash2: str, result: StateComparisonResult):
        """
        Cache comparison result
        """
        cache_key = self._get_cache_key(hash1, hash2)
        self.comparison_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }

    def _is_cache_expired(self, timestamp: float) -> bool:
        """
        Check if cache entry is expired
        """
        return time.time() - timestamp > self.cache_ttl

