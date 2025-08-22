# i3e-partner

Use this tool to automatically collect information about papers and authors at the same speed as manual collection — without manual work.

## Statement

1. This tool uses a fully synchronous API that mimics manual interaction, providing comparable efficiency without unintended overhead on the website.
2. This tool does not grant any permissions beyond what is accessible manually by the user (it works only with appropriate institutional access).

## Install

> better install `uv`

clone the repo, run `uv sync`(in case you have uv installed), or just install `playwright`, run `(uv run(if use uv))playwright install` to install broswer drivers, and you are ready to go.

## Usage

There are 2 plugins supported so far:
1. `cache` — manage cache data (see `python main.py cache -h`)
2. `ieee` — download publication or author information (see `python main.py ieee -h`)

Always use `-h` on subcommands for detailed help. For example, `python main.py ieee pub -h` will show:

```bash
usage: main.py ieee author [-h] --author-id AUTHOR_ID [--no-pub-list] [--start-year START_YEAR] [--end-year END_YEAR] [--cache-ttl CACHE_TTL] [--save {json,db}] [--path PATH]
                           [--strategy {AO,AN,M}]

options:
  -h, --help            show this help message and exit
  --author-id AUTHOR_ID
                        Author ID
  --no-pub-list         Do not fetch published works' information list
  --start-year START_YEAR
                        Start year
  --end-year END_YEAR   End year
  --cache-ttl CACHE_TTL
                        Cache TTL in seconds (optional)
  --save {json,db}      Save result to db or single json file
  --path PATH           Path to save the file, if save db, it's the path to the db file, otherwise it will overwrite the path to the json file
  --strategy {AO,AN,M}  Conflict resolution strategy when saving (AO=Always Old, AN=Always New, M=Manual)
```

For example, to download author with ieee id `37290266200` and his publications between 2024 and 2025, then save to json, just run

```bash
python main.py ieee author --author-id 37290266200 --start-year 2024 --end-year 2025 --save json
```

> Notices: The script may exit abnormally due to failure to properly handle page load timeouts. This is currently being addressed, but thanks to the use of the cache module, you can re-run the command and resume work from the terminal.

## License

MIT — see the License file for details.