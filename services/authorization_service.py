"""Serviço de autorização: extração de roles e decisão de acesso (RBAC).

Módulo de lógica pura (sem Streamlit), testável com pytest.

As roles vêm do ``access_token`` (JWT) emitido pelo Keycloak: união de
``realm_access.roles`` com ``resource_access[client_id].roles`` (aceita tanto
realm roles quanto client roles). O payload é decodificado **sem verificação de
assinatura** — o token chega diretamente do Keycloak via TLS pelo componente
keycloak-js e o enforcement é UI-level, coerente com a arquitetura atual
(ver ``docs/superpowers/specs/2026-09-23-keycloak-rbac-design.md``).
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from config.settings import settings
from utils.cpf import cpf_valido

logger = logging.getLogger(__name__)


class Acesso(str, Enum):
    """Resultado da decisão de acesso baseada nas roles do usuário."""

    ADMIN = "admin"
    CONVOCADO = "convocado"
    AMBOS = "ambos"
    NEGADO = "negado"


@dataclass(frozen=True)
class Usuario:
    """Usuário autenticado (dados do token Keycloak)."""

    cpf: str
    nome: str | None = None
    email: str | None = None
    roles: frozenset[str] = field(default_factory=frozenset)

    def is_admin(self, role_admin: str = settings.KEYCLOAK_ROLE_ADMIN) -> bool:
        return role_admin in self.roles

    def is_convocado(
        self, role_convocado: str = settings.KEYCLOAK_ROLE_CONVOCADO
    ) -> bool:
        return role_convocado in self.roles


def parse_roles(raw: str | None) -> frozenset[str]:
    """Converte uma lista separada por vírgulas (ex.: DEV_ROLES) em conjunto.

    Remove espaços e itens vazios; preserva maiúsculas/minúsculas (nomes de
    roles no Keycloak são case-sensitive).
    """
    if not raw:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


def _decodificar_payload_jwt(token: str) -> dict[str, Any] | None:
    """Decodifica o payload (parte do meio) de um JWT, sem verificar assinatura.

    Returns:
        dict com o payload, ou None se o token for ausente/malformado.
    """
    try:
        partes = token.split(".")
        if len(partes) < 2:
            return None
        payload_b64 = partes[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)  # padding base64url
        conteudo = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")))
        return conteudo if isinstance(conteudo, dict) else None
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        logger.warning("Falha ao decodificar payload do token: %s", exc)
        return None


def extrair_roles(access_token: str | None, client_id: str) -> frozenset[str]:
    """Extrai as roles do access_token (realm + client), sem lançar exceção."""
    if not access_token:
        return frozenset()
    payload = _decodificar_payload_jwt(access_token)
    if payload is None:
        return frozenset()

    roles: set[str] = set()

    realm_access = payload.get("realm_access")
    if isinstance(realm_access, dict):
        roles.update(r for r in (realm_access.get("roles") or []) if isinstance(r, str))

    resource_access = payload.get("resource_access")
    if isinstance(resource_access, dict):
        do_client = resource_access.get(client_id)
        if isinstance(do_client, dict):
            roles.update(r for r in (do_client.get("roles") or []) if isinstance(r, str))

    return frozenset(roles)


def nome_de_user_info(info: dict | None) -> str | None:
    """Monta o nome de exibição a partir do UserInfo (``name`` ou given+family)."""
    info = info or {}
    nome = info.get("name")
    if nome:
        return str(nome)
    partes = [info.get("given_name"), info.get("family_name")]
    composto = " ".join(str(p) for p in partes if p)
    return composto or None


def construir_usuario(
    user_info: dict | None,
    access_token: str | None,
    client_id: str,
) -> Usuario | None:
    """Monta o ``Usuario`` a partir do UserInfo e do access_token do Keycloak.

    O CPF é lido das claims ``cpf`` → ``preferred_username`` → ``username``
    (a primeira com CPF válido vence). Roles vêm do access_token.

    Returns:
        Usuario, ou None quando não há CPF válido no token.
    """
    info = user_info or {}
    cpf_raw = info.get("cpf") or info.get("preferred_username") or info.get("username")
    cpf = cpf_valido(cpf_raw if isinstance(cpf_raw, str) else None)
    if not cpf:
        return None

    email = info.get("email")
    return Usuario(
        cpf=cpf,
        nome=nome_de_user_info(info),
        email=str(email) if email else None,
        roles=extrair_roles(access_token, client_id),
    )


def decidir_acesso(
    roles: frozenset[str],
    role_admin: str = settings.KEYCLOAK_ROLE_ADMIN,
    role_convocado: str = settings.KEYCLOAK_ROLE_CONVOCADO,
) -> Acesso:
    """Decide a visão do sistema a partir das roles do usuário.

    Roles desconhecidas (ex.: ``default-roles-*``, ``offline_access``) são
    ignoradas; sem nenhuma das duas roles esperadas o acesso é NEGADO.
    """
    tem_admin = role_admin in roles
    tem_convocado = role_convocado in roles
    if tem_admin and tem_convocado:
        return Acesso.AMBOS
    if tem_admin:
        return Acesso.ADMIN
    if tem_convocado:
        return Acesso.CONVOCADO
    return Acesso.NEGADO
