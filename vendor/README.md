# Upstream RelateAnything (AGPL)

Governed processing configuration carries Hugging Face relation-model provenance
`e9ea42aed60f766f12ad19d51709129c50110a3b` (weight checksum is verified separately).
That value is not a published commit on `github.com/maelic/RelateAnything`; production
images clone upstream `main` and record the checked-out git SHA in
`/opt/relsgg-corresponding-source-git-revision.txt` for AGPL Corresponding Source.

```bash
git clone https://github.com/maelic/RelateAnything.git vendor/RelateAnything
cd vendor/RelateAnything && pip install -e ".[hub]"
```

Do not commit full upstream sources in this repository; the Docker build clones them to satisfy AGPL Corresponding Source publication for the deployed image revision.
