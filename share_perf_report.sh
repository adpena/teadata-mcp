#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./share_perf_report.sh [options]

Generates a small performance/logging report from JSON logs and copies it to your clipboard
so you can paste it into ChatGPT for further optimization.

Options:
  --log-file PATH       Path to JSON log file (default: $TEADATA_LOG_FILE or logs/teadata-mcp.log)
  --lines N             How many recent log lines to analyze (default: 20000)
  --slow-ms N           Threshold for "slow" tool calls (default: 500)
  --top N               Number of slow calls to include (default: 15)
  --no-rotated          Do not include rotated log files (default: include rotated)
  --no-copy             Do not copy to clipboard (still writes report file)
  --stdout              Also print the report to stdout
  --out PATH            Write report to this file (default: logs/share_perf_report_<ts>.txt)
  --no-redact-home      Do not redact $HOME paths in the report
  -h, --help            Show this help

Examples:
  ./share_perf_report.sh
  ./share_perf_report.sh --slow-ms 250 --lines 50000
  ./share_perf_report.sh --log-file logs/teadata-mcp.log --stdout
EOF
}

LINES=20000
SLOW_MS=500
TOP=15
INCLUDE_ROTATED=1
COPY_TO_CLIPBOARD=1
PRINT_STDOUT=0
REDACT_HOME=1
LOG_FILE="${TEADATA_LOG_FILE:-}"
OUT_FILE=""

while [[ $# -gt 0 ]]; do
  case "${1:-}" in
    --log-file)
      LOG_FILE="${2:-}"
      shift 2
      ;;
    --lines)
      LINES="${2:-}"
      shift 2
      ;;
    --slow-ms)
      SLOW_MS="${2:-}"
      shift 2
      ;;
    --top)
      TOP="${2:-}"
      shift 2
      ;;
    --no-rotated)
      INCLUDE_ROTATED=0
      shift
      ;;
    --no-copy)
      COPY_TO_CLIPBOARD=0
      shift
      ;;
    --stdout)
      PRINT_STDOUT=1
      shift
      ;;
    --out)
      OUT_FILE="${2:-}"
      shift 2
      ;;
    --no-redact-home)
      REDACT_HOME=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required for this script." >&2
  exit 1
fi

if [[ -z "${LOG_FILE}" ]]; then
  if [[ -f "logs/teadata-mcp.log" ]]; then
    LOG_FILE="logs/teadata-mcp.log"
  else
    newest="$(ls -1t logs/*.log 2>/dev/null | head -n 1 || true)"
    if [[ -n "${newest}" ]]; then
      LOG_FILE="${newest}"
    fi
  fi
fi

if [[ -z "${LOG_FILE}" || ! -f "${LOG_FILE}" ]]; then
  echo "Error: log file not found. Looked for \$TEADATA_LOG_FILE or logs/teadata-mcp.log" >&2
  exit 1
fi

if ! [[ "${LINES}" =~ ^[0-9]+$ ]] || [[ "${LINES}" -lt 1 ]]; then
  echo "Error: --lines must be a positive integer" >&2
  exit 2
fi
if ! [[ "${SLOW_MS}" =~ ^[0-9]+$ ]] || [[ "${SLOW_MS}" -lt 0 ]]; then
  echo "Error: --slow-ms must be a non-negative integer" >&2
  exit 2
fi
if ! [[ "${TOP}" =~ ^[0-9]+$ ]] || [[ "${TOP}" -lt 1 ]]; then
  echo "Error: --top must be a positive integer" >&2
  exit 2
fi

