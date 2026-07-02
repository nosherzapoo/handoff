# handoff

Handover repository for work being transitioned to a new maintainer.

## Projects

### `pollstar/`

Tooling to extract the Pollstar Data Cloud Boxoffice dataset into a flat CSV. Pollstar has
no export button and no public API, so this calls the internal `boxoffice2` API, decrypts
the AES-encrypted response, and writes every engagement (EventDate on or after 2010-01-01)
to `concerts.csv`.

Full guide: [`pollstar/README.md`](pollstar/README.md).

Quick start (run from this repository root):

```bash
# 1. Put a valid Pollstar bearer token in ./jwt.txt (see pollstar/README.md, section 3).
# 2. Pull the data:
./pollstar/scripts/refresh_data.sh
```

## Repository layout

```
handoff/
├── README.md                     this file
├── .gitignore
├── jwt.txt                       your Pollstar token (gitignored; you create it)
├── pages/                        API page cache (gitignored)
├── concerts.csv                  the extracted dataset (gitignored)
└── pollstar/                     the extraction project
    ├── README.md                 the extraction guide (start here)
    ├── fetch_pollstar.js         the extractor (Node)
    ├── scripts/
    │   ├── refresh_data.sh        pull data and rebuild concerts.csv
    │   └── split_concerts_csv.sh  split concerts.csv into shareable parts
    └── reference/
        └── chunks/                saved Pollstar site JS (decryption reference)
```

The token, the extracted data, and the page cache live at the repository root and are
gitignored, so only code and docs are tracked. The downstream analysis scripts are kept
separately and are not part of this repository.

Author: Nosher Ali Khan. Last updated: 2026-07-02.
