# Gmail Feature - Archived

## Why Archived

Google OAuth verification requirements block unverified apps from using sensitive Gmail scopes (`gmail.readonly`, `gmail.modify`). The "Something went wrong" error appears after clicking "Go to app" on the consent screen.

**Key findings:**
- `gmail.readonly` and `gmail.modify` are **sensitive scopes** requiring verification
- Unverified apps are limited to 100 users and show warning screens
- Google now blocks the redirect entirely for unverified apps using sensitive Gmail scopes
- Verification requires privacy policy, terms of service, domain verification, and can take months

## Archived Files

The following files were moved to `archive/gmail_feature/`:

| Original Location | File |
|-------------------|------|
| `core/auth/gmail_oauth.py` | OAuth 2.0 PKCE flow for Gmail API |
| `core/gmail/gmail_client.py` | Gmail REST API client |
| `widgets/gmail_widget.py` | Gmail overlay widget |
| `tests/test_gmail_widget.py` | Unit tests |
| `images/google-gmail.svg` | Gmail logo icon |

## How to Restore

### 1. Move files back to original locations

```powershell
# From project root
Move-Item -Path "archive\gmail_feature\gmail_oauth.py" -Destination "core\auth\"
Move-Item -Path "archive\gmail_feature\gmail_client.py" -Destination "core\gmail\"
Move-Item -Path "archive\gmail_feature\gmail_widget.py" -Destination "widgets\"
Move-Item -Path "archive\gmail_feature\test_gmail_widget.py" -Destination "tests\"
Move-Item -Path "archive\gmail_feature\google-gmail.svg" -Destination "images\"
```

### 2. Restore imports in `__init__.py` files

**`core/auth/__init__.py`:**
```python
"""Authentication modules for external services."""
from core.auth.gmail_oauth import GmailOAuthManager, GmailCredentials

__all__ = ["GmailOAuthManager", "GmailCredentials"]
```

**`core/gmail/__init__.py`:**
```python
"""Gmail integration modules."""
from core.gmail.gmail_client import GmailClient, EmailMetadata, GmailLabel

__all__ = ["GmailClient", "EmailMetadata", "GmailLabel"]
```

### 3. Restore import in `rendering/widget_manager.py`

Uncomment line ~24:
```python
from widgets.gmail_widget import GmailWidget, GmailPosition
```

And restore the `create_gmail_widget` method and its call in `setup_all_widgets`.

### 4. Restore UI in `ui/tabs/widgets_tab.py`

- Add `self._btn_gmail = QPushButton("Gmail")` to subtab buttons
- Add Gmail button to the button iteration loop
- Restore Gmail widget UI section (QGroupBox with all settings)
- Restore Gmail methods: `_on_gmail_enabled_changed`, `_authorize_gmail`, etc.
- Restore Gmail settings loading in `_load_settings`
- Restore Gmail config saving in `_save_settings`

### 5. Google Cloud Console Setup

1. Create OAuth 2.0 Client ID (Desktop app type)
2. Enable Gmail API
3. Configure OAuth consent screen with scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`
4. **Complete Google's OAuth verification process** (required for public use)

## Alternative Approaches

If you want Gmail functionality without verification:

1. **Personal use only**: Add yourself as a test user in Google Cloud Console
2. **Google Workspace**: Use domain-wide delegation for internal apps
3. **Different provider**: Consider Microsoft Graph API for Outlook (different verification process)

## Date Archived

December 17, 2025
