"""Utilitários de validação, formatação e máscara de CPF."""
from __future__ import annotations

import re


def cpf_digitos_validos(cpf: str) -> bool:
    """Valida um CPF (11 dígitos) pelos dígitos verificadores oficiais.

    Mesmo algoritmo utilizado em ``services/extraction_service.py``.
    """
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[num]) * ((i + 1) - num) for num in range(0, i))
        digito = ((soma * 10) % 11) % 10
        if digito != int(cpf[i]):
            return False
    return True


def cpf_valido(cpf_raw: str | None) -> str | None:
    """Retorna os 11 dígitos do CPF se for válido; caso contrário, None.

    Args:
        cpf_raw: CPF em qualquer formato (ex.: '123.456.789-00').

    Returns:
        str | None: CPF com apenas dígitos (11 posições) e válido, ou None.
    """
    if not cpf_raw:
        return None
    digitos = re.sub(r"\D", "", str(cpf_raw))
    if len(digitos) != 11:
        return None
    if not cpf_digitos_validos(digitos):
        return None
    return digitos


def formatar_cpf(cpf_digitos: str) -> str:
    """Formata 11 dígitos como 000.000.000-00."""
    d = re.sub(r"\D", "", cpf_digitos or "")
    if len(d) != 11:
        return cpf_digitos
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def mascara_cpf_parcial(valor: str | None) -> str:
    """Aplica máscara progressiva de CPF (000.000.000-00) durante a digitação."""
    d = re.sub(r"\D", "", valor or "")[:11]
    if len(d) <= 3:
        return d
    if len(d) <= 6:
        return f"{d[0:3]}.{d[3:]}"
    if len(d) <= 9:
        return f"{d[0:3]}.{d[3:6]}.{d[6:]}"
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
