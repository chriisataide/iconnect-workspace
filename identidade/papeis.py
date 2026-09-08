"""Os papéis do Workspace.

**Não são os papéis do iConnect.** O iConnect é plataforma separada, com 1432
técnicos e clientes; o Workspace é dos funcionários da icodev, que são algumas
dezenas. Espelhar `UserRole.role` aqui produziria `tecnico_campo` e `cliente`
como papéis do Workspace, que não descrevem nada do que o Workspace faz.

Os papéis abaixo derivam das permissões que os 8 módulos especificados exigem.
Cada um é uma resposta a "quem faz o quê no Workspace", não a "quem é quem no
iConnect".

## Como o escopo funciona

`escopo_padrao` é o que a atribuição herda quando ninguém informa outro. As
permissões trazem o escopo embutido (`rh.ler.equipe`), e o embutido vence o
padrão — é mais específico. Ver `identidade/services/autorizacao.py`.
"""

from __future__ import annotations

from identidade.models import (
    ESCOPO_EQUIPE,
    ESCOPO_GLOBAL,
    ESCOPO_PROPRIO,
    ESCOPO_UNIDADE,
)

# Permissões que TODO funcionário tem. Repetir em cada papel produziria seis
# listas para manter em sincronia.
AUTOATENDIMENTO = [
    "rh.ler.proprio",
    # Reserva de recurso e a própria correspondência são autoatendimento puro:
    # ninguém precisa de aprovação para marcar uma sala nem para saber que
    # chegou uma carta para si.
    "res.reservar.proprio",
    "cor.ler.proprio",
    "rh.solicitar.proprio",
    "fin.ler.proprio",
    "fin.solicitar.proprio",
    "com.solicitar.proprio",
    "log.ler.proprio",
    "log.solicitar.proprio",
    "hab.ler.proprio",
    "hab.inscrever.proprio",
    "ti.ler.proprio",
    "ti.solicitar.proprio",
    "ti.status.ler",
    "doc.ler.publico",
    "doc.sugerir",
    # O PRÓPRIO quadro de metas e o próprio PDI. No autoatendimento e não num
    # papel de gestão, e é a decisão da onda: um sistema de metas em que a
    # pessoa não vê as próprias metas é um sistema de avaliação secreta.
    "met.ler.proprio",
]

