# Siloam Internal Windows Code Signing & App Control
# Paint-by-Numbers Production Runbook

**Document type:** Operational Runbook / Step-by-Step Implementation Guide  
**Audience:** InfoSec, PKI, Endpoint Engineering, DevSecOps, Infrastructure, SOC, Application Owners  
**Target environment:** Siloam managed Windows endpoints  
**Primary technologies:** Microsoft AD CS, Authenticode, SignTool, HSM-backed signing key, Microsoft Intune, App Control for Business  
**Document version:** 1.0  
**Date:** September 2026  
**Status:** Implementation baseline

---

# 0. What This Runbook Does

This document assumes the team starts with little or no implementation knowledge and needs a sequence that can be executed from zero to production.

The target result is:

```text
Developer code
    ↓
Controlled build
    ↓
Unsigned immutable artifact
    ↓
Security checks + approval
    ↓
Central signing service
    ↓
HSM-backed Siloam code-signing certificate
    ↓
RFC 3161 timestamp
    ↓
Signed artifact
    ↓
Signature verification + SHA-256
    ↓
Approved software repository
    ↓
Intune / ConfigMgr
    ↓
Managed Windows endpoint
    ↓
App Control for Business
    ↓
Only approved software executes
```

This runbook is deliberately conservative because the environment includes healthcare/clinical endpoints.

**Do not skip directly to App Control Enforcement.**

---

# 1. Mandatory Safety Rules

Before anyone executes the runbook, agree to the following rules.

## Rule 1 — Never enforce App Control globally on day one

Always:

```text
Lab
→ Audit
→ IT pilot
→ Audit
→ IT enforcement
→ Corporate
→ Clinical non-critical
→ Clinical critical
```

---

## Rule 2 — Production signing private key must not be exportable to developers

Production design:

```text
Signing Server / Signing Service
        ↓
HSM / HSM-backed key
```

Not:

```text
developer-laptop\company-signing.pfx
```

---

## Rule 3 — Never modify a signed binary

Correct:

```text
Build
→ add metadata/icon/version
→ package final binary
→ sign
→ verify
→ release
```

Wrong:

```text
Build
→ sign
→ change icon/version/resources
```

---

## Rule 4 — Generate the public release SHA-256 after signing

Correct:

```text
Signed file
→ Get-FileHash
→ release checksum
```

---

## Rule 5 — Clinical availability wins over rollout speed

If an App Control policy causes unexpected application, driver, boot, login, or clinical-workflow behavior:

```text
STOP ROLLOUT
→ investigate
→ remediate
→ repeat audit
```

Do not continue to the next deployment ring.

---

# 2. Reference Implementation Used by This Runbook

This runbook uses the following reference design.

## Identity / PKI

```text
Siloam Enterprise Root CA
        ↓
Siloam Enterprise Issuing CA
        ↓
Siloam Internal Software Publisher
```

If an existing enterprise PKI already exists, reuse it.

If no enterprise PKI exists, do **not** create an ad-hoc one-tier production CA. Build a proper PKI project first.

---

## Signing

Production signing is performed from a dedicated Windows signing service/server using a private key protected by an HSM or HSM-backed service.

The HSM must expose one of the following supported interfaces:

```text
Windows CNG Key Storage Provider (KSP)
or
vendor-supported code-signing API/service
```

This runbook assumes a CNG KSP-compatible HSM for command examples.

Replace:

```text
<YOUR HSM KSP NAME>
```

with the exact provider name supplied by the HSM vendor.

Examples of provider names vary by vendor. Do not invent one.

---

## Endpoint Management

```text
Microsoft Intune
```

Optional:

```text
Microsoft Configuration Manager
```

---

## Application Control

Use current Microsoft terminology:

```text
App Control for Business
```

Legacy engineering references may still call it:

```text
WDAC
```

---

# 3. Variables to Fill Before Starting

Create an implementation worksheet and populate all values below.

```text
$DOMAIN_FQDN                  = "corp.example"
$PKI_ROOT_CA_NAME             = "<existing root CA name>"
$PKI_ISSUING_CA_NAME          = "<issuing CA name>"
$PKI_ISSUING_CA_HOST          = "<issuing-ca-server-fqdn>"

$SIGNING_SERVER               = "<signing-server-fqdn>"
$SIGNING_SERVICE_ACCOUNT      = "<domain\service-account-or-gMSA>"

$SIGNING_TEMPLATE_DISPLAY     = "Siloam Internal Code Signing"
$SIGNING_TEMPLATE_NAME        = "SiloamInternalCodeSigning"

$PUBLISHER_COMMON_NAME        = "Siloam Internal Software Publisher"

$HSM_KSP_NAME                 = "<exact vendor CNG KSP name>"
$TIMESTAMP_URL                = "<approved RFC3161 TSA URL>"

$INTUNE_RING0_GROUP           = "WIN-AppControl-Ring0-Lab"
$INTUNE_RING1_GROUP           = "WIN-AppControl-Ring1-IT"
$INTUNE_RING2_GROUP           = "WIN-AppControl-Ring2-Corporate"
$INTUNE_RING3_GROUP           = "WIN-AppControl-Ring3-Clinical-NonCritical"
$INTUNE_RING4_GROUP           = "WIN-AppControl-Ring4-Clinical-Critical"

$ARTIFACT_REPOSITORY          = "<approved package/release repository>"
```

Do not proceed until the placeholders are resolved.

---

# 4. Phase 0 — Create Change Record and Owners

## Goal

No production PKI or App Control change should begin without clear ownership.

## Step 4.1 — Create project/change record

Create a formal change/project record containing:

```text
Project:
Internal Software Trust & App Control

Business Owner:
<name>

InfoSec Owner:
<name>

PKI Owner:
<name>

Endpoint/Intune Owner:
<name>

DevSecOps Owner:
<name>

SOC Owner:
<name>

Clinical IT Owner:
<name>

Rollback Owner:
<name>
```

---

## Step 4.2 — Define escalation contacts

Minimum:

```text
L1 Helpdesk
Endpoint Engineering
InfoSec
PKI
SOC
Application Owner
Clinical IT
Major Incident Manager
```

---

## Step 4.3 — Define maintenance window

Do not perform first App Control enforcement on critical endpoints outside an approved maintenance/support window.

---

## CHECKPOINT 0

Do not continue until:

```text
[ ] Project owner assigned
[ ] PKI owner assigned
[ ] Endpoint owner assigned
[ ] Clinical owner assigned
[ ] Rollback owner assigned
[ ] Emergency contact list exists
```

---

# 5. Phase 0 — Build Deployment Rings

Create device security groups in Microsoft Entra ID / the directory used by Intune.

Recommended groups:

```text
WIN-AppControl-Ring0-Lab
WIN-AppControl-Ring1-IT
WIN-AppControl-Ring2-Corporate
WIN-AppControl-Ring3-Clinical-NonCritical
WIN-AppControl-Ring4-Clinical-Critical
```

## Step 5.1 — Ring 0

Add only:

- disposable/rebuildable lab devices;
- representative Windows builds;
- representative hardware;
- test versions of important enterprise software.

Target approximately:

```text
5–20 devices
```

depending on environment size.

---

## Step 5.2 — Ring 1

Add:

```text
IT
Security
Endpoint Engineering
selected support staff
```

Do not add critical clinical devices.

---

## Step 5.3 — Ring 2

Add standard corporate users/devices.

---

## Step 5.4 — Ring 3

Add clinical but non-critical devices only after Ring 2 is stable.

---

## Step 5.5 — Ring 4

Critical clinical endpoints are last.

Examples may include workstations directly involved in:

- patient care;
- clinical imaging;
- medication workflows;
- medical-device integration;
- critical admission/discharge workflows.

Device classification must be confirmed with Clinical IT and the application owner.

---

## CHECKPOINT 1

```text
[ ] All five groups created
[ ] Ring 0 populated
[ ] Ring 1 populated
[ ] Rings 2–4 defined but NOT targeted by enforcement
```

---

# 6. Phase 0 — Inventory Existing Applications

## Goal

Know what actually runs before allowlisting.

Do not rely only on a CMDB.

Use actual endpoint telemetry.

---

## Step 6.1 — Collect inventory sources

Use as many of the following as available:

```text
Microsoft Defender for Endpoint
Intune Discovered Apps
Configuration Manager inventory
EDR process telemetry
software asset management
AppLocker/App Control audit logs
application-owner inventory
```

---

## Step 6.2 — Create master inventory

Minimum columns:

