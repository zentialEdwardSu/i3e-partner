#!/usr/bin/env bash

# Usage (source or run):
#   source d:/LocalWorkdock/ieeecarwler/scripts/db_shell.sh
#   ieee_db_shell -p path/to/db            # interactive sqlite shell
#   ieee_db_shell -e "SELECT * FROM author" # run SQL and exit
#   ./db_shell.sh -p path -e "SELECT ..."   # executable mode
#
# Priority for DB path: -p argument > env DB_PATH > default "ieee.db"

ieee_db_shell() {
	local DB=""
	local SQL=""
	local INTERACTIVE=1

	# parse args
	while getopts ":p:e:hi" opt; do
		case "$opt" in
			p) DB="$OPTARG" ;;
			e) SQL="$OPTARG"; INTERACTIVE=0 ;;
			h) 
				cat <<'EOF'
ieee_db_shell - simple sqlite interactive helper

Options:
  -p PATH    Database file path (overrides DB_PATH env)
  -e SQL     Execute SQL and exit (non-interactive)
  -i         Force interactive mode
  -h         Show this help
If no -p provided, uses $DB_PATH or "ieee.db".
EOF
				return 0
				;;
			i) INTERACTIVE=1 ;;
			\?) echo "Invalid option: -$OPTARG" >&2; return 2 ;;
			:) echo "Option -$OPTARG requires an argument." >&2; return 2 ;;
		esac
	done
	shift $((OPTIND-1))

	# decide DB path
	if [ -z "$DB" ]; then
		if [ -n "${DB_PATH:-}" ]; then
			DB="$DB_PATH"
		else
			DB="ieee.db"
		fi
	fi

	# check sqlite3 existence
	if ! command -v sqlite3 >/dev/null 2>&1; then
		echo "sqlite3 not found in PATH. Please install sqlite3." >&2
		return 3
	fi

	# ensure DB file exists for interactive mode (sqlite will create file on first write otherwise)
	if [ ! -f "$DB" ] && [ "$INTERACTIVE" -eq 1 ]; then
		echo "Database file '$DB' does not exist. A new file may be created when writing."
	fi

	if [ -n "$SQL" ]; then
		# run SQL and exit, enable headers/column mode
		printf "%s\n" "$SQL" | sqlite3 -header -column "$DB"
		return $?
	fi

	# interactive shell
	# set useful defaults: header + column, .timer on for performance info
	echo "Opening sqlite interactive shell for DB: $DB"
	echo "  - Type .help inside sqlite3 for commands, .quit to exit."
	sqlite3 -header -column "$DB"
}

# If script executed directly, call function with provided args
if [ "${BASH_SOURCE[0]}" = "$0" ] || [ "${0##*/}" = "db_shell.sh" ]; then
	ieee_db_shell "$@"
fi

# Suggestion to add to shell rc:
# alias ieee-sql='source d:/LocalWorkdock/ieeecarwler/scripts/db_shell.sh >/dev/null 2>&1 || true; ieee_db_shell'
