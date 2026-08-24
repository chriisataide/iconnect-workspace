# Conhecimento Organizacional

Este documento descreve como manter o conhecimento do Workspace acessivel para
novos colaboradores, mantenedores e liderancas.

## Leituras de onboarding

Para qualquer pessoa que entra no projeto:

1. `README.md`
2. `docs/DOCUMENTACAO_SOFTWARE_EMPRESA.md`
3. `docs/GUIA_USO_WORKSPACE.md`
4. `docs/ARQUITETURA_SISTEMA.md`
5. `docs/EXEC_12_GUIA_DO_TIME.md`
6. `docs/EXEC_13_OPERACAO.md`
7. `docs/EXEC_14_SEGURANCA.md`

Para desenvolvimento:

- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`
- `workspace/models/__init__.py`
- `workspace/urls.py`
- `workspace/modulos.py`
- `identidade/models.py`
- `contas/models.py`
- `financas/models.py`

## Wiki interna sugerida

Estrutura:

- Visao geral do Workspace.
- Como pedir servicos.
- Como aprovar.
- Como atender fila.
- Como publicar documento.
- Como revisar papel e acesso.
- Como cadastrar centro de custo.
- Como operar estoque/frota/reservas.
- Runbooks de incidente.
- Decisoes arquiteturais.
- Perguntas frequentes.

## Registro de decisoes

Decisoes tecnicas e de produto devem registrar:

- contexto;
- decisao;
- alternativas consideradas;
- consequencias;
- data;
- responsavel;
- arquivos afetados.

O historico atual esta espalhado em:

- docstrings do codigo;
- comentarios de settings, models, services e URLs;
- documentos `EXEC_*`;
- README.

Quando a decisao mudar comportamento publico, atualize tambem o guia de uso e o
guia de QA.

## Comentarios no codigo

O projeto usa comentarios para explicar o "por que", nao o "o que". Mantenha
esse padrao:

- explique fronteiras de seguranca;
- explique decisao que parece estranha;
- explique trade-off de arquitetura;
- evite narrar linha obvia.

## LICENCA

Nao ha arquivo `LICENSE` no repositorio no estado atual. Isso significa que o
codigo nao deve ser tratado como open source por padrao.

Acao recomendada:

- se o projeto for interno/proprietario, documentar isso explicitamente;
- se for aberto, adicionar `LICENSE` e atualizar este documento.

## Checklist para novos mantenedores

- Rodar a aplicacao localmente.
- Rodar `python -m pytest`.
- Ler os quatro apps principais.
- Entender a separacao Workspace vs Platform.
- Entender `pode()` e escopos.
- Entender catalogo, aprovacao e fila.
- Entender storage privado de anexos.
- Entender comandos agendados.
- Entender o ratchet de cobertura e contagem.

## Conhecimento tacito a reduzir

- Quem e dono de cada papel critico.
- Quem aprova teto de centro de custo.
- Quem e dono de documentos normativos.
- Qual RPO/RTO final a empresa aceita.
- Qual politica de retencao se aplica a comprovantes e atestados.
- Como o SSO M365 sera habilitado em producao.
