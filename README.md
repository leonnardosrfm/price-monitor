# Price Monitor

Price Monitor é um monitor de preços em Python que acompanha produtos em e-commerces e envia alertas no Discord quando ocorre queda de valor.  
O projeto utiliza seletores CSS configuráveis, permitindo adaptação fácil a diferentes sites.

## Funcionalidades

- Monitoramento periódico de preços por URL
- Extração de valores via CSS selector
- Armazenamento de histórico em SQLite
- Alertas automáticos no Discord via webhook
- Controle de frequência para evitar notificações repetidas
- Configuração simples via arquivo YAML

## Tecnologias

- Python
- Requests
- BeautifulSoup
- SQLite
- PyYAML
- Discord Webhooks

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Configuração

### Variáveis de Ambiente

Crie o arquivo `.env` na raiz do projeto:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/SEU_ID/SEU_TOKEN
```

### Produtos Monitorados

Edite o arquivo `config.yaml`:

```yaml
check_interval_seconds: 300

items:
  - name: "Produto X"
    url: "https://site.com/produto"
    price_selector: "div.border-black-400 > h4"
    currency: "BRL"
    notify_on_drop: true
    drop_threshold_percent: 3
```

O `price_selector` deve apontar diretamente para o elemento HTML que contém o preço.

## Execução

Execute o monitor com:

```bash
python monitor.py
```

O script coleta o preço do produto, registra o histórico localmente e envia alertas no Discord quando a condição definida é atendida.

