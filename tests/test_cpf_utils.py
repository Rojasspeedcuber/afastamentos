"""Testes dos utilitários de CPF (utils/cpf.py)."""
from utils.cpf import cpf_digitos_validos, cpf_valido, formatar_cpf, mascara_cpf_parcial

CPF_VALIDO = "52998224725"
CPF_VALIDO_2 = "11144477735"
CPF_DIGITO_INVALIDO = "12345678900"


def test_cpf_valido_com_e_sem_mascara():
    assert cpf_valido(CPF_VALIDO) == CPF_VALIDO
    assert cpf_valido("529.982.247-25") == CPF_VALIDO
    assert cpf_valido(CPF_VALIDO_2) == CPF_VALIDO_2


def test_cpf_invalido_retorna_none():
    assert cpf_valido(CPF_DIGITO_INVALIDO) is None
    assert cpf_valido("11111111111") is None  # dígitos repetidos
    assert cpf_valido("123456") is None       # curto demais
    assert cpf_valido("") is None
    assert cpf_valido(None) is None


def test_cpf_digitos_validos():
    assert cpf_digitos_validos(CPF_VALIDO) is True
    assert cpf_digitos_validos(CPF_DIGITO_INVALIDO) is False


def test_formatar_cpf():
    assert formatar_cpf(CPF_VALIDO) == "529.982.247-25"
    assert formatar_cpf("123") == "123"  # não formata quando não tem 11 dígitos


def test_mascara_cpf_parcial():
    assert mascara_cpf_parcial("529") == "529"
    assert mascara_cpf_parcial("529982") == "529.982"
    assert mascara_cpf_parcial("529982247") == "529.982.247"
    assert mascara_cpf_parcial("52998224725") == "529.982.247-25"
    assert mascara_cpf_parcial("529.982.247-25") == "529.982.247-25"
    assert mascara_cpf_parcial("") == ""