```text
DeviceGroup
ApplicationName
ExecutableName
Path
Version
Publisher
SignatureStatus
SignerSubject
SignerThumbprint
InstallSource
UpdateMechanism
RunsAsAdmin
Service
DriverDependency
ScriptDependency
BusinessOwner
TechnicalOwner
ClinicalCriticality
VendorSupportStatus
AppControlRuleStrategy
Notes
```

---

## Step 6.3 — Run signature inventory sample

On representative Windows endpoints:

```powershell
$roots = @(
    "C:\Program Files",
    "C:\Program Files (x86)"
)

$results = foreach ($root in $roots) {
    if (Test-Path $root) {
        Get-ChildItem $root -Filter *.exe -Recurse -ErrorAction SilentlyContinue |
            ForEach-Object {
                $sig = Get-AuthenticodeSignature $_.FullName

                [PSCustomObject]@{
                    Path       = $_.FullName
                    Status     = $sig.Status
                    Signer     = $sig.SignerCertificate.Subject
                    Thumbprint = $sig.SignerCertificate.Thumbprint
                }
            }
    }
}

$results |
    Export-Csv C:\Temp\Executable-Signature-Inventory.csv -NoTypeInformation
```

Run against representative Ring 0 systems, not blindly against every endpoint without testing performance.

---

## Step 6.4 — Classify each application

Use:

```text
A = Critical clinical
B = Clinical non-critical
C = Corporate critical
D = Corporate standard
E = IT/Security/Admin
F = Unknown/Legacy
```

---

## Step 6.5 — Choose trust strategy per application

Use this order:

```text
1. Microsoft/Windows trusted component
2. Stable vendor publisher rule
3. Siloam internal publisher rule
4. Managed Installer
5. narrow file attribute/path rule
6. hash exception
```

Avoid hash rules for frequently updated applications.

---

## STOP CONDITION

If critical clinical applications have:

```text
unknown executable dependencies
unknown updater behavior
unknown driver dependencies
no application owner
```

do not plan enforcement for those endpoints yet.

---

# 7. Phase 1 — Assess Existing PKI

## Step 7.1 — Identify CA servers

From an administrative workstation:

```powershell
certutil -config - -ping
```

You can also inspect Active Directory PKI objects:

```powershell
certutil -ADCA
```

Record all discovered CAs.

---

## Step 7.2 — Open Certification Authority console

On a PKI administration workstation/server:

```text
Start
→ Run
→ certsrv.msc
```

Confirm:

```text
Root CA
Issuing CA
Enterprise CA status
CRL configuration
certificate templates
```

---

## Step 7.3 — Confirm enterprise template support

Certificate templates require an Enterprise CA.

Open:

```text
certtmpl.msc
```

or:

```text
Certification Authority
→ Certificate Templates
→ Manage
```

---

## Decision

If a mature enterprise issuing CA exists:

```text
PROCEED
```

If only an unmanaged single-tier CA exists:

```text
STOP
→ PKI architecture review
```

If no PKI exists:

```text
STOP
→ build enterprise PKI project first
```

Do not create a production CA inside this App Control change merely for convenience.

---

# 8. Phase 1 — Prepare the HSM / Signing Server

## Goal

The production private key must not be generated in software and exported around the environment.

---

## Step 8.1 — Provision dedicated signing server

Recommended baseline:

```text
Windows Server 2022 or 2025
Domain joined if required by enterprise design
Fully patched
Defender/EDR onboarded
No general-purpose user workloads
No email/browser use
Restricted administrative group
Restricted inbound firewall
Restricted outbound firewall
Central logging enabled
```

Name example:

```text
SRV-CODESIGN-01
```

---

## Step 8.2 — Restrict interactive logon

Use GPO/security policy so only designated signing administrators can log on interactively.

CI identities should access the signing function through the chosen automation mechanism, not through RDP sessions.

---

## Step 8.3 — Install HSM client/KSP

Follow the **HSM vendor's official installation guide**.

Required result:

```text
Windows can see the HSM-backed CNG KSP
```

List CNG providers:

```powershell
certutil -csplist
```

Confirm the exact provider appears.

Record:

```text
Provider name:
<EXACT NAME>
```

This becomes:

```text
$HSM_KSP_NAME
```

---

## Step 8.4 — Confirm HSM connectivity

Use the HSM vendor's diagnostic utility.

Required:

```text
[ ] HSM reachable
[ ] signing server authenticated
[ ] HSM partition/tenant configured
[ ] production signing role created
[ ] auditing enabled
```

---

## Step 8.5 — Do NOT generate production key yet

First create the certificate template and permissions.

---

# 9. Phase 1 — Create AD CS Code Signing Certificate Template

Microsoft provides a default **Code Signing** template that can be duplicated.

## Step 9.1 — Open Certificate Templates

On the issuing CA:

```text
Server Manager
→ Tools
→ Certification Authority
```

Then:

```text
Issuing CA
→ Certificate Templates
→ right click
→ Manage
```

---

## Step 9.2 — Duplicate Code Signing template

In Certificate Templates Console:

```text
Code Signing
→ right click
→ Duplicate Template
```

---

## Step 9.3 — Compatibility tab

Choose values compatible with the environment.

For a modern Windows estate:

```text
Certification Authority:
Windows Server 2016 or later supported selection

Certificate recipient:
Windows 10 / Windows Server 2016 or later supported selection
```

Do not choose newer settings if unsupported legacy systems still need the certificate.

---

## Step 9.4 — General tab

Set:

```text
Template display name:
Siloam Internal Code Signing

Template name:
SiloamInternalCodeSigning

Validity period:
1 year

Renewal period:
6 weeks
```

Validity may be adjusted to enterprise PKI policy.

Do not make it excessively long.

---

## Step 9.5 — Request Handling tab

Set:

```text
Purpose:
Signature

Allow private key to be exported:
UNCHECKED
```

Production certificate private key must not be exportable.

If the HSM vendor explicitly requires a different enrollment flow, follow the vendor's documented HSM integration.

---

## Step 9.6 — Cryptography tab

Recommended:

```text
Provider Category:
Key Storage Provider

Algorithm:
RSA

Minimum key size:
3072
```

If the enterprise compatibility baseline requires RSA 2048, document the reason.

For App Control policy signing compatibility, Microsoft documents RSA 2K/3K/4K; do not use ECDSA for signed App Control policies.

Select the HSM KSP if the template supports provider restriction:

```text
Requests must use one of the following providers:
<YOUR HSM KSP NAME>
```

If the certificate template cannot directly restrict to the vendor KSP, enforce the HSM provider in the CSR/enrollment procedure and signing service configuration.

---

## Step 9.7 — Extensions tab

Confirm:

```text
Application Policies
→ Code Signing
```

Expected EKU OID:

```text
1.3.6.1.5.5.7.3.3
```

Remove unrelated application-policy EKUs.

---

## Step 9.8 — Subject Name tab

Recommended for a controlled central publisher:

```text
Supply in the request
```

This allows the request to use:

```text
CN=Siloam Internal Software Publisher
```

Because "Supply in the request" is sensitive, restrict Enroll permissions tightly.

Do not grant broad enrollment.

---

## Step 9.9 — Issuance Requirements

Recommended:

```text
CA certificate manager approval:
Enabled
```

This introduces approval before the certificate is issued.

If an enterprise certificate workflow already provides equivalent approval, align with existing policy.

---

## Step 9.10 — Security tab

Remove unnecessary enrollment permissions.

Create an AD security group such as:

```text
PKI-CodeSigning-Enrollers
```

Grant:

```text
Read
Enroll
```

only to the identity authorized to request the production certificate.

Do **not** grant Enroll to:

```text
Domain Users
Authenticated Users
all developers
```

unless specifically required.

---

## Step 9.11 — Save

Click:

```text
Apply
→ OK
```

---

# 10. Phase 1 — Publish the Template on the Issuing CA

On:

```text
certsrv.msc
```

Navigate:

```text
Issuing CA
→ Certificate Templates
→ right click
→ New
→ Certificate Template to Issue
```

Select:

```text
Siloam Internal Code Signing
```

Click:

```text
OK
```

---

## Verification

Run:

```powershell
certutil -CATemplates
```

Confirm:

```text
SiloamInternalCodeSigning
```

is listed.

---

# 11. Phase 1 — Generate HSM-Backed CSR

This section assumes the HSM exposes a CNG Key Storage Provider.

Create:

```text
C:\CodeSigning\request.inf
```

Example:

```ini
[Version]
Signature="$Windows NT$"

[NewRequest]
Subject = "CN=Siloam Internal Software Publisher"
MachineKeySet = TRUE
Exportable = FALSE
KeyLength = 3072
KeySpec = 2
KeyUsage = 0x80
RequestType = PKCS10
ProviderName = "<YOUR HSM KSP NAME>"
ProviderType = 0
HashAlgorithm = sha256

[EnhancedKeyUsageExtension]
OID=1.3.6.1.5.5.7.3.3

[RequestAttributes]
CertificateTemplate = SiloamInternalCodeSigning
```

