# i3e-partner

Use this tool to automatically collect information about papers and authors at the same speed as manual collection — without manual work.

## Statement

1. This tool uses a fully synchronous API that mimics manual interaction, providing comparable efficiency without unintended overhead on the website.
2. This tool does not grant any permissions beyond what is accessible manually by the user (it works only with appropriate institutional access).

## Install

> better install `uv`

clone the repo, run `uv sync`(in case you have uv installed), or just install `playwright`, run `(uv run(if use uv))playwright install` to install broswer drivers, and you are ready to go.

## Usage

Always initialize the local database first:

```bash
python main.py db init
```

You can set the database path via the environment variable `DB_PATH`. If not set, the default is `ieee.db`.

There are 3 plugins supported so far:
1. `cache` — manage cache data (see `python main.py cache -h`)
2. `db` — manage the database: init / export / search (see `python main.py db -h`)
3. `ieee` — download publication or author information (see `python main.py ieee -h`)

Always use `-h` on subcommands for detailed help. For example, `python main.py ieee pub -h` will show:

```bash
usage: main.py ieee pub [-h] --publication-id PUBLICATION_ID [--save-db] [--db-path DB_PATH]
                        [--cache-ttl CACHE_TTL] [--strategy {AO,AN,M}]

options:
  -h, --help            show this help message and exit
  --publication-id PUBLICATION_ID
                        Publication ID
  --save-db             Save to database
  --db-path DB_PATH     Database path
  --cache-ttl CACHE_TTL
                        Cache TTL in seconds (optional)
  --strategy {AO,AN,M}  Conflict resolution strategy when saving (AO=Always Old, AN=Always New, M=Manual)
```

## License

MIT — see the License file for details.