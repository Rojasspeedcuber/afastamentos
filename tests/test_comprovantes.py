"""Testes dos elementos de conferência oficial dos comprovantes."""

from components import comprovantes


URL_SEI_TRE_PE = (
    "https://seiexterno.tre-pe.jus.br/sei/controlador_externo.php?"
    "acao=documento_conferir&id_orgao_acesso_externo=0"
)


def test_render_consulta_oficial_exibe_codigos_captcha_e_link(monkeypatch):
    textos = []
    links = []
    monkeypatch.setattr(comprovantes.st, "info", textos.append)
    monkeypatch.setattr(
        comprovantes.st,
        "link_button",
        lambda label, url, **kwargs: links.append((label, url, kwargs)),
    )

    comprovantes._render_consulta_oficial("3443939", "BCE2B28E", URL_SEI_TRE_PE)

    assert "3443939" in textos[0]
    assert "BCE2B28E" in textos[0]
    assert "CAPTCHA" in textos[0]
    assert links[0][0] == "Conferir autenticidade no SEI/TRE-PE"
    assert links[0][1] == URL_SEI_TRE_PE