**Replace `<YOUR HSM KSP NAME>` exactly.**

---

## Step 11.1 — Generate request

Open elevated PowerShell/Command Prompt:

```cmd
mkdir C:\CodeSigning
cd /d C:\CodeSigning
certreq -new request.inf Siloam-CodeSigning.req
```

Expected:

```text
Siloam-CodeSigning.req
```

The private key should be created/protected by the HSM provider.

---

## Step 11.2 — Verify key presence with HSM

Use vendor tools to confirm:

```text
key exists in HSM
key is non-exportable
correct key size
correct partition/tenant
```

---

## STOP CONDITION

If Windows created the private key under:

```text
Microsoft Software Key Storage Provider
```

instead of the HSM, stop.

Do not use that certificate as production signing identity.

---

# 12. Phase 1 — Submit CSR to Issuing CA

Run:

```cmd
certreq -submit -config "<ISSUING-CA-FQDN>\<CA-CONFIG-NAME>" Siloam-CodeSigning.req Siloam-CodeSigning.cer
```

If unsure of CA config string:

```cmd
certutil -config - -ping
```

Choose the enterprise issuing CA.

---

## If manager approval is enabled

On CA:

```text
Certification Authority
→ Pending Requests
```

Locate the request.

Verify:

```text
Requester
Template
Subject
Key parameters
```

Then:

```text
right click
→ All Tasks
→ Issue
```

Return to signing server and retrieve/complete issuance if necessary.

---

# 13. Phase 1 — Accept Certificate on Signing Server

Run:

```cmd
certreq -accept Siloam-CodeSigning.cer
```

Because the CSR was created as a machine-key request:

```text
certlm.msc
```

Check:

```text
Certificates (Local Computer)
→ Personal
→ Certificates
```

Find:

```text
Siloam Internal Software Publisher
```

---

# 14. Phase 1 — Verify Certificate Properties

Run PowerShell:

```powershell
$cert = Get-ChildItem Cert:\LocalMachine\My |
    Where-Object Subject -eq "CN=Siloam Internal Software Publisher" |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1

$cert | Format-List `
    Subject,
    Issuer,
    Thumbprint,
    NotBefore,
    NotAfter,
    HasPrivateKey,
    EnhancedKeyUsageList
```

Required:

```text
HasPrivateKey = True

EKU contains:
Code Signing
1.3.6.1.5.5.7.3.3
```

Record:

```text
Production signer thumbprint:
<THUMBPRINT>
```

---

## Verify chain

```cmd
certutil -verify Siloam-CodeSigning.cer
```

Do not proceed on chain errors.

---

# 15. Phase 1 — Export PUBLIC Certificates Only

We need public certificates for endpoint trust distribution.

## Root CA

Export:

```text
Siloam-Root-CA.cer
```

## Intermediate/Issuing CA

Export:

```text
Siloam-Issuing-CA.cer
```

## Publisher leaf public certificate

Export:

```text
Siloam-CodeSigning-Publisher.cer
```

Do **not** export the private key.

Example PowerShell:

```powershell
Export-Certificate `
    -Cert $cert `
    -FilePath C:\CodeSigning\Siloam-CodeSigning-Publisher.cer
```

---

# 16. Phase 1 — Select and Test RFC 3161 Timestamp Authority

The TSA must be an explicit architectural dependency.

Fill:

```text
TSA owner:
TSA URL:
Network owner:
Availability requirement:
Proxy requirement:
```

Example variable:

```powershell
$TimestampUrl = "https://<approved-rfc3161-tsa>"
```

---

## Step 16.1 — Test network access

From signing server:

```powershell
Test-NetConnection <tsa-hostname> -Port 443
```

If proxy is required, configure the signing service according to security policy.

---

## STOP CONDITION

Do not remove timestamping just because the signing server cannot reach the TSA.

Fix the architecture/network path.

---

# 17. Phase 1 — Install Windows SDK SignTool

Install a supported Windows SDK / signing toolset on the signing server.

Locate:

```text
signtool.exe
```

Common SDK locations are under:

```text
C:\Program Files (x86)\Windows Kits\
```

Verify:

```powershell
Get-Command signtool.exe
```

If not in `PATH`, define the absolute path in signing automation.

---

# 18. Phase 1 — Manual Signing Smoke Test

Before CI/CD, prove the cryptographic path manually.

Create or copy a harmless internal test executable:

```text
C:\CodeSigning\Test\TestApp.exe
```

Do not use a production app for first test.

---

## Step 18.1 — Capture unsigned hash

```powershell
Get-FileHash `
    C:\CodeSigning\Test\TestApp.exe `
    -Algorithm SHA256
```

Record it.

---

## Step 18.2 — Confirm unsigned state

```powershell
Get-AuthenticodeSignature `
    C:\CodeSigning\Test\TestApp.exe |
    Format-List *
```

Expected before signing:

```text
Status = NotSigned
```

---

## Step 18.3 — Sign

Set:

```powershell
$Thumbprint = "<PRODUCTION-SIGNER-THUMBPRINT>"
$TSA        = "https://<approved-rfc3161-tsa>"
$File       = "C:\CodeSigning\Test\TestApp.exe"
```

Run:

```powershell
signtool sign `
    /sha1 $Thumbprint `
    /sm `
    /fd SHA256 `
    /tr $TSA `
    /td SHA256 `
    $File
```

`/sm` tells SignTool to use the machine certificate store.

If your HSM provider requires vendor-specific SignTool parameters, follow the vendor's instructions.

---

## Step 18.4 — Verify

```powershell
signtool verify /pa /v $File
```

Then:

```powershell
$sig = Get-AuthenticodeSignature $File

$sig | Format-List `
    Status,
    StatusMessage,
    SignerCertificate,
    TimeStamperCertificate
```

Required:

```text
Status = Valid
SignerCertificate = Siloam Internal Software Publisher
TimeStamperCertificate = populated/valid
```

---

## Step 18.5 — Capture signed hash

```powershell
Get-FileHash $File -Algorithm SHA256
```

It must differ from the unsigned hash.

---

## CHECKPOINT 2 — Cryptographic Path

Do not continue until:

```text
[ ] HSM key exists
[ ] key is non-exportable
[ ] certificate chain is valid
[ ] Code Signing EKU present
[ ] SignTool signing succeeds
[ ] RFC3161 timestamp succeeds
[ ] Get-AuthenticodeSignature = Valid
```

---

# 19. Phase 1 — Create Production Signing Script

Create on signing server:

```text
C:\CodeSigning\Scripts\Invoke-SiloamCodeSigning.ps1
```

Example:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path $_ -PathType Leaf })]
    [string]$FilePath,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedUnsignedSha256,

    [Parameter(Mandatory = $true)]
    [string]$ChangeId
)

$ErrorActionPreference = "Stop"

$SignerThumbprint = "<PRODUCTION-SIGNER-THUMBPRINT>"
$TimestampUrl     = "https://<approved-rfc3161-tsa>"
$SignTool         = "<ABSOLUTE-PATH-TO-SIGNTOOL.EXE>"

# 1. Verify input hash
$unsignedHash = (Get-FileHash $FilePath -Algorithm SHA256).Hash.ToUpper()

if ($unsignedHash -ne $ExpectedUnsignedSha256.ToUpper()) {
    throw "Unsigned SHA256 mismatch. Signing aborted."
}

# 2. Confirm input is not already signed unexpectedly
$preSig = Get-AuthenticodeSignature $FilePath

if ($preSig.Status -eq "Valid") {
    throw "Input artifact is already signed. Review required."
}

# 3. Sign
& $SignTool sign `
    /sha1 $SignerThumbprint `
    /sm `
    /fd SHA256 `
    /tr $TimestampUrl `
    /td SHA256 `
    $FilePath

if ($LASTEXITCODE -ne 0) {
    throw "SignTool failed."
}

# 4. Verify
& $SignTool verify /pa /v $FilePath

if ($LASTEXITCODE -ne 0) {
    throw "SignTool verification failed."
}

$sig = Get-AuthenticodeSignature $FilePath

if ($sig.Status -ne "Valid") {
    throw "Authenticode validation failed: $($sig.Status)"
}

if ($sig.SignerCertificate.Thumbprint -ne $SignerThumbprint) {
    throw "Unexpected signer certificate."
}

if (-not $sig.TimeStamperCertificate) {
    throw "Timestamp certificate missing."
}

# 5. Generate final hash
$signedHash = (Get-FileHash $FilePath -Algorithm SHA256).Hash.ToUpper()

# 6. Emit signing record
$result = [PSCustomObject]@{
    ChangeId          = $ChangeId
    File              = (Resolve-Path $FilePath).Path
    UnsignedSHA256    = $unsignedHash
    SignedSHA256      = $signedHash
    SignerSubject     = $sig.SignerCertificate.Subject
    SignerThumbprint  = $sig.SignerCertificate.Thumbprint
    CertificateExpiry = $sig.SignerCertificate.NotAfter
    TimestampSubject  = $sig.TimeStamperCertificate.Subject
    SigningTimeUTC    = (Get-Date).ToUniversalTime().ToString("o")
    Verification      = "Valid"
}

$result | ConvertTo-Json -Depth 3
```

