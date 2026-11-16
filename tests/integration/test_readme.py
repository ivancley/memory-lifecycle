"""The README examples really run, in order, against the suite's database, and print what they say.

Every ```python block runs, in the order it appears, sharing one namespace: each block
continues the previous one, as the text says. Every ``print`` must be announced by a
trailing ``# [...]`` comment with exactly what it prints. Blocks fenced as ```py are
illustrative (they need an LLM or a framework) and only have to compile.

PT: Os exemplos do README rodam de verdade, em ordem, contra o banco da suíte, e imprimem
o que dizem. Todo bloco ```python roda, na ordem em que aparece, num único namespace:
cada bloco continua o anterior, como o texto diz. Todo ``print`` precisa ser anunciado
por um comentário ``# [...]`` no fim da linha com exatamente o que imprime. Blocos
marcados como ```py são ilustrativos (precisam de um LLM ou de um framework) e só
precisam compilar.
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
import pytest

README = Path(__file__).resolve().parents[2] / "README.md"


def _blocks(language: str) -> list[str]:
    return re.findall(rf"```{language}\n(.*?)```", README.read_text(encoding="utf-8"), re.S)


def test_the_readme_examples_run_and_print_what_they_say(
    dsn: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    blocks = _blocks("python")
    assert len(blocks) >= 10, "the concepts section lost its runnable examples"
    monkeypatch.setenv("DATABASE_URL", dsn)
    namespace: dict[str, object] = {}
    try:
        for number, block in enumerate(blocks, start=1):
            exec(compile(block, f"README.md, block {number}", "exec"), namespace)
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute("DROP SCHEMA IF EXISTS memory_lifecycle CASCADE")
    printed = capsys.readouterr().out.splitlines()
    expected = [line for block in blocks for line in re.findall(r"# (\[.*\])$", block, re.M)]
    assert printed == expected


def test_the_readme_illustrative_snippets_compile():
    blocks = _blocks("py")
    assert blocks
    for number, block in enumerate(blocks, start=1):
        compile(block, f"README.md, illustrative block {number}", "exec")
