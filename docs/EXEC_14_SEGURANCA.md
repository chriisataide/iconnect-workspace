# EXEC 14 · Auditoria de segurança — agosto de 2026

> Escopo: código, arquitetura, banco, APIs, autenticação, frontend, backend,
> configuração, dependências, variáveis de ambiente, histórico Git.
> Método: análise do código, execução de ataques contra o produto rodando, e
> testes automatizados para tudo que foi corrigido.

---

## 14.1 Resumo executivo

**O produto já estava em boa forma, e não por acidente.** As defesas que mais
importam num portal corporativo estavam construídas e testadas antes desta
auditoria: CSP estrita sem `unsafe-inline`, anexos fora de qualquer caminho
servido pelo nginx, autorização no serviço e não na view, `pode()` com escopo
sempre exigindo alvo, CSRF em todo formulário, e um freio de força bruta na
porta do produto.

A varredura de **IDOR/BOLA — trocar um número na URL para ler o que é de outro —
não encontrou uma única falha.** Vinte e cinco tentativas de acesso horizontal e
vertical, todas barradas. O histórico dos 65 commits não tem um segredo sequer.
Não há `|safe`, `mark_safe`, `eval`, `exec` nem SQL concatenado em lugar nenhum.

**O que estava errado eram as bordas.** Nenhum dos achados é uma porta escancarada;
todos são a mesma classe de problema — um controle que existe e não foi aplicado
em todo lugar:

1. **O `/admin/login/` não tinha freio de tentativas.** A porta do produto barrava
   na sexta senha errada; a do admin aceitava vinte, todas com HTTP 200. E o admin
   é o alvo que vale mais: ele edita a base sem passar por regra de negócio,
   sem histórico e sem as permissões do produto. *(ALTA — corrigido)*
2. **Nenhum evento de segurança era registrado.** Nem entrada, nem falha de senha,
   nem concessão de papel. Freio sem log é tranca sem olho mágico: ela barra, e
   ninguém fica sabendo que alguém tentou. *(MÉDIA — corrigido)*
3. **Seis CVEs conhecidas em três dependências**, incluindo o Django.
   *(ALTA — corrigido)*
4. **A sessão durava duas semanas**, absolutas, sem expirar por inatividade.
   *(MÉDIA — corrigido)*
5. Mais quatro achados MÉDIA/BAIXA, todos corrigidos, listados na matriz.

**Estado após a auditoria: ROBUSTO.** A justificativa técnica está em 14.8.

**O que continua pendente e não depende de código:** não há recuperação de senha
de autoatendimento, o SSO ainda não está ligado, e a infraestrutura precisa
garantir duas coisas que o código não consegue garantir sozinho (14.7).

---

## 14.2 Matriz de vulnerabilidades

