# IRPF - Controle de Declarações

Aplicativo interno em Streamlit para controlar o fluxo de declarações de IRPF por setor, usando Supabase como banco principal.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

O app lê as credenciais nesta ordem:

- variáveis de ambiente `SUPABASE_URL` e `SUPABASE_ANON_KEY`;
- secrets do Streamlit;
- arquivo local `data/supabase-credentials.txt`.

Para deploy no Streamlit, cadastre os secrets com base em `.streamlit/secrets.example.toml`.
No Streamlit Community Cloud, escolha Python `3.12` em `Advanced settings` antes de publicar.

## Estrutura do projeto

- `app.py`: orquestra login, carga do banco, permissões e roteamento das telas.
- `comercial.py`: fluxo de documentação, atendimento e cobrança.
- `preenchimento.py`: fila disponível, minhas declarações e atualização do preenchimento.
- `revisao.py`: análise geral, revisão do Renato e ajustes do Heverton.
- `database.py`: acesso ao Supabase e operações centrais de persistência.
- `setup_supabase.py` e `bootstrap_database.py`: apoio para estruturar e popular a base.

## Fluxo do sistema

- `Comercial`: atendimento do cliente, checklist de documentos recebidos, relatório de cobrança e mensagem curta para WhatsApp.
- `Preenchimento`: fila disponível, minhas declarações e consulta geral para transferência de responsável, status, observações e documentos solicitados.
- `Revisão`: análise geral, fila `PRONTO PARA REVISÃO`, ajustes do Heverton e histórico diário.
- `Cadastros`: importação parcial por campos selecionados, comparação de planilhas com o banco e exportação completa em XLSX.

## Segurança operacional

- As planilhas, PDFs, exports e credenciais locais estão no `.gitignore`.
- O app usa login do Supabase Auth e libera telas conforme `team_members`.
- Dados sensíveis ficam na tabela `client_private` e só aparecem dentro do app autenticado.
- Para produção mais rígida, revise o RLS para aplicar permissões também no banco, além das travas da interface.

## Deploy MVP

Antes de publicar, conferir:

- `requirements.txt` presente no repositório.
- `logogestao.png` presente no repositório.
- `.streamlit/config.toml` presente no repositório.
- `.streamlit/secrets.example.toml` presente no repositório.
- Secrets configurados no ambiente do deploy.
- Usuários criados no Supabase Auth.
- Tabela `team_members` preenchida com emails e setores corretos.
- RLS ativo no Supabase.
- Planilhas reais fora do git.

## Validação rápida

```bash
python -m py_compile app.py comercial.py preenchimento.py revisao.py setup_supabase.py bootstrap_database.py database.py manage_clients.py
python -m pip check
```
