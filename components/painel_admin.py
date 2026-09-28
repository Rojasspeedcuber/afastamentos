"""Painel administrativo (role ``admin``): consulta de registros por CPF.

Visão **somente leitura** para servidores do TRE: a busca por CPF exibe os
instrumentos de convocação, os comparecimentos, os comprovantes armazenados e
os dias ganhos calculados. Reutiliza os renderizadores da visão do convocado,
passando o CPF consultado explicitamente.
"""
from __future__ import annotations

import logging

import streamlit as st

from components.comprovantes import comprovantes_registrados, render_painel_dias_ganhos
from components.results import render_registros_usuario
from utils.cpf import cpf_valido, formatar_cpf, mascara_cpf_parcial

logger = logging.getLogger(__name__)


def _render_busca_cpf() -> str | None:
    """Formulário de busca por CPF (com máscara progressiva).

    Returns:
        str | None: CPF (11 dígitos) em consulta, ou None se ainda não houve
        busca válida.
    """
    with st.form("form_busca_cpf_admin", clear_on_submit=False):
        cpf_input = st.text_input(
            "CPF do convocado",
            value=st.session_state.get("_cpf_busca_admin_raw", ""),
            max_chars=14,
            placeholder="000.000.000-00",
            help="Consulte instrumentos, comparecimentos, comprovantes e dias ganhos de qualquer CPF.",
        )
        buscar = st.form_submit_button("🔎 Consultar", type="primary", use_container_width=True)

    mascarado = mascara_cpf_parcial(cpf_input)
    if mascarado != st.session_state.get("_cpf_busca_admin_raw"):
        st.session_state["_cpf_busca_admin_raw"] = mascarado

    if buscar:
        digitos = cpf_valido(cpf_input)
        if digitos is None:
            st.error("❌ CPF inválido. Verifique os números digitados.")
            st.session_state.pop("_cpf_consultado_admin", None)
            return None
        st.session_state["_cpf_consultado_admin"] = digitos

    return st.session_state.get("_cpf_consultado_admin")


def render_painel_admin() -> None:
    """Renderiza o painel administrativo (somente consulta)."""
    st.title("🛡️ Painel Administrativo")
    st.markdown(
        "Consulta **somente leitura** dos registros de qualquer convocado: "
        "instrumentos de convocação, comparecimentos, comprovantes armazenados "
        "e dias ganhos."
    )
    st.markdown("---")

    cpf = _render_busca_cpf()
    if not cpf:
        st.info("Informe um CPF válido para consultar os registros.")
        return

    st.markdown(f"### 📄 Registros de {formatar_cpf(cpf)}")

    # Erros de banco são tratados internamente pelos renderizadores (st.warning)
    render_registros_usuario(
        cpf=cpf,
        cpf_fmt=formatar_cpf(cpf),
        titulo="📋 Registros do Convocado",
    )
    render_painel_dias_ganhos(
        comprovantes_registrados(cpf=cpf, incluir_sessao=False)
    )
