"""Testes adicionais (caixa-preta) do CLI onfly_report.

Rodam o CLI como subprocesso, exatamente como o README descreve, e verificam
o contrato: valores da amostra, schema, formato do dinheiro, ordenação,
consistência dos totais e códigos de saída.
"""

import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATA = ROOT / "data"
INPUT = DATA / "reservas_hoteis.csv"
SAMPLE = DATA / "exemplo-validacao.csv"
RATES = DATA / "taxas_cambio.csv"

MONEY_RE = re.compile(r"^-?\d+\.\d{2}$")


def run_cli(*args, cwd=ROOT):
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *map(str, args)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def generate(tmp_path, input_csv=INPUT, *extra):
    out = tmp_path / "report.json"
    result = run_cli("--input", input_csv, "--rates", RATES, "--output", out, *extra)
    assert result.returncode == 0, result.stderr
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def full_report(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("full"))


@pytest.fixture(scope="module")
def sample_report(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("sample"), SAMPLE)


# ---------------------------------------------------------------- amostra

def test_amostra_summary(sample_report):
    assert sample_report["summary"] == {
        "total_reservations": 12,
        "confirmed_reservations": 9,
        "cancelled_reservations": 2,
        "no_show_reservations": 1,
        "total_room_nights": 28,
        "total_amount_brl": "7566.00",
        "average_nightly_rate_brl": "270.21",
    }


def test_amostra_by_month(sample_report):
    assert sample_report["by_month"] == [
        {"month": "2025-01", "reservations": 8, "room_nights": 25, "total_brl": "6684.00"},
        {"month": "2025-02", "reservations": 1, "room_nights": 3, "total_brl": "882.00"},
    ]


def test_amostra_top_hotels(sample_report):
    assert sample_report["top_hotels"] == [
        {"hotel_id": "H01", "hotel_name": "Hotel Aurora Paulista", "room_nights": 3, "total_brl": "1200.00"},
        {"hotel_id": "H02", "hotel_name": "Hotel Mirante", "room_nights": 2, "total_brl": "1084.00"},
        {"hotel_id": "H12", "hotel_name": "Hotel Miami Beach", "room_nights": 1, "total_brl": "1000.00"},
        {"hotel_id": "H10", "hotel_name": "Hotel Madrid, Gran Vía", "room_nights": 4, "total_brl": "900.00"},
        {"hotel_id": "H09", "hotel_name": "Hotel Lisboa, Centro", "room_nights": 3, "total_brl": "882.00"},
    ]


# ---------------------------------------------------------------- schema

def test_schema_exato(full_report):
    assert set(full_report) == {"report_version", "generated_at", "summary", "by_month", "top_hotels"}
    assert full_report["report_version"] == "1.0"
    assert set(full_report["summary"]) == {
        "total_reservations", "confirmed_reservations", "cancelled_reservations",
        "no_show_reservations", "total_room_nights", "total_amount_brl",
        "average_nightly_rate_brl",
    }
    for m in full_report["by_month"]:
        assert set(m) == {"month", "reservations", "room_nights", "total_brl"}
        assert re.fullmatch(r"\d{4}-\d{2}", m["month"])
    for h in full_report["top_hotels"]:
        assert set(h) == {"hotel_id", "hotel_name", "room_nights", "total_brl"}


def test_tipos_inteiros(full_report):
    s = full_report["summary"]
    for k in ("total_reservations", "confirmed_reservations", "cancelled_reservations",
              "no_show_reservations", "total_room_nights"):
        assert type(s[k]) is int, k
    for item in full_report["by_month"] + full_report["top_hotels"]:
        assert type(item["room_nights"]) is int


def test_dinheiro_string_duas_casas(full_report):
    s = full_report["summary"]
    valores = [s["total_amount_brl"], s["average_nightly_rate_brl"]]
    valores += [m["total_brl"] for m in full_report["by_month"]]
    valores += [h["total_brl"] for h in full_report["top_hotels"]]
    for v in valores:
        assert isinstance(v, str) and MONEY_RE.match(v), v


def test_generated_at_offset_sao_paulo(full_report):
    assert full_report["generated_at"].endswith("-03:00")


# ---------------------------------------------------------------- ordenação

def test_by_month_ascendente(full_report):
    meses = [m["month"] for m in full_report["by_month"]]
    assert meses == sorted(meses)
    assert len(meses) == len(set(meses))