LOG_FILES=("${LOG_FILE}")
if [[ "${INCLUDE_ROTATED}" -eq 1 ]]; then
  by_mtime_desc=()
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    by_mtime_desc+=("${line}")
  done < <(ls -1t "${LOG_FILE}" "${LOG_FILE}".* 2>/dev/null || true)
  if [[ "${#by_mtime_desc[@]}" -gt 0 ]]; then
    LOG_FILES=()
    for ((i=${#by_mtime_desc[@]}-1; i>=0; i--)); do
      LOG_FILES+=("${by_mtime_desc[i]}")
    done
  fi
fi

timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
if [[ -z "${OUT_FILE}" ]]; then
  OUT_FILE="logs/share_perf_report_${timestamp}.txt"
fi
mkdir -p "$(dirname "${OUT_FILE}")"

tmp_input="$(mktemp)"
trap 'rm -f "${tmp_input}"' EXIT

{
  for f in "${LOG_FILES[@]}"; do
    cat "${f}" 2>/dev/null || true
  done
} | tail -n "${LINES}" > "${tmp_input}"

PY=(python3)
if command -v uv >/dev/null 2>&1; then
  PY=(uv run python)
elif command -v python >/dev/null 2>&1; then
  PY=(python)
fi

versions="$("${PY[@]}" - <<'PY' 2>/dev/null || true
import importlib
import importlib.metadata
import platform
import sys

def version_of(dist: str) -> str:
    try:
        return importlib.metadata.version(dist)
    except Exception:
        return "n/a"

print(f"python={sys.version.split()[0]}")
print(f"platform={platform.platform()}")
print(f"uvicorn={version_of('uvicorn')}")
print(f"starlette={version_of('starlette')}")
print(f"modelcontextprotocol={version_of('modelcontextprotocol')}")
print(f"teadata={version_of('teadata')}")
try:
    m = importlib.import_module("teadata_mcp")
    print(f"teadata_mcp_module={getattr(m, '__file__', 'n/a')}")
except Exception:
    print("teadata_mcp_module=n/a")
PY
)"

report_body="$(
  jq -r -s --argjson slow_ms "${SLOW_MS}" --argjson top "${TOP}" '
    def perf_by_id:
      (map(select(.logger == "teadata_mcp.perf" and .invocation_id?))
        | reduce .[] as $e ({}; .[$e.invocation_id] = $e)
      );

    def tool_ends:
      map(select(.msg == "tool.end" and .invocation_id?));

    def tool_starts:
      map(select(.msg == "tool.start" and .invocation_id?));

    def last_or_null(predicate):
      (map(select(predicate)) | if length > 0 then .[-1] else null end);

    def format_ms(x):
      if (x == null) then "n/a" else (x|tostring) end;

    def redact(v):
      v;

    . as $logs
    | (perf_by_id) as $perf
    | (tool_ends | map(. + {perf: ($perf[.invocation_id] // {})})) as $ends
    | (tool_starts) as $starts
    | {
        engine: {
          warmup_started: ($logs | last_or_null(.msg=="Warming data engine at startup")),
          engine_initialised: ($logs | last_or_null(.msg=="Data engine initialised")),
          warmup_complete: ($logs | last_or_null(.msg=="Data engine warm-up complete"))
        },
        totals: {
          tool_calls: ($ends|length),
          tools: ($ends | map(.tool) | unique | length),
          errors: ($logs | map(select(.level=="ERROR")) | length)
        },
        slow: ($ends
          | map(select((.ms // 0) >= $slow_ms))
          | sort_by(.ms) | reverse
          | .[:$top]
        ),
        recent_errors: ($logs | map(select(.level=="ERROR")) | .[-10:])
      }
    | . as $r
    | [
        "== Engine Warm-up ==",
        (if $r.engine.warmup_started then ("warmup_start_ts=" + ($r.engine.warmup_started.ts // "n/a")) else "warmup_start_ts=n/a" end),
        (if $r.engine.engine_initialised then ("engine_initialised_ms=" + (($r.engine.engine_initialised.ms // "n/a")|tostring)) else "engine_initialised_ms=n/a" end),
        (if $r.engine.warmup_complete then ("warmup_complete_ms=" + (($r.engine.warmup_complete.ms // "n/a")|tostring)) else "warmup_complete_ms=n/a" end),
        "",
        "== Totals ==",
        ("tool_calls=" + ($r.totals.tool_calls|tostring)),
        ("unique_tools=" + ($r.totals.tools|tostring)),
        ("error_lines=" + ($r.totals.errors|tostring)),
        "",
        ("== Slow Tool Calls (ms >= " + ($slow_ms|tostring) + ") =="),
        "ms\\ttool\\tstatus\\tpayload_bytes\\trss_delta_mb\\tinvocation_id\\tpayload_summary\\targs_summary",
        ($r.slow[]?
          | [
              (.ms|tostring),
              (.tool // ""),
              (.status // ""),
              ((.perf.payload_bytes // "")|tostring),
              (if (.perf.rss_delta_bytes? and (.perf.rss_delta_bytes|type)=="number") then ((.perf.rss_delta_bytes / 1048576)|floor|tostring) else "" end),
              (.invocation_id // ""),
              ((.payload // {})|tojson),
              ((.arguments // {})|tojson)
            ]
          | @tsv
        ),
        "",
        "== Recent Errors (last 10) ==",
        ($r.recent_errors[]? | ("[" + (.ts // "n/a") + "] " + (.logger // "n/a") + " " + (.msg // "n/a"))),
        "",
        "== Excerpts (tool.start/tool.end/perf for slow calls) ==",
        ($r.slow | map(.invocation_id) | unique) as $ids
        | (
            $ids[]? as $id
            | "---- invocation_id=" + $id,
              ($logs
                | map(select(.invocation_id? == $id and (.msg=="tool.start" or .msg=="tool.end" or .logger=="teadata_mcp.perf")))
                | .[]?
                | tojson
              )
          )
      ]
    | join("\n")
  ' "${tmp_input}" 2>/dev/null || echo "Failed to parse logs (are they JSON lines?)."
)"

{
  echo "TEA Data MCP Performance Report"
  echo "generated_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "log_file=${LOG_FILE}"
  echo "log_files_included=$(printf "%s " "${LOG_FILES[@]}")"
  echo "lines_included=${LINES}"
  echo ""
  echo "== Environment =="
  echo "${versions:-python=n/a}"
  echo ""
  echo "== Relevant Env Vars (TEADATA_*) =="
  env | rg -n '^TEADATA_' || true
  echo ""
  echo "${report_body}"
} > "${OUT_FILE}"

if [[ "${REDACT_HOME}" -eq 1 && -n "${HOME:-}" ]]; then
  # macOS sed needs an explicit backup suffix when using -i.
  sed -i.bak "s|${HOME//|/\\|}|<HOME>|g" "${OUT_FILE}" || true
  rm -f "${OUT_FILE}.bak" || true
fi

copied=0
if [[ "${COPY_TO_CLIPBOARD}" -eq 1 ]]; then
  if command -v pbcopy >/dev/null 2>&1; then
    pbcopy < "${OUT_FILE}"
    copied=1
  elif command -v wl-copy >/dev/null 2>&1; then
    wl-copy < "${OUT_FILE}"
    copied=1
  elif command -v xclip >/dev/null 2>&1; then
    xclip -selection clipboard < "${OUT_FILE}"
    copied=1
  fi
fi

echo "Report written to: ${OUT_FILE}"
if [[ "${COPY_TO_CLIPBOARD}" -eq 0 ]]; then
  echo "Clipboard copy skipped (--no-copy)."
elif [[ "${copied}" -eq 1 ]]; then
  echo "Copied report to clipboard. Paste it into ChatGPT."
else
  echo "Clipboard copy not available (pbcopy/wl-copy/xclip not found)."
fi

if [[ "${PRINT_STDOUT}" -eq 1 ]]; then
  echo ""
  cat "${OUT_FILE}"
fi
