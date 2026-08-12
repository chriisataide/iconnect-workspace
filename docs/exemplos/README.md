# Exemplos

## `organograma-inicial.csv`

Seis pessoas que exercitam **os quatro degraus da cadeia de aprovação** decidida
em 12/08/2026 — gestor direto, diretoria acima de R$ 50.000, sócios acima de
R$ 300.000 — e as duas formas de escopo que o `pode()` resolve (`equipe` pelo
organograma, `unidade` pela lotação).

Os nomes são de **cargo, não de pessoa**, de propósito: este arquivo vai para o
git, e planilha de RH com nome, e-mail e matrícula de gente real num repositório
é vazamento de dado pessoal esperando um clone. Troque pelos nomes reais numa
cópia fora do controle de versão.

```
socio.fundador                 (sem gestor — o topo)
└── diretor.operacoes
    ├── gerente.suporte
    │   └── analista.suporte
    └── gerente.campo
        └── tecnico.campo       (Base Salvador — escopo de unidade)
```

### Como usar

```bash
# 1. os papéis (12 + sócios)
python manage.py semear_papeis --aplicar

# 2. a cadeia de aprovação com o teto real
python manage.py semear_regras_aprovacao --aplicar

# 3. simule o organograma — SEMPRE simule primeiro
python manage.py importar_organograma docs/exemplos/organograma-inicial.csv

# 4. aplique, criando as contas de teste
python manage.py importar_organograma docs/exemplos/organograma-inicial.csv \
    --aplicar --criar-usuarios
```

As contas nascem **sem senha utilizável** e entram por SSO — a empresa usa
Microsoft 365. Em produção, a conta deve nascer do primeiro login e o CSV apenas
pendura a estrutura organizacional em quem já entrou; `--criar-usuarios` existe
para ambiente de teste e para quem ainda não acessou.

### O que falta depois

Atribuir os papéis. O import monta o **organograma** (quem responde a quem), não
as **permissões** — são coisas diferentes de propósito: uma promoção muda o
organograma sem mudar o papel, e uma delegação de férias muda o papel sem mudar o
organograma.

```
/admin/identidade/atribuicaopapel/
```

| Pessoa | Papel |
|---|---|
| `socio.fundador` | `socios` |
| `diretor.operacoes` | `diretoria` |
| `gerente.suporte`, `gerente.campo` | `gestor` |
| `analista.suporte`, `tecnico.campo` | `colaborador` |
