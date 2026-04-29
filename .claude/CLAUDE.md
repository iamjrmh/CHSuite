# Claude Code — Global Instructions

You are an expert software engineer. You have full permission to read, write, create,
move, and delete any file in the working directory. Never ask for confirmation before
executing commands, editing files, or running tests. Proceed autonomously and report
results when done.

---

## 🐍 Python Development

### Environment
- Prefer **Python 3.11+** unless a different version is explicitly required.
- Use `uv` for environment/package management when available; fall back to `pip` + `venv`.
- Virtual env convention: `.venv/` at the project root.
  ```bash
  python3 -m venv .venv && source .venv/bin/activate
  ```
- Always check for an existing `pyproject.toml`, `requirements.txt`, or `setup.py`
  before installing anything.

### Code Style & Quality
- Follow **PEP 8** and **PEP 257** (docstrings).
- Use **type hints** on all public functions and class methods.
- Format with **`ruff format`** after every write; lint with **`ruff check --fix`**.
- Run **`mypy --strict`** before considering a module complete.
- Prefer f-strings over `.format()` or `%`.
- Keep functions short — single responsibility. Prefer composition over inheritance.
- Use `pathlib.Path` instead of `os.path`.
- Use context managers (`with`) for all file/network/DB handles.

### Project Structure (default layout)
```
project/
├── src/
│   └── package_name/
│       ├── __init__.py
│       └── ...
├── tests/
│   ├── conftest.py
│   └── test_*.py
├── pyproject.toml
└── README.md
```

### Testing
- Write **pytest** tests alongside every new module.
- Use `pytest-cov` for coverage; target ≥ 80 % on new code.
- Fixtures go in `conftest.py`; use `tmp_path` for temp files.
- Mock external I/O (`httpx`, DB, filesystem) — never hit real services in unit tests.

### Error Handling
- Raise specific exceptions; never `except Exception: pass`.
- Log with the stdlib `logging` module (not `print`), using `__name__` loggers.
- Use `dataclasses` or `pydantic` for structured data; avoid raw dicts for domain objects.

### Dependencies to prefer
| Task | Library |
|------|---------|
| HTTP | `httpx` |
| CLI | `typer` or `click` |
| Data | `pandas`, `polars` |
| Async | `asyncio` + `anyio` |
| Config | `pydantic-settings` |
| DB | `sqlalchemy` 2.x |

---

## 🖥️ Batch Scripting (Windows .bat / .cmd and Shell)

### Windows Batch (.bat / .cmd)
- Always start with `@echo off` and set `SETLOCAL ENABLEEXTENSIONS`.
- Use `%~dp0` to resolve the script's own directory; never rely on CWD.
- Quote all variable expansions: `"%VARIABLE%"`.
- Check `%ERRORLEVEL%` after every significant command; use `|| goto :error`
  for fail-fast behavior.
- Use `CALL :label` for subroutines; define `:error` and `:end` labels.
- Prefer `XCOPY /E /I /Y` or `ROBOCOPY` over `COPY` for directory operations.
- Template:
  ```bat
  @echo off
  SETLOCAL ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION
  SET "SCRIPT_DIR=%~dp0"

  :: --- Main logic ---
  CALL :main
  GOTO :end

  :main
      REM your code here
      EXIT /B 0

  :error
      ECHO [ERROR] Script failed with code %ERRORLEVEL% 1>&2
      EXIT /B %ERRORLEVEL%

  :end
  ENDLOCAL
  ```

### Shell Scripts (.sh / bash)
- Always use `#!/usr/bin/env bash` shebang.
- Set safety flags at the top: `set -euo pipefail`.
- Quote all variable expansions; use `"${VAR}"` syntax.
- Use `$(...)` for command substitution; never backticks.
- Check tool availability with `command -v tool >/dev/null 2>&1`.
- Store temp files in `$(mktemp)` and clean up with `trap cleanup EXIT`.

---

## 🍎 SwiftUI iOS Development

### Environment & Tooling
- Target **iOS 16+** by default unless specified otherwise.
- Use **Xcode 15+** and **Swift 5.9+**.
- Dependency management: **Swift Package Manager (SPM)** only — no CocoaPods or Carthage
  unless the project already uses them.
- Build from CLI: `xcodebuild -scheme <Scheme> -destination 'platform=iOS Simulator,...'`
- List simulators: `xcrun simctl list devices available`

### SwiftUI Architecture — MVVM + Observation
- Use `@Observable` (Swift 5.9 macro) for ViewModels on iOS 17+;
  fall back to `ObservableObject` / `@StateObject` for iOS 16.
- One `ViewModel` per `View`; inject via `.environment()` or `@StateObject` at the root.
- Never put business logic inside a `View` body; move it to the ViewModel or a Service.
- `View` bodies should be **declarative and thin** — only layout and bindings.

### Code Conventions
- Name views `<Feature>View.swift`, models `<Feature>Model.swift`,
  view models `<Feature>ViewModel.swift`.
- Use `enum` with associated values for navigation state (NavigationStack path).
- Prefer `async/await` over Combine for new code; `Task { }` inside `.task { }` modifier.
- Use `@MainActor` on ViewModel classes to keep UI updates on the main thread.
- Handle errors with `Result<Success, Error>` or `do/catch`; present them via
  `@State var alertError: LocalizedError?` pattern.
- Use `PreviewProvider` (or `#Preview` macro) for every view — include light/dark variants.

