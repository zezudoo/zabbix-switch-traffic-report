# Zabbix Switch Traffic Report

Language: English | [Português (Brasil)](README.pt-BR.md)

Python CLI that queries the Zabbix API and exports a CSV report with switch
interface traffic, status, capacity, error counters, and descriptions.

## Features

- Uses the Zabbix JSON-RPC API.
- Discovers interfaces by key prefix, such as `GigabitEthernet` and
  `Ten-GigabitEthernet`.
- Reads traffic trend data over a configurable time window.
- Exports peak Mbps, average Mbps, interface status, errors, and capacity.
- Keeps the API URL, token, and host name out of version control.

## Requirements

- Python 3.10 or later.
- Zabbix API token with read access to the target host.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set the variables from `.env.example` in your shell, CI pipeline, or secret
manager.

## Usage

```bash
python zabbix_switch_traffic_report.py ^
  --url "%ZABBIX_API_URL%" ^
  --token "%ZABBIX_TOKEN%" ^
  --host "%ZABBIX_HOST_NAME%" ^
  --output full_traffic_report.csv
```

Use a custom time window and interface prefixes:

```bash
python zabbix_switch_traffic_report.py ^
  --days 30 ^
  --interface-prefix GigabitEthernet ^
  --interface-prefix Ten-GigabitEthernet
```

By default, values are treated as octets per second and converted to Mbps. Use
`--value-unit bits-per-second` if your Zabbix item values are already in bps.
