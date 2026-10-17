# Sanitized GH Mirror

## Example

```yaml
name: Sanitize and Mirror

on:
  workflow_dispatch:

  push:
    branches: [main]

jobs:
  sanitize-and-mirror:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      - uses: https://git.paynepride.com/nic/homelab-mono/devops/ci/forgejo-actions/sanitized-github-mirror@main
        with:
          remove: "mirror-test"
          github_repo: pypeaday/homelab-mono-mirror
          ssh_private_key: ${{ secrets.SSH_PRIVATE_KEY_FORGEJO_MIRROR_BOT }}
```
