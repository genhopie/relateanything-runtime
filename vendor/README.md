# Upstream RelateAnything (AGPL)

Production container builds check out the pinned upstream revision:

`e9ea42aed60f766f12ad19d51709129c50110a3b`

```bash
git clone https://github.com/maelic/RelateAnything.git vendor/RelateAnything
cd vendor/RelateAnything && git checkout e9ea42aed60f766f12ad19d51709129c50110a3b
pip install -e ".[hub]"
```

Do not commit full upstream sources in this repository; the Docker build clones them to satisfy AGPL Corresponding Source publication for the deployed image revision.