PAPEIS_V1 = [
    {
        "chave": "colaborador",
        "nome": "Colaborador",
        "escopo_padrao": ESCOPO_PROPRIO,
        "permissoes": AUTOATENDIMENTO,
        "descricao": (
            "Todo funcionário. Autoatendimento: suas férias, seus documentos, "
            "suas habilitações, seus pedidos. É o papel padrão."
        ),
    },
    {
        "chave": "gestor",
        "nome": "Gestor",
        "escopo_padrao": ESCOPO_EQUIPE,
        "permissoes": AUTOATENDIMENTO
        + [
            "rh.ler.equipe",
            "rh.aprovar.equipe",
            "apr.aprovar.equipe",
            "fin.aprovar.equipe",
            "com.aprovar.equipe",
            "hab.ler.equipe",
            "hab.inscrever.equipe",
            "doc.leitura.cobrar.equipe",
            # A tela de resultados, recortada ao CENTRO DE CUSTO da própria
            # lotação. `.departamento` e não `.global` de propósito: quem
            # responde por uma operação precisa dos números dela, e o resultado
            # da empresa inteira é conversa de diretoria — mostrar tudo aqui
            # transformaria a tela num vazamento com aparência de transparência.
            "eco.ler.departamento",
            # O quadro da PRÓPRIA equipe, no mesmo recorte. Sem esta linha, a
            # separação das telas RETIRARIA do gestor algo que ele já via dentro
            # da tela 10 — e mudança de arquitetura que tira acesso em silêncio
            # é a que ninguém associa à causa três semanas depois.
            #
            # Satisfação do cliente NÃO vem junto: ela é do comercial, e o
            # gestor de operação nunca a teve recortada por contrato dele.
            "eco.pessoas.departamento",
            # O ciclo de planejamento, e SÓ os ciclos cuja plateia inclui o
            # papel `gestor`. `.departamento` e não `.global`: o escopo global
            # é o que abre TODOS os ciclos, inclusive o trimestral de
            # presidência, e a pauta de quem decide acima não é leitura de
            # rotina de quem executa abaixo.
            "cic.ler.departamento",
            # O quadro dos liderados. `definir` e `aprovar` SEPARADAS: quem
            # escreve a meta não a homologa sozinho no próprio quadro — o
            # `alvo` de `pode()` é a pessoa avaliada, e o gestor não se alcança
            # pelo `.equipe`.
            "met.ler.equipe",
            "met.definir.equipe",
            "met.aprovar.equipe",
            # O orçamento do PRÓPRIO centro de custo, sem revisar. Quem responde
            # por uma operação precisa saber quanto resta antes de aprovar o
            # pedido do liderado — e mexer no teto é outra conversa, com o
            # Financeiro.
            "fin.orcamento.ler.departamento",
        ],
        "descricao": (
            "Responde por uma equipe. Aprova o que vem dos liderados e vê a "
            "cobertura deles. O escopo `equipe` vem do organograma (Lotacao.gestor)."
        ),
    },
    {
        "chave": "diretoria",
        "nome": "Diretoria",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "apr.aprovar.global",
            "fin.aprovar.global",
            "com.aprovar.global",
            "rh.ler.global",
            "fin.ler.global",
            "ops.ler.global",
            # Comunicado da empresa é da diretoria tanto quanto do R.H. — e
            # global, não por unidade: quem anuncia mudança de política anuncia
            # para todo mundo.
            "com.publicar.global",
            "faq.manter.global",
            # O painel de indicadores. Aqui e nos Sócios porque é para eles que
            # ele existe: volume por área, tempo até resolver, onde trava.
            "ind.ler.global",
            "eco.ler.global",
            # AS DUAS TELAS IRMÃS DA 10, e por que são permissões próprias.
            #
            # Quadro e jornada (16) e Satisfação do cliente (17) saíram de
            # dentro da Apresentação de Resultados: são perguntas de outra
            # gente. Enquanto exigiam `eco.ler`, a única forma de dar a alguém o
            # turnover da própria equipe era dar junto a margem de todo contrato
            # da empresa.
            #
            # Ninguém perde nada nesta mudança: quem tinha `eco.ler` recebe as
            # duas. O que muda é o FUTURO — agora dá para conceder uma sem a
            # outra.
            "eco.pessoas.global",
            "eco.satisfacao.global",
            # O painel de exceções INTEIRO. Sem isto, a diretoria veria só as
            # regras dos papéis que ela ocupa — e o painel existe justamente
            # para ver o que está solto nos departamentos dos outros.
            #
            # Quem NÃO tem esta permissão continua entrando: cada regra declara
            # o papel que responde por ela, e a pessoa vê as suas. Ver o painel
            # não é privilégio; ver o painel INTEIRO é.
            "exc.ler.global",
            # O ciclo de planejamento. `conduzir` aqui e em lugar nenhum mais:
            # abrir a reunião, anotar em nome dela e assinar a ATA é ato de
            # quem responde pela pauta. Ler é de quem senta na sala; conduzir é
            # de quem convoca.
            "cic.ler.global",
            "cic.conduzir.global",
            # O quadro de qualquer pessoa, inclusive o próprio: é o único papel
            # com `met.aprovar.global`, e é o que destrava a aprovação do quadro
            # de quem não tem gestor acima.
            "met.ler.global",
            "met.definir.global",
            "met.aprovar.global",
            "fin.orcamento.ler.global",
            "fin.orcamento.revisar.global",
            # Responder por QUALQUER regra com limiar. A diretoria assina o
            # plano do contrato deficitário porque é ela que responde por ele
            # numa reunião de conselho — e porque, nas regras sem papel
            # atribuído, o escopo global é o único caminho.
            "pla.responder.global",
            # A tela de fontes. A pergunta "de onde vem esse número?" é da
            # diretoria antes de ser de quem opera — e a resposta precisa ser um
            # link, não um chamado.
            "eco.carga.global",
            # Exceção de habilitação vencida é de diretoria, auditada e
            # notificada ao jurídico. Bloqueio sem escape faz a operação burlar
            # o sistema; escape fácil torna o bloqueio decorativo.
            "ops.excecao.certificacao",
            # §48 — quem LIBERA exceção de certificação tem de poder VER quem
            # está vencido. Sem isto, a diretoria decidiria sobre uma lista que
            # não pode abrir.
            "hab.auditoria.ler",
            "log.perda.registrar",
        ],
        "descricao": (
            "Terceiro degrau da cadeia. Aprova de R$ 50.000 a R$ 300.000 e vê tudo."
        ),
    },
    {
        "chave": "socios",
        "nome": "Sócios",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "apr.aprovar.global",
            "fin.aprovar.global",
            "fin.ler.global",
            "rh.ler.global",
            "ops.ler.global",
            "ind.ler.global",
            "eco.ler.global",
            "eco.pessoas.global",
            "eco.satisfacao.global",
            "exc.ler.global",
            # Lê o ciclo inteiro e NÃO conduz — pela mesma razão que este papel
            # não tem as permissões administrativas: sócio decide sobre
            # dinheiro, não opera o sistema.
            "cic.ler.global",
        ],
        "descricao": (
            "Último degrau. Aprova acima de R$ 300.000. Deliberadamente SEM as "
            "permissões administrativas de `diretoria` — sócio decide sobre "
            "dinheiro, não opera o sistema, e papel de aprovação com poder de "
            "administração transforma a última instância em superusuário."
        ),
    },
    {
        "chave": "rh",
        "nome": "RH",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "rh.atender.global",
            "rh.ler.global",
            "rh.admin.global",
            "ind.ler.global",
            "eco.ler.global",
            "eco.pessoas.global",
            "eco.satisfacao.global",
            "hab.ler.unidade",
            "hab.registrar.presenca",
            # §48 — o painel de conformidade passou a exigir `hab.auditoria.ler`
            # e não `hab.ler`: a forma `.proprio` desta última está em
            # AUTOATENDIMENTO, e a lista NOMINAL de quem está com certificado
            # vencido ficava aberta para todo colaborador. O R.H. responde pela
            # conformidade numa auditoria e continua vendo o painel.
            # §10 — ver as candidaturas a vaga interna. Permissão própria e não
            # `rh.ler`: a forma `.proprio` daquela está em AUTOATENDIMENTO, e a
            # lista diz quem se candidatou a quê e quem foi reprovado — que muda
            # a relação de uma pessoa com o gestor dela.
            "rh.recrutar.global",
            # Lê os quadros para acompanhar a COBERTURA do ciclo — quantos
            # rascunhos, quantos aprovados. NÃO aprova e NÃO define: metas são
            # combinadas entre a pessoa e quem a lidera, e um R.H. que homologa
            # transforma a conversa num processo de RH.
            "met.ler.global",
            "hab.auditoria.ler",
            "doc.publicar.assunto",
            "com.publicar.unidade",
            # A base de conhecimento do assistente. No R.H. porque metade das
            # perguntas repetidas da empresa é de R.H. — e quem responde a
            # dúvida toda semana é quem sabe escrever a resposta.
            "faq.manter.global",
        ],
        "descricao": "Pessoas: perfil, férias, documentos com validade, onboarding.",
    },
    {
        "chave": "financeiro",
        "nome": "Financeiro",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "fin.atender.global",
            "fin.ler.global",
            "fin.aprovar.centro_custo",
            "fin.contrato.ler.unidade",
            "apr.aprovar.equipe",
            # O resultado econômico inteiro. O Financeiro fecha o mês: negar-lhe
            # a visão da empresa faria a conferência acontecer na planilha, que
            # é de onde este produto está tentando tirar a conversa.
            "eco.ler.global",
            "eco.pessoas.global",
            "eco.satisfacao.global",
            # O orçamento anual, e a REVISÃO. Ler e revisar separadas: montar o
            # ano é ato de planejamento, e mudar o teto vigente é ato de
            # governança — a segunda deixa motivo e autor no histórico.
            "fin.orcamento.ler.global",
            "fin.orcamento.revisar.global",
            # Responder pelos planos das regras que o Financeiro atende — a de
            # margem abaixo do limiar, à frente de todas. `.departamento` e não
            # `.global`: o escopo decide o alcance, e o papel da regra decide
            # QUAL plano; sem o papel, esta permissão não abre nada.
            "pla.responder.departamento",
        ],
        "descricao": "Reembolso, prestação de contas, orçamento por centro de custo.",
    },
    {
        "chave": "compras",
        "nome": "Compras",
        "escopo_padrao": ESCOPO_UNIDADE,
        "permissoes": AUTOATENDIMENTO
        + [
            "com.atender.unidade",
            "com.operar.unidade",
            "com.receber.unidade",
            "com.ler.unidade",
            "com.fornecedor.cadastrar",
            "log.ler.unidade",
            # Comprar sem ver o saldo é comprar o que já está na prateleira.
            "log.estoque.ler.unidade",
        ],
        "descricao": (
            "Transforma requisição aprovada em pedido. NÃO aprova — quem pede não "
            "aprova, quem aprova não compra, quem compra não recebe."
        ),
    },
    {
        "chave": "logistica",
        # O nome que a empresa usa é Suprimentos. A CHAVE continua `logistica`
        # porque ela está gravada em toda `AtribuicaoPapel` já concedida —
        # trocá-la revogaria o papel de quem o tem hoje.
        "nome": "Suprimentos",
        "escopo_padrao": ESCOPO_UNIDADE,
        "permissoes": AUTOATENDIMENTO
        + [
            "log.atender.unidade",
            "log.ler.unidade",
            # §48 — `log.estoque.ler` nasceu porque `log.ler` não servia de
            # porta: a forma `.proprio` dela está em AUTOATENDIMENTO, e usá-la
            # para guardar a tela de estoque abria o saldo de todas as unidades
            # para a empresa inteira.
            "log.estoque.ler.unidade",
            "log.movimentar.unidade",
            "log.custodia.ler.unidade",
            "log.custodia.atribuir.unidade",
            "log.inventario.contar.unidade",
            # §18/§19 — a frota. Fica em Suprimentos e não num papel próprio:
            # quem cuida de material também cuida de veículo, e um papel com
            # duas permissões é um papel que ninguém concede.
            "log.frota.ler.unidade",
            "log.frota.operar.unidade",
            # Facilities: quem cuida de material também cuida de sala, veículo e
            # do que chega na recepção. Módulo próprio para isso seria um papel
            # com uma permissão só.
            "res.admin.global",
            "cor.registrar.global",
        ],
        "descricao": (
            "Materiais e ativos, mais recursos e recepção. Conta o inventário mas "
            "NÃO o fecha — segregação de função é o controle interno mais básico "
            "de patrimônio."
        ),
    },
    {
        "chave": "recepcao",
        "nome": "Recepção",
        "escopo_padrao": ESCOPO_UNIDADE,
        "permissoes": AUTOATENDIMENTO
        + [
            # A recepção REGISTRA o que chega e acompanha o que ainda não foi
            # retirado. Só isso.
            "cor.registrar.global",
            "cor.ler.unidade",
        ],
        "descricao": (
            "Quem recebe carta, encomenda e intimação na portaria. Registra a "
            "chegada, que é o que dispara o aviso para o destinatário, e "
            "acompanha o que ainda está na mesa. Nada de estoque, custódia nem "
            "frota: a função existia dentro de Suprimentos e continua lá para "
            "quem já a exerce, mas dar o almoxarifado inteiro a quem só atende "
            "a portaria é escopo que ninguém pediu."
        ),
    },
    {
        "chave": "ti",
        "nome": "TI",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "ti.atender.unidade",
            "ti.status.publicar",
            "ti.admin.global",
            "log.custodia.ler.unidade",
            # A tela de fontes (99) e o botão de recarregar. Quem opera o
            # produto precisa ver por que uma carga falhou e poder tentar de
            # novo — sem isso, "o número está velho" vira um chamado que só o
            # deploy resolve.
            #
            # `eco.carga` e não `eco.ler`: ver a tela de fontes NÃO dá acesso
            # aos números. São permissões diferentes de propósito — o T.I. tem
            # de consertar a carga sem enxergar o resultado financeiro.
            "eco.carga.global",
        ],
        "descricao": (
            "Status dos serviços e provisionamento de acesso. Provisiona, mas "
            "quem CONCEDE acesso é o dono do sistema — requisito de ISO 27001."
        ),
    },
    {
        "chave": "sesmt",
        "nome": "Segurança do Trabalho",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "hab.atender.global",
            "hab.ler.unidade",
            "hab.validar.evidencia",
            "hab.exigencia.definir",
            "hab.registrar.presenca",
            "hab.auditoria.ler",
        ],
        "descricao": (
            "Valida evidência de habilitação e define o que cada serviço exige. "
            "Separado da operação de propósito: quem coordena a operação tem "
            "incentivo para liberar o técnico."
        ),
    },
    {
        "chave": "operacao",
        "nome": "Operação",
        "escopo_padrao": ESCOPO_UNIDADE,
        "permissoes": AUTOATENDIMENTO
        + [
            "ops.atender.unidade",
            "ops.ler.unidade",
            "ops.despachar.unidade",
            "ops.escala.editar.unidade",
            "ops.incidente.comandar.unidade",
            "hab.ler.equipe",
            # A tratativa do cliente detrator e o projeto bloqueado são planos
            # da Operação — é ela que fala com o cliente e desbloqueia o
            # projeto. Sem isto, a regra apontaria para um papel que não pode
            # responder por ela, e a dívida ficaria sem dono para sempre.
            "pla.responder.unidade",
        ],
        "descricao": "Painel ao vivo, despacho, escala e incidente.",
    },
    {
        "chave": "monitoramento",
        "nome": "Sala de Monitoramento",
        "escopo_padrao": ESCOPO_UNIDADE,
        # Somente leitura de propósito: turno de 12h com poder de despacho e sem
        # supervisão é onde acidente operacional acontece.
        "permissoes": ["ops.ler.unidade", "ti.status.ler", "doc.ler.publico"],
        "descricao": "Leitura da operação ao vivo, 24h. Sem despacho, por decisão.",
    },
    {
        "chave": "auditoria",
        "nome": "Auditoria",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": [
            "doc.ler.publico",
            "doc.auditoria.ler",
            "hab.auditoria.ler",
            "ti.auditoria.ler",
        ],
        "descricao": (
            "Somente leitura de trilha e evidência. Existe como papel próprio "
            "porque o auditor pode ser externo — cliente auditando fornecedor."
        ),
    },
    {
        "chave": "vendas",
        "nome": "Vendas",
        "escopo_padrao": ESCOPO_UNIDADE,
        "permissoes": AUTOATENDIMENTO
        + [
            # A AVALIAÇÃO DO CLIENTE (17) — o público novo que justifica a
            # separação. Antes ela morava dentro da tela 10, e dar o NPS ao
            # comercial exigia dar junto a margem de todo contrato da empresa.
            # Ninguém fez isso, então o comercial simplesmente não via o NPS.
            "eco.satisfacao.global",
            "ven.atender.unidade",
            "ven.aprovar.unidade",
            "ven.ler.unidade",
        ],
        "descricao": (
            "Proposta, desconto e cadastro de cliente. Desconto fora da tabela "
            "passa pelo gestor E por Vendas: um sabe se o cliente merece, o "
            "outro se a margem aguenta."
        ),
    },
    {
        "chave": "marketing",
        "nome": "Marketing",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "mkt.atender.global",
            "mkt.ler.global",
        ],
        "descricao": (
            "Material de divulgação, evento e presença de marca. Atende os "
            "pedidos da área; evento com valor segue a cadeia por faixa."
        ),
    },
    {
        "chave": "juridico",
        "nome": "Jurídico",
        "escopo_padrao": ESCOPO_GLOBAL,
        "permissoes": AUTOATENDIMENTO
        + [
            "jur.atender.global",
            "jur.ler.global",
        ],
        "descricao": (
            "Análise de contrato e parecer. Atende — não aprova pedido de "
            "terceiro: quem decide se o contrato é assinado é quem o assina."
        ),
    },
]
