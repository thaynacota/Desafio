# Declaração de uso de IA

## Ferramenta e modelo
- **Ferramenta:** Claude, pelo site claude.ai (não utilizei Claude Code)
- **Modelo:** Claude Opus 5.5
- **Sessão:** exportada JSON em `sessao.md`

## O que a IA fez
- Explicou como validar o resultado (pytest, comparação com a amostra,
  códigos de saída).
- Escreveu os testes adicionais em `tests/test_cli_contrato.py`, que testam
  o contrato do CLI de fora.
- Orientou a exportação da sessão.

A IA **não teve acesso ao código-fonte** do projeto.

## O que eu fiz
- Configurei o ambiente e rodei os testes.
- Li e investiguei o código em `src/onfly_report/`.
- Identifiquei e corrigi os defeitos (descritos no `README-ENTREGA.md`).
- Validei as correções com o pytest e com a amostra de validação.
- Revisei e rodei os testes adicionais sugeridos.
- Escrevi o `README-ENTREGA.md`.