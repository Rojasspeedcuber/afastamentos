"""Componente de autenticação e acesso do Sistema de Convocações Eleitorais (TRE-PE).

Dois fluxos de login são suportados:

1. **Keycloak (produção):** quando ``settings.KEYCLOAK_URL`` está configurado,
   usa ``streamlit_keycloak.login()`` para autenticação OIDC — o usuário digita
   **CPF (username) + senha** na página do Keycloak, que também oferece a
   recuperação de senha por e-mail ("Esqueceu a senha?"). Após o login, o app
   extrai do token o CPF, o nome, o e-mail e as **roles** (RBAC).

2. **CPF direto (desenvolvimento):** quando o Keycloak não está configurado,
   aceita qualquer CPF válido (dígitos verificadores corretos); as roles vêm de
   ``settings.DEV_ROLES``.

Estado de sessão gravado:
    - ``st.session_state["autenticado"]``     -> bool
    - ``st.session_state["cpf_usuario"]``      -> str (11 dígitos, sem máscara)
    - ``st.session_state["cpf_usuario_fmt"]``  -> str (000.000.000-00)
    - ``st.session_state["roles_usuario"]``    -> list[str] (roles ordenadas)
    - ``st.session_state["nome_usuario"]``     -> str | None
    - ``st.session_state["email_usuario"]``    -> str | None
    - ``st.session_state["kc_id_token"]``      -> str | None (logout no Keycloak)
"""
from __future__ import annotations

import logging
from urllib.parse import urlencode

import streamlit as st

from config.settings import settings
from services.authorization_service import (
    Usuario,
    construir_usuario,
    extrair_roles,
    nome_de_user_info,
    parse_roles,
)
from utils.cpf import cpf_valido, formatar_cpf, mascara_cpf_parcial

logger = logging.getLogger(__name__)

# Cor institucional (azul escuro TRE-PE)
COR_PRIMARIA = "#1e3a8a"

# Chaves de sessão gravadas no login (removidas no logout)
_CHAVES_SESSAO_AUTH = (
    "autenticado",
    "cpf_usuario",
    "cpf_usuario_fmt",
    "roles_usuario",
    "nome_usuario",
    "email_usuario",
    "kc_id_token",
)


# ---------------------------------------------------------------------------
# Sessão de autenticação
# ---------------------------------------------------------------------------
def _persistir_sessao(
    cpf_digitos: str,
    roles: frozenset[str] = frozenset(),
    nome: str | None = None,
    email: str | None = None,
    id_token: str | None = None,
) -> None:
    """Grava os dados do usuário autenticado no session_state."""
    st.session_state["cpf_usuario"] = cpf_digitos
    st.session_state["cpf_usuario_fmt"] = formatar_cpf(cpf_digitos)
    st.session_state["autenticado"] = True
    st.session_state["roles_usuario"] = sorted(roles)
    st.session_state["nome_usuario"] = nome
    st.session_state["email_usuario"] = email
    if id_token:
        st.session_state["kc_id_token"] = id_token
    st.session_state.pop("_kc_id_token_logout", None)
    logger.info(
        "Usuário autenticado com CPF %s (roles: %s).",
        cpf_digitos,
        sorted(roles) or "—",
    )


def limpar_sessao_autenticacao() -> None:
    """Remove do session_state todas as chaves de autenticação."""
    for chave in _CHAVES_SESSAO_AUTH:
        st.session_state.pop(chave, None)


def usuario_autenticado() -> Usuario | None:
    """Reconstrói o ``Usuario`` a partir do session_state (ou None)."""
    cpf = st.session_state.get("cpf_usuario")
    if not st.session_state.get("autenticado") or not cpf:
        return None
    return Usuario(
        cpf=cpf,
        nome=st.session_state.get("nome_usuario"),
        email=st.session_state.get("email_usuario"),
        roles=frozenset(st.session_state.get("roles_usuario") or ()),
    )


def url_logout_keycloak(id_token: str | None = None) -> str | None:
    """Monta a URL de end-session do Keycloak (encerra também a sessão SSO).

    Returns:
        str | None: URL, ou None quando o Keycloak não está configurado.
    """
    if not settings.KEYCLOAK_URL:
        return None
    if id_token is None:
        id_token = st.session_state.get("kc_id_token")
    params = {"client_id": settings.KEYCLOAK_CLIENT_ID}
    if id_token:
        params["id_token_hint"] = id_token
    base = settings.KEYCLOAK_URL.rstrip("/")
    return (
        f"{base}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/logout"
        f"?{urlencode(params)}"
    )


