# Consulta de autenticidade no SEI/TRE-PE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exibir os códigos extraídos do PDF e abrir o formulário HTTPS oficial do SEI/TRE-PE para conferência manual.

**Architecture:** O serviço de autenticidade continuará extraindo assinatura e códigos localmente, mas passará a devolver somente a URL oficial conhecida do TRE-PE quando identificar o contexto SEI. O componente Streamlit apresentará os códigos e um botão externo após a análise, sem tentar contornar o CAPTCHA nem alterar o critério local de aceitação.

**Tech Stack:** Python 3, Streamlit, pypdf, pytest.

---

## Estrutura de arquivos

- `services/authenticity_service.py`: define e seleciona a URL oficial permitida.
- `components/comprovantes.py`: renderiza a orientação, os códigos e o botão externo.
- `tests/test_authenticity_service.py`: testa normalização, fallback e rejeição de domínio externo.
- `tests/test_comprovantes.py`: testa a apresentação dos dados de conferência sem navegador real.
- `README.md`: documenta a etapa manual e o CAPTCHA.

### Task 1: URL oficial de conferência

**Files:**
- Modify: `services/authenticity_service.py:25-110`
- Test: `tests/test_authenticity_service.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar casos que exijam a URL HTTPS oficial, fallback quando a frase contém os códigos sem URL e ausência de destino para domínio não reconhecido:

```python
URL_SEI_TRE_PE = (
    "https://seiexterno.tre-pe.jus.br/sei/controlador_externo.php?"
    "acao=documento_conferir&id_orgao_acesso_externo=0"
)

def test_normaliza_url_antiga_para_formulario_oficial():
    assert extrair_codigos_autenticidade(TEXTO_SEI_VALIDO)["url_conferencia"] == URL_SEI_TRE_PE

def test_usa_formulario_oficial_quando_texto_sei_tem_codigos_sem_url():
    codigos = extrair_codigos_autenticidade(TEXTO_SEM_ASSINATURA)
    assert codigos["url_conferencia"] == URL_SEI_TRE_PE

def test_nao_aceita_url_de_conferencia_de_outro_dominio():
    texto = TEXTO_SEM_ASSINATURA + " https://exemplo.invalid/controlador_externo.php?acao=documento_conferir"
    codigos = extrair_codigos_autenticidade(texto)
    assert codigos["url_conferencia"] == URL_SEI_TRE_PE
```

- [ ] **Step 2: Executar os testes e confirmar a falha esperada**

Run: `python -m pytest tests/test_authenticity_service.py -v`

Expected: FAIL porque a implementação atual mantém a URL HTTP extraída e não aplica fallback sem URL.

- [ ] **Step 3: Implementar a seleção mínima da URL oficial**

Adicionar uma constante e fazer `extrair_codigos_autenticidade` retornar esse destino apenas quando ambos os códigos forem encontrados:

```python
URL_CONFERENCIA_SEI_TRE_PE = (
    "https://seiexterno.tre-pe.jus.br/sei/controlador_externo.php?"
    "acao=documento_conferir&id_orgao_acesso_externo=0"
)

url_conferencia = URL_CONFERENCIA_SEI_TRE_PE if verificador and crc else None
```

Remover a dependência da URL arbitrária extraída do PDF para impedir links externos não confiáveis.

- [ ] **Step 4: Executar os testes do serviço**

Run: `python -m pytest tests/test_authenticity_service.py -v`

Expected: todos os testes passam.

### Task 2: Ação de conferência na interface

**Files:**
- Modify: `components/comprovantes.py:102-138`
- Create: `tests/test_comprovantes.py`

- [ ] **Step 1: Escrever o teste que falha**

Testar uma função de renderização isolada por meio de `monkeypatch`:

```python
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
    assert links[0][1] == URL_SEI_TRE_PE
```

- [ ] **Step 2: Executar o teste e confirmar a falha esperada**

Run: `python -m pytest tests/test_comprovantes.py -v`

Expected: FAIL porque `_render_consulta_oficial` ainda não existe.

- [ ] **Step 3: Implementar e integrar a renderização mínima**

Criar a função:

```python
def _render_consulta_oficial(
    codigo_verificador: str | None,
    codigo_crc: str | None,
    url_conferencia: str | None,
) -> None:
    if not (codigo_verificador and codigo_crc and url_conferencia):
        return
    st.info(
        "Confira também no site oficial do SEI/TRE-PE. "
        f"Informe o código verificador **{codigo_verificador}**, o código CRC "
        f"**{codigo_crc}** e o CAPTCHA solicitado pelo site."
    )
    st.link_button(
        "Conferir autenticidade no SEI/TRE-PE",
        url_conferencia,
        type="primary",
    )
```

Chamá-la em `_processar_upload` imediatamente depois de `verify_pdf_authenticity`, antes da decisão baseada em `report.valido`, para permitir a consulta sempre que os códigos tiverem sido extraídos.

- [ ] **Step 4: Executar os testes do componente**

Run: `python -m pytest tests/test_comprovantes.py -v`

Expected: PASS.

### Task 3: Documentação e regressão

**Files:**
- Modify: `README.md:253-264`

- [ ] **Step 1: Documentar o fluxo real**

Acrescentar à etapa de autenticidade que a aplicação exibe os códigos e abre o formulário oficial em nova aba; o preenchimento e o CAPTCHA são manuais, e a indisponibilidade do site não altera a análise local.

- [ ] **Step 2: Executar a suíte completa**

Run: `python -m pytest -v`

Expected: todos os testes passam sem erros de coleta.

- [ ] **Step 3: Inspecionar as alterações**

Run: `git diff --check`

Expected: nenhuma saída.