def test_top_hotels_ordem_e_desempate(full_report):
    chaves = [(-Decimal(h["total_brl"]), h["hotel_id"]) for h in full_report["top_hotels"]]
    assert chaves == sorted(chaves)


# ---------------------------------------------------------------- consistência

def test_contagens_por_status_somam_total(full_report):
    s = full_report["summary"]
    assert (s["confirmed_reservations"] + s["cancelled_reservations"]
            + s["no_show_reservations"]) == s["total_reservations"]


def test_by_month_soma_bate_com_summary(full_report):
    s = full_report["summary"]
    meses = full_report["by_month"]
    assert sum(m["reservations"] for m in meses) == s["confirmed_reservations"]
    assert sum(m["room_nights"] for m in meses) == s["total_room_nights"]
    soma = sum(Decimal(m["total_brl"]) for m in meses)
    # cada mês é arredondado separadamente: tolera 1 centavo por mês
    assert abs(soma - Decimal(s["total_amount_brl"])) <= Decimal("0.01") * len(meses)


def test_media_diaria(full_report):
    s = full_report["summary"]
    if s["total_room_nights"] == 0:
        assert s["average_nightly_rate_brl"] == "0.00"
    else:
        media = Decimal(s["total_amount_brl"]) / s["total_room_nights"]
        assert abs(media - Decimal(s["average_nightly_rate_brl"])) <= Decimal("0.01")


# ---------------------------------------------------------------- --top

@pytest.mark.parametrize("n", [1, 3])
def test_top_limita_quantidade(tmp_path, n):
    r = generate(tmp_path, INPUT, "--top", n)
    assert len(r["top_hotels"]) == n


def test_top_padrao_e_5(full_report):
    assert len(full_report["top_hotels"]) <= 5


def test_top_grande_retorna_todos_sem_erro(tmp_path):
    r = generate(tmp_path, SAMPLE, "--top", 1000)
    nomes = [h["hotel_id"] for h in r["top_hotels"]]
    assert len(nomes) == len(set(nomes)) >= 5


def test_top_1_e_prefixo_do_top_5(tmp_path, full_report):
    r = generate(tmp_path, INPUT, "--top", 1)
    assert r["top_hotels"] == full_report["top_hotels"][:1]


# ---------------------------------------------------------------- saída

def test_output_padrao(tmp_path):
    result = run_cli("--input", INPUT, "--rates", RATES, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "output" / "report.json").is_file()


def test_cria_diretorio_de_saida(tmp_path):
    out = tmp_path / "a" / "b" / "report.json"
    result = run_cli("--input", INPUT, "--rates", RATES, "--output", out)
    assert result.returncode == 0, result.stderr
    assert out.is_file()


def test_resumo_no_stdout(tmp_path):
    result = run_cli("--input", INPUT, "--rates", RATES, "--output", tmp_path / "r.json")
    assert result.returncode == 0
    assert result.stdout.strip() != ""


def test_execucao_deterministica(tmp_path):
    a = generate(tmp_path / "1")
    b = generate(tmp_path / "2")
    a.pop("generated_at")
    b.pop("generated_at")
    assert a == b


# ---------------------------------------------------------------- códigos de saída

@pytest.mark.parametrize("top", ["0", "-1", "abc", "1.5"])
def test_top_invalido_sai_com_2(tmp_path, top):
    r = run_cli("--input", INPUT, "--rates", RATES, "--output", tmp_path / "r.json", "--top", top)
    assert r.returncode == 2


def test_sem_input_sai_com_2(tmp_path):
    r = run_cli("--rates", RATES, "--output", tmp_path / "r.json")
    assert r.returncode == 2


def test_sem_rates_sai_com_2(tmp_path):
    r = run_cli("--input", INPUT, "--output", tmp_path / "r.json")
    assert r.returncode == 2


def test_input_inexistente_sai_com_2(tmp_path):
    r = run_cli("--input", tmp_path / "nao_existe.csv", "--rates", RATES,
                "--output", tmp_path / "r.json")
    assert r.returncode == 2


def test_rates_inexistente_sai_com_2(tmp_path):
    r = run_cli("--input", INPUT, "--rates", tmp_path / "nao_existe.csv",
                "--output", tmp_path / "r.json")
    assert r.returncode == 2


def test_argumento_desconhecido_sai_com_2(tmp_path):
    r = run_cli("--input", INPUT, "--rates", RATES, "--output", tmp_path / "r.json", "--xyz")
    assert r.returncode == 2