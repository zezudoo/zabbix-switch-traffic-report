import argparse
import csv
import os
import sys
from datetime import datetime, timedelta
from typing import Any

import requests


STATUS_MAP = {
    "1": "UP",
    "2": "DOWN",
    "3": "TESTING",
    "4": "UNKNOWN",
    "5": "DORMANT",
    "6": "NOT_PRESENT",
    "7": "LOWER_LAYER_DOWN",
}


class ZabbixClient:
    def __init__(self, url: str, token: str, timeout: int) -> None:
        self.url = url
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()

    def call(self, method: str, params: dict[str, Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
            "auth": self.token,
        }
        response = self.session.post(self.url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()

        if "error" in body:
            error = body["error"]
            message = error.get("message", "Zabbix API error")
            data = error.get("data", "")
            raise RuntimeError(f"{message}: {data}".strip())

        return body["result"]


def get_required_value(value: str | None, env_name: str, label: str) -> str:
    resolved = value or os.getenv(env_name)
    if not resolved:
        raise SystemExit(f"Missing {label}. Use the CLI option or set {env_name}.")
    return resolved


def get_item(items: list[dict[str, Any]], key_prefix: str, interface: str) -> dict[str, Any] | None:
    target_key = f"{key_prefix}[{interface}]"
    return next((item for item in items if item.get("key_") == target_key), None)


def discover_interfaces(items: list[dict[str, Any]], interface_prefixes: list[str]) -> list[str]:
    interfaces: set[str] = set()

    for item in items:
        key = item.get("key_", "")
        if not key.startswith("ifInOctets[") or not key.endswith("]"):
            continue

        interface = key[len("ifInOctets["):-1]
        if any(interface.startswith(prefix) for prefix in interface_prefixes):
            interfaces.add(interface)

    return sorted(interfaces)


def to_mbps(value: float, value_unit: str) -> float:
    if value_unit == "bits-per-second":
        return value / 1_000_000
    return (value * 8) / 1_000_000


def get_trend_stats(
    client: ZabbixClient,
    itemid: str | None,
    since: int,
    now: int,
    value_unit: str,
) -> tuple[float, float]:
    if not itemid:
        return 0.0, 0.0

    trends = client.call(
        "trend.get",
        {
            "output": ["value_avg", "value_max"],
            "itemids": itemid,
            "time_from": since,
            "time_till": now,
        },
    )

    if not trends:
        return 0.0, 0.0

    peak = max(to_mbps(float(point["value_max"]), value_unit) for point in trends)
    average = sum(to_mbps(float(point["value_avg"]), value_unit) for point in trends) / len(trends)
    return peak, average


def build_report_rows(
    client: ZabbixClient,
    host_name: str,
    days: int,
    interface_prefixes: list[str],
    value_unit: str,
) -> list[list[Any]]:
    hosts = client.call(
        "host.get",
        {
            "output": ["hostid", "host"],
            "filter": {"host": [host_name]},
        },
    )
    if not hosts:
        raise RuntimeError(f"Host not found: {host_name}")

    hostid = hosts[0]["hostid"]
    items = client.call(
        "item.get",
        {
            "output": ["itemid", "name", "key_", "lastvalue"],
            "hostids": hostid,
        },
    )

    now = int(datetime.now().timestamp())
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    rows: list[list[Any]] = []

    for interface in discover_interfaces(items, interface_prefixes):
        in_item = get_item(items, "ifInOctets", interface)
        out_item = get_item(items, "ifOutOctets", interface)
        in_error_item = get_item(items, "ifInErrors", interface)
        out_error_item = get_item(items, "ifOutErrors", interface)
        speed_item = get_item(items, "ifSpeed", interface)
        alias_item = get_item(items, "ifAlias", interface) or get_item(items, "ifDescr", interface)
        status_item = get_item(items, "ifOperStatus", interface)

        capacity_mbps = 0
        if speed_item and speed_item.get("lastvalue"):
            capacity_mbps = int(float(speed_item["lastvalue"])) // 1_000_000

        description = alias_item.get("lastvalue", "") if alias_item else ""
        status = ""
        if status_item and status_item.get("lastvalue") is not None:
            status = STATUS_MAP.get(str(status_item["lastvalue"]), str(status_item["lastvalue"]))

        for direction, traffic_item, error_item in (
            ("Inbound", in_item, in_error_item),
            ("Outbound", out_item, out_error_item),
        ):
            if not traffic_item:
                continue

            peak_mbps, average_mbps = get_trend_stats(
                client=client,
                itemid=traffic_item["itemid"],
                since=since,
                now=now,
                value_unit=value_unit,
            )
            errors = int(float(error_item["lastvalue"])) if error_item and error_item.get("lastvalue") else 0
            peak_percent = round((peak_mbps / capacity_mbps) * 100, 2) if capacity_mbps else 0.0

            rows.append(
                [
                    interface,
                    direction,
                    round(peak_mbps, 2),
                    round(average_mbps, 2),
                    status,
                    errors,
                    capacity_mbps,
                    peak_percent,
                    description,
                ]
            )

    return rows


def write_csv(output_path: str, rows: list[list[Any]]) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "Interface",
                "Direction",
                "Peak Mbps",
                "Average Mbps",
                "Status",
                "Errors",
                "Capacity Mbps",
                "Peak Usage %",
                "Description",
            ]
        )
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export switch traffic data from Zabbix to CSV.")
    parser.add_argument("--url", help="Zabbix API URL. Can also be set with ZABBIX_API_URL.")
    parser.add_argument("--token", help="Zabbix API token. Can also be set with ZABBIX_TOKEN.")
    parser.add_argument("--host", help="Zabbix host name. Can also be set with ZABBIX_HOST_NAME.")
    parser.add_argument("--days", type=int, default=30, help="Number of days to query. Default: 30.")
    parser.add_argument("--output", default="switch_traffic_report.csv", help="Output CSV path.")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds. Default: 60.")
    parser.add_argument(
        "--interface-prefix",
        action="append",
        default=[],
        help="Interface prefix to include. Can be used multiple times.",
    )
    parser.add_argument(
        "--value-unit",
        choices=("octets-per-second", "bits-per-second"),
        default="octets-per-second",
        help="Unit returned by traffic items before Mbps conversion.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    url = get_required_value(args.url, "ZABBIX_API_URL", "Zabbix API URL")
    token = get_required_value(args.token, "ZABBIX_TOKEN", "Zabbix API token")
    host = get_required_value(args.host, "ZABBIX_HOST_NAME", "Zabbix host name")
    interface_prefixes = args.interface_prefix or ["GigabitEthernet", "Ten-GigabitEthernet"]

    client = ZabbixClient(url=url, token=token, timeout=args.timeout)
    rows = build_report_rows(
        client=client,
        host_name=host,
        days=args.days,
        interface_prefixes=interface_prefixes,
        value_unit=args.value_unit,
    )

    if not rows:
        print("No matching interfaces found.", file=sys.stderr)
        return 1

    write_csv(args.output, rows)
    print(f"Report exported to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

