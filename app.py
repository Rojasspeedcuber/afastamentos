"""Aplicação Principal Streamlit para Upload e Extração de Informações de PDF."""
import logging
import streamlit as st
from config.settings import settings
from components.auth import (
    limpar_sessao_autenticacao,
    render_acesso_negado,
    render_login_page,
    usuario_autenticado,
)
from components.fluxo_unificado import render_fluxo_unificado
from components.painel_admin import render_painel_admin
from services.authorization_service import Acesso, decidir_acesso

# Configuração de Logging centralizado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pdf_extractor_app")

# Configuração da página Streamlit
st.set_page_config(
    page_title="PDF Extractor - Processamento e Extração",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização segura do estado de sessão (st.session_state)
for _chave, _valor in {
    "doc_info": None,
    "extraction_result": None,
    "current_file_name": None,
    "is_processing": False,
    "mock_mode": settings.USE_MOCK_EXTRACTION,
    "autenticado": False,
    "cpf_usuario": None,
    "roles_usuario": [],
    "nome_usuario": None,
    "email_usuario": None,
}.items():
    if _chave not in st.session_state:
        st.session_state[_chave] = _valor

# --- GATE DE AUTENTICAÇÃO ---
# Bloqueia todo o conteúdo principal enquanto o usuário não estiver autenticado.
if not render_login_page():
    st.stop()

# --- GATE DE AUTORIZAÇÃO (RBAC) ---
# Usuário autenticado sem a role exigida não acessa nenhum conteúdo.
usuario = usuario_autenticado()
acesso = decidir_acesso(usuario.roles) if usuario else Acesso.NEGADO

if acesso == Acesso.NEGADO:
    render_acesso_negado()
    st.stop()

# --- BARRA LATERAL (USUÁRIO E CONTROLES) ---
with st.sidebar:
    st.title("⚙️ Painel de Controle")
    st.caption("Configurações do ambiente de extração")

    # Bloco do usuário autenticado
    st.markdown("---")
    papeis = []
    assert usuario is not None, "Gate RBAC deveria ter parado antes"
    if usuario.is_admin():
        papeis.append("🛡️ Admin")
    if usuario.is_convocado():
        papeis.append("🗳️ Convocado")
    st.markdown(f"👤 **Usuário:** {usuario.nome or '—'}")
    st.markdown(f"🆔 **CPF:** {st.session_state.get('cpf_usuario_fmt') or usuario.cpf}")
    if usuario.email:
        st.markdown(f"✉️ **E-mail:** {usuario.email}")
    st.markdown(f"**Papel:** {' • '.join(papeis) or '—'}")
    if st.button("🚪 Sair", use_container_width=True):
        id_token = st.session_state.get("kc_id_token")
        limpar_sessao_autenticacao()
        if id_token:
            st.session_state["_kc_id_token_logout"] = id_token
        st.rerun()

    # Usuário com as duas roles escolhe a visão ativa
    visao_admin = acesso == Acesso.ADMIN
    if acesso == Acesso.AMBOS:
        st.markdown("---")
        opcao_visao = st.radio(
            "Visão",
            ["🗳️ Convocado", "🛡️ Administrativo"],
            help="Alterne entre o fluxo do convocado e o painel administrativo.",
        )
        visao_admin = opcao_visao == "🛡️ Administrativo"

    # Controles exclusivos da visão do convocado
    if not visao_admin:
        st.markdown("---")
        mock_toggle = st.toggle(
            "Ativar Modo Mock",
            value=st.session_state.mock_mode,
            help="Quando ativado, retorna dados de demonstração sem processar o texto real do documento."
        )
        if mock_toggle != st.session_state.mock_mode:
            st.session_state.mock_mode = mock_toggle
            settings.USE_MOCK_EXTRACTION = mock_toggle
            st.rerun()

        st.markdown("---")
        st.markdown("### ℹ️ Sobre o Sistema")
        st.markdown(
            f"""
            - **Tecnologia:** 100% Python + Streamlit
            - **Motor de Leitura:** pypdf
            - **Limite de Arquivo:** {settings.MAX_FILE_SIZE_MB} MB
            - **Porta do Servidor:** {settings.PORT}
            - **Status:** Operacional
            """
        )

        if st.button("🔄 Limpar Sessão", use_container_width=True):
            st.session_state.doc_info = None
            st.session_state.extraction_result = None
            st.session_state.current_file_name = None
            st.session_state.is_processing = False
            st.session_state.comprovantes_sessao = {}
            st.rerun()

# --- CONTEÚDO PRINCIPAL (CONFORME O PAPEL) ---
if visao_admin:
    render_painel_admin()
else:
    # --- CABEÇALHO PRINCIPAL ---
    st.title("📄 PDF Extractor")
    st.markdown(
        "Plataforma inteligente em **Python** para upload, validação e extração de dados "
        "da **carta convocatória** e dos **comprovantes de participação** — em um único "
        "fluxo guiado."
    )
    st.markdown("---")

    # --- FLUXO UNIFICADO (Passo 1 → Passo 2 → Resumo) ---
    render_fluxo_unificado()

# --- RODAPÉ ---
st.markdown("<br><br>", unsafe_allow_html=True)
st.caption("PDF Extractor • Arquitetura 100% Python modular • Pronto para EasyPanel / Docker")