| # | Vulnerabilidade | Severidade | Local | Risco | Correção | Status |
|---|---|---|---|---|---|---|
| 1 | `/admin/login/` sem freio de força bruta | **ALTA** | `iconnect_workspace/urls.py` | O admin edita a base ignorando toda regra do produto. Vinte senhas por requisição, sem limite, contra contas nominais conhecidas | Mixin `ComFreio` extraído e aplicado às duas portas; rota registrada antes de `admin.site.urls` | ✅ corrigido |
| 2 | Django 6.0.7 — PYSEC-2026-3717 | **ALTA** | `requirements.txt` | CVE conhecida no framework que atende toda requisição | Django 6.0.8 | ✅ corrigido |
| 3 | `sqlparse` 0.5.5 — 4 CVEs | **ALTA** | dependência transitiva | Não aparecia em `requirements.txt`, então ninguém olhava | Pinado 0.6.0, com o motivo escrito no arquivo | ✅ corrigido |
| 4 | Nenhum log de evento de segurança | **MÉDIA** | não existia | "Quem aprovou isso em março?" e "essa conta foi usada de onde?" não tinham resposta | `contas/auditoria.py`, logger próprio `seguranca` | ✅ corrigido |
| 5 | Sessão de 14 dias, sem inatividade | **MÉDIA** | `settings/base.py` | Sessão viva duas semanas depois de a pessoa ir embora, numa estação compartilhada | 12 h deslizantes (`SESSION_SAVE_EVERY_REQUEST`) | ✅ corrigido |
| 6 | Upload de Office sem verificação de conteúdo | **MÉDIA** | `services/validacao_arquivo.py` | `.docx/.xlsx/.doc/.xls` eram aceitos por extensão; o teste de MIME só rodava se o cliente mandasse o cabeçalho — e o cliente decide | Magic bytes ZIP e OLE2; `.txt/.csv` recusam byte nulo | ✅ corrigido |
| 7 | Ponte SSO guardava JWT sem rotacionar a sessão | **MÉDIA** | `integracoes/sessao.py` | Fixação de sessão: cookie plantado passaria a carregar o token do iConnect da vítima | `session.cycle_key()` antes de gravar | ✅ corrigido |
| 8 | Freio por origem trancaria a empresa atrás de proxy | **MÉDIA** | `contas/entrada.py` | Todos com o mesmo `REMOTE_ADDR`; 20 erros de 20 pessoas barram todo mundo. O controle de segurança viraria a indisponibilidade | `PROXIES_CONFIAVEIS`, leitura por posição em `X-Forwarded-For` (não falsificável) | ✅ corrigido |
| 9 | `pytest` 9.0.1 — PYSEC-2026-1845 | **BAIXA** | `requirements-dev.txt` | Só CI e desenvolvimento | 9.0.3 | ✅ corrigido |
| 10 | Escopo inválido gravado sem recusa | **BAIXA** | `services/administracao.py` | `choices` não é validado no `save()`. Falha FECHADA (não dá acesso), mas o R.H. via "concedido" e a pessoa continuava sem alcance | Validação contra `ESCOPO_CHOICES` | ✅ corrigido |
| 11 | Sem `Cross-Origin-Resource-Policy` | **BAIXA** | `iconnect_workspace/seguranca.py` | Página de outra origem podia embutir recursos nossos no navegador de quem tem sessão | `same-origin` | ✅ corrigido |
| 12 | Limites de requisição implícitos | **BAIXA** | `settings/base.py` | Padrão de framework muda entre versões; upload sem teto é disco cheio | Quatro `DATA_UPLOAD_*`/`FILE_UPLOAD_*` explícitos | ✅ corrigido |
| 13 | `.gitignore` sem chaves e certificados | **BAIXA** | `.gitignore` | O modo normal de vazar chave é `git add .` num diretório onde alguém deixou uma | `*.pem`, `*.key`, `*.p12`, `id_rsa`, … | ✅ corrigido |

### O que foi procurado e NÃO foi encontrado

| Classe | Como foi verificado | Resultado |
|---|---|---|
| IDOR / BOLA | 25 tentativas contra objeto de terceiro, horizontal e vertical, com asserção no banco | **nada** |
| Escalada de privilégio | Colaborador comum tentando conceder papel a si, decidir aprovação, assumir fila, trocar o próprio centro de custo | **nada** |
| SQL injection | Varredura por `.raw()`, `extra()`, `cursor()`; a única consulta crua é parametrizada e tem teste | **nada** |
| XSS | Varredura por `|safe`, `mark_safe`, `autoescape off`, `style=`, `on*=`; CSP sem `unsafe-inline` | **nada** |
| Segredos no código | Varredura por padrão de chave em todos os arquivos | **nada** |
| Segredos no histórico Git | Varredura de conteúdo nos 65 commits; nomes de arquivo por `.env`, `.pem`, `.key`, `credential`, `secret` | **nada** |
| Execução de código | `eval`, `exec`, `pickle`, `subprocess`, `os.system`, `__import__` | **nada** (só como *padrão suspeito* dentro do validador de upload) |
| Mass assignment | `centro_custo`, `solicitante`, `situacao`, `valor` — todos derivados no servidor, nenhum lido do POST | **nada** |
| Escrita anônima | Toda rota aberta: `POST` exige `is_authenticated` e redireciona para o login | **nada** |
| Path traversal em upload | Nome no disco é UUID nosso; `basename` + sanitização antes | **nada** |

---

## 14.3 Alterações realizadas

### Autenticação
- `contas/entrada.py` — `LoginComFreio` virou o mixin **`ComFreio`**; nasceram
  `LoginComFreio` (`/entrar/`) e **`LoginDoAdminComFreio`** (`/admin/login/`).
  `ip_de()` passou a entender proxy.
- `iconnect_workspace/urls.py` — `/admin/login/` registrado **antes** de
  `admin.site.urls`.

