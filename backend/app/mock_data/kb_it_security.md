# Contoso — IT & Security Policy Handbook (v4.2, effective 2026-04-01)

## VPN & Remote Access
Employees working off the corporate network must connect through the Contoso GlobalProtect VPN.
- Download GlobalProtect from the Company Portal (Self Service > Networking).
- Authenticate with your Contoso SSO credentials and approve the Microsoft Authenticator push.
- Split tunneling is **disabled**; all traffic is routed through the corporate gateway.
- VPN sessions time out after 12 hours of inactivity and require re-authentication.
- For "GlobalProtect cannot connect" errors, clear the portal cache via `Settings > Clear Cache` and retry; if it persists, file a ticket with category **Network/VPN**.

## Multi-Factor Authentication (MFA)
MFA is mandatory for all Microsoft 365, VPN, and privileged systems.
- Primary method: Microsoft Authenticator push notification.
- Backup method: FIDO2 security key (issued by IT on request).
- SMS codes are **not permitted** for privileged or admin accounts.
- Lost your phone? Call the IT Service Desk at x4357 to temporarily reset MFA after identity verification.

## Password Policy
- Minimum 14 characters, passphrase style encouraged.
- Rotation is **not** required unless a compromise is suspected (aligned with NIST 800-63B).
- Never reuse Contoso passwords on external sites; the company provides 1Password Business for all staff.

## Data Classification
Four tiers: **Public, Internal, Confidential, Restricted**.
- Restricted data (customer PII, financials, source signing keys) may never be stored on personal devices or non-approved SaaS.
- Confidential data may be shared internally on a need-to-know basis only.
- All Restricted data access is logged and reviewed quarterly by the Security team.

## Acceptable Use of AI Tools
- Approved enterprise AI tools: Microsoft 365 Copilot, GitHub Copilot (Business), and Azure AI Foundry projects.
- Do **not** paste Restricted or Confidential data into consumer/public AI tools.
- Generated code must pass standard code review and security scanning before merge.

## Incident Reporting
Suspected phishing, data loss, or account compromise must be reported within **1 hour**.
- Forward suspected phishing to phish@contoso.com (auto-creates a SOC ticket).
- For active compromise, call the Security hotline x7911 immediately.
