# Relatório de Tráfego de Switch Via Zabbix

Idioma: [English](README.md) | Português (Brasil)

CLI em Python que consulta a API do Zabbix e exporta um relatório CSV com uso
de interfaces de switch, status, capacidade, contadores de erro e descrição.

## Recursos

- Usa a API JSON-RPC do Zabbix.
- Descobre interfaces por prefixo de chave, como `GigabitEthernet` e
  `Ten-GigabitEthernet`.
- Lê dados de tendência de tráfego em uma janela de tempo configurável.
- Exporta pico em Mbps, média em Mbps, status da interface, erros e capacidade.
- Mantém URL da API, token e nome do host fora do controle de versão.

## Requisitos

- Python 3.10 ou mais recente.
- Token da API do Zabbix com permissão de leitura no host alvo.

## Configuração

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Defina as variáveis de ambiente do `.env.example` no shell, no CI ou em um
gerenciador de segredos.

## Uso

```bash
python zabbix_switch_traffic_report.py ^
  --url "%ZABBIX_API_URL%" ^
  --token "%ZABBIX_TOKEN%" ^
  --host "%ZABBIX_HOST_NAME%" ^
  --output relatorio_trafego_completo.csv
```

Usar uma janela e prefixos de interface personalizados:

```bash
python zabbix_switch_traffic_report.py ^
  --days 30 ^
  --interface-prefix GigabitEthernet ^
  --interface-prefix Ten-GigabitEthernet
```

Por padrão, os valores são tratados como octetos por segundo e convertidos para
Mbps. Use `--value-unit bits-per-second` se os valores dos itens no Zabbix já
estiverem em bps.