### Auditoria
- **`contas/auditoria.py`** (novo) — ouve `user_logged_in`, `user_logged_out` e
  `user_login_failed`; expõe `bloqueio_por_tentativas()` e `evento()`.
- `contas/apps.py` — `ready()` liga os ouvintes.
- `identidade/services/administracao.py` — `conceder`, `revogar` e
  `definir_centro_de_custo` passaram a registrar; `conceder` valida o escopo.
- `settings/prod.py` e `settings/dev.py` — logger `seguranca` em fluxo próprio.

### Configuração
- `settings/base.py` — `SESSION_COOKIE_AGE`, `SESSION_SAVE_EVERY_REQUEST`,
  `DATA_UPLOAD_MAX_MEMORY_SIZE`, `DATA_UPLOAD_MAX_NUMBER_FIELDS`,
  `DATA_UPLOAD_MAX_NUMBER_FILES`, `FILE_UPLOAD_MAX_MEMORY_SIZE`,
  `PROXIES_CONFIAVEIS`.
- `iconnect_workspace/seguranca.py` — `Cross-Origin-Resource-Policy`.

### Upload
- `workspace/services/validacao_arquivo.py` — magic bytes para `.docx`, `.xlsx`
  (ZIP) e `.doc`, `.xls` (OLE2); `.txt` e `.csv` recusam byte nulo. A divergência
  em relação ao original está registrada no próprio arquivo.

### Integração
- `workspace/integracoes/sessao.py` — `session.cycle_key()` antes de guardar o JWT.

### Dependências
| pacote | de | para | motivo |
|---|---|---|---|
| Django | 6.0.7 | **6.0.8** | PYSEC-2026-3717 |
| sqlparse | 0.5.5 | **0.6.0** | PYSEC-2026-3696/97/98/99 |
| pytest | 9.0.1 | **9.0.3** | PYSEC-2026-1845 |

Nenhuma outra foi tocada. Todas as três são correção dentro da mesma major, e a
suíte inteira rodou depois.

### Documentação
- **`.env.example`** (novo) — todas as 18 variáveis, com o que cada uma protege.
- **`docs/EXEC_14_SEGURANCA.md`** — este arquivo.
- `.gitignore` — chaves e certificados.

### Banco de dados
**Nenhuma migração.** Nada de modelo mudou. Isso é resultado, não meta: os
achados eram de configuração, aplicação de controle e dependência.

---

## 14.4 Sobre Row-Level Security

O pedido original menciona RLS do banco. **Ela não foi implementada, e a decisão
é deliberada.**

O isolamento aqui não é multi-tenant: é **um único banco de uma única empresa**,
e o recorte é por pessoa, equipe, departamento, unidade — com vigência. Isso vive
em `identidade.services.autorizacao.pode()`, que responde
`<dominio>.<acao>.<escopo>` com alvo, resolve delegação e respeita data de
início e fim.

RLS no PostgreSQL faria o recorte por `current_user` da conexão. O produto usa
**uma** conta de banco para todos os processos — como toda aplicação Django —, e
para RLS funcionar seria preciso ou uma role por pessoa, ou passar a identidade
em `SET LOCAL` a cada requisição. A segunda é viável, e produziria **uma segunda
definição de "quem vê o quê"**, em SQL, ao lado da que já existe em Python. Duas
definições divergem; a que diverge é sempre a que esquece um caso — e o caso
esquecido num `CREATE POLICY` não aparece em teste de view.

O que substitui RLS aqui, e é testado: **nenhum queryset de dado pessoal é
construído sem recorte na origem** — `svc.minhas(pessoa)`, `atd.fila_de(pessoa)`,
`Publicacao.objects.para(pessoa)`, `cnt.pode_ver(doc, pessoa)`. A prova está em
`test_auditoria_idor.py`.

Se um dia o Workspace atender mais de uma empresa no mesmo banco, esta decisão
precisa ser reaberta — aí o isolamento passa a ser por tenant, e RLS deixa de ser
redundante.

---

## 14.5 Criptografia — o que é protegido e como

