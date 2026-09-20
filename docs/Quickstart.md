# Quickstart

The canonical executable Sense quickstart is maintained at the repository root:

[Open QUICKSTART.md](../QUICKSTART.md)

For peaq users with an already configured wallet/client, live verification is:

```bash
sense-peaq verify-live --machine-id 42
```

For a completely fresh local peaq test environment:

```bash
git clone https://github.com/OntosWorld/Sense.git \
  && cd Sense \
  && bash scripts/peaq-live-test.sh
```

The helper handles setup and pauses only for wallet funding and the machine ID.

Keeping one canonical executable quickstart avoids examples drifting away from
the public SDK.

For deeper capability design guidance, see
[Capability-Guide.md](Capability-Guide.md).