---

# 20. Phase 1 — Lock Down Signing Script and Directory

Use NTFS ACLs.

Example conceptual access:

```text
SYSTEM                       Full Control
PKI/Signing Administrators   Full Control
Signing Service Identity     Read/Execute + required signing operation
Developers                    NO access to private key
```

Inspect ACL:

```powershell
Get-Acl C:\CodeSigning | Format-List
```

Do not grant `Everyone` write permission.

---

# 21. Phase 1 — Configure Central Audit Logging

Send at minimum:

```text
Windows Security logs
signing service logs
HSM audit logs
certificate issuance logs
CI/CD release logs
```

to the SIEM.

Each signing record should contain:

```text
request ID
change ID
application
version
repository
commit
build ID
unsigned SHA256
signed SHA256
signer thumbprint
timestamp
requesting identity
approver
result
```

---

# 22. Phase 1 — Intune Deploy Root Certificate

Microsoft Intune Trusted Certificate Profile supports root/intermediate CA trust.

Do not use it as the mechanism for arbitrary leaf publisher certificates.

---

## Step 22.1 — Prepare `.cer`

Use:

```text
Siloam-Root-CA.cer
```

DER-encoded or supported public certificate format.

No private key.

---

## Step 22.2 — Intune portal

Open:

```text
Microsoft Intune admin center
→ Devices
→ Manage devices
→ Configuration
→ Create
```

Choose:

```text
Platform:
Windows 10 and later / Windows

Profile:
Templates
→ Trusted certificate
```

Microsoft UI names can vary slightly by tenant updates; select the **Trusted certificate** profile.

---

## Step 22.3 — Basics

Name:

```text
PKI - Siloam Root CA - Windows
```

Description:

```text
Deploys Siloam Enterprise Root CA trust to managed Windows devices.
```

---

## Step 22.4 — Configuration

Upload:

```text
Siloam-Root-CA.cer
```

Destination:

```text
Computer certificate store - Root
```

---

## Step 22.5 — Assignment

First assign only:

```text
WIN-AppControl-Ring0-Lab
```

Do not assign All Devices first.

---

## Step 22.6 — Create

Review:

```text
Create
```

---

## Step 22.7 — Sync test endpoint

On Windows test endpoint:

```text
Settings
→ Accounts
→ Access work or school
→ <connected account>
→ Info
→ Sync
```

or wait for normal MDM sync.

---

## Step 22.8 — Verify

On Ring 0 device:

```powershell
Get-ChildItem Cert:\LocalMachine\Root |
    Where-Object Subject -Like "*Siloam*"
```

Verify exact thumbprint.

---

# 23. Phase 1 — Intune Deploy Intermediate/Issuing CA

Repeat the previous process.

Profile:

```text
PKI - Siloam Issuing CA - Windows
```

Destination:

```text
Computer certificate store - Intermediate
```

Assign:

```text
WIN-AppControl-Ring0-Lab
```

Verify:

```powershell
Get-ChildItem Cert:\LocalMachine\CA |
    Where-Object Subject -Like "*Siloam*"
```

---

# 24. Phase 1 — Decide Whether TrustedPublisher Leaf Deployment Is Required

Do not automatically put every leaf certificate into Trusted Publishers.

First test the actual Windows behavior and policy requirement.

If explicit Trusted Publisher trust is required, continue.

Store:

```text
Cert:\LocalMachine\TrustedPublisher
```

Because Intune Trusted Certificate Profile is for root/intermediate certificates, deploy the leaf with a controlled script/Win32 package.

---

# 25. Phase 1 — Package Publisher Certificate for Intune

Create folder:

```text
SiloamPublisherCert\
├── Siloam-CodeSigning-Publisher.cer
├── Install-PublisherCert.ps1
└── Detect-PublisherCert.ps1
```

---

## Install-PublisherCert.ps1

```powershell
$ErrorActionPreference = "Stop"

$CerFile = Join-Path $PSScriptRoot "Siloam-CodeSigning-Publisher.cer"
$ExpectedThumbprint = "<PUBLISHER-CERT-THUMBPRINT>".Replace(" ","").ToUpper()

if (-not (Test-Path $CerFile)) {
    throw "Publisher certificate not found."
}

$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CerFile)

if ($cert.Thumbprint.ToUpper() -ne $ExpectedThumbprint) {
    throw "Certificate thumbprint mismatch."
}

$store = New-Object System.Security.Cryptography.X509Certificates.X509Store(
    "TrustedPublisher",
    "LocalMachine"
)

try {
    $store.Open(
        [System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite
    )

    $existing = $store.Certificates |
        Where-Object Thumbprint -eq $ExpectedThumbprint

    if (-not $existing) {
        $store.Add($cert)
        Write-Output "Installed publisher certificate."
    }
    else {
        Write-Output "Publisher certificate already installed."
    }
}
finally {
    $store.Close()
}
```

---

## Detect-PublisherCert.ps1

```powershell
$ExpectedThumbprint = "<PUBLISHER-CERT-THUMBPRINT>".Replace(" ","").ToUpper()

$found = Get-ChildItem Cert:\LocalMachine\TrustedPublisher |
    Where-Object Thumbprint -eq $ExpectedThumbprint

if ($found) {
    Write-Output "Installed"
    exit 0
}

Write-Output "Missing"
exit 1
```

---

# 26. Phase 1 — Deploy Publisher Certificate to Ring 0

Preferred implementation:

```text
Intune Win32 app
or
Intune Remediations
```

If using a PowerShell script, configure:

```text
Run this script using logged-on credentials:
No

Run script in 64-bit PowerShell:
Yes

Enforce script signature check:
according to current script-management policy
```

The script must run as:

```text
SYSTEM
```

to modify LocalMachine stores.

---

## Verify

```powershell
Get-ChildItem Cert:\LocalMachine\TrustedPublisher |
    Where-Object Thumbprint -eq "<THUMBPRINT>"
```

---

# 27. Phase 1 — Validate Signed Internal Application on Ring 0

Copy/install signed test app.

Run:

```powershell
Get-AuthenticodeSignature C:\Path\TestApp.exe |
    Format-List Status,StatusMessage,SignerCertificate,TimeStamperCertificate
```

Expected:

```text
Status = Valid
```

Open:

```text
File Explorer
→ right click EXE
→ Properties
→ Digital Signatures
```

Expected signer:

```text
Siloam Internal Software Publisher
```

---

## CHECKPOINT 3 — Publisher Trust

```text
[ ] Root CA present
[ ] Issuing CA present
[ ] Publisher leaf present if required
[ ] signed test EXE validates
[ ] no Unknown Publisher for tested workflow
```

---

# 28. Phase 2 — Define CI/CD Contract

The build system does **not** receive the private key.

CI produces:

```text
artifact
unsigned SHA-256
commit SHA
build ID
application/version metadata
change/release ID
```

Signing service returns:

```text
signed artifact
signed SHA-256
signature verification result
signing audit record
```

---

# 29. Phase 2 — Build Immutable Artifact

Example GitHub Actions conceptual build job:

```yaml
jobs:
  build:
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v4

      - name: Build
        shell: powershell
        run: |
          # Replace with actual build commands
          .\build.ps1

      - name: Hash unsigned artifact
        shell: powershell
        run: |
          $hash = (Get-FileHash ".\dist\App.exe" -Algorithm SHA256).Hash
          "UNSIGNED_SHA256=$hash" >> $env:GITHUB_ENV

      - name: Upload unsigned artifact
        uses: actions/upload-artifact@v4
        with:
          name: unsigned-release
          path: dist\App.exe
```

Production should consider pinning third-party GitHub Actions to reviewed commit SHAs.

---

# 30. Phase 2 — Implement Signing Service Boundary

Do not simply map an SMB share and allow everyone to execute SignTool remotely.

Minimum service requirements:

```text
Authenticated request
authorized repository
authorized branch/tag
expected artifact hash
change/release ID
approval status
audit log
rate limiting / abuse control
file-type restrictions
signer policy
```

The exact API implementation depends on enterprise tooling.

---

# 31. Phase 2 — Signing Request Validation

Before signing, the service must validate:

```text
[ ] request identity authorized
[ ] artifact hash matches build output
[ ] artifact type allowed
[ ] release/change ID valid
[ ] required approval exists
[ ] repository/project allowed
[ ] binary not already signed unexpectedly
[ ] malware/security gates passed
```

If any fail:

```text
DENY SIGNING
```

---

# 32. Phase 2 — Recommended CI/CD Sequence

```text
1. Checkout exact commit
2. Build
3. Unit/integration tests
4. SAST
5. dependency scan
6. secret scan
7. optional malware scan
8. finalize metadata/resources
9. produce unsigned artifact
10. hash artifact
11. upload immutable artifact
12. release approval
13. request signing
14. signing service verifies hash
15. HSM signs
16. TSA timestamps
17. verify Authenticode
18. generate signed SHA256
19. upload approved release
20. distribute with Intune/ConfigMgr
```

---

# 33. Phase 2 — Sign Nested Artifacts Correctly

For an application with installer:

```text
App.exe unsigned
    ↓
SIGN App.exe
    ↓
App.exe signed
    ↓
Build Installer.msi / Setup.exe
    ↓
SIGN installer
    ↓
Release
```

Sign the executable **before** packaging it into the installer.

Then sign the final installer/package where applicable.

---

# 34. Phase 2 — Release Manifest

Generate a JSON manifest:

```json
{
  "application": "ExampleApp",
  "version": "1.2.3",
  "repository": "org/repository",
  "commit": "abcdef123456",
  "build_id": "12345",
  "change_id": "CHG000000",
  "unsigned_sha256": "....",
  "signed_sha256": "....",
  "signer_subject": "CN=Siloam Internal Software Publisher",
  "signer_thumbprint": "....",
  "timestamp_utc": "2026-09-10T00:00:00Z",
  "verification": "Valid"
}
```

Store it beside the approved release.

---

# 35. Phase 2 — Production Release Repository

Create a clear state separation:

```text
/staging/unsigned
/release/signed
```

Only:

```text
/release/signed
```

may feed Intune/ConfigMgr production packages.

---

# 36. Phase 2 — Add Release Approval

Recommended:

```text
Developer:
can build

Release Manager:
can approve

Signing service:
can sign approved artifact

Endpoint team:
can deploy signed artifact
```

Avoid one identity controlling build + signing key + deployment without review.

---

# 37. Phase 2 — Validate First Real Application

Choose a low-risk internal app.

Perform:

```text
build
→ scan
→ sign
→ timestamp
→ verify
→ package
→ sign package
→ deploy Ring 0
```

On the endpoint verify:

```powershell
Get-AuthenticodeSignature "C:\Program Files\<App>\<App>.exe"
```

---

## CHECKPOINT 4 — Automated Signing

```text
[ ] CI cannot export signing key
[ ] artifact hash bound to signing request
[ ] signing audited
[ ] timestamp verified
[ ] final signature verified automatically
[ ] signed artifact repository operational
[ ] Ring 0 deployment successful
```

---

# 38. Phase 3 — Pre-App-Control Health Check

Before enabling Managed Installer or App Control, check existing AppLocker policy.

Run:

```powershell
Get-AppLockerPolicy -Effective -Xml > C:\Temp\Effective-AppLocker.xml
```

Review:

```text
RuleCollection
EnforcementMode
EXE
DLL
MSI
Script
```

---

## Critical warning

Microsoft documents that enabling Intune Managed Installer introduces AppLocker configuration.

If existing AppLocker policy contains problematic empty `NotConfigured` rule collections, policy merging can create unexpected blocking and potentially serious endpoint behavior.

Do not enable Managed Installer until existing AppLocker posture is reviewed.

---

# 39. Phase 3 — Enable Intune Managed Installer on Ring 0

In Intune:

```text
Endpoint security
→ App Control for Business
→ Managed installer
→ Create
```

---

## Basics

Name:

```text
AppControl - Managed Installer - Ring0
```

Description:

```text
Enables Intune Management Extension as Managed Installer for Ring 0.
```

---

## Settings

Set:

```text
Enable Intune Managed Extension as Managed Installer
= Enabled
```

---

## Assignment

Assign only:

```text
WIN-AppControl-Ring0-Lab
```

---

## Create

Click:

```text
Review + create
→ Create
```

---

## Important

Managed Installer tagging is **not retroactive**.

Applications installed before Managed Installer activation may not receive the trusted origin tag.

Plan to:

```text
explicitly allow them
or
reinstall them through Intune where practical
```

---

# 40. Phase 3 — Verify Managed Installer Policy Delivery

In Intune:

```text
Endpoint security
→ App Control for Business
→ Managed installer
→ AppControl - Managed Installer - Ring0
```

Check device status.

On endpoint, sync Intune.

Install a harmless Win32 test application through Intune **after** Managed Installer is enabled.

---

# 41. Phase 3 — Create App Control Audit Base Policy

For first implementation, use Intune **Built-in controls** before jumping to a highly customized XML base policy.

In Intune:

```text
Endpoint security
→ App Control for Business
→ App Control for Business
→ Create Policy
```

---

## Step 41.1 — Basics

Name:

```text
AppControl - Base - Ring0 - AUDIT
```

Description:

```text
Ring 0 App Control audit policy. No enforcement.
```

---

## Step 41.2 — Configuration settings

Choose:

```text
Configuration settings format:
Built-in controls
```

Set:

```text
Enable trust of Windows components and store apps:
Audit only
```

Additional option:

```text
Trust apps from managed installers:
Enabled
```

For initial strict-enterprise design, do **not** automatically enable:

```text
Trust apps with a good reputation
```

unless InfoSec explicitly decides to use Microsoft Intelligent Security Graph reputation as part of trust strategy.

---

## Step 41.3 — Assign

Assign only:

```text
WIN-AppControl-Ring0-Lab
```

---

## Step 41.4 — Create

```text
Review + create
→ Create
```

---

# 42. Phase 3 — Verify Audit Mode

On Ring 0 endpoint open:

```text
Event Viewer
→ Applications and Services Logs
→ Microsoft
→ Windows
→ CodeIntegrity
→ Operational
```

Also inspect:

```text
Applications and Services Logs
→ Microsoft
→ Windows
→ AppLocker
→ MSI and Script
```

Audit mode should log code that would be blocked while allowing it to execute.

---

# 43. Phase 3 — Collect Audit Events Centrally

Preferred:

```text
Microsoft Defender for Endpoint Advanced Hunting
```

or:

```text
Windows Event Forwarding
SIEM agent
Log Analytics architecture
```

Do not rely on manually opening Event Viewer on hundreds of devices.

---

# 44. Phase 3 — Managed Installer Origin Events

Microsoft documents App Control origin events including:

```text
3090
3091
3092
```

and Defender Advanced Hunting action types such as:

```text
AppControlCodeIntegrityOriginAllowed
AppControlCodeIntegrityOriginAudited
AppControlCodeIntegrityOriginBlocked
```

Use these to validate Managed Installer / trust-origin behavior.

---

# 45. Phase 3 — Run Ring 0 Audit Workload

During audit, intentionally exercise:

```text
boot
user login
VPN
browser
Office
security tools
IT tools
internal apps
Intune deployments
software updates
printers
scanners
peripherals
PowerShell automation
scheduled tasks
services
reboots
patching
```

Ring 0 should simulate normal work, not merely sit idle.

---

# 46. Phase 3 — Build Block Candidate Report

Create a report containing:

```text
File
Path
Publisher
Signer
Hash
Device
User
Process
Event ID
Application owner
Expected?
Rule required?
Rule type
```

Classify each event:

```text
ALLOW
BLOCK
INVESTIGATE
```

---

# 47. Phase 3 — Do Not Allow Everything Seen in Audit

Audit telemetry contains both legitimate and potentially unwanted software.

Do not convert all audit events into allow rules automatically.

For each item ask:

```text
Is it business-required?
Is it trusted?
Is publisher stable?
Can it be deployed via Managed Installer?
Is it legacy?
Is it malicious/PUP?
```

---

# 48. Phase 3 — Create Supplemental Policy for Required Apps

If built-in policy does not allow required enterprise applications, create a supplemental App Control XML policy.

Recommended use:

```text
Siloam internal publisher
approved third-party publishers
legacy exceptions
clinical-specific apps
```