# ---------------------------------------------------------------------------
# Estilo / cabeçalho das telas
# ---------------------------------------------------------------------------
def _render_cabecalho_login(subtitulo_modo: str = "") -> None:
    """Renderiza o cabeçalho visual (ícone, título e subtítulo) do login."""
    st.markdown(
        f"""
        <div style="text-align:center; margin: 8px auto 4px auto;">
            <div style="font-size:3.2rem; line-height:1;">🗳️</div>
            <div style="font-size:1.6rem; font-weight:800; color:{COR_PRIMARIA};
                        margin-top:6px;">
                Sistema de Convocações Eleitorais
            </div>
            <div style="font-size:1.05rem; font-weight:600; color:#334155;
                        letter-spacing:0.08em; margin-top:2px;">
                TRE-PE
            </div>
            <div style="height:3px; width:120px; background:{COR_PRIMARIA};
                        border-radius:2px; margin:12px auto 0 auto; opacity:0.85;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if subtitulo_modo:
        st.markdown(
            f"<div style='text-align:center; color:#64748b; font-size:0.85rem; "
            f"margin-top:8px;'>{subtitulo_modo}</div>",
            unsafe_allow_html=True,
        )


def _render_aviso_logout() -> None:
    """Após 'Sair', oferece o encerramento da sessão SSO no Keycloak."""
    id_token = st.session_state.get("_kc_id_token_logout")
    if not id_token:
        return
    url = url_logout_keycloak(id_token)
    if not url:
        st.session_state.pop("_kc_id_token_logout", None)
        return
    st.warning(
        "Você saiu do sistema. Para **trocar de usuário**, "
        f"[encerre também a sessão no Keycloak]({url}) — caso contrário, o login "
        "anterior pode ser retomado automaticamente (SSO)."
    )


# ---------------------------------------------------------------------------
# Formulário de CPF (compartilhado pelos dois fluxos)
# ---------------------------------------------------------------------------
def _render_form_cpf(titulo: str, ajuda: str = "", **dados_sessao) -> bool:
    """Renderiza o formulário de CPF e trata a submissão.

    Args:
        titulo: título exibido acima do campo.
        ajuda: texto de ajuda do campo CPF.
        **dados_sessao: repassados a ``_persistir_sessao`` (roles, nome, email,
            id_token).

    Returns:
        bool: True se o CPF foi validado e a sessão foi criada.
    """
    st.markdown(
        f"<div style='font-weight:600; color:{COR_PRIMARIA}; margin-bottom:4px;'>"
        f"{titulo}</div>",
        unsafe_allow_html=True,
    )

    with st.form("form_login_cpf", clear_on_submit=False):
        cpf_input = st.text_input(
            "CPF",
            value=st.session_state.get("_cpf_input_raw", ""),
            max_chars=14,
            placeholder="000.000.000-00",
            help=ajuda or "Informe seu CPF (apenas você tem acesso aos seus registros).",
            label_visibility="collapsed",
        )
        enviar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    # Aplica máscara em tempo real para exibição na próxima renderização
    mascarado = mascara_cpf_parcial(cpf_input)
    if mascarado != st.session_state.get("_cpf_input_raw"):
        st.session_state["_cpf_input_raw"] = mascarado

    if enviar:
        cpf_digitos = cpf_valido(cpf_input)
        if cpf_digitos is None:
            st.markdown(
                "<div style='color:#dc2626; font-weight:600; margin-top:8px;'>"
                "❌ CPF inválido. Verifique os números digitados e tente novamente."
                "</div>",
                unsafe_allow_html=True,
            )
            return False
        _persistir_sessao(cpf_digitos, **dados_sessao)
        st.rerun()

    return False


# ---------------------------------------------------------------------------
# Fluxos de login
# ---------------------------------------------------------------------------
def _login_keycloak() -> bool:
    """Fluxo de autenticação via Keycloak (OIDC).

    Após a autenticação, extrai do token: CPF, nome, e-mail e roles (RBAC).
    Se o token não trouxer um CPF válido, solicita a confirmação do CPF.
    """
    try:
        from streamlit_keycloak import login as keycloak_login
    except ImportError:
        st.error(
            "Dependência 'streamlit-keycloak' não instalada. "
            "Execute: pip install streamlit-keycloak"
        )
        logger.error("streamlit-keycloak não está instalado.")
        return False

    keycloak = keycloak_login(
        url=settings.KEYCLOAK_URL,
        realm=settings.KEYCLOAK_REALM,
        client_id=settings.KEYCLOAK_CLIENT_ID,
    )

    if not getattr(keycloak, "authenticated", False):
        st.info("🔐 Redirecionando para a autenticação segura (Keycloak)…")
        return False

    access_token = getattr(keycloak, "access_token", None)
    id_token = getattr(keycloak, "id_token", None)
    user_info = getattr(keycloak, "user_info", None) or {}

    usuario = construir_usuario(user_info, access_token, settings.KEYCLOAK_CLIENT_ID)
    if usuario is not None:
        _persistir_sessao(
            usuario.cpf,
            roles=usuario.roles,
            nome=usuario.nome,
            email=usuario.email,
            id_token=id_token,
        )
        st.rerun()
        return True

    # Token sem CPF válido: extrai roles/dados e pede a confirmação do CPF
    roles = extrair_roles(access_token, settings.KEYCLOAK_CLIENT_ID)
    st.success("✅ Autenticado com sucesso. Confirme seu CPF para continuar.")
    return _render_form_cpf(
        "Confirme seu CPF",
        roles=roles,
        nome=nome_de_user_info(user_info),
        email=user_info.get("email"),
        id_token=id_token,
    )


def _login_cpf_direto() -> bool:
    """Fluxo de login direto (desenvolvimento) baseado apenas no CPF.

    As roles do usuário vêm de ``settings.DEV_ROLES``.
    """
    st.markdown(
        "<div style='text-align:center; background:#fef9c3; border:1px solid #fde047; "
        "color:#854d0e; border-radius:8px; padding:6px 10px; font-size:0.8rem; "
        "margin-bottom:14px;'>⚠️ Modo de desenvolvimento – sem Keycloak</div>",
        unsafe_allow_html=True,
    )
    return _render_form_cpf(
        "Acesse com seu CPF",
        ajuda="Modo desenvolvimento: qualquer CPF válido é aceito.",
        roles=parse_roles(settings.DEV_ROLES),
    )


# ---------------------------------------------------------------------------
# Acesso negado (RBAC)
# ---------------------------------------------------------------------------
def render_acesso_negado() -> None:
    """Tela para usuários autenticados sem a role exigida (acesso negado)."""
    roles = st.session_state.get("roles_usuario") or []
    roles_txt = ", ".join(sorted(roles)) if roles else "nenhuma"

    _, col_centro, _ = st.columns([1, 1.4, 1])
    with col_centro:
        with st.container(border=True):
            _render_cabecalho_login()
            st.markdown(
                """
                <div style="text-align:center; margin-top:18px;">
                    <div style="font-size:2.4rem;">🚫</div>
                    <div style="font-weight:700; color:#b91c1c; font-size:1.15rem;
                                margin-top:6px;">
                        Acesso negado
                    </div>
                    <div style="color:#334155; margin-top:8px;">
                        Sua conta não possui permissão para usar este sistema.<br>
                        Contate o administrador.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(f"Papéis encontrados na sua conta: **{roles_txt}**")

            col_btn, col_link = st.columns(2)
            with col_btn:
                if st.button("🚪 Sair", type="primary", use_container_width=True):
                    id_token = st.session_state.get("kc_id_token")
                    limpar_sessao_autenticacao()
                    if id_token:
                        st.session_state["_kc_id_token_logout"] = id_token
                    st.rerun()
            with col_link:
                url = url_logout_keycloak()
                if url:
                    st.markdown(
                        f"<div style='text-align:center; padding-top:8px;'>"
                        f"<a href='{url}' target='_blank' rel='noopener'>"
                        f"Encerrar sessão no Keycloak</a></div>",
                        unsafe_allow_html=True,
                    )

            st.markdown(
                "<div style='text-align:center; color:#94a3b8; font-size:0.72rem; "
                "margin-top:16px;'>Tribunal Regional Eleitoral de Pernambuco</div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------
def render_login_page() -> bool:
    """Renderiza a página de login e retorna o estado de autenticação.

    Returns:
        bool: True se o usuário já está autenticado, False caso contrário.
    """
    if st.session_state.get("autenticado") and st.session_state.get("cpf_usuario"):
        return True

    usa_keycloak = bool(settings.KEYCLOAK_URL)

    # Layout centralizado (card com sombra)
    _, col_centro, _ = st.columns([1, 1.4, 1])
    with col_centro:
        with st.container(border=True):
            _render_cabecalho_login(
                subtitulo_modo="Autenticação segura via Keycloak" if usa_keycloak else ""
            )
            _render_aviso_logout()
            st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)

            if usa_keycloak:
                autenticado = _login_keycloak()
            else:
                autenticado = _login_cpf_direto()

            st.markdown(
                "<div style='text-align:center; color:#94a3b8; font-size:0.72rem; "
                "margin-top:16px;'>Tribunal Regional Eleitoral de Pernambuco</div>",
                unsafe_allow_html=True,
            )

    return bool(autenticado or st.session_state.get("autenticado"))
