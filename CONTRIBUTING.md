# Contributing to ani-cli-sync

Thank you for your interest in contributing to **ani-cli-sync**! We welcome contributions, bug fixes, documentation improvements, and feature proposals.

---

## 🎯 Design Principles

When submitting pull requests, please keep our core architectural principles in mind:

1. **Zero External Runtime Dependencies**: `ani-cli-sync` relies strictly on the Python standard library (`urllib.request`, `json`, `argparse`, `pathlib`, `subprocess`). Do not introduce third-party runtime package dependencies.
2. **Agentic-First & Headless Compatibility**:
   - All commands must support non-interactive execution (standard exit codes: `0` for success, non-zero for errors).
   - Machine-parseable output formats (e.g. `ani-cli-sync list`) must remain stable.
3. **Non-Destructive Watchlist Synchronization**: Respect existing watchlist entries before falling back to global searches to prevent accidental clobbering of multi-season progress.

---

## 🛠️ Local Development Setup

### 1. Clone & Set Up

```bash
git clone https://github.com/niStee/ani-cli-sync.git
cd ani-cli-sync

# Install in editable mode
pip install -e .
```

### 2. Run the Test Suite

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Ensure all unit tests pass before submitting your changes.

---

## 📝 Commit & Release Conventions

We use **Conventional Commits** to automate versioning, changelog generation, and releases via [Release Please](https://github.com/googleapis/release-please):

| Prefix | Description | Example |
| :--- | :--- | :--- |
| `feat:` | A new feature or capability (bumps minor version) | `feat: add fallback provider for season mapping` |
| `fix:` | A bug fix (bumps patch version) | `fix: resolve episode offset when progress exceeds total` |
| `docs:` | Documentation changes only | `docs: update setup guide in README` |
| `chore:` | Maintenance or dependency updates | `chore: update github action SHAs` |
| `test:` | Adding or modifying tests | `test: add unit tests for subtitle selection` |

---

## 🔀 Submitting Pull Requests

1. Create a descriptive feature branch:
   ```bash
   git checkout -b feat/my-improvement
   ```
2. Make your changes, maintaining test coverage and docstrings.
3. Verify that tests pass:
   ```bash
   PYTHONPATH=src python3 -m unittest discover -s tests
   ```
4. Push your branch and create a Pull Request:
   ```bash
   git push -u origin feat/my-improvement
   gh pr create --fill
   ```

---

## 🔒 Security Vulnerabilities

If you discover a security vulnerability, please refer to our [Security Policy](SECURITY.md) and report it privately rather than opening a public issue.
