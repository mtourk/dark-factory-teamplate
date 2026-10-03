# Profiles

The Dark Factory is built **once**, as a reusable template/engine, and reused
across every future project. A **profile** is how a single project plugs
into that engine: it names a target GitHub repository (and, optionally, a
Cloudflare project reference) without the factory's orchestration code ever
needing to change.

Each profile is one file: `profiles/<name>.yml`. Profile files are safe to
commit — they never contain secrets.

## Creating a profile

```
factory profile create my-project --repo https://github.com/acme/my-project
```

This writes `profiles/my-project.yml`:

```yaml
name: my-project
target_repo:
  owner: acme
  name: my-project
  url: https://github.com/acme/my-project
cloudflare:
  project_name: null
  preview_url: null
  production_url: null
business_requirements_source: null
protected_paths: []
notes: ''
```

## Running the factory against a profile

```
factory --profile my-project feature "Add ROI calculator"
factory --profile my-project run
```

If only one profile exists, `--profile` can be omitted — it resolves
implicitly. The `FACTORY_PROFILE` environment variable is also honored,
taking precedence over implicit single-profile resolution but not over an
explicit `--profile` flag.

## Secrets

Profiles never hold Cloudflare or GitHub credentials. Credentials for a
profile's target repository live **only** as encrypted GitHub Actions
repository secrets on that target repository — set once via
`factory/deploy/target_repo_setup.py`, never stored locally and never
read by factory orchestration code. See master plan §15 and §17.

## Fields

| Field | Required | Description |
|---|---|---|
| `name` | yes | Profile identifier; must match the filename. |
| `target_repo.url` | yes | `https://github.com/<owner>/<name>` of the managed project. |
| `cloudflare.project_name` | no | Wrangler/Cloudflare project name, if deploying there. |
| `cloudflare.preview_url` / `production_url` | no | Filled in after first deploy; informational only. |
| `business_requirements_source` | no | Where this project's business requirements come from (e.g. `github_issues`, a local file path). |
| `protected_paths` | no | Additional paths (beyond the factory's own defaults) that auto-merge must never touch for this project. |
| `notes` | no | Free text. |
