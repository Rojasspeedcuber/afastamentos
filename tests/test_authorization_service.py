"""Testes do serviço de autorização (RBAC) — lógica pura."""
import base64
import json

from services.authorization_service import (
    Acesso,
    Usuario,
    construir_usuario,
    decidir_acesso,
    extrair_roles,
    nome_de_user_info,
    parse_roles,
)

CLIENT_ID = "convocacoes-app"
CPF_VALIDO = "52998224725"


def _jwt(payload: dict) -> str:
    """Monta um JWT falso (header.payload.assinatura) com o payload informado."""
    def _b64(dados: dict) -> str:
        bruto = json.dumps(dados).encode("utf-8")
        return base64.urlsafe_b64encode(bruto).decode("ascii").rstrip("=")

    return f"{_b64({'alg': 'none'})}.{_b64(payload)}.assinatura-falsa"


# ---------------------------------------------------------------- extrair_roles

def test_extrai_roles_do_realm():
    token = _jwt({"realm_access": {"roles": ["convocado", "offline_access"]}})
    assert extrair_roles(token, CLIENT_ID) == frozenset({"convocado", "offline_access"})


def test_extrai_roles_do_client():
    token = _jwt({"resource_access": {CLIENT_ID: {"roles": ["admin"]}}})
    assert extrair_roles(token, CLIENT_ID) == frozenset({"admin"})


def test_combina_roles_de_realm_e_client():
    token = _jwt({
        "realm_access": {"roles": ["convocado"]},
        "resource_access": {CLIENT_ID: {"roles": ["admin"]}},
    })
    assert extrair_roles(token, CLIENT_ID) == frozenset({"convocado", "admin"})


def test_ignora_roles_de_outro_client():
    token = _jwt({"resource_access": {"outro-client": {"roles": ["admin"]}}})
    assert extrair_roles(token, CLIENT_ID) == frozenset()


def test_token_ausente_ou_vazio_retorna_conjunto_vazio():
    assert extrair_roles(None, CLIENT_ID) == frozenset()
    assert extrair_roles("", CLIENT_ID) == frozenset()


def test_token_malformado_nao_quebra():
    assert extrair_roles("isso-nao-e-um-jwt", CLIENT_ID) == frozenset()
    assert extrair_roles("a.b", CLIENT_ID) == frozenset()
    token_payload_nao_json = "eyJhbG...lIn0." + base64.urlsafe_b64encode(
        b"ola"
    ).decode("ascii").rstrip("=") + ".x"
    assert extrair_roles(token_payload_nao_json, CLIENT_ID) == frozenset()


def test_estrutura_inesperada_nao_quebra():
    token = _jwt({"realm_access": " nao-e-dict", "resource_access": [1, 2]})
    assert extrair_roles(token, CLIENT_ID) == frozenset()


# --------------------------------------------------------------- decidir_acesso

def test_decidir_acesso_somente_admin():
    assert decidir_acesso(
        frozenset({"admin"}), role_admin="admin", role_convocado="convocado"
    ) == Acesso.ADMIN


def test_decidir_acesso_somente_convocado():
    assert decidir_acesso(
        frozenset({"convocado"}), role_admin="admin", role_convocado="convocado"
    ) == Acesso.CONVOCADO


def test_decidir_acesso_ambas_roles():
    assert decidir_acesso(
        frozenset({"admin", "convocado"}), role_admin="admin", role_convocado="convocado"
    ) == Acesso.AMBOS


def test_decidir_acesso_sem_roles_negado():
    assert decidir_acesso(
        frozenset(), role_admin="admin", role_convocado="convocado"
    ) == Acesso.NEGADO


def test_decidir_acesso_roles_desconhecidas_negado():
    assert decidir_acesso(
        frozenset({"default-roles-tre", "offline_access"}),
        role_admin="admin",
        role_convocado="convocado",
    ) == Acesso.NEGADO


def test_decidir_acesso_respeita_nomes_customizados():
    assert decidir_acesso(
        frozenset({"app_admin"}), role_admin="app_admin", role_convocado="app_user"
    ) == Acesso.ADMIN


# ------------------------------------------------------------------ parse_roles

def test_parse_roles_separa_por_virgula():
    assert parse_roles("admin,convocado") == frozenset({"admin", "convocado"})


def test_parse_roles_remove_espacos():
    assert parse_roles(" admin , convocado ") == frozenset({"admin", "convocado"})


def test_parse_roles_vazio_ou_none():
    assert parse_roles("") == frozenset()
    assert parse_roles(None) == frozenset()
    assert parse_roles(",,,") == frozenset()


# ------------------------------------------------------------- construir_usuario

def test_usuario_a_partir_de_preferred_username():
    token = _jwt({"realm_access": {"roles": ["convocado"]}})
    usuario = construir_usuario(
        {"preferred_username": CPF_VALIDO, "name": "Maria Silva", "email": "m@tre.jus.br"},
        token,
        CLIENT_ID,
    )
    assert usuario == Usuario(
        cpf=CPF_VALIDO,
        nome="Maria Silva",
        email="m@tre.jus.br",
        roles=frozenset({"convocado"}),
    )


def test_claim_cpf_tem_precedencia_sobre_username():
    usuario = construir_usuario(
        {"cpf": CPF_VALIDO, "preferred_username": "maria.silva"}, None, CLIENT_ID
    )
    assert usuario is not None
    assert usuario.cpf == CPF_VALIDO
    assert usuario.roles == frozenset()


def test_usuario_sem_nome_ou_email():
    usuario = construir_usuario({"preferred_username": CPF_VALIDO}, None, CLIENT_ID)
    assert usuario is not None
    assert usuario.nome is None
    assert usuario.email is None


def test_cpf_invalido_ou_ausente_retorna_none():
    assert construir_usuario({"preferred_username": "12345678900"}, None, CLIENT_ID) is None
    assert construir_usuario({"preferred_username": "maria.silva"}, None, CLIENT_ID) is None
    assert construir_usuario(None, None, CLIENT_ID) is None
    assert construir_usuario({}, None, CLIENT_ID) is None


# ------------------------------------------------------------- nome_de_user_info

def test_nome_de_user_info():
    assert nome_de_user_info({"name": "Maria Silva"}) == "Maria Silva"
    assert nome_de_user_info({"given_name": "Maria", "family_name": "Silva"}) == "Maria Silva"
    assert nome_de_user_info({"given_name": "Maria"}) == "Maria"
    assert nome_de_user_info({}) is None
    assert nome_de_user_info(None) is None


# --------------------------------------------------------------------- Usuario

def test_usuario_is_admin_e_is_convocado():
    admin = Usuario(cpf=CPF_VALIDO, roles=frozenset({"admin"}))
    assert admin.is_admin(role_admin="admin") is True
    assert admin.is_convocado(role_convocado="convocado") is False

    ambos = Usuario(cpf=CPF_VALIDO, roles=frozenset({"admin", "convocado"}))
    assert ambos.is_admin(role_admin="admin") is True
    assert ambos.is_convocado(role_convocado="convocado") is True
