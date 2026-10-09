# 🚨 CRITICAL: Credentials Remediation Guide

**Status**: Real credentials (`DATABASE_URL`, `JWT_SECRET_KEY`, `WEATHER_API_KEY`) are committed in `.env` file.

**Risk Level**: 🔴 CRITICAL  
**Action Required**: Immediately execute steps below before ANY production deployment.

---

## Step 1: Invalidate All Exposed Keys (Immediately)

### Neon Database
1. Go to [https://console.neon.tech](https://console.neon.tech)
2. Select your project
3. Go to **Settings → Connection strings**
4. Rotate the password:
   - Click "Reset password"
   - Confirm action
   - Copy new connection string
5. Update your production `.env` file with new `DATABASE_URL`

### JWT Secret
This key is used to sign/verify authentication tokens. All existing tokens will become invalid (users will need to re-login).

```bash
# Generate a new secure JWT secret
openssl rand -hex 32
# Output: <new_jwt_secret>
```

Update: 
- Production `.env`: `JWT_SECRET_KEY=<new_jwt_secret>`
- All deployed instances must be updated simultaneously
- Users will be logged out (acceptable, they re-login)

### Weather API Key
1. Go to [https://openweathermap.org/api](https://openweathermap.org/api)
2. Log in to your account
3. Go to **API keys** section
4. Delete or regenerate the exposed key
5. Create a new API key
6. Update production `.env`: `WEATHER_API_KEY=<new_key>`

---

## Step 2: Remove `.env` From Git History

### Option A: Using `git filter-branch` (Recommended)

```bash
cd c:\Users\rifat\Downloads\Compressed\floodshield_backend_reviewed

# 1. Remove .env from entire history
git filter-branch --tree-filter 'rm -f .env' --prune-empty HEAD

# 2. Force push (only if this is a shared repo, coordinate with team)
git push origin --force-all
git push origin --force --tags

# 3. Verify .env is gone
git log --full-history --all -- .env

# 4. Clean up old refs
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### Option B: Using `bfg` (Faster for Large Repos)

```bash
# Install bfg
brew install bfg  # macOS
# or download from https://rtyley.github.io/bfg-repo-cleaner/

# Remove .env from history
bfg --delete-files .env --no-blob-protection

# Push changes
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force-all
```

### Verify Removal

```bash
# Check no credentials appear in git history
git log -p --all -- '*.env' | head -100

# Should output nothing; if it shows old .env content, repeat Step 2
```

---

## Step 3: Add Prevention Measures

### 3a. Update `.gitignore` (Already Done)

Verify file contains:
```
.env
.env.local
.env.*.local
```

### 3b. Add Pre-Commit Hook (Prevent Future Commits)

Create `backend/.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Prevent .env from being committed

if git diff --cached --name-only | grep -q '^\.env$'; then
    echo "ERROR: .env file detected in staged changes!"
    echo "Commit aborted. .env must not be committed to git."
    echo ""
    echo "Use .env.example to document structure instead."
    exit 1
fi

if git diff --cached --name-only | grep -q 'DATABASE_URL\|JWT_SECRET_KEY\|API_KEY'; then
    echo "ERROR: Possible credentials detected in staged files!"
    echo "Please review your changes before committing."
    exit 1
fi

exit 0
```

Make it executable:
```bash
chmod +x backend/.git/hooks/pre-commit
```

---

## Step 4: Update Environment Variables in Production

### For Railway.app (Recommended Platform)

```bash
# Login to Railway
railway login

# Link to project
railway link <your-project-id>

# Set environment variables
railway variables set DATABASE_URL="postgresql://..."
railway variables set JWT_SECRET_KEY="<new_secret>"
railway variables set WEATHER_API_KEY="<new_key>"
railway variables set LLM_API_KEY="<your_anthropic_key>"

# Redeploy
railway up
```

### For Docker/Kubernetes

```yaml
# kubernetes/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: floodshield-secrets
type: Opaque
stringData:
  DATABASE_URL: postgresql://...
  JWT_SECRET_KEY: <new_secret>
  WEATHER_API_KEY: <new_key>
  LLM_API_KEY: <your_key>
```

Then reference in deployment:
```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: floodshield-secrets
        key: DATABASE_URL
```

---

## Step 5: Restore Clean `.env.example`

Ensure `.env.example` contains ONLY placeholder values:

```bash
# backend/.env.example
DATABASE_URL=postgresql://user:password@your-neon-host/dbname?sslmode=require
JWT_SECRET_KEY=generate-with-openssl-rand-hex-32
ACCESS_TOKEN_EXPIRE_MINUTES=60
WEATHER_API_KEY=your-openweathermap-api-key
LLM_API_KEY=your-anthropic-claude-api-key
```

✅ This file is safe to commit and shared with team.

---

## Checklist: Completion Verification

- [ ] **Day 1 (Emergency)**
  - [ ] Neon database password rotated
  - [ ] JWT secret regenerated
  - [ ] Weather API key regenerated
  - [ ] New credentials entered in production environment
  - [ ] All production servers redeployed with new env vars

- [ ] **Day 2 (Git Cleanup)**
  - [ ] `.env` removed from git history using `git filter-branch` or `bfg`
  - [ ] Force push executed (coordinate with team)
  - [ ] Git history verified clean (`git log --all -- .env` returns nothing)

- [ ] **Day 3 (Prevention)**
  - [ ] Pre-commit hook installed and tested
  - [ ] `.gitignore` verified includes `.env`
  - [ ] Team educated on `.env` security practices
  - [ ] README.md updated with setup instructions

- [ ] **Ongoing**
  - [ ] Audit logs monitored for any use of exposed credentials
  - [ ] Regular security reviews of committed files
  - [ ] Optional: Run `git-secrets` in CI/CD to catch credentials

---

## Estimated Impact

| Action | Downtime | User Impact | Complexity |
|--------|----------|---|---|
| Rotate DB password | <5 min | None (auto-reconnect) | ⭐ Easy |
| Regenerate JWT secret | <1 min | Users logged out (must re-login) | ⭐ Easy |
| Rotate API keys | <5 min | Weather API temporarily unavailable | ⭐ Easy |
| Remove from git history | <30 min | None (git only) | ⭐⭐ Medium |

**Total remediation time**: 1-2 hours  
**Total downtime**: < 10 minutes

---

## Additional Resources

- [Git Security - GitHub Docs](https://docs.github.com/en/code-security/secret-scanning)
- [BFG Repo Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)
- [Neon Database Docs](https://neon.tech/docs)
- [Best Practices - Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

**Next Steps After Remediation**:
1. ✅ Credentials are secured
2. 🟡 HIGH: Add weather fallback UI badge (already implemented)
3. 🟡 HIGH: Replace synthetic forecast with real data
4. 🟠 MEDIUM: Integrate real LLM
5. 🟠 MEDIUM: Finish prefers-reduced-motion support (in progress)
