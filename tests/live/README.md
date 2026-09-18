# Live integration tests

Live tests are intentionally separate from normal CI because they require
network access, credentials and potentially gas.

## peaq Activity Event

Configure the official peaqOS environment first, including the appropriate RPC,
wallet and contract addresses.

Then set:

```bash
export SENSE_RUN_LIVE_PEAQ=1
export SENSE_PEAQ_MACHINE_ID=<decimal machine id>
```

Install the adapter and run:

```bash
pip install -e .
pip install -e packages/Sense-peaq
pip install python-dotenv

pytest tests/live/test_peaq_activity_event.py -v -s
```

This submits a real self-reported Activity Event using
`PeaqosClient.from_env()`. Do not enable this flag in ordinary CI.
