# migrations

`tools/upgrade.py` runs these in version order, and only those newer than the project's `KIT_VERSION`.

One file per kit version that changes the data shape (`v0_2_16.py`). Most releases have none.

Migrations may only reshape data structures (add empty fields, rename keys, move entries). They must never change relationships, facts, or confidence levels, and never merge people.

## Release checklist

- If a release changes data shape, add a migration file.