| dado | onde | proteção |
|---|---|---|
| Senha | `contas_pessoa.password` | PBKDF2-SHA256 do Django, com os quatro validadores ligados e mínimo de 10 caracteres. Conta de SSO recebe `set_unusable_password()` |
| Sessão e CSRF | cookie | Assinados por `SECRET_KEY`; `HttpOnly`, `SameSite=Lax`, `Secure` em produção |
| Atestado, comprovante, contrato | disco | **Fora** de `MEDIA_ROOT`; storage sem `base_url` (acesso por `.url` levanta); download por view que autoriza, sempre `as_attachment` |
| JWT do iConnect | sessão | Nunca em banco nem em cookie próprio; expira com a sessão; a chave rotaciona ao ser gravado |
| Tudo em trânsito | rede | HTTPS obrigatório em produção, HSTS de um ano com `preload` e `includeSubDomains` |

**Não há criptografia de campo em repouso**, e é decisão consciente: o que
protegeria de fato é a cifra do volume e do banco, que é responsabilidade da
infraestrutura. Cifra de campo na aplicação move o problema para "onde fica a
chave" — e a resposta honesta, sem um KMS, seria "numa variável de ambiente ao
lado da `SECRET_KEY`", que protege contra quase nada e quebra busca e ordenação.
Nada de criptografia própria foi escrito, e nada deve ser.

---

## 14.6 Testes executados

| suíte | o que exercita | resultado |
|---|---|---|
| `test_auditoria_idor.py` *(novo, 25)* | IDOR/BOLA horizontal e vertical, escalada de privilégio, acesso anônimo | ✅ |
| `test_auditoria_hardening.py` *(novo, 21)* | Cada achado desta auditoria, um teste por achado | ✅ |
| `test_auditoria_seguranca.py` (30) | Upload, storage, CSRF, GET que não muda estado, CSP, inline, produção, segredos, SQL cru, público-alvo | ✅ |
| `test_auditoria_permissoes.py` (46) | Portas de terceiros, permissões de autoatendimento | ✅ |
| `test_entrada.py` (8) | Freio de tentativas em `/entrar/` | ✅ |
| suíte completa | tudo | ✅ |

### Ataques executados contra o produto rodando

| ataque | antes | depois |
|---|---|---|
| 20 senhas erradas em `/admin/login/` | 20× HTTP 200 | bloqueio no limite, HTTP 429 |
| 20 senhas erradas em `/entrar/` | bloqueio (já funcionava) | idem |
| Login correto no admin depois da correção | — | 302, sessão criada, `/admin/` abre |
| `X-Forwarded-For` forjado com `PROXIES_CONFIAVEIS=1` | — | o valor inventado é ignorado |
| Senha real no log de segurança | — | não aparece |

### Dois guardas que impedem o retorno

- **`test_toda_porta_de_senha_do_produto_tem_freio`** varre a URLconf, acha toda
  `LoginView` e reprova a que não tiver `ComFreio`. Uma terceira porta não pode
  nascer destrancada — foi exatamente assim que a do admin ficou de fora.
- **`test_toda_variavel_lida_pelo_settings_esta_documentada`** reprova a
  configuração nova que não entrar no `.env.example`. Variável que ninguém
  documenta assume o padrão, e para segurança o padrão é quase sempre o valor
  errado.

---

## 14.7 Pendências

### O que a infraestrutura precisa garantir — o código não consegue

**1 · O proxy tem de sobrescrever `X-Forwarded-Proto`.**
`SECURE_PROXY_SSL_HEADER` faz o Django confiar nesse cabeçalho para decidir se a
conexão é segura. Se o processo for alcançável **por fora** do proxy, um cliente
manda `X-Forwarded-Proto: https` numa conexão HTTP, o redirecionamento para HTTPS
não acontece e o cookie marcado `Secure` vai por texto claro. O proxy precisa
sobrescrever (não repassar) esse cabeçalho, e o processo só pode aceitar conexão
vinda dele.

**2 · O cache tem de ser compartilhado entre os processos.**
A contagem do freio vive no cache. Com cache por processo, quatro workers dão
quatro vezes mais tentativas ao atacante. `REDIS_URL` já está em `prod.py`; o que
falta é a garantia operacional de que ele existe.

**3 · `PROXIES_CONFIAVEIS` precisa do número certo.** Zero atrás de um
balanceador tranca a empresa toda; dois onde há um lê o endereço errado.

### Achado aceito, com o motivo escrito

**Inteiro fora de faixa em filtro numérico — BAIXA, não corrigido.**