### Project Structure
```
MyApp/
├── MyApp.swift              # @main entry point
├── ContentView.swift
├── Features/
│   ├── Home/
│   │   ├── HomeView.swift
│   │   └── HomeViewModel.swift
│   └── Settings/
│       ├── SettingsView.swift
│       └── SettingsViewModel.swift
├── Models/
├── Services/                # Networking, persistence, etc.
├── Components/              # Reusable SwiftUI views
└── Resources/               # Assets, Localizable.strings
```

### Networking
- Use `URLSession` with `async/await`; wrap in a `NetworkService` actor.
- Decode responses with `JSONDecoder`; use `CodingKeys` for snake_case → camelCase mapping.
- Always handle HTTP error status codes explicitly — don't just check for nil.

### Data Persistence
- **SwiftData** (iOS 17+) or **Core Data** for relational/complex data.
- `UserDefaults` only for small primitives / user preferences.
- Keychain (via `Security` framework or a thin wrapper) for secrets/tokens.

### Testing
- Unit-test ViewModels with `XCTest`; inject mock services via protocols.
- UI tests with `XCUITest` for critical user flows.
- Use `#expect` / `#require` (Swift Testing framework, Xcode 16) for new test targets.

---

## 🚀 GitHub Actions CI/CD — iOS Release Workflow

### Release Build Checklist
When pushing a version tag (`v*`) to trigger a release build:

1. **Monitor the build** — build takes ~1 min 30 sec. Check workflow status after 1 minute, not 2.
2. **Use unsigned workflow** — `02-build-ipa.yml` with `CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO`
3. **Required workflow permissions** — job MUST have `permissions: contents: write` for gh CLI to work
4. **gh CLI auth** — set `env: GH_TOKEN: ${{ github.token }}` (do NOT pass `--clob` or change dir to `$RUNNER_TEMP` when running `gh release create`)
5. **Create release from repo root** — run `gh release create` commands from the repository checkout directory, not from `$RUNNER_TEMP`
6. **Use prerelease flag** — always pass `--prerelease` on `gh release create`

### Persistent Scan on Release Push
When a release tag is pushed:
- Poll `gh run list --workflow=02-build-ipa.yml` every **60 seconds**
- If status is `completed` with `success`: verify IPA asset via `gh release view <tag> --json assets`
- If status is `failed` or `cancelled`: read `gh run view <run-id> --log` to identify the error and fix it
- Repeat until the release is `published` with IPA attached

### Workflow File Requirements (`.github/workflows/02-build-ipa.yml`)
```yaml
permissions:
  contents: write   # Required for gh CLI and artifact upload

jobs:
  build:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      # ... build steps ...
      - name: Create GitHub Release
        if: startsWith(github.ref, 'refs/tags/v')
        env:
          GH_TOKEN: ${{ github.token }}   # Required env var, NOT --clob
        run: |
          gh release create "${{ github.ref_name }}" \
            --title "CHSuite iOS ${{ github.ref_name }}" \
            --notes "Pre-release build..." \
            --prerelease \
            "${{ runner.temp }}/CHSuite-iOS.ipa"   # Path from repo root, not $RUNNER_TEMP
```

### Common Build Failures
| Error | Fix |
|-------|-----|
| `HTTP 403` on `gh release create` | Add `permissions: contents: write` to job |
| `GH_TOKEN` missing | Add `env: GH_TOKEN: ${{ github.token }}` to gh step |
| IPA not attached | Ensure artifact path uses `${{ runner.temp }}`, not `cd $RUNNER_TEMP` before zip |
| Draft release instead of published | Remove `--draft` flag; add `--prerelease` |
| `gh: command not found` | Install gh via `brew install gh` or use `actions/github-script` |

---

## 🔄 Auto-Push & Auto-Release

### After Every Change
After completing any code change (fix, feat, refactor, etc.):

1. **Stage all changes**: `git add -A`
2. **Commit with message**: Use Conventional Commits format (`fix:`, `feat:`, etc.)
3. **Push immediately**: `git push origin <branch>` — do not batch commits
4. **Monitor release workflow**: The workflow `02-build-ipa.yml` auto-triggers on push to main branch with tag `v*`
   - Poll `gh run list --workflow=02-build-ipa.yml` every **60 seconds**
   - Wait for build to complete before confirming done
5. **Verify release**: Check `gh release view <tag> --json assets` confirms IPA is attached

### No Manual Steps
- Never wait for manual trigger — the workflow auto-runs on tags
- Never skip monitoring — builds fail silently without verification
- Always confirm IPA is attached before reporting success

---

## 🔧 General Engineering Standards

### Version Control
- Write concise, imperative commit messages: `fix: handle nil in UserViewModel`.
- Conventional Commits format: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Never commit secrets, API keys, or credentials — check `.gitignore` first.

### File Operations
- Before overwriting any file, read it and understand its current contents.
- Prefer targeted edits over full rewrites unless the file needs a major restructure.
- When unzipping archives: `unzip -o <file> -d <destination>`.

### When Asked to "Fix" Something
1. Read the relevant file(s) first.
2. Identify the root cause — don't treat symptoms.
3. Make the minimal, correct change.
4. Run tests / linters / the compiler to verify.
5. Report what was changed and why.

### Autonomous Operation
- You have full permission to act within the working directory.
- Do not ask "Are you sure?" or request confirmation for standard operations.
- If genuinely ambiguous, state your assumption, proceed, and note it in your response.
- After completing a task, summarize: what you did, what changed, and any caveats.
