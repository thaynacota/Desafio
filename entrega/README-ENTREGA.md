# Entrega — Consolidador de reservas de hotel (Onfly)

## Resumo

O CLI gerava o relatório com números errados: noites negativas (`total_room_nights = -33`), diária média zerada, totais em BRL errados quando o pagamento era em USD ou EUR, reservas `NO_SHOW` entrando nos totais e o ranking de hotéis invertido.

Encontrei **4 defeitos**, todos dentro de `src/onfly_report/`. Depois das correções, os 5 testes fornecidos passam e nenhum teste foi alterado.

## Defeitos corrigidos

| # | Arquivo | Sintoma no relatório | Causa raiz (uma frase) |
|---|---------|----------------------|------------------------|
| 1 | `currency_converter.py` | `total_amount_brl` e `total_brl` errados para reservas em USD/EUR | A conversão **dividia** o valor pela taxa (`amount / rate`), quando o certo é **multiplicar** (`amount * rate_to_brl`). |
| 2 | `stay_calculator.py` | `total_room_nights` negativo (-33), `room_nights` negativo em `by_month` e `average_nightly_rate_brl` zerado | As noites eram calculadas subtraindo só o dia do mês (`checkout.day - checkin.day`), o que dá negativo quando a estadia atravessa a virada de mês ou de ano. |
| 3 | `status_policy.py` | Valores e noites de reservas `NO_SHOW` entravam nos totais | O filtro de reserva faturável só excluía `CANCELLED` (`status != "CANCELLED"`), então `NO_SHOW` passava como faturável. |
| 4 | `report_builder.py` | `top_hotels` vinha do menor para o maior valor | A ordenação usava `amount` em ordem crescente, e o contrato pede `total_brl` em ordem **decrescente**, com desempate por `hotel_id` crescente. |

### 1. `currency_converter.py` — conversão de câmbio invertida

```python
# Antes
return Decimal(str(float(amount) / float(rate)))
# Depois
return Decimal(amount * rate)
```

`rate_to_brl` diz quantos reais vale uma unidade da moeda estrangeira. Para converter para BRL, multiplica-se o valor pela taxa, como pede o README (`amount * rate_to_brl`). Dividir dava valores muito menores do que os reais para USD e EUR. Isso distorcia `total_amount_brl`, o `total_brl` de cada mês e o ranking de hotéis.

### 2. `stay_calculator.py` — noites negativas na virada do mês

```python
# Antes
return (checkout.days - checkin.days) * rooms
# Depois
return (checkout - checkin).days * rooms
```

O código subtraía apenas os números dos dias. Numa estadia de 30/04 a 03/05, a conta era `3 - 30 = -27`, quando o certo são 3 noites. Agora as duas datas são subtraídas inteiras, o que gera um `timedelta`, e só depois se pega `.days`. Isso respeita mês e ano e segue a regra não inclusiva do README (check-in 10/01 e check-out 13/01 = 3 noites).

Este defeito também explicava o `average_nightly_rate_brl` zerado, porque o total de noites negativo quebrava a divisão `total_amount_brl / total_room_nights`. Depois da correção, a média voltou a ser calculada normalmente.

### 3. `status_policy.py` — `NO_SHOW` contado como faturável

```python
# Antes
return status != "CANCELLED"
# Depois
return status not in ("CANCELLED", "NO_SHOW")
```

Pelo README, só `CONFIRMED` é faturável. `CANCELLED` e `NO_SHOW` contam em `total_reservations` e nas contagens por status, mas não entram em noites, valores, `by_month` nem `top_hotels`. Como o filtro só barrava `CANCELLED`, as reservas `NO_SHOW` entravam nos totais financeiros e de noites. Usei `not in` com uma tupla para deixar a regra mais legível e não repetir a variável `status`.

### 4. `report_builder.py` — ranking de hotéis em ordem crescente

