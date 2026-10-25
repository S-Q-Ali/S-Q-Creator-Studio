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

- **Encrypted Settings:** API keys are stored encrypted using Windows DPAPI
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
