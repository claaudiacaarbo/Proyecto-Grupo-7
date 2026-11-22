"""Instala las librerías cuando haga falta y abre el planificador."""

import os
import sys
import venv
from pathlib import Path
from subprocess import CalledProcessError, run


def main():
    if sys.version_info < (3, 10):
        print("Necesitas Python 3.10 o posterior.")
        return 1

    carpeta = Path(__file__).resolve().parent
    requisitos = carpeta / "requirements.txt"
    mayor, menor = sys.version_info[:2]
    entorno = Path.home() / ".planificador-atd" / f"python-{mayor}.{menor}"
    python = entorno / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    instalados = entorno / "requisitos-instalados.txt"

    try:
        if not python.is_file():
            print("Primera vez. Preparando el planificador…", flush=True)
            venv.create(entorno, with_pip=True)

        lista = requisitos.read_bytes()
        if not instalados.is_file() or instalados.read_bytes() != lista:
            print("Instalando las librerías del planificador…", flush=True)
            run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                 "-r", str(requisitos)], check=True)
            instalados.write_bytes(lista)

        resultado = run([str(python), "-B", "-X", "utf8", str(carpeta / "planificador.py")])
        return resultado.returncode
    except KeyboardInterrupt:
        print("Inicio cancelado.")
        return 130
    except (OSError, CalledProcessError) as error:
        print(f"No se pudo iniciar el planificador. {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
