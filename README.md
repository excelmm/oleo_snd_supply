# Global Oleochemicals

Run `Launch Global Oleochemicals.bat` on Windows, or run `python serve.py --open` with Python 3.10 or later. The dashboard runs at `http://127.0.0.1:8767/`.

## Local capacity records

Save capacity records in `data/capacities.json` and restart the server. The JSON object has a `records` array. Each record uses a unique positive integer `id` and text fields `region`, `country`, `state`, `city`, `parent`, and `company`. Use an empty string for an unknown text field. The optional `coords` array contains longitude followed by latitude.

The `acid` and `alcohol` arrays contain 12 annual capacities in kt/yr, in order from 2019 through 2030. Use `0` for zero capacity and `null` for an unknown value. The top-level object can also provide a `source` label, an `initialRecordId`, and `locationSources` entries with a `label` and an HTTPS `url`.

Edits are saved in `data/capacity-edits.sqlite3`. Keep the same record IDs when updating the local snapshot so saved edits stay associated with their records.