```python
# Antes
ranked_hotels = sorted(hotels.items(), key=lambda item: (item[1]["amount"], item[0]))
# Depois
ranked_hotels = sorted(hotels.items(), key=lambda item: (-float(item[1]["amount"]), item[0]))
```

Negar o valor inverte a ordem dentro do `sorted` crescente: 1200 vira -1200 e 882 vira -882, então o hotel de maior valor fica primeiro. O segundo elemento da chave (`item[0]`, o `hotel_id`) foi mantido como desempate em ordem crescente (H01 antes de H04), como pede o contrato.

## Como investiguei

1. **Li as regras de negócio do README** e separei o que o relatório deveria seguir: status, cálculo de noites, câmbio, totais, ordem do processamento, exatidão e ordenação.
2. **Rodei o CLI e comparei o `output/report.json` com essas regras.** Listei os problemas:
   - `total_room_nights` negativo (-33), o que não pode existir;
   - `average_nightly_rate_brl` zerado;
   - `total_amount_brl` com valor errado;
   - `room_nights` negativo em `by_month` (2025-01);
   - `total_brl` errado quando o pagamento era em USD ou EUR;
   - `top_hotels` em ordem crescente, quando o pedido é decrescente.
3. **Percorri os módulos de `src/onfly_report/` um a um**, ligando cada sintoma ao arquivo responsável:
   - `csv_rate_repository.py`: já converte as taxas para `Decimal`. Nenhum defeito.
   - `csv_reservation_repository.py`: leitura correta. Nenhum defeito.
   - `row_parser.py`: conversão de tipos correta. Nenhum defeito.
   - `currency_converter.py`: defeito 1.
   - `stay_calculator.py`: defeito 2.
   - `status_policy.py`: defeito 3.
   - `report_builder.py`: defeito 4.
4. **Corrigi um defeito por vez e rodei `pytest -q` depois de cada correção**, para confirmar que cada mudança resolvia um problema sem quebrar outro:

   | Correção aplicada | Testes passando |
   |-------------------|-----------------|
   | `currency_converter.py` | 2 de 5 |
   | `stay_calculator.py` | 3 de 5 |
   | `status_policy.py` | 4 de 5 |
   | `report_builder.py` | **5 de 5** |

Alterei só os arquivos em `src/onfly_report/`. Os testes fornecidos, o comando do CLI, o schema do relatório e os arquivos `data/reservas_hoteis.csv` e `data/taxas_cambio.csv` continuam iguais.

## Como validar

Requisitos: Python 3.11+.

```bash
python3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

**1. Testes fornecidos**

```bash
pytest -q
```

**2. Relatório completo**

```bash
PYTHONPATH=src python -m onfly_report \
  --input data/reservas_hoteis.csv \
  --rates data/taxas_cambio.csv \
  --output output/report.json
```

O relatório é gravado em `output/report.json`. Confira que `total_room_nights` é positivo, que `average_nightly_rate_brl` é diferente de `"0.00"` e que `top_hotels` está em ordem decrescente de `total_brl`.

**3. Amostra de validação**

```bash
PYTHONPATH=src python -m onfly_report \
  --input data/exemplo-validacao.csv \
  --rates data/taxas_cambio.csv \
  --output output/exemplo.json
```

O `output/exemplo.json` deve bater com a tabela do README do desafio:

| Campo | Esperado |
|-------|----------|
| `total_reservations` | 12 |
| `confirmed_reservations` | 9 |
| `cancelled_reservations` | 2 |
| `no_show_reservations` | 1 |
| `total_room_nights` | 28 |
| `total_amount_brl` | 7566.00 |
| `average_nightly_rate_brl` | 270.21 |
| `by_month` | 2025-01: 8 reservas, 25 noites, 6684.00 · 2025-02: 1 reserva, 3 noites, 882.00 |
| `top_hotels` | H01 1200.00 · H02 1084.00 · H12 1000.00 · H10 900.00 · H09 882.00 |

## Resultado do pytest

```
$ pytest -q
.....                                                                    [100%]
5 passed in 0.97s
```