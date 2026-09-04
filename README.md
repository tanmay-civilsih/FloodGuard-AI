# FloodGuard-AI

FloodGuard-AI is a scientifically defensible urban flood digital-twin and 0–3 hour nowcasting platform for a Kolkata pilot catchment.

Development is governed by:

- `docs/Urban_Flood_Digital_Twin_Authoritative_20_Sequence_Plan_FROZEN.md`
- `agent.md`

## Current milestone

**Sequence 1 — Platform Foundation, Contracts, Units, Time, Jobs and Events (v0.1)**

Sequence 2 has been implemented and reviewed on the `sequence-2-registry` branch and is ready to be promoted as the next milestone.

## Requirements

- Python **3.12.x**
- Docker Engine + Docker Compose v2

## Local setup

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the pinned dependency set:

```bash
python -m pip install -r requirements.lock
```

Optionally copy the development environment template:

```bash
cp .env.example .env
```

Do not commit `.env` or credentials.

## Verify code and contracts

```bash
python scripts/verify.py
```

## Start platform

```bash
docker compose up -d --build
python scripts/verify.py --services
```

## Scientific scope boundary

Do not infer hydraulic validity from these early releases. Scientific hydraulics begins only in later sequences and remains subject to the frozen validation gates.
