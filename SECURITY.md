# Security Policy

SandiRaksa is a privacy and security tool: it detects and protects sensitive
data (PII) in documents before they are shared with public AI systems. Because
of that positioning, we take the security of the software itself seriously and
welcome coordinated, responsible disclosure of vulnerabilities.

## Supported Versions

Security fixes are applied to the latest released version. We recommend always
running the most recent release.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.** Public disclosure of an unpatched issue puts
all users at risk.

Instead, report privately using one of the following:

- **Email:** infosecguru.id@gmail.com (preferred)
- **GitHub private advisory:** open a draft advisory via the repository's
  **Security → Advisories → Report a vulnerability** page.

Please include as much of the following as you can:

- A clear description of the vulnerability and its impact
- The affected version(s) and operating system
- Step-by-step instructions to reproduce (proof-of-concept if available)
- Any relevant logs, screenshots, or crash output — **with sensitive data
  redacted**
- Your assessment of severity, if you have one

If your report involves example data, use synthetic/fictitious values only.
Never send real personal data.

## What to Expect

- **Acknowledgement:** we aim to acknowledge your report within 3 business days.
- **Assessment:** we will investigate and keep you informed of progress.
- **Fix and disclosure:** we will work on a fix and coordinate a disclosure
  timeline with you. We ask that you give us a reasonable window (typically up
  to 90 days) to release a fix before any public disclosure.
- **Credit:** with your permission, we are happy to credit you in the release
  notes and advisory.

## Scope

This policy covers the SandiRaksa application and its source code in this
repository. Please note:

- SandiRaksa processes documents **locally**. It does not upload document
  content or send telemetry containing document content.
- Findings that require an attacker to already have full control of the user's
  machine or OS keychain are generally considered out of scope, but we still
  welcome the report.

Thank you for helping keep SandiRaksa and its users safe.