Microsoft supports multiple supplemental policies attached to a base policy.

---

# 49. Phase 3 — Create Publisher Rules

Use the App Control Wizard / WDAC Wizard or PowerShell tooling on a controlled policy-authoring workstation.

Preferred rule scope for internal applications:

```text
Publisher / signer-based
```

rather than per-file hashes.

Example logic:

```text
Allow:
Siloam Internal Software Publisher
```

Scope carefully to avoid allowing unrelated code signed by overly broad certificates.

---

# 50. Phase 3 — Supplemental Policy Naming

Use clear names:

```text
AppControl-Supplemental-SiloamInternalApps.xml
AppControl-Supplemental-CorporateApps.xml
AppControl-Supplemental-ClinicalApps.xml
AppControl-Supplemental-ITTools.xml
AppControl-Supplemental-LegacyExceptions.xml
```

Version-control these policies.

---

# 51. Phase 3 — Upload Supplemental Policy to Intune

In Intune:

```text
Endpoint security
→ App Control for Business
→ Create Policy
```

Set:

```text
Configuration settings format:
Enter XML data
```

Upload supplemental XML.

Assign to same Ring 0 group as the corresponding base policy.

---

# 52. Phase 3 — Repeat Audit

After each significant policy change:

```text
deploy in audit
→ collect events
→ analyze
→ fix rules
→ repeat
```

Microsoft recommends auditing App Control policy changes before enforcement.

---

# 53. Phase 3 — Ring 0 Enforcement Go/No-Go

Do not enforce until:

```text
[ ] No known boot component would be blocked
[ ] No required driver would be blocked
[ ] No EDR/security component would be blocked
[ ] No required internal app would be blocked
[ ] No required updater would be blocked
[ ] rollback procedure tested
[ ] emergency supplemental policy tested
[ ] SOC receives events
```

---

# 54. Phase 3 — Create Enforced Policy

For XML-authored policies, enforcement is controlled by App Control rule options.

Microsoft documents Audit Mode as option 3.

To convert a policy copy from audit to enforcement:

```powershell
Copy-Item `
    .\Siloam-Base-Audit.xml `
    .\Siloam-Base-Enforced.xml

Set-RuleOption `
    -FilePath .\Siloam-Base-Enforced.xml `
    -Option 3 `
    -Delete
```

For the **first enforced deployment ring**, Microsoft recommends considering:

```text
Option 9  = Advanced Boot Options Menu
Option 10 = Boot Audit on Failure
```

Commands:

```powershell
Set-RuleOption `
    -FilePath .\Siloam-Base-Enforced.xml `
    -Option 9

Set-RuleOption `
    -FilePath .\Siloam-Base-Enforced.xml `
    -Option 10
```

These should be reviewed and potentially removed after pilot stabilization.

---

# 55. Phase 3 — Convert XML to Binary Policy if Required

Example:

```powershell
ConvertFrom-CIPolicy `
    .\Siloam-Base-Enforced.xml `
    .\Siloam-Base-Enforced.cip
```

Whether XML or binary deployment is used depends on the chosen Intune/App Control deployment pattern.

For an Intune custom XML policy, upload the appropriate XML according to Intune's current App Control workflow.

---

# 56. Phase 3 — First Enforcement: Ring 0 Only

Create a separate Intune policy:

```text
AppControl - Base - Ring0 - ENFORCED
```

Assign:

```text
WIN-AppControl-Ring0-Lab
```

Do not target Rings 1–4.

---

# 57. Phase 3 — Reboot and Test Ring 0

After policy deployment, test:

```text
boot
login
network
VPN
browser
Office
security agent
internal software
software update
Intune install
PowerShell administration
printing/peripherals
shutdown/restart
```

---

## Test an intentionally unauthorized executable

Use a harmless unsigned internal test executable that is **not allowed**.

Expected in enforcement:

```text
BLOCKED
```

Confirm event appears in central telemetry.

---

# 58. Phase 3 — Test Emergency Supplemental Allow

Prepare a harmless test file that is intentionally blocked.

Then:

```text
create narrow supplemental allow rule
→ approve emergency change
→ deploy Ring 0
→ sync
→ validate application starts
```

This proves emergency remediation works before clinical rollout.

---

# 59. Phase 3 — Test Rollback

Do not merely document rollback. Execute it in Ring 0.

Microsoft documents a safe removal pattern that includes first replacing enforcement with an Allow All policy before deleting the policy, so blocking does not remain unexpectedly until reboot.

Maintain a tested:

```text
Emergency-AllowAll
```

rollback package/policy.

---

# 60. Phase 3 — Ring 1 Audit

Once Ring 0 enforcement is stable, deploy **AUDIT** to:

```text
WIN-AppControl-Ring1-IT
```

Not enforcement.

Run normal IT workloads.

Collect events.

Resolve missing rules.

---

# 61. Phase 3 — Ring 1 Enforcement

Only after audit acceptance criteria are met.

Then:

```text
Ring 1
→ ENFORCED
```

Measure:

```text
App Control incidents
login/boot failures
application failures
helpdesk tickets
software installation failures
security tooling health
```

---

# 62. Phase 3 — Ring 2 Corporate Audit

Deploy audit to:

```text
WIN-AppControl-Ring2-Corporate
```

Include representative:

```text
Finance
HR
Operations
Legal
Procurement
Management
shared workstations
```

Exercise real software updates during audit.

---

# 63. Phase 3 — Ring 2 Corporate Enforcement

Do not promote by date alone.

Required:

```text
0 unresolved critical blocks
0 security-agent blocks
0 boot-impact issues
acceptable helpdesk incident rate
validated application update paths
```

Then move Ring 2 to enforcement.

---

# 64. Phase 3 — Clinical Pre-Assessment

Before Ring 3:

Create an **Application Trust Record** for every clinical application.

Template:

```text
Application:
Business owner:
Technical owner:
Vendor:
Clinical criticality:
Supported version:
Installer:
Executables:
DLLs:
Services:
Drivers:
Scripts:
COM components:
Browser dependencies:
Peripheral dependencies:
Update mechanism:
Digital signer:
Publisher certificate:
Managed Installer compatible:
Required network endpoints:
Rollback package:
Vendor support contact:
App Control rule type:
Last validation date:
```

---

# 65. Phase 3 — Ring 3 Clinical Non-Critical Audit

Deploy only audit.

Run full workflow with actual clinical staff/application owners.

Validate:

```text
startup
authentication
patient-data access
printing
scanning
device middleware
report export
background services
update process
failover workflows
```

---

# 66. Phase 3 — Ring 3 Enforcement

Require written owner acceptance.

Go/no-go:

```text
[ ] all clinical workflows tested
[ ] no known critical blocks
[ ] driver behavior validated
[ ] vendor update tested
[ ] rollback tested
[ ] on-call support present
```

Then enforce Ring 3.

---

# 67. Phase 3 — Ring 4 Critical Clinical Audit

Ring 4 receives the longest and strictest audit.

Do not treat a few days without tickets as sufficient evidence.

Test:

```text
normal operation
scheduled updates
application upgrades
Windows patching
reboots
peripheral reconnect
network interruption/recovery
service restart
night/weekend workflows
emergency workflow
```

---

# 68. Ring 4 Mandatory Go/No-Go Checklist

All must be true:

```text
[ ] Zero known critical application blocks
[ ] Zero known boot-impact events
[ ] Zero required driver blocks
[ ] EDR/AV/endpoint security fully healthy
[ ] Emergency supplemental policy tested
[ ] Emergency rollback tested
[ ] Intune delivery validated
[ ] Offline recovery procedure documented
[ ] Clinical app owner approval
[ ] Endpoint Engineering approval
[ ] InfoSec approval
[ ] Change/CAB approval
[ ] Helpdesk runbook distributed
[ ] Major Incident escalation tested
```

If any is false:

```text
NO GO
```

---

# 69. Ring 4 Enforcement

Deploy during approved maintenance/support window.

Have live coverage from:

```text
Endpoint Engineering
InfoSec
Clinical IT
Application owner
Helpdesk
SOC
```

Start with a very small subset of Ring 4.

Do not convert the entire critical estate at once.

---

# 70. Production Steady-State Operations

After broad enforcement, the project becomes an operational control.

Every new application follows:

```text
request
→ risk review
→ inventory
→ choose trust rule
→ audit
→ approve
→ deploy
```

Every internal software release follows:

```text
build
→ scan
→ approve
→ sign
→ timestamp
→ verify
→ hash
→ release
```

---

# 71. New Internal Application Onboarding Runbook

For every new Siloam-developed app:

## Step 1

Confirm application owner.

## Step 2

Register repository.

## Step 3

Enable CI tests and security scans.

## Step 4

Ensure final binary metadata and icon are applied before signing.

## Step 5

Build unsigned release.

## Step 6

Calculate SHA-256.

## Step 7

Obtain release approval.

## Step 8

Submit exact hash/artifact to signing service.

## Step 9

HSM signs.

## Step 10

RFC3161 TSA timestamps.

## Step 11

Verify:

```powershell
Get-AuthenticodeSignature <file>
```

Must be:

```text
Valid
```

## Step 12

Generate signed SHA256.

## Step 13

Package installer.

## Step 14

Sign installer too.

## Step 15

Verify installer.

## Step 16

Upload signed artifact to release repository.

## Step 17

Deploy through Intune/ConfigMgr.

## Step 18

Confirm App Control allows it in pilot.

## Step 19

Promote through deployment rings.

---

# 72. New Third-Party Application Onboarding

## If vendor-signed

Verify:

```powershell
Get-AuthenticodeSignature vendor.exe
```

Check:

```text
Status = Valid
expected publisher
valid chain
```

Prefer App Control publisher rules.

---

## If unsigned

Ask vendor for signed software first.

If not available:

```text
Managed Installer
→ narrow rule
→ hash rule as last resort
```

Document exception.

Do not re-sign vendor software unless contractual/support implications are fully understood.

---

# 73. PowerShell Script Handling

Do not treat execution policy as the only security control.

For privileged/internal scripts:

```text
source controlled
peer reviewed
signed
logged
App Control-aware
```

Optional administrative policy:

```text
AllSigned
```

but remember PowerShell execution policy is not a complete security boundary.

---

# 74. Certificate Rotation Runbook

Start before expiry.

Recommended example:

```text
T-90:
issue replacement certificate/key

