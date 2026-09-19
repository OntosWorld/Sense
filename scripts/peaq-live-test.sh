#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/OntosWorld/Sense.git"
BRANCH="fix/sdk-alignment-peaq"
TARGET_DIR="${SENSE_DIR:-Sense}"
RPC_URL="${PEAQOS_RPC_URL:-https://peaq-agung.api.onfinality.io/public}"
DEPLOYMENT_ID="${TOKENOMICS_DEPLOYMENT_ID:-agung-2026-08-28}"

say() {
  printf '\n%s\n' "$*"
}

die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found."
}

prompt() {
  local message="$1"
  local value
  printf "%s" "$message" >/dev/tty
  IFS= read -r value </dev/tty
  printf "%s" "$value"
}

need_cmd git

PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
[ -n "$PYTHON" ] || die "Python 3.10+ is required."

"$PYTHON" - <<'PY' || die "Python 3.10+ is required."
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY

say "1/7  Preparing Sense repository"

if git rev-parse --show-toplevel >/dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
  cd "$REPO_ROOT"
elif [ -d "$TARGET_DIR/.git" ]; then
  cd "$TARGET_DIR"
else
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$TARGET_DIR"
  cd "$TARGET_DIR"
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  die "Sense checkout has uncommitted changes. Commit/stash them first."
fi

git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

CURRENT_BRANCH="$(git branch --show-current)"
[ "$CURRENT_BRANCH" = "$BRANCH" ] || die "Expected branch $BRANCH, got $CURRENT_BRANCH."

say "2/7  Creating Python environment"

"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -e packages/Sense-peaq
python -m pip install python-dotenv pytest

VERSIONS="$(python - <<'PY'
import sense_ai
import sense_peaq
print(f"{sense_ai.__version__} {sense_peaq.__version__}")
PY
)"
[ "$VERSIONS" = "0.3.0 0.3.0" ] || die "Expected Sense 0.3.0 packages, got: $VERSIONS"
say "Sense versions: $VERSIONS"

say "3/7  Preparing local test wallet"

# .env is already ignored by the repository, but also exclude it locally as a second guard.
grep -qxF ".env" .git/info/exclude 2>/dev/null || printf ".env\n" >> .git/info/exclude

WALLET_ADDRESS="$(
  PEAQOS_RPC_URL="$RPC_URL" TOKENOMICS_DEPLOYMENT_ID="$DEPLOYMENT_ID" python - <<'PY'
from __future__ import annotations

import os
import re
from pathlib import Path

from eth_account import Account

env_path = Path(".env")
existing: dict[str, str] = {}

if env_path.exists():
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        existing[key.strip()] = value.strip()

private_key = existing.get("PEAQOS_PRIVATE_KEY")
if private_key:
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", private_key):
        raise SystemExit("Existing PEAQOS_PRIVATE_KEY in .env is not a valid 0x-prefixed 32-byte key.")
    account = Account.from_key(private_key)
else:
    account = Account.create()
    private_key = "0x" + account.key.hex()

machine_id = existing.get("SENSE_PEAQ_MACHINE_ID", "")

values = {
    "PEAQOS_RPC_URL": os.environ["PEAQOS_RPC_URL"],
    "PEAQOS_PRIVATE_KEY": private_key,
    "TOKENOMICS_DEPLOYMENT_ID": os.environ["TOKENOMICS_DEPLOYMENT_ID"],
    "SENSE_RUN_LIVE_PEAQ": "1",
    "SENSE_PEAQ_MACHINE_ID": machine_id,
}

env_path.write_text(
    "".join(f"{key}={value}\n" for key, value in values.items())
)
env_path.chmod(0o600)

print(account.address)
PY
)"

say "Test wallet address:"
printf '%s\n' "$WALLET_ADDRESS"
say "The private key was written only to Sense/.env with mode 600. It is not printed."

say "4/7  Waiting for testnet funding"
printf '%s\n' "Fund this address with Agung test PEAQ:" "$WALLET_ADDRESS"

while true; do
  prompt "After funding it, press Enter to check the balance..." >/dev/null

  BALANCE_WEI="$(
    python - <<'PY'
from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3
import os

load_dotenv()
rpc = os.environ["PEAQOS_RPC_URL"]
key = os.environ["PEAQOS_PRIVATE_KEY"]
address = Account.from_key(key).address
w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
if not w3.is_connected():
    raise SystemExit("Could not connect to peaq RPC.")
print(w3.eth.get_balance(address))
PY
  )"

  if [ "$BALANCE_WEI" != "0" ]; then
    say "Wallet funded. Balance (wei): $BALANCE_WEI"
    break
  fi

  printf '%s\n' "Balance is still zero. Fund the address and press Enter again." >/dev/tty
done

say "5/7  Configuring machine ID"

MACHINE_ID="$(python - <<'PY'
from dotenv import dotenv_values
print(dotenv_values(".env").get("SENSE_PEAQ_MACHINE_ID", "") or "")
PY
)"

if [ -z "$MACHINE_ID" ]; then
  MACHINE_ID="$(prompt "Enter the existing peaq machine ID controlled by this wallet: ")"
fi

case "$MACHINE_ID" in
  ''|*[!0-9]*) die "Machine ID must be a base-10 integer." ;;
esac

python - "$MACHINE_ID" <<'PY'
from pathlib import Path
import sys

machine_id = sys.argv[1]
path = Path(".env")
lines = path.read_text().splitlines()
out = []
found = False
for line in lines:
    if line.startswith("SENSE_PEAQ_MACHINE_ID="):
        out.append(f"SENSE_PEAQ_MACHINE_ID={machine_id}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"SENSE_PEAQ_MACHINE_ID={machine_id}")
path.write_text("\n".join(out) + "\n")
path.chmod(0o600)
PY

say "6/7  Running wallet-free peaq checks"
python -m pytest tests/e2e/test_peaq_integration.py -v

say "7/7  Submitting the real Sense Activity Event"
sense-peaq verify-live --machine-id "$MACHINE_ID" --yes

say "Done."
printf '%s\n' "Wallet: $WALLET_ADDRESS"
printf '%s\n' "Machine ID: $MACHINE_ID"
printf '%s\n' "Network RPC: $RPC_URL"
printf '%s\n' "Keep Sense/.env private. Never commit or share it."
