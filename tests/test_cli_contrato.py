import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "exemplo-validacao.csv"
RATES = ROOT / "data" / "taxas_cambio.csv"
MONEY = re.compile(r"^-?\d+\.\d{2}$")


def run_cli(*args):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "onfly_report", *args],
        cwd=ROOT, env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )


def gerar(tmp_path, *extra):
    out = tmp_path / "report.json"
    r = run_cli("--input", str(SAMPLE), "--rates", str(RATES),
                "--output", str(out), *extra)
    assert r.returncode == 0, r.stderr
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.fixture
def report(tmp_path):
    return gerar(tmp_path)


def test_resumo_bate_com_amostra(report):
    assert report["summary"] == {
        "total_reservations": 12,
        "confirmed_reservations": 9,
        "cancelled_reservations": 2,
        "no_show_reservations": 1,
        "total_room_nights": 28,
        "total_amount_brl": "7566.00",
        "average_nightly_rate_brl": "270.21",
    }


def test_by_month_ordenado_e_correto(report):
    assert report["by_month"] == [
        {"month": "2025-01", "reservations": 8, "room_nights": 25, "total_brl": "6684.00"},
        {"month": "2025-02", "reservations": 1, "room_nights": 3, "total_brl": "882.00"},
    ]


def test_top_hotels_ordem_e_valores(report):
    ids = [h["hotel_id"] for h in report["top_hotels"]]
    assert ids == ["H01", "H02", "H12", "H10", "H09"]
    assert report["top_hotels"][3]["hotel_name"] == "Hotel Madrid, Gran Vía"


def test_dinheiro_sempre_string_com_duas_casas(report):
    valores = [report["summary"]["total_amount_brl"],
               report["summary"]["average_nightly_rate_brl"]]
    valores += [m["total_brl"] for m in report["by_month"]]
    valores += [h["total_brl"] for h in report["top_hotels"]]
    for v in valores:
        assert isinstance(v, str) and MONEY.match(v), v


def test_metadados(report):
    assert report["report_version"] == "1.0"
    assert report["generated_at"].endswith("-03:00")
    assert set(report) == {"report_version", "generated_at", "summary",
                           "by_month", "top_hotels"}


def test_top_limita_quantidade(tmp_path):
    assert len(gerar(tmp_path, "--top", "2")["top_hotels"]) == 2


def test_top_maior_que_numero_de_hoteis(tmp_path):
    rep = gerar(tmp_path, "--top", "1000")
    assert 0 < len(rep["top_hotels"]) < 1000


def test_cria_diretorio_de_saida(tmp_path):
    out = tmp_path / "nova" / "pasta" / "r.json"
    r = run_cli("--input", str(SAMPLE), "--rates", str(RATES), "--output", str(out))
    assert r.returncode == 0, r.stderr
    assert out.exists()


@pytest.mark.parametrize("top", ["0", "-1", "abc"])
def test_top_invalido_sai_com_2(top):
    r = run_cli("--input", str(SAMPLE), "--rates", str(RATES), "--top", top)
    assert r.returncode == 2


def test_input_inexistente_sai_com_2():
    r = run_cli("--input", "nao_existe.csv", "--rates", str(RATES))
    assert r.returncode == 2