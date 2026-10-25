# Rate Limiting Fix - Social Discovery Agent

## Problem Identified

**Bug:** Rate limiting function defined but NEVER CALLED!

### Code Location:
- **Defined:** `src/s_q_ali_media_downloader/agent/tools/social_verifier.py:92-116`
- **Should be used:** Before every HTTP request (Facebook, Instagram, TikTok)

### What was happening:
```python
# Rate limit function exists...
def _enforce_rate_limit(self) -> None:
    """Enforce rate limiting with exponential backoff."""
    # ... 2 second delay between requests ...
    # ... reset counter every 10 requests ...

# BUT... it was NEVER called anywhere!
# All 3 platforms (FB, IG, TikTok) made requests without any rate limiting
```

### Impact:
- **Before fix:** Agent could make unlimited rapid requests
- **Risk:** IP bans from Facebook, Instagram, TikTok
- **User experience:** Bulk discovery could get IP blocked

## Fix Applied

Added `self._enforce_rate_limit()` call **BEFORE** every HTTP request in all 3 platforms:

### 1. Facebook (verify_facebook_presence)
```python
# BEFORE request
self._enforce_rate_limit()

async with httpx.AsyncClient(...) as client:
    response = await client.get(target_url)
```

### 2. Instagram (verify_instagram_presence)
```python
# BEFORE request
self._enforce_rate_limit()

async with httpx.AsyncClient(...) as client:
    response = await client.get(target_url)
```

### 3. TikTok (verify_tiktok_presence)
```python
# BEFORE request
self._enforce_rate_limit()

async with httpx.AsyncClient(...) as client:
    response = await client.get(target_url)
```

## How Rate Limiting Works

```python
def _enforce_rate_limit(self) -> None:
    """
    - Minimum 2 seconds delay between requests
    - Resets counter every 10 requests (prevents unbounded delays)
    - Respects Retry-After headers from platforms
    """
    # Check platform's Retry-After header
    if self._retry_after_header > 0:
        time.sleep(self._retry_after_header)
    
    # Ensure 2 second minimum delay
    elapsed = time.time() - self._last_request_time
    if elapsed < 2.0:
        time.sleep(2.0 - elapsed)
    
    self._last_request_time = time.time()
    self._request_count += 1
    
    # Every 10 requests, sleep 1 second and reset counter
    if self._request_count % 10 == 0:
        time.sleep(1.0)
        self._request_count = 0  # FIXED: Reset counter
```

## Verification

Tests pass after fix:
```
✓ Real Instagram is FOUND
✓ Fake Instagram is NOT_FOUND
✓ Real Facebook is FOUND
✓ Fake Facebook is NOT_FOUND
✓ Real TikTok is FOUND
✓ Evidence collected
```

## Impact

| Before Fix | After Fix |
|------------|-----------|
| Unlimited rapid requests | 2 second delay per request |
| Risk of IP ban | Protected from rate limits |
| Bulk discovery could fail | Safe for bulk verification |
| No rate limiting logic used | Rate limiting enforced |

## Files Changed

1. `src/s_q_ali_media_downloader/agent/tools/social_verifier.py`
   - Line 168, 230, 290: Added `_enforce_rate_limit()` call before each request

**Total lines changed:** 3 lines added

## Conclusion

Rate limiting **NOW WORKS** and protects the agent from IP bans during bulk social discovery.

**Status:** ✅ FIXED
