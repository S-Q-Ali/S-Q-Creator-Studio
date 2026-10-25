#!/usr/bin/env python
"""Run comprehensive social discovery tests.

This script runs all tests for the social discovery agent and reports results.
"""

import sys
import subprocess


def run_test(test_file: str) -> bool:
    """Run a single test file and return True if it passed."""
    print(f"\n{'='*60}")
    print(f"Running: {test_file}")
    print('='*60)
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
        cwd="E:\\Web App\\S Q Ali Media Downloader",
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"✓ PASSED: {test_file}")
        return True
    else:
        print(f"✗ FAILED: {test_file}")
        print(result.stdout)
        print(result.stderr)
        return False


def main():
    """Run all comprehensive tests."""
    print("="*60)
    print("Social Discovery Comprehensive Test Suite")
    print("="*60)
    
    tests = [
        "tests/test_social_verify.py",
        "tests/test_social_browser.py",
        "tests/test_social_comprehensive.py",
        "tests/test_social_verifier.py",
        "tests/test_social_resolve.py",
        "tests/test_social_judge.py",
    ]
    
    results = []
    for test in tests:
        results.append(run_test(test))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
