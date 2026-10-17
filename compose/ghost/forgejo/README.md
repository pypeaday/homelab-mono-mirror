# Forgejo

## Runner in Compose

They provide oci-image installation instructions [here]()

for my platform, it should support init scripts of some kind for compose stacks. in the docs here we need to do:

> NOTE: `data` from there example will be my zfs dataset path

```bash
set -e

mkdir -p data
touch data/.runner
mkdir -p data/.cache

chown -R 1001:1001 data/.runner
chown -R 1001:1001 data/.cache
chmod 775 data/.runner
chmod 775 data/.cache
chmod g+s data/.runner
chmod g+s data/.cache
```