T-60:
deploy new publisher certificate if TrustedPublisher is used

T-45:
allow new signer in App Control supplemental policy

T-30:
start signing pilot releases with new certificate

T-14:
validate enterprise deployment

T-0:
stop using old certificate for new releases
```

Keep old certificate trust long enough to support already timestamped historical software according to policy.

---

# 75. Signing Key Compromise Runbook

If compromise is suspected:

## Step 1

Disable signing service.

## Step 2

Disable signing CI identity.

## Step 3

Notify:

```text
InfoSec
PKI
SOC
Endpoint
Incident Response
Application teams
```

## Step 4

Revoke affected certificate.

## Step 5

Publish updated CRL/revocation status.

## Step 6

Identify every artifact signed during the suspected compromise window.

## Step 7

Hunt endpoints for:

```text
signer thumbprint
artifact hashes
unexpected paths
unknown applications
```

## Step 8

Create new HSM-backed key.

## Step 9

Issue new code-signing certificate.

## Step 10

Update App Control trust and TrustedPublisher deployment as required.

## Step 11

Resume signing only after incident approval.

---

# 76. Certificate Renewal Runbook

Never overwrite the old certificate blindly.

Process:

```text
new HSM key
→ new CSR
→ new certificate
→ deploy trust
→ App Control allows new signer
→ test
→ switch signing
→ retire old signing capability
```

---

# 77. Emergency App Control Incident Runbook

If legitimate application is blocked:

## Step 1

Capture:

```text
device
user
timestamp
application
path
hash
publisher
event ID
```

## Step 2

Determine clinical impact.

## Step 3

If critical clinical impact:

```text
Major Incident process
```

## Step 4

Validate file is legitimate.

Do not allow an unknown file simply because a user says it is needed.

## Step 5

Choose narrowest rule:

```text
publisher
managed installer
file attribute
hash
```

## Step 6

Create supplemental policy.

## Step 7

Peer review.

## Step 8

Emergency approval.

## Step 9

Deploy only to affected ring/devices where possible.

## Step 10

Confirm service restoration.

## Step 11

Post-incident review.

---

# 78. App Control Rollback Runbook

Maintain:

```text
known-good base policy
known-good supplemental policies
Emergency-AllowAll policy
documented Intune removal procedure
offline recovery documentation
```

For a bad enforcement policy:

```text
1. stop broader assignment
2. assign emergency AllowAll/recovery policy according to Microsoft-supported removal path
3. sync affected devices
4. reboot where required
5. verify application execution
6. remove bad policy only after safe replacement is active
7. investigate
```

Do not simply delete a policy without understanding removal/reboot behavior.

---

# 79. SOC Monitoring Baseline

Create alerts/dashboard for:

```text
App Control blocked execution
critical clinical endpoint block
unexpected unsigned internal application
unexpected signer thumbprint
signing service failure
unusual signing volume
after-hours signing
certificate revocation event
HSM authentication failure
Managed Installer policy error
```

---

# 80. Defender Advanced Hunting Concepts

Where Defender for Endpoint is available, monitor App Control-related events centrally.

Particularly distinguish:

```text
allowed
audited
blocked
origin allowed
origin audited
origin blocked
```

Create a critical-device enrichment table/group so a block on Ring 4 generates higher operational priority.

---

# 81. Intune Monitoring

In:

```text
Endpoint security
→ App Control for Business
```

review:

```text
Device and user check-in status
Device assignment status
Per-setting status
Managed Installer device status
```

Do not consider a policy production-ready while large numbers of endpoints are:

```text
Error
Conflict
Pending
```

without explanation.

---

# 82. Helpdesk Runbook

Helpdesk should never tell users to:

```text
disable SmartScreen
disable Defender
disable App Control
turn off Windows Security
run unknown file as administrator
```

Helpdesk response:

```text
1. collect screenshot/error
2. collect app name/path
3. collect device name
4. collect business impact
5. escalate to Endpoint/App Control queue
```

---

# 83. Production KPI / KRI

Track:

```text
% internally developed binaries signed
% production packages signed
% endpoints with correct root trust
% endpoints receiving App Control
App Control block rate
false-positive block rate
critical block count
exception count
expired exception count
signing failures
certificate age
unsigned internal software detected
```

---

# 84. Monthly Review

Every month:

```text
review signing logs
review exceptions
review App Control block trends
review unknown publishers
review certificate expiry
review HSM health
review TSA availability
review policy conflicts
review clinical-app changes
```

---

# 85. Quarterly Recovery Test

At least according to enterprise recovery policy, test:

```text
certificate rotation
signing-service recovery
App Control rollback
emergency supplemental policy
clinical application validation
```

---

# 86. What Must Be Backed Up

Back up according to PKI/HSM vendor requirements:

```text
CA configuration
CA database
CA private key using approved protected method
HSM configuration/HA/backup
App Control XML source policies
signed policy artifacts
signing audit logs
release manifests
certificate inventory
CRL configuration
runbooks
```

Do not create an exportable backup of an HSM-protected production key outside approved HSM backup procedures.

---

# 87. Final Production Acceptance Test

A release is only fully production-ready when all tests pass.

## Cryptography

```text
[ ] Code signing certificate valid
[ ] private key HSM-backed
[ ] key non-exportable
[ ] RFC3161 timestamp works
[ ] Authenticode status Valid
[ ] chain validation succeeds
```

## CI/CD

```text
[ ] build reproducible enough for audit
[ ] unsigned hash recorded
[ ] approval required
[ ] signing event logged
[ ] signed hash recorded
[ ] private key absent from CI
```

## Intune

```text
[ ] root profile Success
[ ] intermediate profile Success
[ ] publisher cert Success if required
[ ] Managed Installer validated if used
```

## App Control

```text
[ ] Ring 0 enforced and stable
[ ] Ring 1 enforced and stable
[ ] Ring 2 enforced and stable
[ ] Ring 3 owner-approved and stable
[ ] Ring 4 go/no-go passed before enforcement
```

## Operations

```text
[ ] SOC visibility
[ ] helpdesk guide
[ ] emergency allow procedure
[ ] rollback tested
[ ] certificate rotation runbook
[ ] compromise runbook
```

---

# 88. First 30-Day Execution Plan

If starting now, execute in this order.

## Workstream A — Week 1

```text
Day 1:
owners + change record + rings

Day 2:
software inventory + AppLocker current-state

Day 3:
PKI assessment

Day 4:
signing server/HSM readiness

