import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
PROHIBIDO = re.compile(r"datetime\.now\(|datetime\.utcnow\(|date\.today\(|time\.time\(")


def test_nadie_fuera_del_reloj_consulta_la_hora_del_sistema():
    infractores = [
        f"{archivo.relative_to(APP)}:{n}"
        for archivo in APP.rglob("*.py")
        if archivo.name != "reloj.py" or archivo.parent != APP
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1)
        if PROHIBIDO.search(linea)
    ]
    assert infractores == [], f"Usar el reloj inyectable (D27): {infractores}"
