# Windows releases

After Windows validation passes on main, the release job packs the executable and
its runtime dependencies. It starts the app from the extracted ZIP, then publishes
the ZIP and its SHA-256 checksum under the version from pyproject.toml. Published
versions are kept intact. GitHub Actions still retains the CI artifact separately.

Download the ZIP and extract the whole folder before running ChessEngineBattle.exe.
The checksum can be checked with PowerShell.

```powershell
Get-FileHash .\ChessEngineBattle-0.5.28-Windows.zip -Algorithm SHA256
```

Compare the result with the companion .sha256 file. RELEASE-INFO.txt records the
source commit, executable hash and Authenticode status of that package.

## Authenticode

The release job supports Azure Artifact Signing using GitHub OpenID Connect.
Configure a verified public-trust certificate profile and an Azure application
with the Artifact Signing Certificate Profile Signer role. The federated credential
should trust only the main branch of this repository. Set repository variables
AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, AZURE_SIGNING_ENDPOINT,
AZURE_SIGNING_ACCOUNT and AZURE_SIGNING_PROFILE. Set WINDOWS_SIGNING_ENABLED
to true once the Azure identity and profile are ready.

The workflow signs the application executable, verifies a Valid Authenticode status
and runs the packaged startup check. Third-party runtime files retain their original
signatures. Windows Smart App Control behavior still needs testing on a machine
with that policy enabled. Without a configured signing identity, the release job
records and publishes the unsigned build.
