"""PON — o lote de pendências de ponto, de quem importou até quem recebeu.

## Por que o estado mora aqui e não no n8n

A automação original guardava tudo dentro da execução do n8n: ela lia o Excel
de um arquivo montado, agrupava, enviava e o resultado existia apenas na aba
*Executions* — podada em 168 horas. Isso responde "deu certo agora?" e não
responde nenhuma das perguntas que o R.H. faz depois: quem importou, com qual
arquivo, quem foi avisado em setembro, por que o Fulano não recebeu.

Agora o Portal é o dono do estado. O n8n recebe dados já validados e o
identificador do lote, entrega ao WhatsApp e devolve o resultado. Ele deixa de
ser o sistema e passa a ser o transporte.

## Quatro tabelas

`LotePonto` é a importação. `ColaboradorPonto` é uma pessoa dentro dela — uma
linha por pessoa, nunca por linha do Excel, porque uma pessoa recebe uma
mensagem. `EnvioPonto` é cada TENTATIVA de entrega: o mesmo colaborador é
enviado em teste e depois em produção, e juntar os dois na linha da pessoa
apagaria o teste no momento em que a produção acontecesse. `EventoPonto` é a
auditoria — quem mexeu no telefone, quem confirmou o envio real.

Não são cinco: as pendências de uma pessoa moram num JSON dentro dela. Elas
são sempre lidas junto com o colaborador, nunca consultadas isoladamente, e uma
tabela para elas seria um `JOIN` em todo acesso para nunca responder pergunta
própria.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class ModoEnvio(models.TextChoices):
    """Teste manda tudo para um número só; produção manda para as pessoas."""

    TESTE = "teste", "Teste"
    PRODUCAO = "producao", "Produção"


class SituacaoLote(models.TextChoices):
    RASCUNHO = "rascunho", "Rascunho"
    VALIDANDO = "validando", "Validando"
    VALIDADO = "validado", "Validado"
    PROCESSANDO = "processando", "Processando"
    CONCLUIDO = "concluido", "Concluído"
    CONCLUIDO_COM_ERROS = "concluido_com_erros", "Concluído com erros"
    CANCELADO = "cancelado", "Cancelado"


class SituacaoEnvio(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    ENVIANDO = "enviando", "Enviando"
    ENVIADO = "enviado", "Enviado"
    ERRO = "erro", "Erro"
    IGNORADO = "ignorado", "Ignorado"


class AcaoPonto(models.TextChoices):
    """O vocabulário da auditoria — §33. Um verbo por linha, no passado."""

    UPLOAD = "upload", "Planilha enviada"
    VALIDACAO = "validacao", "Planilha validada"
    ALTERACAO_TELEFONE = "alteracao_telefone", "Telefone corrigido"
    TESTE_SOLICITADO = "teste_solicitado", "Teste solicitado"
    TESTE_EXECUTADO = "teste_executado", "Teste executado"
    PRODUCAO_CONFIRMADA = "producao_confirmada", "Envio real confirmado"
    ENVIO_REAL_INICIADO = "envio_real_iniciado", "Envio real iniciado"
    ENVIO_CONCLUIDO = "envio_concluido", "Envio concluído"
    ENVIO_FALHOU = "envio_falhou", "Envio falhou"
    CANCELAMENTO = "cancelamento", "Lote cancelado"


class LotePonto(models.Model):
    """Uma importação de planilha, do upload ao último envio."""

    arquivo_nome = models.CharField(max_length=255)
    arquivo_bytes = models.PositiveIntegerField(default=0)

    # O conteúdo da planilha NÃO é guardado. Ela traz CPF e a senha do totem de
    # todos os colaboradores, e nada depois do processamento precisa dela: as
    # pendências e o telefone já foram extraídos. Guardar o arquivo seria
    # manter uma cópia de dado sensível para responder a nenhuma pergunta.
    arquivo_digest = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 do arquivo — reconhece a mesma planilha importada duas vezes.",
    )

    quem_importou = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="lotes_de_ponto",
    )

    situacao = models.CharField(
        max_length=20, choices=SituacaoLote.choices, default=SituacaoLote.RASCUNHO, db_index=True
    )

    # §18: o lote NASCE em teste. O padrão do campo é parte da barreira — um
    # lote criado por um caminho que esqueça de definir o modo continua sendo
    # um lote de teste, e não um disparo real por omissão.
    modo = models.CharField(max_length=10, choices=ModoEnvio.choices, default=ModoEnvio.TESTE)
    telefone_teste = models.CharField(max_length=20, blank=True)

    erro_validacao = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "lote de pendências de ponto"
        verbose_name_plural = "lotes de pendências de ponto"
        indexes = [models.Index(fields=["situacao", "-criado_em"], name="wks_ponto_lote_idx")]

    def __str__(self) -> str:
        return f"{self.arquivo_nome} · {self.criado_em:%d/%m/%Y %H:%M}"

    @property
    def em_teste(self) -> bool:
        return self.modo == ModoEnvio.TESTE

    @property
    def total_pendencias(self) -> int:
        return sum(c.quantidade_pendencias for c in self.colaboradores.all())


class ColaboradorPonto(models.Model):
    """Uma pessoa dentro de um lote — uma pessoa, uma mensagem."""

    lote = models.ForeignKey(LotePonto, on_delete=models.CASCADE, related_name="colaboradores")

    nome = models.CharField(max_length=160)
    codigo = models.CharField(max_length=40, blank=True)
    local = models.CharField(max_length=200, blank=True)

    telefone_planilha = models.CharField(
        max_length=60, blank=True, help_text="Como veio no arquivo, para o R.H. reconhecer."
    )
    telefone_normalizado = models.CharField(max_length=20, blank=True)

    # §14: a correção vale para ESTE lote. O cadastro mestre da pessoa não é
    # tocado — o Portal não é dono do cadastro de RH, e escrever nele a partir
    # de uma planilha avulsa faria uma digitação errada virar verdade oficial.
    telefone_corrigido = models.CharField(max_length=20, blank=True)

    pendencias = models.JSONField(default=list, blank=True)
    quantidade_pendencias = models.PositiveSmallIntegerField(default=0)

    selecionado = models.BooleanField(default=False)

    class Meta:
        ordering = ["nome"]
        verbose_name = "colaborador do lote"
        verbose_name_plural = "colaboradores do lote"
        indexes = [models.Index(fields=["lote", "nome"], name="wks_ponto_colab_idx")]

    def __str__(self) -> str:
        return self.nome

    @property
    def telefone_efetivo(self) -> str:
        """O corrigido manda; sem ele, o da planilha."""
        return self.telefone_corrigido or self.telefone_normalizado

    @property
    def pode_produzir(self) -> bool:
        """§35: sem telefone bom, não vai para produção. Teste continua livre."""
        return bool(self.telefone_efetivo)

    @property
    def telefone_mascarado(self) -> str:
        """O que a TELA mostra. O número inteiro só existe no envio — §34."""
        from workspace.services.ponto import mascarar_telefone

        return mascarar_telefone(self.telefone_efetivo)

    @property
    def motivo_sem_telefone(self) -> str:
        """A mesma frase do motor — §35. A regra mora num lugar só."""
        from workspace.services.ponto import motivo_sem_telefone

        return motivo_sem_telefone(self.telefone_planilha, self.telefone_efetivo)


class EnvioPonto(models.Model):
    """Uma tentativa de entrega. Teste e produção deixam linhas separadas."""

    lote = models.ForeignKey(LotePonto, on_delete=models.CASCADE, related_name="envios")
    colaborador = models.ForeignKey(
        ColaboradorPonto, on_delete=models.CASCADE, related_name="envios"
    )

    modo = models.CharField(max_length=10, choices=ModoEnvio.choices)

    # Para onde FOI, não para onde deveria ir. Em teste é o telefone de teste,
    # e é isso que precisa ficar registrado: a pergunta da auditoria é "essa
    # mensagem chegou em quem?", não "de quem era o número na planilha".
    destino = models.CharField(max_length=20, blank=True)
    mensagem = models.TextField(blank=True)

    situacao = models.CharField(
        max_length=12, choices=SituacaoEnvio.choices, default=SituacaoEnvio.PENDENTE, db_index=True
    )
    erro = models.TextField(blank=True)
    resposta = models.JSONField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["colaborador__nome", "pk"]
        verbose_name = "envio de pendência de ponto"
        verbose_name_plural = "envios de pendência de ponto"
        indexes = [models.Index(fields=["lote", "situacao"], name="wks_ponto_envio_idx")]

    def __str__(self) -> str:
        return f"{self.colaborador.nome} · {self.get_situacao_display()}"

    @property
    def destino_mascarado(self) -> str:
        """Para a tela de detalhe. O número inteiro fica no campo, não na página."""
        from workspace.services.ponto import mascarar_telefone

        return mascarar_telefone(self.destino)


class EventoPonto(models.Model):
    """A auditoria — §33. Nunca guarda token, chave ou o telefone inteiro."""

    lote = models.ForeignKey(LotePonto, on_delete=models.CASCADE, related_name="eventos")
    acao = models.CharField(max_length=24, choices=AcaoPonto.choices)

    quem = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_de_ponto",
    )
    ip = models.GenericIPAddressField(null=True, blank=True)

    detalhe = models.CharField(max_length=400, blank=True)
    quando = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["quando", "pk"]
        verbose_name = "evento do lote de ponto"
        verbose_name_plural = "eventos do lote de ponto"
        indexes = [models.Index(fields=["lote", "quando"], name="wks_ponto_evento_idx")]

    def __str__(self) -> str:
        return f"{self.get_acao_display()} · {self.quando:%d/%m/%Y %H:%M}"
