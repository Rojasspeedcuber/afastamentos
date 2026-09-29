# Consulta de autenticidade no SEI/TRE-PE

## Objetivo

Garantir que a aplicação oriente a conferência dos documentos pelo formulário
oficial indicado no próprio PDF, usando o código verificador e o código CRC
extraídos do documento.

## Contexto

O formulário oficial do SEI/TRE-PE exige código verificador, código CRC e
CAPTCHA. Por isso, a consulta não pode ser concluída automaticamente pela
aplicação. A solução aprovada é abrir o formulário oficial e apresentar os
códigos ao usuário para preenchimento manual.

## Comportamento

- A aplicação continua verificando a assinatura e extraindo o código
  verificador e o CRC do PDF.
- A URL de conferência é normalizada para o endereço HTTPS atual do SEI externo:
  `https://seiexterno.tre-pe.jus.br/sei/controlador_externo.php?acao=documento_conferir&id_orgao_acesso_externo=0`.
- Quando os dois códigos forem encontrados, os detalhes da verificação exibem
  uma orientação para a consulta oficial.
- A interface apresenta o código verificador, o CRC e um botão para abrir o
  formulário oficial em nova aba.
- O usuário informa manualmente os códigos e o CAPTCHA no site do SEI/TRE-PE.
- A validação automática existente permanece responsável pela aceitação do PDF;
  abrir o formulário oficial não altera o resultado armazenado.

## Componentes

- `services/authenticity_service.py`: reconhece a URL indicada no documento e
  produz uma URL oficial segura e estável para conferência.
- `components/comprovantes.py`: exibe os códigos e o botão de acesso ao SEI nos
  detalhes da verificação.
- `tests/`: cobre a normalização da URL e a apresentação dos dados necessários
  à conferência oficial.

## Erros e segurança

- Se a URL não for extraída, mas os códigos SEI estiverem presentes, a aplicação
  usa o endereço oficial conhecido do TRE-PE.
- URLs de outros domínios não serão apresentadas como destino de conferência.
- Falhas ou indisponibilidade do site externo não interrompem o processamento
  local do documento.

## Testes

- Extrair os códigos do texto fornecido e retornar a URL HTTPS oficial.
- Substituir a URL HTTP antiga pelo domínio HTTPS atual.
- Não aceitar como destino uma URL externa não reconhecida.
- Renderizar código verificador, CRC, instrução sobre CAPTCHA e botão oficial.
