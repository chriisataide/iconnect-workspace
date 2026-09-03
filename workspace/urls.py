"""URLs do Workspace, montadas sob `/workspace/`."""

from django.urls import path

from . import views

app_name = "workspace"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.buscar_view, name="buscar"),
    path("ajuda/", views.ajuda, name="ajuda"),
    # O código da tela vira endereço — ver `workspace/enderecamento.py`.
    # `str` e não `slug`: o código tem ponto, e `slug` não aceita ponto.
    path("ir/<str:codigo>/", views.ir_para, name="ir"),
    path("assistente/", views.perguntar, name="assistente"),
    path("faq/", views.faq, name="faq"),
    path("faq/nova/", views.faq_editar, name="faq_nova"),
    path("faq/<int:pk>/editar/", views.faq_editar, name="faq_editar"),
    path("faq/<int:pk>/excluir/", views.faq_excluir, name="faq_excluir"),
    path("publicacao/<int:pk>/", views.publicacao_detalhe, name="publicacao_detalhe"),
    path("publicacoes/", views.publicacoes, name="publicacoes"),
    path("publicacoes/nova/", views.publicacao_editar, name="publicacao_nova"),
    path("publicacoes/<int:pk>/editar/", views.publicacao_editar, name="publicacao_editar"),
    path("publicacoes/<int:pk>/acao/", views.publicacao_acao, name="publicacao_acao"),
    # Módulos — o destino dos tiles da home. Públicos como o hub.
    #
    # Prefixo `m/` e não `<slug:chave>/` na raiz: sem ele, um módulo chamado
    # "buscar" ou "servicos" sequestraria uma rota existente, e o erro só
    # apareceria no dia em que alguém acrescentasse a chave errada.
    path("m/<slug:chave>/", views.modulo, name="modulo"),
    # Documentação.
    path("documentacao/", views.documentacao, name="documentacao"),
    # A REDAÇÃO do acervo — §37. Antes dela, criar um POP exigia o `/admin/`,
    # que pede `is_staff`: publicar norma significava pedir para outra pessoa.
    #
    # Estas três rotas vêm ANTES de `documentacao/<slug:slug>/`: sem isso, um
    # documento com slug "novo" sequestraria a tela de criação, e o erro só
    # apareceria no dia em que alguém escolhesse esse título.
    path("documentacao/acervo/", views.documentos, name="documentos"),
    path("documentacao/novo/", views.documento_editar, name="documento_novo"),
    path("documentacao/<slug:slug>/editar/", views.documento_editar,
         name="documento_editar"),
    path("documentacao/<slug:slug>/revogar/", views.documento_revogar,
         name="documento_revogar"),
    path("documentacao/<slug:slug>/", views.documento, name="documento"),
    path("documentacao/<slug:slug>/baixar/", views.baixar_documento,
         name="baixar_documento"),
    path("documentacao/<slug:slug>/anexar/", views.anexar_documento,
         name="anexar_documento"),
    path("documentacao/<slug:slug>/confirmar/", views.confirmar_leitura,
         name="confirmar_leitura"),
    # Reservas.
    path("reservas/", views.reservas, name="reservas"),
    path("reservas/minhas/", views.minhas_reservas, name="minhas_reservas"),
    path("reservas/<slug:codigo>/", views.reservar, name="reservar"),
    path("reserva/<int:pk>/cancelar/", views.cancelar_reserva,
         name="cancelar_reserva"),
    # Correspondências.
    path("correspondencias/", views.correspondencias, name="correspondencias"),
    path("correspondencias/registrar/", views.registrar_correspondencia,
         name="registrar_correspondencia"),
    path("correspondencia/<int:pk>/entregar/", views.entregar_correspondencia,
         name="entregar_correspondencia"),
    path("correspondencia/<int:pk>/confirmar/", views.confirmar_correspondencia,
         name="confirmar_correspondencia"),
    path("correspondencia/<int:pk>/identificar/",
         views.identificar_correspondencia, name="identificar_correspondencia"),
    # Estoque e custódia — o que a empresa tem, e quem está com o quê.
    #
    # O modelo e o serviço de estoque existiam desde a onda de Suprimentos e não
    # havia tela: dava para GASTAR estoque pela conclusão de um pedido e não
    # dava para repor, contar nem registrar o que voltou de campo.
    path("estoque/", views.estoque, name="estoque"),
    path("estoque/movimentar/", views.registrar_movimento, name="registrar_movimento"),
    path("custodia/", views.custodia, name="custodia"),
    path("custodia/entregar/", views.entregar_custodia, name="entregar_custodia"),
    path("custodia/<int:pk>/aceitar/", views.aceitar_custodia, name="aceitar_custodia"),
    path("custodia/<int:pk>/devolver/", views.devolver_custodia,
         name="devolver_custodia"),
    # Frota — §18 e §19.
    #
    # NÃO há rota de reserva de veículo aqui, e é a decisão que mais importa
    # deste módulo: o carro de uso comum é o mesmo `Recurso` da grade de
    # Reservas. Duas portas para marcar o mesmo veículo foi como o produto
    # passou a permitir duas equipes na porta esperando a mesma van.
    path("frota/", views.frota, name="frota"),
    path("frota/novo/", views.cadastrar_veiculo, name="cadastrar_veiculo"),
    path("frota/<int:pk>/", views.atualizar_veiculo, name="atualizar_veiculo"),
    path("frota/<int:pk>/gasto/", views.lancar_despesa_veiculo,
         name="lancar_despesa_veiculo"),
    # §10 — as candidaturas a vaga interna, vistas de quem recruta.
    #
    # NÃO há model novo: a inscrição já é um pedido do catálogo (`rh.vaga`), com
    # currículo e cadeia de aprovação. O que faltava era a pergunta invertida —
    # quem se candidatou a esta vaga, e a que vagas esta pessoa já se candidatou.
    path("candidaturas/", views.candidaturas, name="candidaturas"),
    # Marketing — §23. O radar de oportunidades.
    #
    # NÃO há rota de aprovação aqui: decidir ir a uma feira é gastar dinheiro da
    # empresa, e esse caminho já existe — o item `evento` do catálogo, que passa
    # por gestor e diretoria conforme a faixa.
    path("marketing/", views.marketing, name="marketing"),
    path("marketing/nova/", views.oportunidade_registrar,
         name="oportunidade_nova"),
    path("marketing/<int:pk>/", views.oportunidade_registrar,
         name="oportunidade_editar"),
    path("marketing/<int:pk>/decidir/", views.oportunidade_decidir,
         name="oportunidade_decidir"),
    # O que o Workspace LÊ do iConnect — §20, §21, §38 e §18.
    #
    # Nenhuma das duas escreve. Abrir chamado é no iConnect, que é onde ele é
    # atendido; o Workspace direciona, exibe status e exibe histórico.
    path("chamados/", views.chamados, name="chamados"),
    path("campo/", views.campo, name="campo"),
    # Meu dia e notificações.
    path("meu-dia/", views.meu_dia, name="meu_dia"),
    path("indicadores/", views.indicadores, name="indicadores"),
    # A Apresentação de Resultados (10) e a tela irmã de fontes (99).
    #
    # `fontes/` ANTES de qualquer rota com parâmetro sob `resultados/`: sem
    # isso, o dia em que existir `resultados/<slug>/` a palavra "fontes"
    # sequestraria a tela — o mesmo cuidado de `documentacao/acervo/`.
    # O painel de exceções (11). Lista de REGRAS com contagem, e não um
    # dashboard — ver `workspace/excecoes/base.py`.
    # O ciclo de planejamento (12) — a pauta como objeto do produto.
    #
    # A competência entra na URL e não em query string: a reunião de 09/2026 é
    # um endereço que se manda por mensagem, e um link com `?ano=` é um link
    # que alguém trunca ao copiar.
    #
    # `?etapa=CP05` e `?apresentacao=1` seguem em query string, e isso é o
    # ADR-025: uma etapa por vez e o trilho fora do HTML são RECORTES da mesma
    # tela, não telas novas. Duas telas divergiriam na terceira semana — e a que
    # a diretoria vê na reunião é justamente a que não pode divergir.
    path("ciclos/", views.ciclos, name="ciclos"),
    path("ciclos/<slug:chave>/", views.ciclo, name="ciclo"),
    path("ciclos/<slug:chave>/<int:ano>/<int:mes>/", views.ciclo,
         name="ciclo_competencia"),
    path("ciclos/<slug:chave>/<int:ano>/<int:mes>/abrir/", views.abrir_ciclo,
         name="abrir_ciclo"),
    path("ciclos/<slug:chave>/<int:ano>/<int:mes>/anotar/", views.anotar_etapa,
         name="anotar_etapa"),
    path("ciclos/<slug:chave>/<int:ano>/<int:mes>/fechar/", views.fechar_ciclo,
         name="fechar_ciclo"),
    path("excecoes/", views.excecoes, name="excecoes"),
    # Planos de ação (13) — o limiar que gera obrigação.
    #
    # `novo/` ANTES de `<int:pk>/` por hábito, e não por necessidade: `int`
    # nunca casaria com "novo". O hábito é o que protege o dia em que alguém
    # trocar o conversor por `str`.
    # Metas, avaliação e PDI (14). O quadro é de UMA pessoa por vez — não
    # existe grade de pessoas com nota, e é a restrição 8 no lugar em que ela é
    # mais fácil de violar sem perceber.
    #
    # `desenvolvimento/` ANTES de `<int:pessoa_id>/`: `int` não casaria com a
    # palavra, mas a ordem é o hábito que protege o dia em que alguém trocar o
    # conversor.
    path("metas/", views.metas, name="metas"),
    path("metas/desenvolvimento/", views.desenvolvimento, name="desenvolvimento"),
    path("metas/desenvolvimento/acao/", views.acao_pdi, name="acao_pdi"),
    path("metas/desenvolvimento/<int:pessoa_id>/", views.desenvolvimento,
         name="desenvolvimento_de"),
    path("metas/desenvolvimento/<int:pessoa_id>/acao/", views.acao_pdi,
         name="acao_pdi_de"),
    path("metas/quadro/<int:quadro_id>/meta/", views.meta_editar,
         name="meta_editar"),
    path("metas/quadro/<int:quadro_id>/meta/remover/", views.meta_remover,
         name="meta_remover"),
    path("metas/quadro/<int:quadro_id>/acao/", views.quadro_acao,
         name="quadro_acao"),
    path("metas/<int:pessoa_id>/", views.metas, name="metas_de"),
    path("metas/<int:pessoa_id>/abrir/", views.abrir_quadro, name="abrir_quadro"),
    # Orçamento anual e revisão (15). O teto vigente muda por REVISÃO — não há
    # rota de edição, e é a decisão da onda, não uma folga do formulário.
    path("orcamento/", views.orcamento, name="orcamento"),
    path("orcamento/<str:codigo>/<int:ano>/", views.orcamento_centro,
         name="orcamento_centro"),
    path("orcamento/<str:codigo>/<int:ano>/revisar/", views.revisar_orcamento,
         name="revisar_orcamento"),
    path("orcamento/<str:codigo>/<int:ano>/vigorar/", views.vigorar_orcamento,
         name="vigorar_orcamento"),
    path("planos/", views.planos, name="planos"),
    path("planos/novo/", views.plano_novo, name="plano_novo"),
    path("planos/<int:pk>/", views.plano, name="plano"),
    path("planos/<int:pk>/fechar/", views.fechar_plano, name="fechar_plano"),
    path("excecoes/<slug:chave>/notificar/", views.notificar_excecao,
         name="notificar_excecao"),
    path("resultados/", views.resultados, name="resultados"),
    path("resultados/pdf/", views.resultados_pdf, name="resultados_pdf"),
    # O DETALHE — mecanismo 4. Tela própria e não gaveta: uma tela tem URL, e é
    # isso que permite mandar o detalhe numa mensagem como se manda o agregado.
    path("resultados/detalhe/", views.resultados_detalhe, name="resultados_detalhe"),
    # O contrato de dados. MESMO escopo da tela — o erro clássico é a API
    # devolver tudo enquanto a tela filtra.
    path("resultados/dados/", views.resultados_dados, name="resultados_dados"),
    path("resultados/fontes/", views.fontes, name="fontes"),
    path("resultados/fontes/<slug:chave>/recarregar/", views.recarregar_fonte,
         name="recarregar_fonte"),
    path("relatorios/", views.relatorios, name="relatorios"),
    path("relatorios/novo/", views.relatorio_editar, name="relatorio_novo"),
    path("relatorios/<int:pk>/editar/", views.relatorio_editar, name="relatorio_editar"),
    path("relatorios/<int:pk>/", views.relatorio_ver, name="relatorio_ver"),
    path("relatorios/<int:pk>/acao/", views.relatorio_acao, name="relatorio_acao"),
    path("relatorios/<int:pk>/pdf/", views.relatorio_pdf, name="relatorio_pdf"),
    path("universidade/", views.universidade, name="universidade"),
    path("universidade/painel/", views.universidade_painel, name="universidade_painel"),
    path("notificacoes/", views.notificacoes, name="notificacoes"),
    path("notificacoes/lidas/", views.marcar_lidas, name="marcar_lidas"),
    # Serviços.
    path("servicos/", views.catalogo, name="servicos"),
    path("servicos/<slug:chave>/", views.pedir, name="pedir"),
    path("minhas-solicitacoes/", views.minhas_solicitacoes, name="minhas_solicitacoes"),
    path("solicitacao/<int:pk>/cancelar/", views.cancelar_solicitacao, name="cancelar_solicitacao"),
    path("solicitacao/<int:pk>/reabrir/", views.reabrir_solicitacao, name="reabrir_solicitacao"),
    path("solicitacao/<int:pk>/comentar/", views.comentar_solicitacao,
         name="comentar_solicitacao"),
    # §43 — o rascunho. Descartar APAGA, e é a única exclusão do produto: ver
    # `catalogo.descartar_rascunho` para o motivo de a regra da casa não valer
    # para um formulário que nunca foi enviado.
    path("solicitacao/<int:pk>/descartar/", views.descartar_rascunho,
         name="descartar_rascunho"),
    # O segundo passo do reembolso que presta contas de um adiantamento: para
    # onde corre a diferença. Rota própria porque a pessoa volta a ela — a
    # conta fica aberta até ser confirmada.
    path("solicitacao/<int:pk>/acerto/", views.acerto, name="acerto"),
    # Anexos — o único caminho até o arquivo. Não há URL pública: eles moram
    # fora de MEDIA_ROOT, que o nginx serve sem autenticação.
    path("anexo/<int:pk>/", views.baixar_anexo, name="baixar_anexo"),
    # A fila de quem ATENDE — o passo que faltava depois da aprovação. Sem ela,
    # o pedido parava em "aprovado" para sempre e o prazo REAL nunca era medido.
    path("fila/", views.fila, name="fila"),
    path("fila/<int:pk>/", views.atender, name="atender"),
    # Pessoas e papéis — quem aprova o quê. Administração de produto, para o
    # R.H. não precisar do /admin/ do Django.
    path("pessoas/", views.pessoas, name="pessoas"),
    path("pessoas/conceder/", views.conceder_papel, name="conceder_papel"),
    path("papel/<int:pk>/encerrar/", views.revogar_papel, name="revogar_papel"),
    # CENTRO DE CUSTO — o campo que decide dinheiro e não tinha tela.
    #
    # Duas rotas porque são duas decisões diferentes: em que centro a PESSOA é
    # debitada (lotação, de identidade) e quais centros EXISTEM com que teto
    # (cadastro, do domínio financeiro, alcançado pelo contrato). Juntá-las num
    # formulário só faria corrigir o CC de alguém exigir redigitar o orçamento
    # do mês.
    path("pessoas/centro-custo/", views.definir_centro_custo,
         name="definir_centro_custo"),
    path("centros-custo/", views.salvar_centro_custo, name="salvar_centro_custo"),
    # Aprovações
    path("aprovacoes/", views.bandeja, name="aprovacoes"),
    path("aprovacoes/<int:pk>/decidir/", views.decidir_aprovacao, name="decidir_aprovacao"),
    path("aprovacoes/lote/", views.aprovar_em_lote, name="aprovar_em_lote"),
]
