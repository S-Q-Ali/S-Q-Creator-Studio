# Security Policy

## Supported Versions

We take the security of S-Q Creator Studio seriously. We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 2.6.x   | ✅ Yes             |
| 2.5.x   | ⚠️ Limited         |
| 2.4.x   | ⚠️ Limited         |
| < 2.0   | ❌ No              |

## Reporting a Vulnerability

We take the security of S-Q Creator Studio seriously. If you believe you have found a security vulnerability, please report it to us immediately.

**DO NOT create a public issue on GitHub for security vulnerabilities.** Public issues can be exploited by malicious actors before fixes are deployed.

### How to Report

Please report security vulnerabilities via email to:

**Email:** `[YOUR-EMAIL-HERE]@example.com`

**Include in your report:**
- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact/risks
- Your contact information for follow-up

### What to Expect

1. **Response Time:** Within 48 hours
2. **Investigation:** We will review and investigate your report
3. **Status Update:** We will keep you updated on our progress
4. **Resolution:** Once fixed, we will notify you and publish the security advisory

### Best Practices

- Keep your yt-dlp and all dependencies updated to the latest versions
- Only download and use official release binaries from GitHub Releases
- Export cookies.txt only from trusted browsers
- Don't share your Groq API key or YouTube API key publicly
- Use the latest version of the app for maximum security

## Security Features

- **Encrypted Settings:** API keys are sealed at rest, and the row says which
  backend sealed it. Windows uses DPAPI, tied to your Windows account. Linux and
  macOS use the machine's keychain through `keyring`, and the database keeps only
  the item's name. Where no secret store is reachable, the value is stored with a
  `plain:` marker, the Settings page states it, and a warning is logged that names
  the key and never the key's value. Both backends hang off your login, so what
  they defend is a copied disk or a lost machine, not an attacker who is already
  running as you. The backend an OS gets is resolved on that OS in CI, where the
  app is built and launched on Windows, Ubuntu 24.04 and macOS 15; a CI runner is
  not a desktop, so the sealed round-trip against a real user keychain is covered
  by tests with a stand-in keychain and is proved on a user's machine. If your
  keychain refuses the app, that is a bug — report it with the OS and desktop.
- **Input Validation:** All user inputs are validated to prevent injection attacks
- **Secure Downloads:** Downloads are sandboxed and use yt-dlp's security features
- **No Telemetry:** The app does not collect or send user data to any server

## Security Updates

Security updates will be released as soon as possible after a vulnerability is confirmed. Users are encouraged to:

- Keep the app updated to the latest version
- Monitor GitHub Releases for security advisories
- Subscribe to GitHub notifications for this repository

## Acknowledgments

We thank the security researchers and community members who help us improve the security of S-Q Creator Studio by responsibly disclosing vulnerabilities.