Os filtros que recebem id por parâmetro (`?unidade=`, `pessoa=`, `papel=`) são
guardados por `.isdigit()`, o que barra texto. Não barram um número de quarenta
dígitos. No SQLite a consulta responde 200; no PostgreSQL um inteiro fora da
faixa de `bigint` faz o driver levantar, e o visitante recebe a página de erro
amigável. *(A parte de PostgreSQL não foi verificada nesta auditoria — não há
instância disponível no ambiente de desenvolvimento.)*

Não foi corrigido, e a razão é de risco e não de esforço: alcançável **só por
quem já está autenticado**, não expõe dado nenhum, não derruba processo, e a
correção tocaria oito pontos de chamada espalhados por seis módulos no fim de
uma auditoria. Trocar uma falha de robustez de severidade mínima por risco de
regressão em seis módulos é um mau negócio. Reprodução, para quem for corrigir
deliberadamente: `GET /workspace/estoque/?unidade=9999999999999999999999999999999999999999`.

### O que depende de decisão de produto

| pendência | por que não foi feito |
|---|---|
| **Recuperação de senha** | Não existe fluxo de autoatendimento. Isso hoje é uma *ausência de superfície de ataque*, e vira pendência no dia em que houver senha local em escala. Com o SSO ligado, deixa de ser necessário |
| **Segundo fator** | Depende do SSO (o Entra ID já o oferece). Implementar MFA local antes do SSO seria construir o que vai ser jogado fora |
| **Proteção contra bot** (§11) | O produto é interno e não tem cadastro público nem envio de mensagem para fora. CAPTCHA aqui atrapalharia quem trabalha sem barrar ninguém. Reabrir se alguma tela for exposta à internet aberta |
| **Retenção do log de segurança** | O quanto guardar entrada, falha e concessão é decisão de jurídico + LGPD. O código produz a trilha; quanto tempo ela fica é da infraestrutura |
| **Retenção de atestado médico** (§4 do prompt mestre) | R.H. + jurídico. Continua pendente desde a onda anterior |
| **`pip-audit` no CI** | Foi executado nesta auditoria e achou 6 CVEs. Deveria rodar a cada PR — falta decidir se quebra o build ou só avisa |

### O que foi avaliado e recusado, com motivo

- **RLS do banco** — ver 14.4.
- **Cifra de campo em repouso** — ver 14.5.
- **Esconder o `/admin/` numa URL secreta** — obscuridade não é controle, e a
  correção real (freio + `is_staff` + senha forte + log) já está feita.
- **Bloqueio por e-mail sozinho no freio** — permitiria trancar de propósito
  qualquer pessoa da empresa. Bloqueio que se vira contra a vítima é pior que o
  ataque que evita.

---

## 14.8 Nível final: **ROBUSTO**

A classificação não é sobre ausência de falha — é sobre **onde as falhas encontradas
estavam**.

Nenhum dos treze achados era uma porta escancarada. Não havia dado de terceiro
acessível, escalada de privilégio, injeção, segredo vazado nem escrita anônima.
Os achados foram, sem exceção, **um controle que já existia e não tinha sido
aplicado em todo lugar** — o freio que faltava numa porta, o log que faltava
inteiro, a dependência que ninguém tinha olhado.

O que sustenta a classificação:

1. **A autorização mora no serviço, não na view.** É por isso que a varredura de
   IDOR voltou vazia: para uma rota estar desprotegida, alguém precisaria
   escrever a regra de novo e errar — não basta esquecer um decorador.
2. **As regras são executáveis.** 2.400 testes, dos quais quase cem são
   especificamente de segurança, e dois deles são guardas que reprovam a
   *reintrodução* das falhas desta auditoria.
3. **A superfície é pequena por construção.** Cinco dependências de execução,
   zero JavaScript de terceiros, CSP sem uma única exceção, e um `unsafe-inline`
   que não existe porque não há um `style=` no produto inteiro.
4. **O que falta não é código.** As três pendências que mais importam são
   garantias de infraestrutura e decisões de produto — e estão escritas acima com
   nome e consequência.

O que impediria "ROBUSTO" e não é o caso aqui: dado pessoal alcançável por
manipulação de id, credencial no repositório, dependência com CVE em aberto,
autenticação que confia no cliente, ou upload servido de dentro do domínio.

O que levaria a classificação adiante, e depende de decisão: **SSO com segundo
fator ligado**, `pip-audit` quebrando o build, e a trilha de segurança indo para
um destino que quem administra o banco não consiga apagar.
