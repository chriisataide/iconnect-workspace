# Continuidade e Risco

Este documento descreve riscos operacionais, continuidade, SLAs sugeridos,
backups e terceiros do iConnect Workspace.

## Componentes criticos

| componente | impacto se falhar |
|---|---|
| Aplicacao Django | usuarios nao acessam o Workspace |
| PostgreSQL | produto indisponivel; health check retorna `503` |
| Redis | freio de tentativas deixa de ser compartilhado entre processos |
| `ARQUIVOS_PRIVADOS_ROOT` | anexos, documentos e evidencias ficam indisponiveis |
| Proxy/HTTPS | risco de sessao insegura, CSRF e sondas incorretas |
| iConnect Platform | telas integradas degradam, mas Workspace continua |

## Health check

`GET /saude/` executa `SELECT 1`.

- `200 {"status":"ok","banco":"ok"}`: pronto.
- `503 {"status":"indisponivel","banco":"erro"}`: nao rotear trafego.

A resposta usa `Cache-Control: no-store`.

## Backups

Inclua:

- banco PostgreSQL;
- `ARQUIVOS_PRIVADOS_ROOT`;
- variaveis de ambiente em cofre seguro;
- manifests/artefatos de deploy;
- versao do codigo implantada.

Teste restore periodicamente. Backup nao testado ainda e uma hipotese.

## RPO e RTO sugeridos

Valores iniciais, a validar com a empresa:

| servico | RPO sugerido | RTO sugerido |
|---|---|---|
| Workspace app | 15 minutos | 2 horas |
| Banco | 15 minutos | 2 horas |
| Arquivos privados | 1 hora | 4 horas |
| Integracao Platform | sem RPO local | 1 dia para degradacao aceitavel |

## Plano de resposta a incidente

1. Confirmar `/saude/`.
2. Verificar banco e conexoes.
3. Verificar storage privado.
4. Verificar logs de aplicacao e seguranca.
5. Se incidente for de deploy, executar rollback do artefato.
6. Se incidente for de dados, restaurar banco/storage conforme RPO.
7. Comunicar stakeholders com impacto, escopo e previsao.
8. Registrar causa, correcao e prevencao.

## Rollback

Rollback seguro exige:

- migracoes revisadas antes do deploy;
- backup antes de mudancas destrutivas;
- artefato anterior disponivel;
- compatibilidade entre codigo anterior e schema atual, ou plano de reversao de
  schema aprovado.

O projeto evita apagar registros historicos importantes. Isso reduz risco de
perder trilha de aprovacao e auditoria.

## Riscos conhecidos

| risco | controle atual | acao recomendada |
|---|---|---|
| sessao compartilhada com Platform | produtos separados e cookies proprios | manter separacao em deploy |
| anexos expostos por web server | storage privado fora de `MEDIA_ROOT` | validar nginx/proxy |
| brute force no login | freio em produto e admin | Redis compartilhado |
| host header indevido | `ALLOWED_HOSTS` obrigatorio e sem `*` | incluir hosts de sonda corretamente |
| upload abusivo | limites de tamanho/campos/arquivos | monitorar disco |
| conhecimento tacito | docs e comentarios explicativos | manter onboarding e ADRs |
| pessoa sem papel para aprovar | notificacao de aprovacao sem dono | rotina de revisao de papeis |
| busca desatualizada por update em massa | comando `reindexar_busca` | rodar apos cargas e migracoes |

## Terceiros e fornecedores

- PostgreSQL: banco de dados.
- Redis: cache compartilhado.
- iConnect Platform: integracao opcional.
- Microsoft Entra ID/M365: SSO futuro.
- ReportLab: geracao de PDF.
- Infraestrutura de proxy/orquestracao: HTTPS, headers e health checks.

## Operacoes recorrentes

Agendar:

- `avisar_habilitacoes --aplicar`
- `avisar_frota --aplicar`
- `avisar_documentos --aplicar`
- `avisar_marketing --aplicar`
- `conferir_estoque`

Rodar sob demanda:

- `reindexar_busca`
- `conferir_estoque`
- seeders em simulacao antes de `--aplicar`.
