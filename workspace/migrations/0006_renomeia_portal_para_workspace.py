"""Só o `help_text` do resumo da publicação, que dizia "card do Portal".

SQL nenhum — `sqlmigrate` responde `(no-op)`. Existe para o estado das migrações
não divergir dos models, senão `makemigrations --check` reprova o CI a cada
execução por uma frase de ajuda.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0005_anexo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='publicacao',
            name='resumo',
            field=models.CharField(blank=True, help_text='Uma linha, exibida no card do Workspace.', max_length=300),
        ),
    ]
