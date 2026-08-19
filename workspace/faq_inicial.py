"""As perguntas frequentes iniciais, por área.

São as perguntas que o §3 do pedido lista, mais as que o próprio catálogo torna
inevitáveis. **As respostas descrevem o que o Workspace faz** — não políticas de
RH, que não estão escritas em lugar nenhum que este código conheça.

Essa distinção é o que mantém a base honesta: "como peço férias" tem resposta
verificável (abre tal item, vai para tal fila, leva tantos dias); "quantos dias
de férias eu tenho" não tem, e inventá-la seria pior que não responder.

`url_acao` aponta para caminho INTERNO. Um link para fora daqui envelhece sem
ninguém perceber — o item de catálogo, não: se ele sumir, a URL dá 404 na cara
de quem mantém a FAQ.
"""

from __future__ import annotations

FAQ_INICIAL = [
    # ── R.H. ────────────────────────────────────────────────────────
    {
        # Férias, atestado e declaração saíram do catálogo no §10. A pergunta
        # CONTINUA — as pessoas seguem perguntando —, e a resposta passa a dizer
        # a verdade nova em vez de apontar para um item que não existe mais.
        #
        # Apagar a FAQ junto com o item seria o erro fácil: quem pergunta
        # "como peço férias" receberia silêncio, e concluiria que o assistente
        # não sabe nada — quando o que mudou foi o caminho.
        "area": "rh", "prioridade": 90,
        "pergunta": "Como solicitar férias?",
        "palavras_chave": ["ferias", "descanso", "folga", "programar ferias",
                           "atestado", "afastamento", "declaracao", "comprovante",
                           "trabalho remoto", "home office"],
        "resposta": (
            "Férias, atestado, declaração e trabalho remoto saíram do catálogo do "
            "Workspace — esses pedidos passaram a ser tratados fora daqui. "
            "Procure o R.H. pelo canal da sua unidade. "
            "O que você já pediu antes continua em “Minhas solicitações”, com o "
            "histórico completo."
        ),
        "url_acao": "/workspace/minhas-solicitacoes/",
        "rotulo_acao": "Ver o que já pedi",
    },
    {
        "area": "rh", "prioridade": 88,
        "pergunta": "Sou PJ. Como envio minha nota fiscal?",
        "palavras_chave": ["pj", "nota fiscal", "nf", "pessoa juridica", "prestador",
                           "faturar", "competencia", "meu pagamento"],
        "resposta": (
            "Abra “Pagamento de PJ”, escolha a competência — o MÊS DO SERVIÇO, não "
            "o mês em que a nota foi emitida —, anexe o PDF da nota e informe o valor. "
            "O pedido vai para o Financeiro. Você acompanha o status em “Minhas "
            "solicitações”, e ninguém além de você e de quem atende vê a sua nota."
        ),
        "url_acao": "/workspace/servicos/pagamento-pj/", "rotulo_acao": "Enviar NF",
    },
    {
        "area": "rh", "prioridade": 70,
        "pergunta": "Como funciona uma vaga interna?",
        "palavras_chave": ["vaga interna", "vaga", "recrutamento interno", "candidatar"],
        "resposta": (
            "Vagas abertas aparecem no catálogo em “Inscrição em vaga interna”. "
            "Você se inscreve por lá e o R.H. acompanha as candidaturas. "
            "Abrir uma vaga NOVA é outro item — “Abertura de vaga” — e é para quem "
            "vai contratar."
        ),
        "url_acao": "/workspace/servicos/vaga-interna/", "rotulo_acao": "Ver vagas",
    },
    {
        "area": "rh", "prioridade": 60,
        "pergunta": "Como consulto o andamento de um pedido meu?",
        "palavras_chave": ["andamento", "status", "acompanhar", "em que pe esta", "consultar processo"],
        "resposta": (
            "Em “Minhas solicitações” você vê todos os seus pedidos, com filtro por "
            "situação e a linha do tempo de cada um — quem aprovou, quem assumiu e quando."
        ),
        "url_acao": "/workspace/minhas-solicitacoes/", "rotulo_acao": "Minhas solicitações",
    },
    # ── Operações ───────────────────────────────────────────────────
    {
        "area": "ops", "prioridade": 90,
        "pergunta": "Como abrir um chamado predial?",
        "palavras_chave": ["chamado predial", "predial", "ar condicionado", "lampada",
                           "infiltracao", "manutencao", "eletrica", "hidraulica",
                           "ordem de servico", "inspecao", "preventiva"],
        "resposta": (
            "Chamado predial é aberto no iConnect Platform, não aqui — é lá que "
            "existem ordem de serviço, despacho de técnico, SLA e o histórico "
            "junto do cliente. No módulo de Operações há um card que leva direto. "
            "Um segundo sistema de chamados criaria duas filas para o mesmo "
            "trabalho, e a segunda seria a que ninguém olha."
        ),
        "url_acao": "/workspace/m/operacoes/",
        "rotulo_acao": "Ir para Operações",
    },
    {
        "area": "ops", "prioridade": 70,
        "pergunta": "Quem atende o meu chamado?",
        "palavras_chave": ["quem atende", "responsavel", "quem resolve", "fila"],
        "resposta": (
            "Cada serviço tem uma área responsável, definida pelo tipo do pedido. "
            "Assim que alguém assume, o nome aparece no seu pedido e você recebe aviso. "
            "Até lá o pedido fica na fila da área, do mais antigo para o mais novo."
        ),
    },
    # ── Suprimentos ─────────────────────────────────────────────────
    {
        "area": "log", "prioridade": 90,
        "pergunta": "Como solicitar material?",
        "palavras_chave": ["material", "epi", "uniforme", "capacete", "luva", "papelaria"],
        "resposta": (
            "Depende do que você precisa. Se o material já existe em estoque, use "
            "“Requisição de material” — a lista mostra o saldo da sua unidade e o "
            "pedido é recusado na hora se não couber. Se for algo a providenciar, "
            "use “Controle de materiais”."
        ),
        "url_acao": "/workspace/servicos/requisicao-material/",
        "rotulo_acao": "Requisitar do estoque",
    },
    {
        "area": "log", "prioridade": 85,
        "pergunta": "Como consultar os materiais disponíveis?",
        "palavras_chave": ["estoque", "saldo", "disponivel", "tem quanto", "quantidade"],
        "resposta": (
            "A própria tela de requisição mostra o que existe: cada material aparece "
            "com o saldo da SUA unidade ao lado do nome. Material zerado não aparece "
            "na lista — se não está lá, não tem na sua unidade."
        ),
        "url_acao": "/workspace/servicos/requisicao-material/",
        "rotulo_acao": "Ver o estoque",
    },
    {
        # §17. A pergunta aparece sempre no desligamento e sempre tarde: a
        # resposta vinha da memória de quem entregou, e o resultado é o rádio
        # que ninguém cobra.
        "area": "log", "prioridade": 82,
        "pergunta": "Que equipamentos da empresa estão no meu nome?",
        "palavras_chave": ["equipamento", "notebook", "radio", "ferramenta",
                           "patrimonio", "devolver", "termo", "responsabilidade",
                           "custodia"],
        "resposta": (
            "Em “Equipamentos” está tudo o que a empresa registrou no seu nome, com "
            "patrimônio, desde quando e em qual unidade. Quando Suprimentos entrega "
            "algo, você é avisado no sino e confirma o recebimento ali — é essa "
            "confirmação que vale, e não o registro de quem entregou."
        ),
        "url_acao": "/workspace/custodia/", "rotulo_acao": "Ver meus equipamentos",
    },
    {
        "area": "log", "prioridade": 80,
        "pergunta": "Como solicitar uma viagem?",
        "palavras_chave": ["viagem", "passagem", "hospedagem", "hotel", "aereo", "locacao"],
        "resposta": (
            "Abra “Viagem” no catálogo. Escolha o que precisa — passagem, hospedagem "
            "ou locação de veículo —, informe destino e datas. O pedido passa pelo seu "
            "gestor e depois por Suprimentos, que faz as reservas."
        ),
        "url_acao": "/workspace/servicos/viagem/", "rotulo_acao": "Pedir viagem",
    },
    # ── Compras ─────────────────────────────────────────────────────
    {
        "area": "com", "prioridade": 80,
        "pergunta": "Como peço um notebook ou equipamento novo?",
        "palavras_chave": ["notebook", "laptop", "computador", "equipamento novo", "monitor"],
        "resposta": (
            "Abra “Notebook” no catálogo e diga por que precisa — substituição, "
            "colaborador novo ou projeto. O pedido passa pelo gestor e por Compras. "
            "Se o equipamento atual PAROU de funcionar, o caminho é outro: "
            "“Meu equipamento parou de funcionar”, que vai para T.I. e é mais rápido."
        ),
        "url_acao": "/workspace/servicos/notebook/", "rotulo_acao": "Pedir notebook",
    },
    # ── Financeiro ──────────────────────────────────────────────────
    {
        # Área R.H., não Financeiro: quem trata o reembolso é o R.H.
        "area": "rh", "prioridade": 92,
        "pergunta": "Como solicitar reembolso?",
        "palavras_chave": ["reembolso", "gastei", "despesa", "nota fiscal", "cupom",
                           "uber", "taxi", "prestacao de contas", "restituicao"],
        "resposta": (
            "Use “Prestação de contas”, no módulo de R.H.: lance cada gasto com o "
            "comprovante anexado. O total é a soma das linhas — não um valor "
            "digitado —, e é ele que vai para a aprovação. O pedido passa pelo seu "
            "gestor e depois pelo R.H., que confere e libera o pagamento. "
            "Se você recebeu adiantamento antes, aponte o adiantamento no mesmo "
            "pedido para a conta fechar."
        ),
        "url_acao": "/workspace/servicos/prestacao-contas/",
        "rotulo_acao": "Prestar contas",
    },
    {
        "area": "fin", "prioridade": 70,
        "pergunta": "Qual a diferença entre adiantamento e prestação de contas?",
        "palavras_chave": ["adiantamento", "antecipacao", "dinheiro antes", "diferenca"],
        "resposta": (
            "Adiantamento é dinheiro ANTES da despesa. Prestação de contas é o "
            "acerto DEPOIS, com os comprovantes. Todo adiantamento precisa de uma "
            "prestação de contas para fechar."
        ),
        "url_acao": "/workspace/servicos/adiantamento/", "rotulo_acao": "Pedir adiantamento",
    },
    {
        "area": "fin", "prioridade": 60,
        "pergunta": "Quem aprova o meu pedido?",
        "palavras_chave": ["quem aprova", "aprovacao", "aprovador", "gestor aprova"],
        "resposta": (
            "Primeiro o seu gestor direto. Depois a área responsável pelo assunto. "
            "Acima de R$ 50 mil entra a Diretoria; acima de R$ 300 mil, os Sócios. "
            "A trilha aparece no seu pedido, em “Minhas solicitações”."
        ),
        "url_acao": "/workspace/minhas-solicitacoes/", "rotulo_acao": "Ver meus pedidos",
    },
    # ── T.I. e Redes ────────────────────────────────────────────────
    {
        "area": "ti", "prioridade": 90,
        "pergunta": "Como pedir acesso a um sistema?",
        "palavras_chave": ["acesso", "senha", "login", "sistema", "permissao", "bloqueado"],
        "resposta": (
            "Abra “Acesso a um sistema”, escolha qual e diga para qual trabalho. "
            "Se for acesso remoto à rede, o item é “Acesso à VPN” — e lá você diz se "
            "é temporário ou definitivo, porque acesso temporário sai sozinho na data."
        ),
        "url_acao": "/workspace/servicos/acesso-sistema/", "rotulo_acao": "Pedir acesso",
    },
    {
        "area": "ti", "prioridade": 80,
        "pergunta": "Meu equipamento parou de funcionar. O que faço?",
        # "notebook" entra AQUI também, e não só na FAQ de compra: "meu notebook
        # quebrou" tem dois sinais desta pergunta (notebook + quebrou) e um só da
        # outra, e é o desempate que manda a pessoa para T.I. em vez de Compras.
        "palavras_chave": ["quebrou", "nao liga", "defeito", "parou", "travando",
                           "conserto", "notebook", "celular", "monitor", "teclado"],
        "resposta": (
            "Abra “Meu equipamento parou de funcionar” e descreva o que acontece. "
            "Vai direto para a fila de T.I., sem passar por aprovação — o prazo "
            "prometido é de 2 dias."
        ),
        "url_acao": "/workspace/servicos/equipamento-quebrado/",
        "rotulo_acao": "Abrir chamado",
    },
    # ── Universidade ────────────────────────────────────────────────
    {
        "area": "hab", "prioridade": 80,
        "pergunta": "Como pedir um curso ou treinamento?",
        "palavras_chave": ["curso", "treinamento", "certificacao", "congresso", "capacitacao"],
        "resposta": (
            "Abra “Treinamento ou curso”. Se for reciclagem de NR — NR-10, NR-35 e "
            "outras habilitações —, o item certo é “Reciclagem de NR”, que vai para "
            "o SESMT e tem prazo maior."
        ),
        "url_acao": "/workspace/servicos/treinamento/", "rotulo_acao": "Pedir curso",
    },
    {
        "area": "hab", "prioridade": 70,
        "pergunta": "Minha NR está vencendo. O que faço?",
        "palavras_chave": ["nr", "nr10", "nr35", "vencendo", "habilitacao", "reciclagem", "vencida"],
        "resposta": (
            "Abra “Reciclagem de NR” com antecedência: o prazo prometido é de 10 dias "
            "e habilitação vencida bloqueia despacho. O pedido vai para o SESMT."
        ),
        "url_acao": "/workspace/servicos/reciclagem-nr/", "rotulo_acao": "Pedir reciclagem",
    },
    # ── Jurídico ────────────────────────────────────────────────────
    {
        "area": "jur", "prioridade": 70,
        "pergunta": "Como mandar um contrato para análise?",
        "palavras_chave": ["contrato", "analise de contrato", "juridico", "minuta"],
        "resposta": (
            "Abra “Análise de contrato” e anexe a minuta. O Jurídico devolve com os "
            "pontos de atenção."
        ),
        "url_acao": "/workspace/servicos/analise-contrato/",
        "rotulo_acao": "Enviar contrato",
    },
    # ── Reservas ────────────────────────────────────────────────────
    {
        "area": "res", "prioridade": 85,
        "pergunta": "Como reservar uma sala?",
        "palavras_chave": ["sala", "reserva", "reuniao", "auditorio", "agendar sala"],
        "resposta": (
            "Em “Reservas” cada sala mostra a grade do dia: as horas verdes estão "
            "livres e levam direto ao formulário com o horário preenchido. No topo "
            "há um atalho de “Livres agora”, para quando você precisa de sala já."
        ),
        "url_acao": "/workspace/reservas/", "rotulo_acao": "Ver as salas",
    },
    {
        "area": "res", "prioridade": 70,
        "pergunta": "Como reservo um carro da empresa?",
        "palavras_chave": ["carro", "veiculo", "van", "utilitario", "frota"],
        "resposta": (
            "Veículos aparecem na mesma tela de Reservas, junto com as salas. "
            "Para locação de carro EM VIAGEM o caminho é outro: o item “Viagem”, "
            "de Suprimentos."
        ),
        "url_acao": "/workspace/reservas/", "rotulo_acao": "Ver veículos",
    },
    # ── Documentos ──────────────────────────────────────────────────
    {
        "area": "doc", "prioridade": 80,
        "pergunta": "Onde encontro as políticas e normas da empresa?",
        "palavras_chave": ["politica", "norma", "pop", "manual", "procedimento", "documentacao"],
        "resposta": (
            "Em “Documentação” estão POPs, políticas, normas e manuais. Documentos "
            "com leitura obrigatória aparecem também no seu “Meu dia” até você confirmar."
        ),
        "url_acao": "/workspace/documentacao/", "rotulo_acao": "Abrir documentação",
    },
    # ── Correspondência e processos internos ────────────────────────
    {
        "area": "proc", "prioridade": 80,
        "pergunta": "Chegou uma carta para mim. Como sei?",
        "palavras_chave": ["carta", "correspondencia", "encomenda", "intimacao", "recepcao"],
        "resposta": (
            "Você recebe aviso no sino assim que a recepção registra. Em "
            "“Correspondências” está o que espera retirada, e depois de retirar você "
            "confirma o recebimento — é essa confirmação que vale como prova, não o "
            "registro da recepção."
        ),
        "url_acao": "/workspace/correspondencias/", "rotulo_acao": "Ver correspondências",
    },
    {
        "area": "proc", "prioridade": 75,
        "pergunta": "Meu pedido foi devolvido. E agora?",
        "palavras_chave": ["devolvido", "devolucao", "voltou", "recusado", "corrigir"],
        "resposta": (
            "Devolvido quer dizer “corrija e reenvie” — o motivo aparece no pedido, "
            "escrito por quem devolveu. É diferente de reprovado, que encerra o pedido. "
            "Pedidos devolvidos aparecem em destaque no seu “Meu dia”."
        ),
        "url_acao": "/workspace/minhas-solicitacoes/?filtro=devolvida",
        "rotulo_acao": "Ver devolvidos",
    },
    {
        "area": "proc", "prioridade": 70,
        "pergunta": "Recebi o que pedi, mas não resolveu. O que faço?",
        "palavras_chave": ["nao resolveu", "reabrir", "voltou a acontecer", "de novo", "nao funcionou"],
        "resposta": (
            "Em “Minhas solicitações”, o pedido concluído tem a opção “não resolveu” "
            "por 7 dias. Ele volta para a MESMA fila, com o mesmo histórico — não abra "
            "um segundo pedido, senão a história do problema fica partida em duas."
        ),
        "url_acao": "/workspace/minhas-solicitacoes/?filtro=concluida",
        "rotulo_acao": "Ver concluídos",
    },
]