Day 5:
code-signing certificate template
```

---

## Workstream B — Week 2

```text
HSM-backed CSR
certificate issuance
RFC3161 TSA
manual signing test
signature verification
Root/Issuing trust Ring 0
```

---

## Workstream C — Week 3

```text
CI/CD signing integration
release manifest
artifact repository
first low-risk signed application
Managed Installer Ring 0
```

---

## Workstream D — Week 4

```text
App Control Ring 0 Audit
event collection
rule analysis
supplemental policy
emergency/rollback test
```

Do not promise that production enforcement will be completed in 30 days. Promotion is based on evidence, not calendar time.

---

# 89. Exact Order — One-Page Checklist

For engineers who only need the sequence:

```text
01. Create project owners
02. Create Rings 0–4
03. Inventory applications
04. Inventory current AppLocker
05. Identify existing Enterprise PKI
06. Identify Issuing CA
07. Provision signing server
08. Install/configure HSM KSP
09. Verify HSM with certutil -csplist
10. Duplicate Code Signing template
11. Configure Code Signing EKU
12. Configure RSA / key size
13. Disable private-key export
14. Restrict Enroll permissions
15. Enable CA manager approval
16. Publish template
17. Create HSM-backed CSR
18. Submit CSR
19. Approve/issue certificate
20. certreq -accept certificate
21. Verify EKU/private key/chain
22. Export public Root/Intermediate/Publisher .cer
23. Configure RFC3161 TSA
24. Install SignTool
25. Sign harmless TestApp.exe
26. Verify signature + timestamp
27. Build production signing script/service
28. Centralize signing logs
29. Deploy Root CA to Ring 0 via Intune
30. Deploy Intermediate CA to Ring 0
31. Deploy TrustedPublisher leaf if actually required
32. Validate signed app on Ring 0
33. Integrate CI build → hash → approval → signing
34. Verify signed hash + manifest
35. Deploy first real signed internal app Ring 0
36. Review existing AppLocker configuration
37. Enable Intune Managed Installer Ring 0
38. Install test app through Intune
39. Create App Control built-in AUDIT policy
40. Assign Ring 0
41. Collect CodeIntegrity/AppLocker logs
42. Classify every meaningful audit event
43. Create supplemental allow rules
44. Repeat audit
45. Test emergency supplemental allow
46. Test rollback
47. Move Ring 0 to enforcement
48. Validate unauthorized test file is blocked
49. Audit Ring 1
50. Enforce Ring 1
51. Audit Ring 2
52. Enforce Ring 2
53. Build Clinical Application Trust Records
54. Audit Ring 3
55. Enforce Ring 3 after owner signoff
56. Long audit Ring 4
57. Complete Ring 4 go/no-go checklist
58. Enforce small Ring 4 subset
59. Expand Ring 4 gradually
60. Enter steady-state operations
```

---

# 90. Hard Stops

The engineer must STOP and escalate if any of the following occurs:

```text
HSM key is exportable
certificate has wrong EKU
certificate chain invalid
timestamp unavailable
signature verification not Valid
Root CA profile has widespread errors
unknown existing AppLocker enforcement
Ring 0 boot/login issue
EDR or security tool blocked
critical driver blocked
unknown clinical application dependency
rollback not tested
SOC cannot see App Control events
```

No exception is permitted merely to meet the deployment schedule.

---

# 91. Lab-Only Fallback

If the HSM is not yet available, a **lab proof-of-concept only** can use:

```text
Microsoft Software Key Storage Provider
non-exportable key
dedicated lab certificate
```

The lab certificate must be clearly named:

```text
Siloam Code Signing LAB - NOT PRODUCTION
```

Do not promote this certificate/key into production.

Production cutover requires the HSM-backed signing identity.

---

# 92. Important Design Distinctions

## Root trust

```text
Cert:\LocalMachine\Root
```

Trusts CA chain.

## Intermediate trust

```text
Cert:\LocalMachine\CA
```

Supports issuing chain.

## Trusted Publisher

```text
Cert:\LocalMachine\TrustedPublisher
```

Explicit publisher trust where required.

## App Control

Separate application authorization engine.

These are related, but they are not interchangeable.

---

# 93. Anti-Patterns

Never implement:

```text
PFX in Git repository
PFX emailed to developer
PFX copied to normal CI runner
password in YAML
unsigned production EXE
hash generated before signing and published as final hash
App Control enforcement without audit
All Devices assignment for first policy
clinical production as first pilot
Allow * from writable directory
blind hash allowlisting of everything observed
disable Defender/SmartScreen to solve publisher issue
```

---

# 94. Reference Commands Cheat Sheet

## Show CA selection

```cmd
certutil -config - -ping
```

## Show templates

```cmd
certutil -CATemplates
```

## List crypto providers

```cmd
certutil -csplist
```

## Create CSR

```cmd
certreq -new request.inf request.req
```

## Submit CSR

```cmd
certreq -submit request.req certificate.cer
```

## Accept certificate

```cmd
certreq -accept certificate.cer
```

## Verify certificate

```cmd
certutil -verify certificate.cer
```

## Sign

```powershell
signtool sign `
  /sha1 <THUMBPRINT> `
  /sm `
  /fd SHA256 `
  /tr <RFC3161-URL> `
  /td SHA256 `
  Application.exe
```

## Verify signature

```powershell
signtool verify /pa /v Application.exe
```

## PowerShell verify

```powershell
Get-AuthenticodeSignature Application.exe | Format-List *
```

## Hash

```powershell
Get-FileHash Application.exe -Algorithm SHA256
```

## AppLocker effective policy

```powershell
Get-AppLockerPolicy -Effective -Xml
```

## Remove Audit option from App Control XML

```powershell
Set-RuleOption -FilePath .\Policy.xml -Option 3 -Delete
```

## Add first-ring boot safety options

```powershell
Set-RuleOption -FilePath .\Policy.xml -Option 9
Set-RuleOption -FilePath .\Policy.xml -Option 10
```

## Convert policy

```powershell
ConvertFrom-CIPolicy .\Policy.xml .\Policy.cip
```

---

# 95. Official Microsoft Documentation

Use these as source of truth if Microsoft changes menus, supported platforms, or behavior.

## AD CS Certificate Templates

https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/manage-certificate-templates

## Certificate Template Concepts

https://learn.microsoft.com/en-us/windows-server/identity/ad-cs/certificate-template-concepts

## certreq

https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/certreq_1

## App Control Code-Signing Certificate

https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/deployment/create-code-signing-cert-for-appcontrol

## Intune Trusted Certificate Profiles

https://learn.microsoft.com/en-us/intune/device-configuration/certificates/trusted-root-profiles

## Intune App Control for Business and Managed Installer

https://learn.microsoft.com/en-us/intune/device-configuration/endpoint-security/manage-app-control

## App Control Deployment Guide

https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/deployment/appcontrol-deployment-guide

## App Control Audit

https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/deployment/audit-appcontrol-policies

## App Control Enforcement

https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/deployment/enforce-appcontrol-policies

## Managed Installer

https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/design/configure-authorized-apps-deployed-with-a-managed-installer

---

# 96. Final Target State

The project is complete only when the following is normal operating behavior:

```text
Developer
    ↓
source-controlled change
    ↓
review
    ↓
CI build + security checks
    ↓
unsigned immutable artifact + SHA256
    ↓
release approval
    ↓
central signing request
    ↓
HSM-backed signature + RFC3161 timestamp
    ↓
automated verification
    ↓
signed artifact repository
    ↓
Intune/ConfigMgr deployment
    ↓
managed endpoint
    ↓
App Control policy verifies authorization
    ↓
authorized software runs
unauthorized software is blocked
    ↓
SOC sees the event
```

And if a legitimate application is unexpectedly blocked:

```text
detect
→ triage
→ narrow exception/supplemental policy
→ approve
→ deploy
→ recover
→ review
```

without globally disabling endpoint security.

---

# 97. Definition of Done

The implementation is **Production Ready** only when all boxes below are checked:

```text
[ ] Existing PKI reviewed and approved
[ ] Production signing key HSM-backed
[ ] Production signing certificate Code Signing EKU only as designed
[ ] Non-exportable private key
[ ] RFC3161 timestamp operational
[ ] Signing service audited
[ ] CI/CD cannot access raw private key
[ ] Root/intermediate trust deployed successfully
[ ] Publisher trust deployed only where needed
[ ] At least one production internal application signed end-to-end
[ ] Signed app successfully deployed through approved channel
[ ] Managed Installer validated if enabled
[ ] Ring 0 Audit completed
[ ] Ring 0 Enforcement stable
[ ] Emergency supplemental policy tested
[ ] App Control rollback tested
[ ] Central telemetry active
[ ] Ring 1–2 phased rollout successful
[ ] Clinical trust records completed before clinical enforcement
[ ] Ring 3 approved
[ ] Ring 4 explicit go/no-go passed before enforcement
[ ] Certificate rotation runbook tested
[ ] Key compromise runbook approved
[ ] Helpdesk and SOC runbooks operational
```

Only then should the architecture be described as a production internal software trust and application-control capability.
