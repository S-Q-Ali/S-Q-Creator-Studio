# Validate the key fixes work
import sys
sys.path.insert(0, 'src')

print("Testing settings_store...")
from s_q_ali_media_downloader.core import settings_store
settings_store.configure(None)
settings_store.set_setting("test_key", "test_value")
value = settings_store.get_setting("test_key")
assert value == "test_value", f"Expected 'test_value', got '{value}'"
print("[PASS] settings_store.get_setting/set_setting works")

print("\nTesting engine...")
from s_q_ali_media_downloader.engine import is_youtube_url, is_tiktok_url, MAX_ACCOUNT_VIDEOS, ACCOUNT_LIMITS
assert is_youtube_url("https://www.youtube.com/watch?v=abc123")
assert is_tiktok_url("https://www.tiktok.com/@user/video/123")
assert MAX_ACCOUNT_VIDEOS == max(ACCOUNT_LIMITS), "MAX_ACCOUNT_VIDEOS should be derived from ACCOUNT_LIMITS"
print("[PASS] engine functions work")

print("\nTesting browser.py...")
from s_q_ali_media_downloader.agent.tools.browser import BROWSER_CHANNELS
assert "firefox" in BROWSER_CHANNELS, "Firefox should be in browser channels"
print(f"[PASS] BROWSER_CHANNELS includes firefox: {BROWSER_CHANNELS}")

print("\nTesting orchestrator...")
from s_q_ali_media_downloader.agent.orchestrator import AgentOrchestrator
orch = AgentOrchestrator()
assert hasattr(orch, "_loop"), "Orchestrator should have _loop attribute"
assert hasattr(orch, "__del__"), "Orchestrator should have __del__ method"
orch.__del__()
print("[PASS] orchestrator has persistent event loop")

print("\nAll critical fixes validated!")
